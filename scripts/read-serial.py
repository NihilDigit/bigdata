#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time

import serial


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("port")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    with serial.Serial(args.port, args.baud, timeout=0.2) as ser:
        if args.reset:
            ser.dtr = False
            ser.rts = True
            time.sleep(0.1)
            ser.rts = False
            time.sleep(0.4)
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            data = ser.readline()
            if data:
                print(data.decode("utf-8", errors="replace").rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
