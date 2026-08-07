#!/usr/bin/env python3
"""Build deterministic static API files from verified EIA source snapshots."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = ROOT / "data" / "official"
DEFAULT_OUTPUT = ROOT / "api" / "v1"


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_latest_snapshot() -> tuple[Path, dict]:
    paths = sorted(SNAPSHOT_DIR.glob("eia-weekly-stocks-*.json"))
    if not paths:
        raise ValueError("no EIA source snapshot found")
    path = paths[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_snapshot(payload)
    return path, payload


def validate_snapshot(payload: dict) -> None:
    if payload.get("schema_version") != "1.0.0":
        raise ValueError("unsupported snapshot schema_version")
    source = payload.get("source")
    if not isinstance(source, dict) or source.get("publisher") != "U.S. Energy Information Administration (EIA)":
        raise ValueError("unexpected or missing source publisher")
    latest = source.get("latest_period_confirmed")
    date.fromisoformat(latest)
    series = payload.get("series")
    if not isinstance(series, list) or not series:
        raise ValueError("series must be a non-empty list")
    seen_ids: set[str] = set()
    for item in series:
        series_id = item.get("id")
        if not isinstance(series_id, str) or not series_id:
            raise ValueError("series id is required")
        if series_id in seen_ids:
            raise ValueError(f"duplicate series id: {series_id}")
        seen_ids.add(series_id)
        observations = item.get("observations")
        if not isinstance(observations, list) or not observations:
            raise ValueError(f"observations missing for {series_id}")
        periods: list[str] = []
        for obs in observations:
            period = obs.get("period")
            value = obs.get("value")
            date.fromisoformat(period)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"invalid value for {series_id} at {period}")
            periods.append(period)
        if periods != sorted(set(periods)):
            raise ValueError(f"periods must be sorted and unique for {series_id}")
        if periods[-1] != latest:
            raise ValueError(f"latest observation mismatch for {series_id}")


def build_files(snapshot_path: Path, payload: dict) -> dict[str, bytes]:
    source = payload["source"]
    series_records = []
    latest_records = []
    csv_buffer = io.StringIO(newline="")
    writer = csv.writer(csv_buffer, lineterminator="\n")
    writer.writerow(["series_id", "title", "area", "period", "value", "unit"])

    observation_count = 0
    for item in sorted(payload["series"], key=lambda value: value["id"]):
        record = {
            "id": item["id"],
            "title": item["title"],
            "area": item["area"],
            "unit": item["unit"],
            "frequency": source["frequency"],
            "source_url": source["commercial_crude_url"] if item["id"].startswith("commercial_crude_") else source["us_stocks_url"],
            "observation_count": len(item["observations"]),
            "first_period": item["observations"][0]["period"],
            "last_period": item["observations"][-1]["period"],
        }
        series_records.append(record)
        latest = item["observations"][-1]
        latest_records.append({**record, "period": latest["period"], "value": latest["value"]})
        for obs in item["observations"]:
            writer.writerow([item["id"], item["title"], item["area"], obs["period"], obs["value"], item["unit"]])
            observation_count += 1

    files: dict[str, bytes] = {
        "series.json": canonical_json({"schema_version": "1.0.0", "series": series_records}),
        "latest.json": canonical_json({"schema_version": "1.0.0", "latest_period": source["latest_period_confirmed"], "series": latest_records}),
        "observations.csv": csv_buffer.getvalue().encode(),
    }
    snapshot_bytes = snapshot_path.read_bytes()
    manifest = {
        "api_version": "v1",
        "schema_version": "1.0.0",
        "source_snapshot": str(snapshot_path.relative_to(ROOT)),
        "source_snapshot_sha256": sha256_bytes(snapshot_bytes),
        "publisher": source["publisher"],
        "release_date_confirmed": source["release_date_confirmed"],
        "latest_period_confirmed": source["latest_period_confirmed"],
        "series_count": len(series_records),
        "observation_count": observation_count,
        "cache_control_seconds": 3600,
        "files": {
            name: {"bytes": len(data), "sha256": sha256_bytes(data)}
            for name, data in sorted(files.items())
        },
    }
    files["manifest.json"] = canonical_json(manifest)
    return files


def write_files(output_dir: Path, files: dict[str, bytes]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (output_dir / name).write_bytes(data)


def check_files(output_dir: Path, files: dict[str, bytes]) -> None:
    for name, expected in files.items():
        path = output_dir / name
        if not path.exists() or path.read_bytes() != expected:
            raise SystemExit(f"generated API is stale: {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    snapshot_path, payload = load_latest_snapshot()
    files = build_files(snapshot_path, payload)
    if args.check:
        check_files(args.output, files)
    else:
        write_files(args.output, files)
        print(json.dumps({"series": len(payload["series"]), "files": sorted(files)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
