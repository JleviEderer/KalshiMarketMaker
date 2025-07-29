# https://kalshi.com/market-data

# Import modules
import json
import requests
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import os
from datetime import date, timedelta

# --- DEFINE A MASTER SCHEMA TO HANDLE HISTORICAL DATA CHANGES ---
# This list includes all columns that have ever appeared in the data files.
MASTER_COLUMNS = [
    'ticker_name', 'open_interest', 'high', 'low', 'daily_volume', 
    'block_volume', 'payout_type', 'report_ticker', 'date', 'status', 
    'old_ticker_name' # This is the column that appears in later data
]

# Set dates
daybefore = date.today() - timedelta(days=1)
start_date = pd.to_datetime('2021-06-30')
daterange = pd.date_range(start_date, daybefore).strftime('%Y-%m-%d').tolist()

# Define the output file
output_filename = './kalshi_all_markets_archive.parquet'

# Clean up old file if it exists, to prevent schema conflicts from previous runs
if os.path.exists(output_filename):
    os.remove(output_filename)
    print("Removed old parquet file to start fresh.")

writer = None

# --- Progress tracking ---
total_days = len(daterange)
print(f"Starting robust, memory-efficient download of {total_days} daily market files...")

# Loop through list of dates
for i, day_str in enumerate(daterange):

    print(f"Fetching and writing data for day {i+1} of {total_days}: {day_str}...")

    base_url = "https://kalshi-public-docs.s3.amazonaws.com/reporting/market_data_"
    end_url = ".json"
    URL = base_url + str(day_str) + end_url

    try:
        response = requests.get(URL)
        response.raise_for_status()

        if not response.text:
            print(f"⚠️  Warning: No data for {day_str}, skipping.")
            continue

        jsondata = response.json()
        df = pd.DataFrame(jsondata)

        if not df.empty:
            # --- ENFORCE THE MASTER SCHEMA ---
            # This adds missing columns (like 'old_ticker_name' for old dates)
            # and ensures column order is always the same.
            df = df.reindex(columns=MASTER_COLUMNS)

            table = pa.Table.from_pandas(df)

            if writer is None:
                writer = pq.ParquetWriter(output_filename, table.schema)

            writer.write_table(table=table)

    except requests.exceptions.HTTPError as http_err:
        print(f"⚠️  Warning: HTTP error for {day_str}: {http_err}. Skipping.")
    except (json.JSONDecodeError, KeyError):
        print(f"⚠️  Warning: Could not decode or parse JSON for {day_str}. Skipping.")
    except Exception as e:
        print(f"⚠️  An unexpected error occurred for {day_str}: {e}. Skipping.")

# --- Final Step: Close the writer ---
if writer:
    writer.close()
    print(f"\n✅ Success! All market data saved to: {output_filename}")
else:
    print("\n❌ No data was downloaded. The output file was not created.")