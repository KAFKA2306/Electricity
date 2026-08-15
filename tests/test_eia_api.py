import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_eia_api", ROOT / "scripts" / "build_eia_api.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class EiaApiTest(unittest.TestCase):
    def test_snapshot_and_generated_files(self):
        snapshot_path, payload = MODULE.load_latest_snapshot()
        files = MODULE.build_files(snapshot_path, payload)
        self.assertEqual(len(payload["series"]), 11)
        self.assertIn("manifest.json", files)
        manifest = json.loads(files["manifest.json"])
        self.assertEqual(manifest["series_count"], 11)
        self.assertEqual(manifest["observation_count"], 99)
        self.assertEqual(manifest["latest_period_confirmed"], "2026-08-07")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            MODULE.write_files(out, files)
            MODULE.check_files(out, files)

    def test_duplicate_series_is_rejected(self):
        _, payload = MODULE.load_latest_snapshot()
        payload["series"].append(dict(payload["series"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate series id"):
            MODULE.validate_snapshot(payload)


if __name__ == "__main__":
    unittest.main()
