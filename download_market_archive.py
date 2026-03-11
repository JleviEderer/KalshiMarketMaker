from __future__ import annotations

import argparse
import os
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from http_utils import build_retry_session

EARLIEST_ARCHIVE_DATE = date.fromisoformat("2021-06-30")
DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_OUTPUT_PATH = "kalshi_all_markets_archive.csv"
PUBLIC_ARCHIVE_URL_TEMPLATE = os.getenv(
    "KALSHI_PUBLIC_ARCHIVE_URL_TEMPLATE",
    "https://kalshi-public-docs.s3.amazonaws.com/reporting/market_data_{day}.json",
)


def resolve_date_window(start_date: str | None = None, end_date: str | None = None) -> tuple[date, date]:
    end = pd.to_datetime(end_date).date() if end_date else date.today() - timedelta(days=1)
    if start_date:
        start = pd.to_datetime(start_date).date()
    else:
        start = end - timedelta(days=DEFAULT_LOOKBACK_DAYS - 1)
    if end < start:
        raise ValueError("end_date must be on or after start_date")
    if start < EARLIEST_ARCHIVE_DATE:
        raise ValueError(f"start_date must be on or after {EARLIEST_ARCHIVE_DATE.isoformat()}")
    if end < EARLIEST_ARCHIVE_DATE:
        raise ValueError(f"end_date must be on or after {EARLIEST_ARCHIVE_DATE.isoformat()}")
    return start, end


def build_date_range(start_date: str | None = None, end_date: str | None = None) -> list[str]:
    start, end = resolve_date_window(start_date, end_date)
    return pd.date_range(start, end).strftime("%Y-%m-%d").tolist()


def fetch_market_file(day_str: str, timeout: int = 30, session: requests.Session | None = None) -> pd.DataFrame:
    client = session or build_retry_session()
    response = client.get(PUBLIC_ARCHIVE_URL_TEMPLATE.format(day=day_str), timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if not payload:
        return pd.DataFrame()
    return pd.DataFrame(payload)


def download_market_archive(
    start_date: str | None = None,
    end_date: str | None = None,
    output_path: str = DEFAULT_OUTPUT_PATH,
    allow_incomplete_overwrite: bool = False,
    existing_target_exists: bool = False,
) -> dict[str, Any]:
    resolved_start, resolved_end = resolve_date_window(start_date, end_date)
    date_range = pd.date_range(resolved_start, resolved_end).strftime("%Y-%m-%d").tolist()
    frames: list[pd.DataFrame] = []
    downloaded_days = 0
    missing_days: list[str] = []
    session = build_retry_session()

    for day_str in date_range:
        try:
            frame = fetch_market_file(day_str, session=session)
            downloaded_days += 1
            if frame.empty:
                continue
            frames.append(frame)
        except requests.HTTPError:
            missing_days.append(day_str)
            continue
        except ValueError:
            missing_days.append(day_str)
            continue

    if not frames:
        raise RuntimeError("No archive data was downloaded for the requested date range")

    archive = pd.concat(frames, ignore_index=True)
    target_path = Path(output_path).expanduser()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    complete_window = downloaded_days == len(date_range) and not missing_days
    if existing_target_exists and not complete_window and not allow_incomplete_overwrite:
        raise RuntimeError(
            "Refusing to overwrite an existing archive with an incomplete download. "
            "Pass allow_incomplete_overwrite=true to replace it anyway."
        )

    fd, temp_name = tempfile.mkstemp(prefix=f"{target_path.stem}-", suffix=".tmp", dir=target_path.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        archive.to_csv(temp_path, index=False, encoding="utf-8")
        os.replace(temp_path, target_path)
    finally:
        temp_path.unlink(missing_ok=True)

    return {
        "output_path": str(target_path.resolve()),
        "rows": int(len(archive)),
        "days_requested": len(date_range),
        "days_downloaded": downloaded_days,
        "complete_window": complete_window,
        "missing_days": missing_days,
        "start_date": resolved_start.isoformat(),
        "end_date": resolved_end.isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Kalshi public market archive data")
    parser.add_argument("--start-date", default=None, help="Inclusive start date in YYYY-MM-DD format")
    parser.add_argument("--end-date", default=None, help="Inclusive end date in YYYY-MM-DD format")
    parser.add_argument("--output-path", default=DEFAULT_OUTPUT_PATH, help="Where to write the consolidated CSV")
    args = parser.parse_args()

    summary = download_market_archive(
        start_date=args.start_date,
        end_date=args.end_date,
        output_path=args.output_path,
    )
    print(summary)


if __name__ == "__main__":
    main()
