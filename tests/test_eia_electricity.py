import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "collect_eia_electricity", ROOT / "scripts" / "collect_eia_electricity.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def response(rows, total=3):
    return json.dumps(
        {
            "apiVersion": "2.1.12",
            "response": {"total": total, "warnings": [], "data": rows},
        }
    ).encode()


class EiaElectricityCollectorTest(unittest.TestCase):
    def test_collect_paginates_and_redacts_api_key(self):
        pages = [
            response([{"period": "2026-08-18T00", "value": 1}, {"period": "2026-08-17T23", "value": 2}]),
            response([{"period": "2026-08-17T22", "value": 3}]),
        ]
        with patch.dict(os.environ, {"EIA_API_KEY": "secret-key"}), patch.object(
            MODULE, "fetch", side_effect=pages
        ) as mocked_fetch:
            result = MODULE.collect(
                "electricity/rto/region-data",
                ["value"],
                "hourly",
                "2026-05-01T00",
                "2026-08-18T00",
                2,
                [("respondent", "US48"), ("type", "D")],
            )

        self.assertEqual(result["schema_version"], 2)
        self.assertEqual(result["row_count"], 3)
        self.assertEqual(len(result["source_pages"]), 2)
        self.assertEqual([page["offset"] for page in result["source_pages"]], [0, 2])
        self.assertEqual(result["facets"][0], {"name": "respondent", "value": "US48"})
        self.assertNotIn("secret-key", json.dumps(result))
        self.assertIn("api_key=REDACTED", result["source_url"])

        first_url = mocked_fetch.call_args_list[0].args[0]
        second_url = mocked_fetch.call_args_list[1].args[0]
        self.assertIn("offset=0", first_url)
        self.assertIn("offset=2", second_url)
        self.assertIn("facets%5Brespondent%5D%5B%5D=US48", first_url)
        self.assertIn("facets%5Btype%5D%5B%5D=D", first_url)

    def test_page_size_above_eia_limit_is_rejected(self):
        with patch.dict(os.environ, {"EIA_API_KEY": "secret-key"}):
            with self.assertRaisesRegex(ValueError, "between 1 and 5000"):
                MODULE.build_url("electricity/rto/region-data", ["value"], "hourly", None, None, 5001)

    def test_invalid_facet_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "KEY=VALUE"):
            MODULE.parse_facets(["respondent"])


if __name__ == "__main__":
    unittest.main()
