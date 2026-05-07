#!/usr/bin/env python3
"""
TLC59108 example: hardware group-blink — outputs blink autonomously, no CPU required.

Unlike the software blink example (tlc59108_blink.py), the chip's internal oscillator
drives the blink cycle.  After ``set_group_blink()`` returns the CPU is free to sleep
or do other work — no periodic I²C writes are needed to sustain the blink.

Per-channel PWM values (set via ``set_brightness``) determine the on-phase brightness.
Channels not in the blink set remain at their individual LEDOUT state (off here).

Run::

    PYTHONPATH=src python3 examples/tlc59108_hw_blink.py
    PYTHONPATH=src python3 examples/tlc59108_hw_blink.py --period 0.5 --duty 0.25
    PYTHONPATH=src python3 examples/tlc59108_hw_blink.py --channels 0,2,4 --period 2.0
"""

from __future__ import annotations

import argparse
import time

from tlc591xx import TLC59108


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Blink TLC59108 outputs using the chip's hardware group-blink oscillator.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--bus",
        type=int,
        default=1,
        help="I²C bus number (/dev/i2c-<bus>)",
    )
    parser.add_argument(
        "--address",
        type=lambda s: int(s, 0),
        default=0x40,
        help="7-bit I²C address (match A0–A3 strapping)",
    )
    parser.add_argument(
        "--period",
        type=float,
        default=1.0,
        metavar="SEC",
        help="Blink period in seconds (hardware range: 0.042–10.67 s)",
    )
    parser.add_argument(
        "--duty",
        type=float,
        default=0.5,
        metavar="FRAC",
        help="On-time fraction 0.0–1.0 (0.5 = 50%%)",
    )
    parser.add_argument(
        "--channels",
        default=None,
        metavar="N[,N,...]",
        help="Comma-separated channel indices to blink (default: all 8)",
    )
    args = parser.parse_args()

    channels: list[int] | None = None
    if args.channels:
        channels = [int(c.strip(), 0) for c in args.channels.split(",")]

    print(
        f"[hw-blink] bus={args.bus} addr=0x{args.address:02x}"
        f"  period={args.period}s  duty={args.duty:.0%}"
        f"  channels={'all' if channels is None else channels}"
        f"  (Ctrl+C to stop)",
        flush=True,
    )

    with TLC59108(args.bus, address=args.address) as drv:
        drv.set_all_off()

        # Write individual PWM values (1–254) so that the on-phase shows the
        # desired brightness.  set_brightness(ch, 255) sets LEDOUT_ON and does
        # not write the PWM register, so use 254 as a "full" PWM value here.
        chs = channels if channels is not None else list(range(drv.num_leds))
        for ch in chs:
            drv.set_brightness(ch, 254)

        drv.set_group_blink(args.period, duty=args.duty, channels=channels)

        print(
            f"[hw-blink] hardware blink active — CPU idle"
            f"  (actual period ≈ {(round(args.period * 24 - 1) + 1) / 24:.3f} s)",
            flush=True,
        )
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            print("\n[hw-blink] interrupted", flush=True)
        finally:
            drv.set_all_off()
            print("[hw-blink] all outputs off, exit.", flush=True)


if __name__ == "__main__":
    main()
