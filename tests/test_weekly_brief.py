import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_weekly_brief", ROOT / "scripts" / "build_weekly_brief.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class WeeklyBriefTest(unittest.TestCase):
    def setUp(self):
        self.snapshot_path = ROOT / "data" / "official" / "eia-weekly-stocks-2026-08-08.json"
        self.watchlist_path = ROOT / "config" / "watchlists" / "weekly-petroleum-sample.json"
        self.snapshot = MODULE.load_json(self.snapshot_path)
        self.watchlist = MODULE.load_json(self.watchlist_path)

    def test_sample_build_is_traceable_and_deterministic(self):
        first = MODULE.build_brief(self.snapshot_path, self.snapshot, self.watchlist)
        second = MODULE.build_brief(self.snapshot_path, self.snapshot, self.watchlist)
        self.assertEqual(MODULE.canonical_json(first), MODULE.canonical_json(second))
        self.assertEqual(first["latest_period"], "2026-07-17")
        self.assertEqual(first["release_date"], "2026-07-22")
        self.assertEqual(len(first["series"]), 7)
        self.assertEqual(len(first["source_snapshot_sha256"]), 64)
        self.assertTrue(first["source_snapshot"].startswith("data/official/"))
        self.assertTrue(all(item["source_url"].startswith("https://www.eia.gov/") for item in first["series"]))

    def test_known_us_weekly_change(self):
        brief = MODULE.build_brief(self.snapshot_path, self.snapshot, self.watchlist)
        us = next(item for item in brief["series"] if item["series_id"] == "commercial_crude_us")
        self.assertEqual(us["latest_value"], 411675)
        self.assertEqual(us["weekly_change"], {"status": "OK", "value": 2010, "reason": None})
        self.assertEqual(us["weekly_percentage_change"]["status"], "OK")
        self.assertAlmostEqual(us["weekly_percentage_change"]["value"], 0.491, places=3)
        self.assertAlmostEqual(us["versus_window_average"]["value"], 1411.0, places=3)

    def test_zero_denominator_is_not_computable(self):
        snapshot = copy.deepcopy(self.snapshot)
        series = next(item for item in snapshot["series"] if item["id"] == "commercial_crude_us")
        series["observations"][-2]["value"] = 0
        brief = MODULE.build_brief(self.snapshot_path, snapshot, self.watchlist)
        us = next(item for item in brief["series"] if item["series_id"] == "commercial_crude_us")
        self.assertEqual(us["weekly_percentage_change"]["status"], MODULE.NOT_COMPUTABLE)
        self.assertIsNone(us["weekly_percentage_change"]["value"])

    def test_insufficient_window_is_not_computable(self):
        snapshot = copy.deepcopy(self.snapshot)
        series = next(item for item in snapshot["series"] if item["id"] == "commercial_crude_us")
        series["observations"] = series["observations"][-2:]
        brief = MODULE.build_brief(self.snapshot_path, snapshot, self.watchlist)
        us = next(item for item in brief["series"] if item["series_id"] == "commercial_crude_us")
        self.assertEqual(us["window_average"]["status"], MODULE.NOT_COMPUTABLE)
        self.assertEqual(us["versus_window_average"]["status"], MODULE.NOT_COMPUTABLE)

    def test_unknown_series_fails_closed(self):
        watchlist = copy.deepcopy(self.watchlist)
        watchlist["series"][0]["id"] = "unknown_series"
        with self.assertRaisesRegex(ValueError, "not present in snapshot"):
            MODULE.build_brief(self.snapshot_path, self.snapshot, watchlist)

    def test_output_contains_json_markdown_and_html(self):
        brief = MODULE.build_brief(self.snapshot_path, self.snapshot, self.watchlist)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            MODULE.write_output(output, brief)
            self.assertEqual({path.name for path in output.iterdir()}, {"brief.json", "brief.md", "brief.html"})
            machine = json.loads((output / "brief.json").read_text(encoding="utf-8"))
            self.assertEqual(machine["source_snapshot_sha256"], brief["source_snapshot_sha256"])
            self.assertIn("no price forecast", (output / "brief.html").read_text(encoding="utf-8").lower())


if __name__ == "__main__":
    unittest.main()
