import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("update_eia_electricity", ROOT / "scripts" / "update_eia_electricity.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def rto_payload(type_code="D", days=91):
    data = [
        {
            "period": f"2026-{5 + (i // 28):02d}-{1 + (i % 28):02d}",
            "respondent": "US48",
            "type": type_code,
            "value": str(500000 + i),
        }
        for i in range(days)
    ]
    return {
        "publisher": "U.S. Energy Information Administration",
        "route": MODULE.RTO_ROUTE,
        "frequency": "daily",
        "retrieved_at": "2026-08-18T00:00:00+00:00",
        "source_url": "https://api.eia.gov/v2/example?api_key=REDACTED",
        "raw_sha256": "a" * 64,
        "data": data,
    }


class EiaElectricityViewsTest(unittest.TestCase):
    def test_rto_view_requires_ninety_days_and_keeps_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demand.json"
            path.write_text(json.dumps(rto_payload()), encoding="utf-8")
            view = MODULE.rto_view("demand", rto_payload(), path)
        self.assertGreaterEqual(view["period_count"], 90)
        self.assertEqual(view["geography"]["id"], "US48")
        self.assertEqual(view["measure"], {"id": "value", "unit": "megawatthours", "kind": "actual"})
        self.assertIn("api_key=REDACTED", view["source_url"])
        self.assertEqual(len(view["source_snapshot_sha256"]), 64)

    def test_demand_rejects_forecast_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "forecast.json"
            payload = rto_payload("DF")
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "forecast/interchange"):
                MODULE.rto_view("demand", payload, path)

    def test_rto_view_rejects_short_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "short.json"
            payload = rto_payload(days=89)
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, ">=90"):
                MODULE.rto_view("demand", payload, path)

    def test_capacity_view_sums_capacity_fields(self):
        payload = {
            "publisher": "U.S. Energy Information Administration",
            "route": MODULE.CAPACITY_ROUTE,
            "frequency": "monthly",
            "retrieved_at": "2026-08-18T00:00:00+00:00",
            "source_url": "https://api.eia.gov/v2/example?api_key=REDACTED",
            "raw_sha256": "b" * 64,
            "data": [
                {"period": "2026-06", "nameplate-capacity-mw": "10.5", "net-summer-capacity-mw": "9.5", "net-winter-capacity-mw": "10"},
                {"period": "2026-06", "nameplate-capacity-mw": "20", "net-summer-capacity-mw": "19", "net-winter-capacity-mw": "19.5"},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capacity.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            view = MODULE.capacity_view(payload, path)
        self.assertEqual(view["period"], "2026-06")
        self.assertEqual(view["generator_row_count"], 2)
        self.assertEqual(view["totals_mw"]["net-summer-capacity-mw"], 28.5)

    def test_snapshot_is_content_addressed_and_not_rewritten(self):
        payload = rto_payload()
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp)
            first = MODULE.persist_snapshot(raw, "demand", payload)
            original = first.read_bytes()
            payload["retrieved_at"] = "2026-08-19T00:00:00+00:00"
            second = MODULE.persist_snapshot(raw, "demand", payload)
            self.assertEqual(first, second)
            self.assertEqual(second.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
