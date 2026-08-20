#!/usr/bin/env python3
"""Build a compact decision-metric view from canonical EIA electricity outputs."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "api" / "v1" / "electricity"
DEFAULT_OUTPUT = DEFAULT_INPUT / "metrics.json"
MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def capacity_period(source_url: str) -> str:
    name = Path(urlparse(source_url).path).name
    match = re.fullmatch(r"([a-z]+)_generator(20\d{2})\.xlsx", name, re.I)
    if not match:
        raise ValueError(f"cannot derive EIA-860M reporting month from {name}")
    month = MONTHS.get(match.group(1).lower())
    if month is None:
        raise ValueError(f"unknown month in EIA-860M filename: {name}")
    return f"{match.group(2)}-{month}"


def latest(series: dict) -> dict:
    rows = series.get("daily")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{series.get('dataset')}: missing daily observations")
    row = rows[-1]
    if row.get("period") != series.get("last_period"):
        raise ValueError(f"{series.get('dataset')}: last_period does not match final observation")
    return row


def build(input_dir: Path) -> dict:
    capacity = load(input_dir / "capacity.json")
    demand = load(input_dir / "demand.json")
    generation = load(input_dir / "generation.json")
    demand_latest = latest(demand)
    generation_latest = latest(generation)
    cap_period = capacity_period(str(capacity["source_url"]))
    provider = "U.S. Energy Information Administration"

    observations = [
        {
            "metric": "electricity_demand",
            "as_of": demand_latest["period"],
            "value": demand_latest["value"],
            "unit": demand["unit"],
            "provider": provider,
            "product": "US48 electricity demand",
            "geography": demand["geography"]["id"],
            "period": "daily actual",
            "qualifier": "sum of complete hourly observations for the UTC day",
            "source_url": demand["source_url"],
        },
        {
            "metric": "net_generation",
            "as_of": generation_latest["period"],
            "value": generation_latest["value"],
            "unit": generation["unit"],
            "provider": provider,
            "product": "US48 net generation",
            "geography": generation["geography"]["id"],
            "period": "daily actual",
            "qualifier": "sum of complete hourly observations for the UTC day",
            "source_url": generation["source_url"],
        },
        {
            "metric": "operating_net_summer_capacity",
            "as_of": cap_period,
            "value": capacity["operating"]["net_summer_capacity_mw"],
            "unit": "MW",
            "provider": provider,
            "product": "EIA-860M operating generators",
            "geography": capacity["geography"]["coverage"],
            "period": "monthly reported inventory",
            "qualifier": "reported operating net summer capacity; not a forecast",
            "source_url": capacity["source_url"],
        },
        {
            "metric": "planned_net_summer_capacity",
            "as_of": cap_period,
            "value": capacity["planned"]["net_summer_capacity_mw"],
            "unit": "MW",
            "provider": provider,
            "product": "EIA-860M planned generators",
            "geography": capacity["geography"]["coverage"],
            "period": "monthly reported inventory",
            "qualifier": "reported planned capacity; kept separate from operating capacity",
            "source_url": capacity["source_url"],
        },
    ]
    return {"schema_version": 1, "observations": observations}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = build(args.input_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
