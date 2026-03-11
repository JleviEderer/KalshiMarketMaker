"""Legacy parameter sweep script for manual backtest experiments."""

import itertools
import os
from datetime import datetime, timedelta
import pandas as pd
import logging
import sys
from pathlib import Path

from _bootstrap import add_repo_root_to_path

REPO_ROOT = add_repo_root_to_path()
LEGACY_DIR = Path(__file__).resolve().parent
RESULTS_PATH = LEGACY_DIR / "backtest_results_log.csv"

from backtest_config import BacktestConfig
from backtest_engine import KalshiBacktester

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    print("🚀 STARTING AUTOMATED GRID SEARCH")
    print("=" * 60)

    if RESULTS_PATH.exists():
        os.remove(RESULTS_PATH)
        print("🗑️  Cleared old backtest results log file.")
   

    print("DEBUG: Script started.")

    print("DEBUG: Script started.")

    # --- 1. DEFINE THE PARAMETERS YOU WANT TO TEST ---
    # New search space for the Simple Market Maker
    search_space = {
        'fixed_spread': [0.02, 0.04, 0.06],
        'inventory_skew_factor': [0.0, 0.001, 0.01],
        'sma_window': [2, 3, 5]  # We can still test fair value smoothing
    }

    # --- 2. MANUALLY SELECT A FEW MARKETS FOR THE TEST ---
    target_markets = [
        {'ticker': 'KXHIGHLAX-25JUL27-B71.5', 'close_date': '2025-07-27'},
        {'ticker': 'KXHIGHDEN-25JUL27-B97.5', 'close_date': '2025-07-27'},
        {'ticker': 'KXHIGHAUS-25JUL27-B96.5', 'close_date': '2025-07-27'}
    ]

    # --- 3. SETUP THE BACKTESTER ---
    backtester = KalshiBacktester(BacktestConfig())

    # Generate all parameter combinations
    keys, values = zip(*search_space.items())
    param_combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]

    total_runs = len(target_markets) * len(param_combinations)
    print(f"Total backtest runs to execute: {total_runs}")
    run_count = 0

    # --- 4. EXECUTE THE GRID SEARCH LOOP ---
    for market_info in target_markets:
        for params in param_combinations:
            run_count += 1
            print("\n" + "-"*80)
            print(f"Executing run {run_count} of {total_runs}...")
            print(f"Market: {market_info['ticker']}, Params: {params}")
            print("-"*80)

            try:
                # --- THIS IS THE CORRECTED CONFIGURATION ---
                # Create a new config for this specific run
                config = BacktestConfig(
                    strategy='simple', # Explicitly set strategy for the run
                    fixed_spread=params['fixed_spread'],
                    inventory_skew_factor=params['inventory_skew_factor'],
                    sma_window=params['sma_window']
                )
                backtester.config = config

                # Automatically determine the time window
                event_date = datetime.strptime(market_info['close_date'], "%Y-%m-%d").date()
                if "HIGH" in market_info['ticker'].upper(): # Check for weather markets
                    # The event day is the day before the 'close_date'
                    event_day = datetime.strptime(market_info['close_date'], "%Y-%m-%d").date() - timedelta(days=1)
                    start_time = datetime.combine(event_day, datetime.min.time()).replace(hour=10, minute=0) # 10:00 AM EDT
                    end_time = datetime.combine(event_day, datetime.min.time()).replace(hour=23, minute=59) # 11:59 PM EDT

                elif "CPI" in market_info['ticker'].upper():
                    event_time = datetime.combine(event_date, datetime.min.time()).replace(hour=12, minute=30)
                    end_time = event_time
                    start_time = end_time - timedelta(hours=4)
                else: # Default for FED or others
                    event_time = datetime.combine(event_date, datetime.min.time()).replace(hour=19, minute=0)
                    end_time = event_time
                    start_time = end_time - timedelta(hours=4)

                # Run the backtest and log the results
                results = backtester.run_backtest(market_info['ticker'], start_date=start_time, end_date=end_time)
                backtester.log_results_to_csv(results, market_info['ticker'], start_date=start_time, end_date=end_time)

            except Exception as e:
                print(f"❌ Run failed for Market: {market_info['ticker']} with Params: {params}. Error: {e}")

    print("\n" + "=" * 60)
    print("✅ GRID SEARCH COMPLETE")
    print(f"Results have been saved to {RESULTS_PATH}")
    print("=" * 60)
