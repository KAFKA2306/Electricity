import importlib.util
import io
import json
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("update_eia_electricity", ROOT / "scripts" / "update_eia_electricity.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def hourly_series(series_id="EBA.US48-ALL.D.H", days=91):
    start = datetime(2026, 5, 1, tzinfo=timezone.utc)
    return {
        "series_id": series_id,
        "name": "test",
        "units": "megawatthours",
        "f": "H",
        "data": [[(start + timedelta(hours=i)).strftime("%Y%m%dT%H"), "10"] for i in range(days * 24)],
    }


def bulk_zip(*series):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("EBA.txt", "\n".join(json.dumps(item) for item in series) + "\n")
    return output.getvalue()


class FakeSheet:
    title = "Operating"

    def __init__(self):
        self.rows = [
            ("Preliminary inventory", None, None, None, None),
            ("Plant ID", "Generator ID", "Nameplate Capacity (MW)", "Net Summer Capacity (MW)", "Technology"),
            (1, "A", 10, 9, "Solar Photovoltaic"),
        ]

    def iter_rows(self, min_row=1, values_only=True):
        return iter(self.rows[min_row - 1 :])


class EiaElectricityViewsTest(unittest.TestCase):
    def test_bulk_discovers_totals_fuels_and_interchange(self):
        series = [
            hourly_series(),
            hourly_series("EBA.US48-ALL.NG.H"),
            hourly_series("EBA.US48-ALL.TI.H"),
            *[hourly_series(f"EBA.US48-ALL.NG.{code}.H") for code in ("COL", "NG", "NUC", "SUN", "WND")],
            hourly_series("EBA.TEST.EXTRA.H"),
        ]
        totals, fuels, interchange = MODULE.read_us48_bulk(bulk_zip(*series))
        self.assertEqual(set(totals), set(MODULE.TOTAL_SERIES.values()))
        self.assertEqual(set(fuels), {"COL", "NG", "NUC", "SUN", "WND"})
        self.assertIn("EBA.US48-ALL.TI.H", interchange)

    def test_hourly_actual_is_aggregated_to_ninety_plus_utc_days(self):
        rows = MODULE.daily_actual(hourly_series(), days=91)
        self.assertEqual(len(rows), 91)
        self.assertEqual(rows[0]["value"], 240)
        self.assertEqual(rows[0]["hour_count"], 24)

    def test_current_and_legacy_hour_formats_are_accepted(self):
        self.assertEqual(MODULE.parse_hour("20260817T20"), MODULE.parse_hour("20260817T20Z"))

    def test_short_history_fails_closed(self):
        with self.assertRaisesRegex(ValueError, ">=90"):
            MODULE.daily_actual(hourly_series(days=89), days=120)

    def test_weekly_aggregate_keeps_day_count(self):
        rows = MODULE.daily_actual(hourly_series(), days=91)
        weeks = MODULE.weekly(rows)
        self.assertEqual(sum(row["day_count"] for row in weeks), 91)
        self.assertTrue(all(row["value"] > 0 for row in weeks))

    def test_latest_860m_link_is_discovered_from_official_index(self):
        html = b'<a href="/electricity/data/eia860m/xls/june_generator2026.xlsx">XLS</a>'
        self.assertEqual(MODULE.latest_eia860m_url(html), "https://www.eia.gov/electricity/data/eia860m/xls/june_generator2026.xlsx")

    def test_worksheet_header_is_discovered_without_fixed_row_number(self):
        records = MODULE.worksheet_records(FakeSheet())
        self.assertEqual(records[0]["Generator ID"], "A")
        self.assertEqual(records[0]["Net Summer Capacity (MW)"], 9)

    def test_evidence_identity_ignores_retrieval_time(self):
        payload = {"retrieved_at": "2026-08-18T00:00:00Z", "views": {"a": 1}}
        first = MODULE.evidence_name(payload)
        payload["retrieved_at"] = "2026-08-19T00:00:00Z"
        self.assertEqual(first, MODULE.evidence_name(payload))


if __name__ == "__main__":
    unittest.main()
