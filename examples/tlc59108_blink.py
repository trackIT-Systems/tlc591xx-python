#!/usr/bin/env python3
"""
TLC59108 example: all channels on/off together (blink), until Ctrl+C.

Run::

    PYTHONPATH=src python3 examples/tlc59108_blink.py
    PYTHONPATH=src python3 examples/tlc59108_blink.py --bus 1 --delay 0.2
"""

from __future__ import annotations

import argparse
import time

from tlc591xx import TLC59108


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Blink all TLC59108 outputs together until Ctrl+C.",
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
        help="7-bit I²C address (match A0–A3)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.35,
        metavar="SEC",
        help="Time for each on phase and each off phase (seconds)",
    )
    args = parser.parse_args()

    if args.delay < 0:
        parser.error("--delay must be >= 0")

    print(
        f"[blink] start bus={args.bus} addr=0x{args.address:02x} "
        f"delay={args.delay}s (Ctrl+C to stop)",
        flush=True,
    )

    with TLC59108(args.bus, address=args.address) as drv:
        drv.set_all_off()
        cycle = 0
        try:
            while True:
                cycle += 1
                print(f"[blink] cycle {cycle} → ON  (all {drv.num_leds} ch @ 255)", flush=True)
                drv.set_all_brightness([255] * drv.num_leds)
                time.sleep(args.delay)
                print(f"[blink] cycle {cycle} → OFF", flush=True)
                drv.set_all_off()
                time.sleep(args.delay)
        except KeyboardInterrupt:
            print("\n[blink] interrupted", flush=True)
        finally:
            drv.set_all_off()
            print("[blink] all outputs off, exit.", flush=True)


if __name__ == "__main__":
    main()
