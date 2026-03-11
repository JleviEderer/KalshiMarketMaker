import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pandas as pd
import requests

import download_market_archive as archive_module
import server


class ServerToolTests(unittest.TestCase):
    def test_download_archive_defaults_to_recent_safe_window(self):
        expected_end = date.today() - timedelta(days=1)
        expected_start = expected_end - timedelta(days=server.DEFAULT_ARCHIVE_LOOKBACK_DAYS - 1)

        with patch.object(server, "download_market_archive", return_value={"ok": True}) as mock_download:
            server.download_archive()

        mock_download.assert_called_once_with(
            start_date=expected_start.isoformat(),
            end_date=expected_end.isoformat(),
            output_path=str(server.DEFAULT_ARCHIVE_PATH.expanduser().resolve()),
            allow_incomplete_overwrite=False,
            existing_target_exists=False,
        )

    def test_download_archive_rejects_path_outside_archive_directory(self):
        with self.assertRaisesRegex(ValueError, "archive path must stay within archive directory"):
            server.download_archive(output_path="../outside.csv")

    def test_download_archive_rejects_non_csv_output_path(self):
        with self.assertRaisesRegex(ValueError, "archive path must end with .csv"):
            server.download_archive(output_path="archive.json")

    def test_download_archive_requires_explicit_overwrite(self):
        temp_root = Path(__file__).resolve().parents[1] / ".tmp-tests" / uuid4().hex
        temp_root.mkdir(parents=True, exist_ok=True)
        archive_path = temp_root / "archive.csv"
        archive_path.write_text("existing", encoding="utf-8")

        try:
            with patch.object(server, "DEFAULT_ARCHIVE_PATH", archive_path):
                with self.assertRaisesRegex(FileExistsError, "allow_overwrite=true"):
                    server.download_archive()
        finally:
            archive_path.unlink(missing_ok=True)
            temp_root.rmdir()

    def test_download_archive_allows_explicit_overwrite(self):
        temp_root = Path(__file__).resolve().parents[1] / ".tmp-tests" / uuid4().hex
        temp_root.mkdir(parents=True, exist_ok=True)
        archive_path = temp_root / "archive.csv"
        archive_path.write_text("existing", encoding="utf-8")

        try:
            with patch.object(server, "DEFAULT_ARCHIVE_PATH", archive_path):
                with patch.object(server, "download_market_archive", return_value={"ok": True}) as mock_download:
                    server.download_archive(allow_overwrite=True)

            mock_download.assert_called_once_with(
                start_date=(date.today() - timedelta(days=server.DEFAULT_ARCHIVE_LOOKBACK_DAYS)).isoformat(),
                end_date=(date.today() - timedelta(days=1)).isoformat(),
                output_path=str(archive_path.resolve()),
                allow_incomplete_overwrite=False,
                existing_target_exists=True,
            )
        finally:
            archive_path.unlink(missing_ok=True)
            temp_root.rmdir()

    def test_download_market_archive_rejects_incomplete_overwrite_of_existing_file(self):
        temp_root = Path(__file__).resolve().parents[1] / ".tmp-tests"
        temp_root.mkdir(exist_ok=True)
        output_path = temp_root / f"archive-{uuid4().hex}.csv"
        output_path.write_text("original archive", encoding="utf-8")
        success_frame = pd.DataFrame([{"ticker_name": "TEST-MKT", "status": "finalized"}])

        try:
            with patch.object(
                archive_module,
                "fetch_market_file",
                side_effect=[success_frame, requests.HTTPError("missing day")],
            ):
                with self.assertRaisesRegex(RuntimeError, "allow_incomplete_overwrite=true"):
                    archive_module.download_market_archive(
                        start_date="2025-03-08",
                        end_date="2025-03-09",
                        output_path=str(output_path),
                        existing_target_exists=True,
                    )

            self.assertEqual("original archive", output_path.read_text(encoding="utf-8"))
        finally:
            output_path.unlink(missing_ok=True)

    def test_download_market_archive_allows_explicit_incomplete_overwrite(self):
        temp_root = Path(__file__).resolve().parents[1] / ".tmp-tests"
        temp_root.mkdir(exist_ok=True)
        output_path = temp_root / f"archive-{uuid4().hex}.csv"
        output_path.write_text("original archive", encoding="utf-8")
        success_frame = pd.DataFrame([{"ticker_name": "TEST-MKT", "status": "finalized"}])

        try:
            with patch.object(
                archive_module,
                "fetch_market_file",
                side_effect=[success_frame, requests.HTTPError("missing day")],
            ):
                summary = archive_module.download_market_archive(
                    start_date="2025-03-08",
                    end_date="2025-03-09",
                    output_path=str(output_path),
                    allow_incomplete_overwrite=True,
                    existing_target_exists=True,
                )

            self.assertFalse(summary["complete_window"])
            self.assertIn("TEST-MKT", output_path.read_text(encoding="utf-8"))
        finally:
            output_path.unlink(missing_ok=True)

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

    def test_search_settled_markets_rejects_path_outside_archive_directory(self):
        with self.assertRaisesRegex(ValueError, "archive path must stay within archive directory"):
            server.search_settled_markets(search_term="GDPW", archive_path="../outside.csv")

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

    def test_download_market_archive_reports_partial_windows(self):
        output_path = (Path(__file__).resolve().parents[1] / ".tmp-tests" / f"archive-{uuid4().hex}.csv").resolve()
        success_frame = pd.DataFrame([{"ticker_name": "TEST-MKT", "status": "finalized"}])

        with patch.object(
            archive_module,
            "fetch_market_file",
            side_effect=[success_frame, requests.HTTPError("missing day")],
        ):
            summary = archive_module.download_market_archive(
                start_date="2025-03-08",
                end_date="2025-03-09",
                output_path=str(output_path),
            )

        self.assertFalse(summary["complete_window"])
        self.assertEqual(["2025-03-09"], summary["missing_days"])
        output_path.unlink(missing_ok=True)

    def test_search_settled_markets_prefers_latest_close_time_per_ticker(self):
        temp_root = Path(__file__).resolve().parents[1] / ".tmp-tests"
        temp_root.mkdir(exist_ok=True)
        csv_path = temp_root / f"archive-{uuid4().hex}.csv"
        csv_path.write_text(
            "ticker_name,status,report_ticker,date\n"
            "GDPW-2023-A2,finalized,GDPW,2025-03-07\n"
            "GDPW-2023-A2,finalized,GDPW,2025-03-08\n",
            encoding="utf-8",
        )

        try:
            matches = server.search_settled_markets(search_term="GDPW", archive_path=str(csv_path))
        finally:
            csv_path.unlink(missing_ok=True)

        self.assertEqual(1, len(matches))
        self.assertEqual("2025-03-08", matches[0]["close_time"])

    def test_search_settled_markets_raises_for_invalid_archive_schema(self):
        temp_root = Path(__file__).resolve().parents[1] / ".tmp-tests"
        temp_root.mkdir(exist_ok=True)
        csv_path = temp_root / f"archive-{uuid4().hex}.csv"
        csv_path.write_text(
            "ticker_name,report_ticker,date\n"
            "GDPW-2023-A2,GDPW,2025-03-08\n",
            encoding="utf-8",
        )

        try:
            with self.assertRaisesRegex(ValueError, "missing required columns: status"):
                server.search_settled_markets(search_term="GDPW", archive_path=str(csv_path))
        finally:
            csv_path.unlink(missing_ok=True)

    def test_search_settled_markets_raises_for_malformed_csv(self):
        temp_root = Path(__file__).resolve().parents[1] / ".tmp-tests"
        temp_root.mkdir(exist_ok=True)
        csv_path = temp_root / f"archive-{uuid4().hex}.csv"
        csv_path.write_text(
            'ticker_name,status,report_ticker,date\n"broken,finalized,GDPW,2025-03-08\n',
            encoding="utf-8",
        )

        try:
            with self.assertRaisesRegex(ValueError, "could not be parsed as CSV"):
                server.search_settled_markets(search_term="GDPW", archive_path=str(csv_path))
        finally:
            csv_path.unlink(missing_ok=True)

    def test_search_settled_markets_raises_for_empty_csv(self):
        temp_root = Path(__file__).resolve().parents[1] / ".tmp-tests"
        temp_root.mkdir(exist_ok=True)
        csv_path = temp_root / f"archive-{uuid4().hex}.csv"
        csv_path.write_text("", encoding="utf-8")

        try:
            with self.assertRaisesRegex(ValueError, "could not be parsed as CSV"):
                server.search_settled_markets(search_term="GDPW", archive_path=str(csv_path))
        finally:
            csv_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
