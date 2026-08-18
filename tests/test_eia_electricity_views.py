import importlib.util
import io
import json
import tempfile
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
    def test_bulk_extracts_only_required_series(self):
        demand = hourly_series()
        generation = hourly_series("EBA.US48-ALL.NG.H")
        extra = hourly_series("EBA.TEST.EXTRA.H")
        found = MODULE.read_bulk_series(bulk_zip(extra, demand, generation), set(MODULE.SERIES.values()))
        self.assertEqual(set(found), set(MODULE.SERIES.values()))

    def test_hourly_actual_is_aggregated_to_ninety_plus_utc_days(self):
        rows = MODULE.daily_actual(hourly_series(), days=91)
        self.assertEqual(len(rows), 91)
        self.assertEqual(rows[0]["value"], 240)
        self.assertEqual(rows[0]["hour_count"], 24)

    def test_short_history_fails_closed(self):
        with self.assertRaisesRegex(ValueError, ">=90"):
            MODULE.daily_actual(hourly_series(days=89), days=120)

    def test_latest_860m_link_is_discovered_from_official_index(self):
        html = b'<a href="/electricity/data/eia860m/xls/june_generator2026.xlsx">XLS</a>'
        self.assertEqual(
            MODULE.latest_eia860m_url(html),
            "https://www.eia.gov/electricity/data/eia860m/xls/june_generator2026.xlsx",
        )

    def test_worksheet_header_is_discovered_without_fixed_row_number(self):
        records = MODULE.worksheet_records(FakeSheet())
        self.assertEqual(records[0]["Generator ID"], "A")
        self.assertEqual(records[0]["Net Summer Capacity (MW)"], 9)

    def test_evidence_identity_ignores_retrieval_time(self):
        payload = {"retrieved_at": "2026-08-18T00:00:00Z", "actual": {"a": 1}}
        first = MODULE.evidence_name(payload)
        payload["retrieved_at"] = "2026-08-19T00:00:00Z"
        self.assertEqual(first, MODULE.evidence_name(payload))


if __name__ == "__main__":
    unittest.main()
