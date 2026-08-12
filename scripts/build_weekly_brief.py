#!/usr/bin/env python3
"""Build an auditable weekly petroleum stock brief from a verified EIA snapshot."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT = ROOT / "data" / "official" / "eia-weekly-stocks-2026-08-08.json"
DEFAULT_WATCHLIST = ROOT / "config" / "watchlists" / "weekly-petroleum-sample.json"
DEFAULT_OUTPUT = ROOT / "build" / "weekly-brief"
NOT_COMPUTABLE = "NOT_COMPUTABLE"


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def validate_watchlist(watchlist: dict[str, Any]) -> None:
    if watchlist.get("schema_version") != "1.0.0":
        raise ValueError("unsupported watchlist schema_version")
    entries = watchlist.get("series")
    if not isinstance(entries, list) or not entries:
        raise ValueError("watchlist series must be a non-empty list")
    seen: set[str] = set()
    for entry in entries:
        series_id = entry.get("id")
        if not isinstance(series_id, str) or not series_id or series_id in seen:
            raise ValueError(f"invalid or duplicate watchlist series id: {series_id}")
        seen.add(series_id)
        if not isinstance(entry.get("label"), str) or not entry["label"].strip():
            raise ValueError(f"display label required for {series_id}")
        absolute = entry.get("absolute_change_threshold")
        percentage = entry.get("percentage_change_threshold")
        if absolute is not None and (not isinstance(absolute, (int, float)) or absolute < 0):
            raise ValueError(f"invalid absolute threshold for {series_id}")
        if percentage is not None and (not isinstance(percentage, (int, float)) or percentage < 0):
            raise ValueError(f"invalid percentage threshold for {series_id}")
    window = watchlist.get("comparison_window", 4)
    if not isinstance(window, int) or window < 2:
        raise ValueError("comparison_window must be an integer >= 2")
    formats = watchlist.get("delivery_formats")
    if formats != ["html", "markdown"]:
        raise ValueError("delivery_formats must be exactly ['html', 'markdown'] for v1")


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    if snapshot.get("schema_version") != "1.0.0":
        raise ValueError("unsupported snapshot schema_version")
    source = snapshot.get("source")
    if not isinstance(source, dict) or source.get("publisher") != "U.S. Energy Information Administration (EIA)":
        raise ValueError("unexpected source publisher")
    series = snapshot.get("series")
    if not isinstance(series, list) or not series:
        raise ValueError("snapshot series must be a non-empty list")
    seen: set[str] = set()
    for item in series:
        series_id = item.get("id")
        if not isinstance(series_id, str) or not series_id or series_id in seen:
            raise ValueError(f"invalid or duplicate snapshot series id: {series_id}")
        seen.add(series_id)
        observations = item.get("observations")
        if not isinstance(observations, list) or not observations:
            raise ValueError(f"observations missing for {series_id}")
        periods = [obs.get("period") for obs in observations]
        values = [obs.get("value") for obs in observations]
        if any(not isinstance(period, str) for period in periods) or periods != sorted(set(periods)):
            raise ValueError(f"periods must be sorted and unique for {series_id}")
        if any(not isinstance(value, (int, float)) or value < 0 for value in values):
            raise ValueError(f"invalid observations for {series_id}")


def metric(value: float | int | None, *, reason: str | None = None, digits: int = 3) -> dict[str, Any]:
    if value is None:
        return {"status": NOT_COMPUTABLE, "value": None, "reason": reason}
    if isinstance(value, float):
        value = round(value, digits)
    return {"status": "OK", "value": value, "reason": None}


def source_url_for(series_id: str, source: dict[str, Any]) -> str:
    key = "commercial_crude_url" if series_id.startswith("commercial_crude_") else "us_stocks_url"
    value = source.get(key)
    if not isinstance(value, str) or not value.startswith("https://www.eia.gov/"):
        raise ValueError(f"missing official EIA source URL for {series_id}")
    return value


def build_brief(snapshot_path: Path, snapshot: dict[str, Any], watchlist: dict[str, Any]) -> dict[str, Any]:
    validate_snapshot(snapshot)
    validate_watchlist(watchlist)
    source = snapshot["source"]
    by_id = {item["id"]: item for item in snapshot["series"]}
    window = watchlist.get("comparison_window", 4)
    records: list[dict[str, Any]] = []

    for requested in watchlist["series"]:
        series_id = requested["id"]
        if series_id not in by_id:
            raise ValueError(f"watchlist series not present in snapshot: {series_id}")
        item = by_id[series_id]
        observations = item["observations"]
        latest = observations[-1]

        if len(observations) >= 2:
            previous = observations[-2]
            weekly_change = latest["value"] - previous["value"]
            weekly_change_metric = metric(weekly_change)
            if previous["value"] == 0:
                weekly_pct_metric = metric(None, reason="previous observation is zero")
            else:
                weekly_pct_metric = metric(weekly_change / previous["value"] * 100)
        else:
            previous = None
            weekly_change_metric = metric(None, reason="fewer than two observations")
            weekly_pct_metric = metric(None, reason="fewer than two observations")

        if len(observations) >= window:
            window_values = [obs["value"] for obs in observations[-window:]]
            window_average = mean(window_values)
            versus_average = latest["value"] - window_average
            window_average_metric = metric(window_average)
            versus_average_metric = metric(versus_average)
        else:
            window_average_metric = metric(None, reason=f"fewer than {window} observations")
            versus_average_metric = metric(None, reason=f"fewer than {window} observations")

        alert_reasons: list[str] = []
        absolute_threshold = requested.get("absolute_change_threshold")
        percentage_threshold = requested.get("percentage_change_threshold")
        if weekly_change_metric["status"] == "OK" and absolute_threshold is not None:
            if abs(weekly_change_metric["value"]) >= absolute_threshold:
                alert_reasons.append(f"absolute weekly change >= {absolute_threshold}")
        if weekly_pct_metric["status"] == "OK" and percentage_threshold is not None:
            if abs(weekly_pct_metric["value"]) >= percentage_threshold:
                alert_reasons.append(f"absolute weekly percentage change >= {percentage_threshold}%")

        records.append(
            {
                "series_id": series_id,
                "label": requested["label"],
                "title": item["title"],
                "area": item["area"],
                "unit": item["unit"],
                "observation_date": latest["period"],
                "latest_value": latest["value"],
                "previous_observation_date": previous["period"] if previous else None,
                "previous_value": previous["value"] if previous else None,
                "weekly_change": weekly_change_metric,
                "weekly_percentage_change": weekly_pct_metric,
                "window_weeks": window,
                "window_average": window_average_metric,
                "versus_window_average": versus_average_metric,
                "alert": bool(alert_reasons),
                "alert_reasons": alert_reasons,
                "source_url": source_url_for(series_id, source),
            }
        )

    return {
        "schema_version": "1.0.0",
        "brief_type": "observed_weekly_petroleum_stock_change",
        "latest_period": source["latest_period_confirmed"],
        "release_date": source["release_date_confirmed"],
        "snapshot_captured_at": snapshot.get("observed_at"),
        "source_publisher": source["publisher"],
        "source_snapshot": str(snapshot_path.relative_to(ROOT)),
        "source_snapshot_sha256": sha256_file(snapshot_path),
        "watchlist_id": watchlist.get("id"),
        "watchlist_schema_version": watchlist["schema_version"],
        "disclaimer": "Observed EIA stock changes only; no price forecast, security recommendation, or investment advice.",
        "alerts": [record["series_id"] for record in records if record["alert"]],
        "series": records,
    }


def format_metric(value: dict[str, Any], suffix: str = "") -> str:
    if value["status"] != "OK":
        return NOT_COMPUTABLE
    return f"{value['value']:+,.3f}{suffix}" if suffix else f"{value['value']:+,.3f}"


def markdown_document(brief: dict[str, Any]) -> str:
    lines = [
        "# Weekly Petroleum Stock Brief (sample)",
        "",
        f"- Observation period: `{brief['latest_period']}`",
        f"- EIA release date: `{brief['release_date']}`",
        f"- Source snapshot: `{brief['source_snapshot']}`",
        f"- Snapshot SHA-256: `{brief['source_snapshot_sha256']}`",
        f"- Scope: {brief['disclaimer']}",
        "",
        "| Series | Area | Latest | Weekly change | Weekly % | 4-week avg diff | Alert |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for record in brief["series"]:
        lines.append(
            "| {label} | {area} | {latest:,} | {change} | {pct} | {avg} | {alert} |".format(
                label=record["label"],
                area=record["area"],
                latest=record["latest_value"],
                change=format_metric(record["weekly_change"]),
                pct=format_metric(record["weekly_percentage_change"], "%"),
                avg=format_metric(record["versus_window_average"]),
                alert="; ".join(record["alert_reasons"]) if record["alert"] else "-",
            )
        )
    lines.extend(["", "## Provenance"])
    for record in brief["series"]:
        lines.append(f"- `{record['series_id']}` — {record['source_url']}")
    lines.append("")
    return "\n".join(lines)


def html_document(brief: dict[str, Any]) -> str:
    rows = []
    for record in brief["series"]:
        rows.append(
            "<tr><td>{}</td><td>{}</td><td>{:,}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html.escape(record["label"]),
                html.escape(record["area"]),
                record["latest_value"],
                html.escape(format_metric(record["weekly_change"])),
                html.escape(format_metric(record["weekly_percentage_change"], "%")),
                html.escape(format_metric(record["versus_window_average"])),
                html.escape("; ".join(record["alert_reasons"]) if record["alert"] else "-"),
            )
        )
    sources = "".join(
        f'<li><code>{html.escape(record["series_id"])}</code> — <a href="{html.escape(record["source_url"], quote=True)}">EIA source</a></li>'
        for record in brief["series"]
    )
    return """<!doctype html>
<html lang="en"><meta charset="utf-8"><title>Weekly Petroleum Stock Brief (sample)</title>
<body><main><h1>Weekly Petroleum Stock Brief (sample)</h1>
<p>Observation period: <code>{period}</code>; EIA release date: <code>{release}</code></p>
<p>{disclaimer}</p>
<table><thead><tr><th>Series</th><th>Area</th><th>Latest</th><th>Weekly change</th><th>Weekly %</th><th>4-week avg diff</th><th>Alert</th></tr></thead>
<tbody>{rows}</tbody></table>
<h2>Provenance</h2><p>Snapshot: <code>{snapshot}</code><br>SHA-256: <code>{sha}</code></p><ul>{sources}</ul>
</main></body></html>
""".format(
        period=html.escape(brief["latest_period"]),
        release=html.escape(brief["release_date"]),
        disclaimer=html.escape(brief["disclaimer"]),
        rows="".join(rows),
        snapshot=html.escape(brief["source_snapshot"]),
        sha=html.escape(brief["source_snapshot_sha256"]),
        sources=sources,
    )


def write_output(output_dir: Path, brief: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "brief.json").write_bytes(canonical_json(brief))
    (output_dir / "brief.md").write_text(markdown_document(brief), encoding="utf-8")
    (output_dir / "brief.html").write_text(html_document(brief), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--watchlist", type=Path, default=DEFAULT_WATCHLIST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    snapshot = load_json(args.snapshot)
    watchlist = load_json(args.watchlist)
    brief = build_brief(args.snapshot, snapshot, watchlist)
    write_output(args.output, brief)
    print(json.dumps({"alerts": len(brief["alerts"]), "series": len(brief["series"]), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
