#!/usr/bin/env python3
"""Collect versioned electricity observations from EIA API v2."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://api.eia.gov/v2"


def build_url(route: str, data_fields: list[str], frequency: str, start: str | None, end: str | None, length: int) -> str:
    key = os.environ.get("EIA_API_KEY")
    if not key:
        raise RuntimeError("EIA_API_KEY is required by the EIA API")
    params: list[tuple[str, str]] = [("api_key", key), ("frequency", frequency), ("offset", "0"), ("length", str(length))]
    for index, field in enumerate(data_fields):
        params.append((f"data[{index}]", field))
    if start:
        params.append(("start", start))
    if end:
        params.append(("end", end))
    params.extend([("sort[0][column]", "period"), ("sort[0][direction]", "desc")])
    return f"{API}/{route.strip('/')}/data/?{urlencode(params)}"


def fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "energy-supply/1.0 github.com/KAFKA2306/oil"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def collect(route: str, data_fields: list[str], frequency: str, start: str | None, end: str | None, length: int) -> dict[str, object]:
    url = build_url(route, data_fields, frequency, start, end, length)
    raw = fetch(url)
    payload = json.loads(raw)
    response = payload.get("response") or {}
    rows = response.get("data") or []
    if not rows:
        raise RuntimeError(f"EIA returned no rows for route={route!r} fields={data_fields!r}")
    safe_url = url.replace(os.environ["EIA_API_KEY"], "REDACTED")
    return {
        "schema_version": 1,
        "publisher": "U.S. Energy Information Administration",
        "api_version": payload.get("apiVersion"),
        "route": route,
        "frequency": frequency,
        "data_fields": data_fields,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source_url": safe_url,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "warnings": response.get("warnings") or [],
        "total": response.get("total"),
        "data": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route", default="electricity/rto/region-data")
    parser.add_argument("--data", action="append", default=["value"], help="EIA data field; repeat for multiple fields")
    parser.add_argument("--frequency", default="hourly")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--length", type=int, default=5000)
    parser.add_argument("--output", type=Path, default=Path("data/electricity/eia-rto-region-data.json"))
    args = parser.parse_args()
    result = collect(args.route, args.data, args.frequency, args.start, args.end, args.length)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(result['data'])} observations -> {args.output}")


if __name__ == "__main__":
    main()
