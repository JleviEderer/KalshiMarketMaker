# https://kalshi.com/market-data

# Import modules
import json
import requests
import pandas as pd
import numpy as np
import datetime
from datetime import date, timedelta

# Set dates
daybefore = date.today() - timedelta(days=1)
start_date = pd.to_datetime('2021-06-30')
daterange = pd.date_range(start_date, daybefore).strftime('%Y-%m-%d').tolist()

# Create list of dataframes
list_of_dataframes = []

# --- Progress tracking ---
total_days = len(daterange)
print(f"Starting download of {total_days} daily market files...")

# Loop through list of dates
for i, day_str in enumerate(daterange):

    print(f"Fetching data for day {i+1} of {total_days}: {day_str}...")

    # Pull in market data
    base_url = "https://kalshi-public-docs.s3.amazonaws.com/reporting/market_data_"
    end_url = ".json"
    URL = base_url + str(day_str) + end_url

    try:
        response = requests.get(URL)
        response.raise_for_status() # Will raise an exception for bad status codes (like 404)

        # --- CRITICAL FIX: Check if the response is empty ---
        if not response.text:
            print(f"⚠️  Warning: No data for {day_str}, skipping.")
            continue # Skip to the next day

        jsondata = response.json()
        data = json.dumps(jsondata)

        # Convert JSON to dataframe
        df = pd.DataFrame(eval(data))

        # Append to list of dataframes
        if not df.empty:
            list_of_dataframes.append(df)

    except requests.exceptions.HTTPError as http_err:
        print(f"⚠️  Warning: HTTP error for {day_str}: {http_err}. Skipping.")
    except json.JSONDecodeError:
        print(f"⚠️  Warning: Could not decode JSON for {day_str}. The file is likely empty. Skipping.")
    except Exception as e:
        print(f"⚠️  An unexpected error occurred for {day_str}: {e}. Skipping.")

print("\nDownload complete. Consolidating data into a single CSV file...")

# Concatenate list of dataframes into df_all
if list_of_dataframes:
    df_all = pd.concat(list_of_dataframes)

    # Reset index
    df_all.reset_index(level=0, inplace=True, drop=True)

    # Write out to local directory
    output_filename = './kalshi_all_markets_archive.csv'
    df_all.to_csv(output_filename, sep=',', encoding='utf-8', header='true')

    print(f"\n✅ Success! All market data saved to: {output_filename}")
else:
    print("\n❌ No data was downloaded. The output file was not created.")