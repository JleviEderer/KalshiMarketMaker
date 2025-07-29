import itertools
from datetime import datetime, timedelta
import pandas as pd
import logging
import sys

from backtest_config import BacktestConfig
from backtest_engine import KalshiBacktester

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    print("🚀 STARTING AUTOMATED GRID SEARCH")
    print("=" * 60)

    print("DEBUG: Script started.")

    # --- 1. DEFINE THE PARAMETERS YOU WANT TO TEST ---
    search_space = {
        'sma_window': [3, 8],
        'min_spread': [0.03, 0.07],
        'gamma': [0.05, 0.15],
        'sigma': [0.01, 0.05],
        'k': [1.0, 2.0],
        'inventory_skew_factor': [0.001, 0.05]
    }
    print(f"DEBUG: search_space is populated with {len(search_space)} keys.")

    # --- 2. MANUALLY SELECT A FEW MARKETS FOR THE TEST ---
    target_markets = [
        {'ticker': 'KXCPI-25JUN-T0.2', 'close_date': '2025-07-15'},
        {'ticker': 'KXCPIYOY-25JUN-T2.5', 'close_date': '2025-07-15'},
        {'ticker': 'KXCPI-25JUN-T0.3', 'close_date': '2025-07-15'}
    ]
    print(f"DEBUG: target_markets is populated with {len(target_markets)} markets.")

    # --- 3. SETUP THE BACKTESTER ---
    print("DEBUG: Initializing backtester...")
    backtester = KalshiBacktester(BacktestConfig())
    print("DEBUG: Backtester initialized.")

    # Generate all parameter combinations
    print("DEBUG: Generating parameter combinations...")
    keys, values = zip(*search_space.items())
    param_combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
    print(f"DEBUG: Generated {len(param_combinations)} parameter combinations.")

    total_runs = len(target_markets) * len(param_combinations)
    print(f"Total backtest runs to execute: {total_runs}")
    run_count = 0

    # --- 4. EXECUTE THE GRID SEARCH LOOP ---
    print("DEBUG: Entering main loops...")
    for market_info in target_markets:
        print(f"DEBUG: --- Top of market loop for {market_info['ticker']} ---")
        for params in param_combinations:
            print(f"DEBUG: --- Top of params loop for {params} ---")
            run_count += 1
            print("\n" + "-"*80)
            print(f"Executing run {run_count} of {total_runs}...")
            print(f"Market: {market_info['ticker']}, Params: {params}")
            print("-"*80)

            try:
                config = BacktestConfig(
                    sma_window=params['sma_window'],
                    min_spread=params['min_spread'],
                    gamma=params['gamma'],
                    sigma=params['sigma'],
                    k=params['k'],
                    inventory_skew_factor=params['inventory_skew_factor']
                )
                backtester.config = config

                event_date = datetime.strptime(market_info['close_date'], "%Y-%m-%d").date()
                if "CPI" in market_info['ticker'].upper():
                    event_time = datetime.combine(event_date, datetime.min.time()).replace(hour=12, minute=30)
                else: 
                    event_time = datetime.combine(event_date, datetime.min.time()).replace(hour=19, minute=0)

                end_time = event_time
                start_time = end_time - timedelta(hours=4)

                # Run the backtest and get the results
                results = backtester.run_backtest(market_info['ticker'], start_date=start_time, end_date=end_time)

                # Now, explicitly log the results
                backtester.log_results_to_csv(results, market_info['ticker'], start_date=start_time, end_date=end_time)

            except Exception as e:
                print(f"❌ Run failed for Market: {market_info['ticker']} with Params: {params}. Error: {e}")

    print("\n" + "=" * 60)
    print("✅ GRID SEARCH COMPLETE")
    print(f"Results have been saved to backtest_results_log.csv")
    print("=" * 60)