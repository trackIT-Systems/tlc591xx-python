#!/usr/bin/env python3
"""
TLC59108 — multi-channel fade / wave demo.

Wiring: connect SDA/SCL to your I²C bus, set A0–A3 to match ``--address`` (default 0x40).

Defaults match a typical Raspberry Pi setup: **I²C bus 1** (``/dev/i2c-1``) and **address 0x40**
(A0–A3 strapping per datasheet). Override with ``--bus`` / ``--address`` if needed.

Logging defaults to **WARNING**. Use **-v** for INFO (progress) or **-d** for DEBUG (per-frame values).

Run from an environment where ``tlc591xx`` is installed, or from the repo root::

    PYTHONPATH=src python3 examples/tlc59108_fade.py
    PYTHONPATH=src python3 examples/tlc59108_fade.py -v
    PYTHONPATH=src python3 examples/tlc59108_fade.py -c 0,1,5,6
"""

from __future__ import annotations

import argparse
import logging
import time

from tlc591xx import TLC59108

_NUM_CHANNELS = 8
# Adjacent channels always differ by this many brightness steps (mod 256).
_LEVEL_STEP = 16
# Phase advances by this much each frame. Must be 1 (or small) for a visible “traveling”
# pattern: stepping phase by _LEVEL_STEP each frame only scales all channels together, so the
# gradient looks frozen until wrap.
_PHASE_STEP = 1


def _configure_logging(*, verbose: bool, debug: bool) -> None:
    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
    )


def _parse_channels(spec: str | None) -> list[int]:
    """
    Ordered unique indices in ``0 .. _NUM_CHANNELS-1``.

    ``None`` or blank means all channels. Order defines wave assignment: the first
    channel gets ``phase``, the next ``phase + _LEVEL_STEP``, and so on.
    """
    if spec is None or not str(spec).strip():
        return list(range(_NUM_CHANNELS))
    out: list[int] = []
    seen: set[int] = set()
    for raw in str(spec).split(","):
        part = raw.strip()
        if not part:
            continue
        ch = int(part, 0)
        if ch < 0 or ch >= _NUM_CHANNELS:
            raise ValueError(
                f"channel {ch} out of range; use 0..{_NUM_CHANNELS - 1} inclusive",
            )
        if ch in seen:
            continue
        seen.add(ch)
        out.append(ch)
    if not out:
        raise ValueError("channel list is empty after parsing; pass at least one channel")
    return out


def _brightness_row(phase: int, active: list[int]) -> list[int]:
    """Eight brightness values; inactive channels stay ``0``."""
    row = [0] * _NUM_CHANNELS
    for i, ch in enumerate(active):
        row[ch] = (phase + i * _LEVEL_STEP) % 256
    return row


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "TLC59108 I²C fade: selected outputs get a wave with "
            f"{_LEVEL_STEP}-step spacing between neighbours (in channel order); phase sweeps each frame."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-c",
        "--channels",
        default=None,
        metavar="N[,N,...]",
        help=(
            f"Comma-separated channel indices 0-{_NUM_CHANNELS - 1} to animate (default: all). "
            "Example: -c 0 or -c 0,1,5,6"
        ),
    )
    parser.add_argument(
        "--bus",
        type=int,
        default=1,
        help="I²C bus number (/dev/i2c-<bus> on Linux)",
    )
    parser.add_argument(
        "--address",
        type=lambda s: int(s, 0),
        default=0x40,
        help="7-bit I²C address (must match A0–A3)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.08,
        help="Delay between animation steps (seconds)",
    )
    log_group = parser.add_mutually_exclusive_group()
    log_group.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="INFO logging (startup and periodic progress)",
    )
    log_group.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="DEBUG logging (every frame; includes all channel values)",
    )
    args = parser.parse_args()

    try:
        active_channels = _parse_channels(args.channels)
    except ValueError as exc:
        parser.error(str(exc))

    _configure_logging(verbose=args.verbose, debug=args.debug)
    log = logging.getLogger(__name__)

    log.debug(
        "Parsed args: bus=%s address=0x%02x delay=%s channels=%s",
        args.bus,
        args.address,
        args.delay,
        active_channels,
    )

    with TLC59108(args.bus, address=args.address) as drv:
        e1, e2 = drv.read_errors()
        log.info(
            "TLC59108 ready on bus %d, address 0x%02x (read_errors: EFLAG=0x%02x, second=0x%02x)",
            args.bus,
            args.address,
            e1,
            e2,
        )
        if e1 != 0:
            log.warning(
                "Non-zero EFLAG (0x%02x) after init — check open-load/overtemperature (datasheet).",
                e1,
            )

        phase = 0
        frame = 0
        log.info(
            "Animating channels %s (%d outputs): neighbour spacing=%d (in listed order), phase step=%d/frame. Ctrl+C to stop.",
            active_channels,
            len(active_channels),
            _LEVEL_STEP,
            _PHASE_STEP,
        )

        try:
            while True:
                values = _brightness_row(phase, active_channels)
                drv.set_all_brightness(values)
                log.debug("frame=%d phase=%s values=%s", frame, phase, values)
                # Avoid a logging interval that shares a factor with 256/_PHASE_STEP or the
                # pattern repeats on stale-looking samples (e.g. frame%%16 with phase+=16).
                if log.isEnabledFor(logging.INFO) and frame % 23 == 0:
                    log.info(
                        "frame=%d phase=%d active=%s levels=%s",
                        frame,
                        phase,
                        active_channels,
                        [values[ch] for ch in active_channels],
                    )

                phase = (phase + _PHASE_STEP) % 256
                frame += 1
                time.sleep(args.delay)
        except KeyboardInterrupt:
            log.warning("Interrupted by user; clearing all outputs.")
        finally:
            drv.set_all_off()
            log.info("All outputs off.")


if __name__ == "__main__":
    main()
