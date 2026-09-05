#!/usr/bin/env python3
"""Build compact decision metrics and EIA revision changes from canonical outputs."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
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


def observations_by_period(series: dict) -> dict[str, dict]:
    rows = series.get("daily")
    if not isinstance(rows, list):
        raise ValueError(f"{series.get('dataset')}: daily must be a list")
    result: dict[str, dict] = {}
    for row in rows:
        period = row.get("period")
        if not isinstance(period, str) or not period:
            raise ValueError(f"{series.get('dataset')}: daily row missing period")
        if period in result:
            raise ValueError(f"{series.get('dataset')}: duplicate period {period}")
        result[period] = row
    return result


def revision_changes(previous: dict, current: dict) -> list[dict]:
    if previous.get("series_id") != current.get("series_id"):
        raise ValueError("cannot compare different series_id values")
    if previous.get("unit") != current.get("unit"):
        raise ValueError("cannot compare different units")
    before = observations_by_period(previous)
    after = observations_by_period(current)
    changes: list[dict] = []
    for period in sorted(before.keys() & after.keys()):
        old = before[period].get("value")
        new = after[period].get("value")
        if old != new:
            changes.append(
                {
                    "period": period,
                    "before": old,
                    "after": new,
                    "delta": round(float(new) - float(old), 3),
                }
            )
    return changes


def load_from_head(path: Path) -> dict:
    relative = path.resolve().relative_to(ROOT).as_posix()
    result = subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object in HEAD:{relative}")
    return value


def build_revision_report(input_dir: Path) -> dict:
    datasets: dict[str, dict] = {}
    total_changes = 0
    for name in ("demand", "generation", "interchange"):
        path = input_dir / f"{name}.json"
        current = load(path)
        previous = load_from_head(path)
        changes = revision_changes(previous, current)
        total_changes += len(changes)
        datasets[name] = {
            "series_id": current["series_id"],
            "unit": current["unit"],
            "previous_source_evidence": previous.get("source_evidence"),
            "previous_source_evidence_sha256": previous.get("source_evidence_sha256"),
            "current_source_evidence": current.get("source_evidence"),
            "current_source_evidence_sha256": current.get("source_evidence_sha256"),
            "overlap_period_count": len(
                observations_by_period(previous).keys() & observations_by_period(current).keys()
            ),
            "revision_count": len(changes),
            "revisions": changes,
        }
    return {
        "schema_version": 1,
        "publisher": "U.S. Energy Information Administration",
        "comparison_scope": (
            "Same series, unit, and daily period present in both consecutive canonical snapshots. "
            "Rolling-window entry or expiry is not treated as a data revision."
        ),
        "total_revision_count": total_changes,
        "datasets": datasets,
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--revision-output", type=Path)
    args = parser.parse_args()
    write_json(args.output, build(args.input_dir))
    if args.revision_output is not None:
        write_json(args.revision_output, build_revision_report(args.input_dir))


if __name__ == "__main__":
    main()
