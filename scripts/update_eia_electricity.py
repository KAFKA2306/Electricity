#!/usr/bin/env python3
"""Collect canonical EIA electricity datasets and publish compact derived views."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from collect_eia_electricity import MAX_PAGE_SIZE, collect

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW = ROOT / "data" / "electricity" / "official"
DEFAULT_API = ROOT / "api" / "v1" / "electricity"

RTO_ROUTE = "electricity/rto/daily-region-data"
CAPACITY_ROUTE = "electricity/operating-generator-capacity"
CAPACITY_FIELDS = [
    "nameplate-capacity-mw",
    "net-summer-capacity-mw",
    "net-winter-capacity-mw",
    "operating-year-month",
]


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def snapshot_path(raw_dir: Path, name: str, payload: dict[str, Any]) -> Path:
    digest = str(payload["raw_sha256"])[:16]
    return raw_dir / f"{name}-{digest}.json"


def persist_snapshot(raw_dir: Path, name: str, payload: dict[str, Any]) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_path(raw_dir, name, payload)
    if not path.exists():
        path.write_bytes(canonical_json(payload))
    return path


def numeric(value: object) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def rto_view(name: str, payload: dict[str, Any], snapshot: Path) -> dict[str, Any]:
    rows = payload.get("data") or []
    if not rows:
        raise ValueError(f"{name}: no rows")
    expected_type = {"demand": "D", "generation": "NG"}[name]
    periods = sorted({str(row["period"]) for row in rows if row.get("period")})
    if len(periods) < 90:
        raise ValueError(f"{name}: expected >=90 daily periods, got {len(periods)}")
    bad = [row for row in rows if row.get("type") not in (None, expected_type)]
    if bad:
        raise ValueError(f"{name}: unexpected type values; forecast/interchange must stay separate")
    values = [numeric(row.get("value")) for row in rows]
    if not any(value is not None for value in values):
        raise ValueError(f"{name}: no numeric values")
    latest_period = periods[-1]
    latest_rows = [row for row in rows if str(row.get("period")) == latest_period]
    latest_value = numeric(latest_rows[0].get("value")) if latest_rows else None
    return {
        "schema_version": 1,
        "dataset": name,
        "publisher": payload["publisher"],
        "route": payload["route"],
        "frequency": payload["frequency"],
        "geography": {"level": "balancing-authority-region", "id": "US48"},
        "measure": {"id": "value", "unit": "megawatthours", "kind": "actual"},
        "period_count": len(periods),
        "first_period": periods[0],
        "last_period": latest_period,
        "latest_value": latest_value,
        "row_count": len(rows),
        "source_url": payload["source_url"],
        "source_snapshot": str(snapshot.relative_to(ROOT)) if snapshot.is_relative_to(ROOT) else str(snapshot),
        "source_snapshot_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        "retrieved_at": payload["retrieved_at"],
    }


def capacity_view(payload: dict[str, Any], snapshot: Path) -> dict[str, Any]:
    rows = payload.get("data") or []
    if not rows:
        raise ValueError("capacity: no rows")
    periods = sorted({str(row["period"]) for row in rows if row.get("period")})
    if len(periods) != 1:
        raise ValueError(f"capacity: expected one latest month, got {periods}")
    totals: dict[str, float] = {}
    for field in CAPACITY_FIELDS[:3]:
        values = [numeric(row.get(field)) for row in rows]
        totals[field] = round(sum(value for value in values if value is not None), 3)
    return {
        "schema_version": 1,
        "dataset": "capacity",
        "publisher": payload["publisher"],
        "route": payload["route"],
        "frequency": payload["frequency"],
        "geography": {"level": "generator", "coverage": "United States"},
        "measure_units": {
            "nameplate-capacity-mw": "MW",
            "net-summer-capacity-mw": "MW",
            "net-winter-capacity-mw": "MW",
            "operating-year-month": "YYYY-MM",
        },
        "period": periods[0],
        "generator_row_count": len(rows),
        "totals_mw": totals,
        "source_url": payload["source_url"],
        "source_snapshot": str(snapshot.relative_to(ROOT)) if snapshot.is_relative_to(ROOT) else str(snapshot),
        "source_snapshot_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        "retrieved_at": payload["retrieved_at"],
    }


def write_views(api_dir: Path, views: dict[str, dict[str, Any]]) -> None:
    api_dir.mkdir(parents=True, exist_ok=True)
    for name, view in views.items():
        (api_dir / f"{name}.json").write_bytes(canonical_json(view))
    index = {
        "schema_version": 1,
        "publisher": "U.S. Energy Information Administration",
        "datasets": {
            name: {
                "path": f"{name}.json",
                "route": view["route"],
                "frequency": view["frequency"],
                "source_url": view["source_url"],
            }
            for name, view in sorted(views.items())
        },
    }
    (api_dir / "index.json").write_bytes(canonical_json(index))


def collect_all(start: str | None = None) -> dict[str, dict[str, Any]]:
    start = start or (date.today() - timedelta(days=120)).isoformat()
    demand = collect(RTO_ROUTE, ["value"], "daily", start, None, MAX_PAGE_SIZE, [("respondent", "US48"), ("type", "D")])
    generation = collect(RTO_ROUTE, ["value"], "daily", start, None, MAX_PAGE_SIZE, [("respondent", "US48"), ("type", "NG")])
    probe = collect(CAPACITY_ROUTE, CAPACITY_FIELDS, "monthly", None, None, 1)
    latest = str(probe["data"][0]["period"])
    capacity = collect(CAPACITY_ROUTE, CAPACITY_FIELDS, "monthly", latest, latest, MAX_PAGE_SIZE)
    return {"demand": demand, "generation": generation, "capacity": capacity}


def publish(raw_dir: Path, api_dir: Path, payloads: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    snapshots = {name: persist_snapshot(raw_dir, name, payload) for name, payload in payloads.items()}
    stored = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in snapshots.items()}
    views = {
        "demand": rto_view("demand", stored["demand"], snapshots["demand"]),
        "generation": rto_view("generation", stored["generation"], snapshots["generation"]),
        "capacity": capacity_view(stored["capacity"], snapshots["capacity"]),
    }
    write_views(api_dir, views)
    return views


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", help="inclusive RTO daily start; defaults to 120 days ago")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--api-dir", type=Path, default=DEFAULT_API)
    args = parser.parse_args()
    views = publish(args.raw_dir, args.api_dir, collect_all(args.start))
    print(json.dumps({name: view.get("row_count", view.get("generator_row_count")) for name, view in views.items()}))


if __name__ == "__main__":
    main()
