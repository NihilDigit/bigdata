#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path

import serial


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("port")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--out", default="data/raw/esp32_usb_samples.csv")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    with serial.Serial(args.port, args.baud, timeout=2) as ser:
        while len(rows) < args.count:
            raw = ser.readline().decode("utf-8", errors="replace").strip()
            if not raw:
                continue
            print(raw)
            parts = raw.split(",")
            if len(parts) != 4 or parts[0] != "tangshan":
                continue
            rows.append(
                {
                    "collect_time": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "station_id": parts[0],
                    "station_name": parts[1],
                    "temperature": parts[2],
                    "humidity": parts[3],
                }
            )

    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["collect_time", "station_id", "station_name", "temperature", "humidity"],
        )
        writer.writeheader()
        writer.writerows(rows)

    print("wrote {}".format(out_path))
    print("samples={}".format(len(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
