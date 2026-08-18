#!/usr/bin/env python3
"""Publish EIA electricity evidence without requiring an API key."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import urllib.request
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE = ROOT / "data" / "electricity" / "official"
DEFAULT_API = ROOT / "api" / "v1" / "electricity"
EBA_URL = "https://www.eia.gov/opendata/bulk/EBA.zip"
EIA860M_INDEX = "https://www.eia.gov/electricity/data/eia860m/"
SERIES = {"demand": "EBA.US48-ALL.D.H", "generation": "EBA.US48-ALL.NG.H"}
CAPACITY_SHEETS = ("Operating", "Planned", "Retired")
USER_AGENT = "energy-supply/1.0 github.com/KAFKA2306/oil"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)


def latest_eia860m_url(index_html: bytes) -> str:
    parser = LinkParser()
    parser.feed(index_html.decode("utf-8", errors="replace"))
    candidates = [
        urljoin(EIA860M_INDEX, href)
        for href in parser.hrefs
        if re.search(r"/eia860m/xls/[a-z]+_generator20\d{2}\.xlsx$", href, re.I)
    ]
    if not candidates:
        raise ValueError("EIA-860M index did not expose a generator workbook")
    return candidates[0]


def read_bulk_series(zip_bytes: bytes, wanted: set[str]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".txt")]
        if len(names) != 1:
            raise ValueError(f"EBA bulk expected one txt file, got {names}")
        with archive.open(names[0]) as source:
            for raw_line in source:
                if not any(series_id.encode() in raw_line for series_id in wanted):
                    continue
                obj = json.loads(raw_line)
                series_id = obj.get("series_id")
                if series_id in wanted:
                    found[series_id] = obj
                    if len(found) == len(wanted):
                        break
    missing = wanted - set(found)
    if missing:
        raise ValueError(f"EBA bulk missing required series: {sorted(missing)}")
    return found


def parse_hour(period: str) -> datetime:
    return datetime.strptime(period, "%Y%m%dT%HZ").replace(tzinfo=timezone.utc)


def daily_actual(series: dict[str, Any], days: int = 120) -> list[dict[str, Any]]:
    if series.get("f") != "H":
        raise ValueError(f"{series.get('series_id')}: expected hourly series")
    points: list[tuple[datetime, float]] = []
    for period, value in series.get("data") or []:
        if value in (None, "null", "w", "*"):
            continue
        try:
            points.append((parse_hour(str(period)), float(value)))
        except (TypeError, ValueError):
            continue
    if not points:
        raise ValueError(f"{series.get('series_id')}: no numeric hourly observations")
    latest_day = max(dt.date() for dt, _ in points)
    cutoff = latest_day - timedelta(days=days - 1)
    grouped: dict[str, list[float]] = defaultdict(list)
    for dt, value in points:
        if dt.date() >= cutoff:
            grouped[dt.date().isoformat()].append(value)
    rows = [
        {"period": period, "value": round(sum(values), 3), "hour_count": len(values)}
        for period, values in sorted(grouped.items())
        if len(values) >= 20
    ]
    if len(rows) < 90:
        raise ValueError(f"{series.get('series_id')}: expected >=90 daily periods, got {len(rows)}")
    return rows


def normalize_header(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def worksheet_records(ws: Any) -> list[dict[str, Any]]:
    header_row = None
    headers: list[str] = []
    for row_number, row in enumerate(ws.iter_rows(values_only=True), start=1):
        normalized = [normalize_header(value) for value in row]
        if "generator id" in normalized and any(name in normalized for name in ("plant id", "plant code")):
            header_row = row_number
            headers = [str(value or "").strip() for value in row]
            break
        if row_number >= 15:
            break
    if header_row is None:
        raise ValueError(f"{ws.title}: header row not found")
    records: list[dict[str, Any]] = []
    for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
        if not any(value not in (None, "") for value in row):
            continue
        records.append({headers[i]: value for i, value in enumerate(row) if i < len(headers) and headers[i]})
    return records


def find_column(record: dict[str, Any], *names: str) -> str:
    normalized = {normalize_header(key): key for key in record}
    for name in names:
        key = normalized.get(normalize_header(name))
        if key:
            return key
    raise ValueError(f"required column missing; wanted {names}, got {list(record)[:20]}")


def number(value: object) -> float | None:
    if value in (None, "", " ", "NA", "N/A"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summarize_capacity(xlsx_bytes: bytes) -> dict[str, Any]:
    try:
        import openpyxl
    except ImportError as exc:
        raise RuntimeError("openpyxl is required to parse EIA-860M") from exc
    workbook = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), read_only=True, data_only=True)
    missing = [name for name in CAPACITY_SHEETS if name not in workbook.sheetnames]
    if missing:
        raise ValueError(f"EIA-860M workbook missing sheets: {missing}; got {workbook.sheetnames}")
    result: dict[str, Any] = {}
    for sheet_name in CAPACITY_SHEETS:
        records = worksheet_records(workbook[sheet_name])
        if not records:
            raise ValueError(f"{sheet_name}: no generator records")
        sample = records[0]
        summer_key = find_column(sample, "Net Summer Capacity (MW)")
        nameplate_key = find_column(sample, "Nameplate Capacity (MW)")
        tech_key = find_column(sample, "Technology")
        state_key = find_column(sample, "Plant State", "State")
        summer_total = 0.0
        nameplate_total = 0.0
        by_technology: dict[str, float] = defaultdict(float)
        by_state: dict[str, float] = defaultdict(float)
        for record in records:
            summer = number(record.get(summer_key))
            nameplate = number(record.get(nameplate_key))
            if summer is not None:
                summer_total += summer
                by_technology[str(record.get(tech_key) or "Unknown")] += summer
                by_state[str(record.get(state_key) or "Unknown")] += summer
            if nameplate is not None:
                nameplate_total += nameplate
        result[sheet_name.lower()] = {
            "generator_count": len(records),
            "nameplate_capacity_mw": round(nameplate_total, 3),
            "net_summer_capacity_mw": round(summer_total, 3),
            "by_technology_net_summer_mw": dict(sorted(by_technology.items())),
            "by_state_net_summer_mw": dict(sorted(by_state.items())),
        }
    return result


def build_payload(days: int = 120) -> dict[str, Any]:
    retrieved_at = datetime.now(timezone.utc).isoformat()
    eba_zip = fetch(EBA_URL)
    eba_series = read_bulk_series(eba_zip, set(SERIES.values()))
    index_html = fetch(EIA860M_INDEX)
    capacity_url = latest_eia860m_url(index_html)
    capacity_xlsx = fetch(capacity_url)
    capacity = summarize_capacity(capacity_xlsx)
    actual: dict[str, Any] = {}
    for name, series_id in SERIES.items():
        series = eba_series[series_id]
        rows = daily_actual(series, days=days)
        actual[name] = {
            "series_id": series_id,
            "name": series.get("name"),
            "unit": "megawatthours",
            "frequency": "daily",
            "kind": "actual",
            "day_boundary": "UTC",
            "geography": {"level": "region", "id": "US48", "name": "United States Lower 48"},
            "first_period": rows[0]["period"],
            "last_period": rows[-1]["period"],
            "period_count": len(rows),
            "data": rows,
        }
    return {
        "schema_version": 3,
        "publisher": "U.S. Energy Information Administration",
        "retrieved_at": retrieved_at,
        "sources": {
            "eba_bulk": {"url": EBA_URL, "sha256": sha256(eba_zip), "series_ids": sorted(SERIES.values())},
            "eia860m": {"index_url": EIA860M_INDEX, "url": capacity_url, "sha256": sha256(capacity_xlsx), "sheets": list(CAPACITY_SHEETS)},
        },
        "actual": actual,
        "capacity": capacity,
    }


def evidence_name(payload: dict[str, Any]) -> str:
    core = dict(payload)
    core.pop("retrieved_at", None)
    return f"eia-electricity-{sha256(canonical_json(core))[:16]}.json"


def publish(evidence_dir: Path, api_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = evidence_dir / evidence_name(payload)
    if not path.exists():
        path.write_bytes(canonical_json(payload))
    stored = json.loads(path.read_text(encoding="utf-8"))
    evidence_sha = sha256(path.read_bytes())
    api_dir.mkdir(parents=True, exist_ok=True)
    views: dict[str, Any] = {}
    for name in ("demand", "generation"):
        item = stored["actual"][name]
        views[name] = {
            "schema_version": 1,
            "dataset": name,
            "publisher": stored["publisher"],
            "series_id": item["series_id"],
            "frequency": item["frequency"],
            "kind": item["kind"],
            "unit": item["unit"],
            "day_boundary": item["day_boundary"],
            "geography": item["geography"],
            "period_count": item["period_count"],
            "first_period": item["first_period"],
            "last_period": item["last_period"],
            "latest": item["data"][-1],
            "source_url": EBA_URL,
            "source_evidence": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            "source_evidence_sha256": evidence_sha,
        }
    views["capacity"] = {
        "schema_version": 1,
        "dataset": "capacity",
        "publisher": stored["publisher"],
        "frequency": "monthly",
        "kind": "reported-inventory",
        "unit": "MW",
        "geography": {"level": "generator", "coverage": "United States and Puerto Rico where reported"},
        "operating": stored["capacity"]["operating"],
        "planned": stored["capacity"]["planned"],
        "retired": stored["capacity"]["retired"],
        "source_url": stored["sources"]["eia860m"]["url"],
        "source_evidence": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "source_evidence_sha256": evidence_sha,
    }
    for name, view in views.items():
        (api_dir / f"{name}.json").write_bytes(canonical_json(view))
    index = {
        "schema_version": 1,
        "publisher": stored["publisher"],
        "datasets": {name: {"path": f"{name}.json", "frequency": view["frequency"], "kind": view["kind"], "source_url": view["source_url"]} for name, view in sorted(views.items())},
    }
    (api_dir / "index.json").write_bytes(canonical_json(index))
    return views


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=120)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--api-dir", type=Path, default=DEFAULT_API)
    args = parser.parse_args()
    if args.days < 90:
        raise SystemExit("--days must be at least 90")
    views = publish(args.evidence_dir, args.api_dir, build_payload(args.days))
    print(json.dumps({
        "demand_days": views["demand"]["period_count"],
        "generation_days": views["generation"]["period_count"],
        "operating_generators": views["capacity"]["operating"]["generator_count"],
        "planned_generators": views["capacity"]["planned"]["generator_count"],
        "retired_generators": views["capacity"]["retired"]["generator_count"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
