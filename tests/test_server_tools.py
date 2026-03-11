import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pandas as pd

import download_market_archive as archive_module
import server


class ServerToolTests(unittest.TestCase):
    def test_run_backtest_rejects_inverted_time_window(self):
        with self.assertRaisesRegex(ValueError, "end_date must be later than start_date"):
            server.run_backtest(
                market_ticker="TEST-MKT",
                start_date="2025-03-08T01:00:00Z",
                end_date="2025-03-08T00:00:00Z",
            )

    def test_search_settled_markets_rejects_blank_term(self):
        with self.assertRaisesRegex(ValueError, "search_term is required"):
            server.search_settled_markets(search_term="   ")

    def test_download_market_archive_creates_parent_directory(self):
        temp_root = Path(__file__).resolve().parents[1] / ".tmp-tests"
        temp_root.mkdir(exist_ok=True)
        output_path = temp_root / uuid4().hex / "archive.csv"

        with patch.object(
            archive_module,
            "fetch_market_file",
            return_value=pd.DataFrame([{"ticker_name": "TEST-MKT", "status": "finalized"}]),
        ):
            summary = archive_module.download_market_archive(
                start_date="2025-03-08",
                end_date="2025-03-08",
                output_path=str(output_path),
            )

        self.assertTrue(output_path.exists())
        self.assertEqual(str(output_path.resolve()), summary["output_path"])
        output_path.unlink(missing_ok=True)
        output_path.parent.rmdir()


if __name__ == "__main__":
    unittest.main()
