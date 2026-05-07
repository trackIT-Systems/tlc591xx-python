#!/usr/bin/env python3
"""
TLC59108 example: hardware group-dim — master brightness knob with a single I²C write.

``set_group_dim(level)`` sets all opted-in channels to LEDOUT_BLINK state.
In group-dim mode (the default MODE2 setting) this scales each channel's
individual PWM output by ``level``, acting as a hardware master-brightness
multiplier.  One GRPPWM register write dims all participating channels
simultaneously without touching per-channel PWM registers.

This demo sets a sawtooth brightness pattern across all channels, then slowly
ramps the group-dim level up and down so you can see the whole group dim
together while the relative pattern between channels stays fixed.

Run::

    PYTHONPATH=src python3 examples/tlc59108_hw_dim.py
    PYTHONPATH=src python3 examples/tlc59108_hw_dim.py --delay 0.02
    PYTHONPATH=src python3 examples/tlc59108_hw_dim.py --channels 0,1,2,3
"""

from __future__ import annotations

import argparse
import math
import time

from tlc591xx import TLC59108


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Demonstrate TLC59108 hardware group-dim (master brightness) via set_group_dim().",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--bus", type=int, default=1, help="I²C bus number (/dev/i2c-<bus>)")
    parser.add_argument(
        "--address",
        type=lambda s: int(s, 0),
        default=0x40,
        help="7-bit I²C address (match A0–A3 strapping)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.05,
        metavar="SEC",
        help="Delay between group-dim steps (seconds)",
    )
    parser.add_argument(
        "--channels",
        default=None,
        metavar="N[,N,...]",
        help="Comma-separated channel indices to include in group dim (default: all 8)",
    )
    args = parser.parse_args()

    channels: list[int] | None = None
    if args.channels:
        channels = [int(c.strip(), 0) for c in args.channels.split(",")]

    print(
        f"[hw-dim] bus={args.bus} addr=0x{args.address:02x}"
        f"  delay={args.delay}s"
        f"  channels={'all' if channels is None else channels}"
        f"  (Ctrl+C to stop)",
        flush=True,
    )

    with TLC59108(args.bus, address=args.address) as drv:
        drv.set_all_off()

        # Set a fixed sawtooth brightness pattern across all channels.
        # These PWM values stay constant throughout the demo; only GRPPWM changes.
        chs = channels if channels is not None else list(range(drv.num_leds))
        step = 200 // max(len(chs), 1)
        for i, ch in enumerate(chs):
            drv.set_brightness(ch, max(1, min(254, 30 + i * step)))

        # Opt channels into the group generator in dim mode.
        drv.set_group_dim(1.0, channels=channels)

        print("[hw-dim] sweeping group-dim level 0 → 1 → 0  (single GRPPWM write per step)", flush=True)
        try:
            t = 0.0
            while True:
                # Sine-wave sweep: 0.0 → 1.0 → 0.0
                level = (1.0 - math.cos(t * math.pi * 2)) / 2.0
                drv.set_group_dim(level, channels=channels)
                t = (t + 0.01) % 1.0
                time.sleep(args.delay)
        except KeyboardInterrupt:
            print("\n[hw-dim] interrupted", flush=True)
        finally:
            drv.set_all_off()
            print("[hw-dim] all outputs off, exit.", flush=True)


if __name__ == "__main__":
    main()
