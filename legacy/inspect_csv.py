"""Legacy helper to inspect a downloaded archive CSV."""

from pathlib import Path
import pandas as pd
from datetime import date, timedelta

from _bootstrap import add_repo_root_to_path

REPO_ROOT = add_repo_root_to_path()

# --- Configuration ---
# This generates the exact filename of your large CSV file.
daybefore = date.today() - timedelta(days=1)
file_path = REPO_ROOT / f'kalshi_all_markets_{str(daybefore)}.csv'
# -------------------

print(f"🔍 Inspecting the first 100 rows of: {file_path}")

try:
    # Read only the first 100 rows to avoid memory issues
    df_head = pd.read_csv(file_path, nrows=100)

    print("\n--- Column Headers ---")
    print(list(df_head.columns))

    print("\n--- First 100 Rows of Data ---")
    print(df_head)

except FileNotFoundError:
    print(f"\n❌ ERROR: The file '{file_path}' was not found.")
    print("Please make sure the data download script has finished successfully.")
except Exception as e:
    print(f"\n❌ An error occurred: {e}")
