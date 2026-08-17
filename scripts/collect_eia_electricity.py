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
MAX_PAGE_SIZE = 5000


def api_key() -> str:
    key = os.environ.get("EIA_API_KEY")
    if not key:
        raise RuntimeError("EIA_API_KEY is required by the EIA API")
    return key


def build_url(
    route: str,
    data_fields: list[str],
    frequency: str,
    start: str | None,
    end: str | None,
    length: int,
    offset: int = 0,
    facets: list[tuple[str, str]] | None = None,
) -> str:
    if length < 1 or length > MAX_PAGE_SIZE:
        raise ValueError(f"length must be between 1 and {MAX_PAGE_SIZE}")
    params: list[tuple[str, str]] = [
        ("api_key", api_key()),
        ("frequency", frequency),
        ("offset", str(offset)),
        ("length", str(length)),
    ]
    for index, field in enumerate(data_fields):
        params.append((f"data[{index}]", field))
    for name, value in facets or []:
        params.append((f"facets[{name}][]", value))
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


def redact(url: str) -> str:
    return url.replace(api_key(), "REDACTED")


def collect(
    route: str,
    data_fields: list[str],
    frequency: str,
    start: str | None,
    end: str | None,
    length: int,
    facets: list[tuple[str, str]] | None = None,
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    pages: list[dict[str, object]] = []
    response_set_hash = hashlib.sha256()
    offset = 0
    total: int | None = None
    api_version: str | None = None
    warnings: list[object] = []

    while True:
        url = build_url(route, data_fields, frequency, start, end, length, offset, facets)
        raw = fetch(url)
        response_set_hash.update(raw)
        payload = json.loads(raw)
        response = payload.get("response") or {}
        page_rows = response.get("data") or []
        if not page_rows:
            if not rows:
                raise RuntimeError(f"EIA returned no rows for route={route!r} fields={data_fields!r}")
            break

        if api_version is None:
            api_version = payload.get("apiVersion")
        if not warnings:
            warnings = response.get("warnings") or []
        if total is None and response.get("total") is not None:
            total = int(response["total"])

        pages.append(
            {
                "offset": offset,
                "row_count": len(page_rows),
                "source_url": redact(url),
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        rows.extend(page_rows)

        if len(page_rows) < length or (total is not None and len(rows) >= total):
            break
        offset += len(page_rows)

    return {
        "schema_version": 2,
        "publisher": "U.S. Energy Information Administration",
        "api_version": api_version,
        "route": route,
        "frequency": frequency,
        "data_fields": data_fields,
        "facets": [{"name": name, "value": value} for name, value in facets or []],
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source_url": pages[0]["source_url"],
        "source_pages": pages,
        "raw_sha256": response_set_hash.hexdigest(),
        "warnings": warnings,
        "total": total,
        "row_count": len(rows),
        "data": rows,
    }


def parse_facets(values: list[str]) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for value in values:
        name, separator, facet_value = value.partition("=")
        if not separator or not name.strip() or not facet_value.strip():
            raise ValueError(f"facet must be KEY=VALUE, got {value!r}")
        result.append((name.strip(), facet_value.strip()))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route", default="electricity/rto/region-data")
    parser.add_argument("--data", action="append", default=["value"], help="EIA data field; repeat for multiple fields")
    parser.add_argument("--facet", action="append", default=[], help="EIA facet as KEY=VALUE; repeat for multiple values")
    parser.add_argument("--frequency", default="hourly")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--length", type=int, default=MAX_PAGE_SIZE, help="rows per EIA API page")
    parser.add_argument("--output", type=Path, default=Path("data/electricity/eia-rto-region-data.json"))
    args = parser.parse_args()
    result = collect(
        args.route,
        args.data,
        args.frequency,
        args.start,
        args.end,
        args.length,
        parse_facets(args.facet),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {result['row_count']} observations from {len(result['source_pages'])} page(s) -> {args.output}")


if __name__ == "__main__":
    main()
