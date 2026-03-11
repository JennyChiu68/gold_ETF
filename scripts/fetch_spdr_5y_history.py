#!/usr/bin/env python3
"""Fetch SPDR GLD archive CSV and build 5-year history JSON for the demo page."""

from __future__ import annotations

import csv
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from statistics import pstdev

SOURCE_URL = "https://www.spdrgoldshares.com/assets/dynamic/GLD/GLD_US_archive_EN.csv"
OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "spdr_gld_5y_history.json"


def quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    pos = (len(sorted_values) - 1) * q
    base = int(math.floor(pos))
    rest = pos - base
    nxt = sorted_values[base + 1] if base + 1 < len(sorted_values) else sorted_values[base]
    return sorted_values[base] + (nxt - sorted_values[base]) * rest


def fetch_csv() -> str:
    result = subprocess.run(
        ["curl", "-L", "--max-time", "30", "-A", "Mozilla/5.0", SOURCE_URL],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def parse_rows(raw_csv: str) -> list[dict]:
    rows: list[dict] = []
    reader = csv.DictReader(raw_csv.splitlines())
    ton_key = " Total Net Asset Value Tonnes in the Trust as at 4.15 p.m. NYT"
    close_key = " GLD Close"
    for row in reader:
        try:
            dt = datetime.strptime(row["Date"].strip(), "%d-%b-%Y").date()
            holding_ton = float(row[ton_key].replace(",", "").strip())
            gld_close = float(row[close_key].replace(",", "").replace("$", "").strip())
        except Exception:
            continue
        rows.append({"date": dt, "holdingTon": holding_ton, "gldClose": gld_close})

    rows.sort(key=lambda x: x["date"])
    for idx, item in enumerate(rows):
        item["changeTon"] = 0.0 if idx == 0 else item["holdingTon"] - rows[idx - 1]["holdingTon"]
    return rows


def pick_last_5y(rows: list[dict]) -> list[dict]:
    latest = rows[-1]["date"]
    try:
        start = latest.replace(year=latest.year - 5)
    except ValueError:
        start = latest.replace(year=latest.year - 5, day=28)
    return [r for r in rows if r["date"] >= start]


def main() -> None:
    raw_csv = fetch_csv()
    rows = parse_rows(raw_csv)
    if len(rows) < 2:
        raise RuntimeError("not enough parsed rows")

    rows_5y = pick_last_5y(rows)
    changes = [r["changeTon"] for r in rows_5y[1:]]
    abs_changes = [abs(v) for v in changes]

    baseline = {
        "dateFrom": rows_5y[0]["date"].isoformat(),
        "dateTo": rows_5y[-1]["date"].isoformat(),
        "records": len(rows_5y),
        "changes": len(changes),
        "meanChangeTon": sum(changes) / len(changes),
        "stdChangeTon": pstdev(changes),
        "absQ25Ton": quantile(abs_changes, 0.25),
        "absQ90Ton": quantile(abs_changes, 0.90),
        "absQ95Ton": quantile(abs_changes, 0.95),
        "absQ99Ton": quantile(abs_changes, 0.99),
    }

    payload = {
        "sourceUrl": SOURCE_URL,
        "generatedAtUtc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "baseline": baseline,
        "rows": [
            {
                "date": r["date"].isoformat(),
                "holdingTon": round(r["holdingTon"], 2),
                "changeTon": round(r["changeTon"], 2),
                "gldClose": round(r["gldClose"], 2),
            }
            for r in rows_5y
        ],
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT_PATH}")
    print(f"range={baseline['dateFrom']}~{baseline['dateTo']} records={baseline['records']} q95={baseline['absQ95Ton']:.2f}")


if __name__ == "__main__":
    main()
