#!/usr/bin/env python3
"""Fetch SPDR GLD historical archive and build anomaly baseline metrics."""

from __future__ import annotations

import csv
import json
import math
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import pstdev

SOURCE_URL = "https://www.spdrgoldshares.com/assets/dynamic/GLD/GLD_US_archive_EN.csv"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "spdr_baseline.json"


@dataclass
class Baseline:
    source_url: str
    fetched_at_utc: str
    date_from: str
    date_to: str
    records: int
    changes: int
    mean_change_ton: float
    std_change_ton: float
    abs_q25_ton: float
    abs_q90_ton: float
    abs_q95_ton: float
    abs_q99_ton: float
    holiday_gap_count: int


def quantile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    pos = (len(sorted_values) - 1) * q
    base = int(math.floor(pos))
    rest = pos - base
    nxt = sorted_values[base + 1] if base + 1 < len(sorted_values) else sorted_values[base]
    return sorted_values[base] + (nxt - sorted_values[base]) * rest


def parse_rows(csv_text: str) -> list[tuple[datetime.date, float]]:
    rows: list[tuple[datetime.date, float]] = []
    reader = csv.DictReader(csv_text.splitlines())
    ton_key = " Total Net Asset Value Tonnes in the Trust as at 4.15 p.m. NYT"
    for row in reader:
        try:
            dt = datetime.strptime(row["Date"].strip(), "%d-%b-%Y").date()
            ton = float(row[ton_key].replace(",", "").strip())
        except Exception:
            continue
        rows.append((dt, ton))
    rows.sort(key=lambda x: x[0])
    return rows


def build_baseline(rows: list[tuple[datetime.date, float]]) -> Baseline:
    changes: list[float] = []
    holiday_gap_count = 0
    for i in range(1, len(rows)):
        prev_date, prev_ton = rows[i - 1]
        date, ton = rows[i]
        changes.append(ton - prev_ton)
        if (date - prev_date).days > 3:
            holiday_gap_count += 1

    abs_changes = sorted(abs(v) for v in changes)

    return Baseline(
        source_url=SOURCE_URL,
        fetched_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        date_from=rows[0][0].isoformat(),
        date_to=rows[-1][0].isoformat(),
        records=len(rows),
        changes=len(changes),
        mean_change_ton=sum(changes) / len(changes),
        std_change_ton=pstdev(changes),
        abs_q25_ton=quantile(abs_changes, 0.25),
        abs_q90_ton=quantile(abs_changes, 0.90),
        abs_q95_ton=quantile(abs_changes, 0.95),
        abs_q99_ton=quantile(abs_changes, 0.99),
        holiday_gap_count=holiday_gap_count,
    )


def main() -> None:
    result = subprocess.run(
        [
            "curl",
            "-L",
            "--max-time",
            "30",
            "-A",
            "Mozilla/5.0",
            SOURCE_URL,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    body = result.stdout

    rows = parse_rows(body)
    if len(rows) < 2:
        raise RuntimeError("not enough parsed rows from SPDR CSV")

    baseline = build_baseline(rows)
    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT.write_text(json.dumps(asdict(baseline), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {DEFAULT_OUTPUT}")
    print(json.dumps(asdict(baseline), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
