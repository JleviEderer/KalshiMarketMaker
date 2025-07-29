import os
from datetime import datetime, timedelta, date
import matplotlib.pyplot as plt
import numpy as np
import logging

from backtest_config import BacktestConfig
from backtest_engine import KalshiBacktester

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    print("🔍 KALSHI BACKTESTER - OFFLINE DISCOVERY & RESEARCH TOOL")
    print("=" * 60)

    market_data_file = './kalshi_all_markets_archive.parquet'

    if not os.path.exists(market_data_file):
        print(f"❌ Market data file not found: {market_data_file}")
        print("💡 Run download_market_archive.py first.")
        exit()
    else:
        print(f"✅ Found market data file: {market_data_file}")

    backtester = KalshiBacktester(BacktestConfig())

    search_term = input("\n👉 Enter a search term (e.g., FED, CPI): ").strip()

    if search_term:
        settled_markets = backtester.find_settled_markets(market_data_file, search_term=search_term)

        # --- ADD THIS LINE TO SORT THE RESULTS ---
        settled_markets.sort(key=lambda x: x['close_time'], reverse=True)
        
        if not settled_markets:
            print(f"❌ No settled markets found for '{search_term}'.")
            exit()

        print("\n--- Found Settled Markets ---")
        for i, market in enumerate(settled_markets[:20]): # Show top 20
            # NEW: Also print the close_time to give the user the date
            print(f"  {i+1}. {market['ticker']} (Closes on: {market['close_time']})")

        try:
            choice = int(input("\n👉 Enter the number of the market you want to test: "))
            selected_market = settled_markets[choice - 1]
            selected_ticker = selected_market['ticker']

            date_str = input(f"👉 Enter the event date for {selected_ticker} (YYYY-MM-DD): ")
            event_date = datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, IndexError, KeyboardInterrupt):
            print("❌ Invalid input or user cancelled. Exiting.")
            exit()

        print(f"\n🎯 Selected market: {selected_ticker}")

        # Always load the main config from the file
        config = BacktestConfig()
        # Handle event-specific timing without overriding strategy parameters
        if "FED" in selected_ticker.upper():
            event_time = event_date.replace(hour=19, minute=0)
        elif "CPI" in selected_ticker.upper(): # Add this block for CPI
            event_time = event_date.replace(hour=12, minute=30)
        else:
            # Default for other events
            event_time = event_date.replace(hour=12, minute=0)

        start_time, end_time = event_time - timedelta(hours=4), event_time

        print(f"⚙️  Running with preset config. Test window: {start_time} to {end_time} UTC")

        backtester.config = config
        # Pass the new series_ticker to the backtester
        results = backtester.run_backtest(selected_ticker, start_date=start_time, end_date=end_time)

        report = backtester.generate_report(results, selected_ticker, start_date=start_time, end_date=end_time)
        print("\n" + "="*80 + "\n📊 BACKTEST RESULTS\n" + "="*80)
        print(report)

        try:
            plt.figure(figsize=(12, 8))
            plt.subplot(2, 2, 1)
            if results and results['pnl_series']: plt.plot(results['timestamps'], results['pnl_series'])
            plt.title('PnL Over Time')
            plt.ylabel('PnL ($)')
            plt.grid(True, alpha=0.3)

            plt.subplot(2, 2, 2)
            if results and results['position_series']: plt.plot(results['timestamps'], results['position_series'])
            plt.title('Position Over Time')
            plt.ylabel('Contracts')
            plt.grid(True, alpha=0.3)

            plt.tight_layout()
            plt.savefig(f"backtest_{selected_ticker}.png")
            print(f"\n📈 Chart saved to backtest_{selected_ticker}.png")

             # --- ADD THE NEW LOGGER CALL HERE ---
            backtester.log_results_to_csv(results, selected_ticker, start_date=start_time, end_date=end_time)

            if results.get('tradelog_path'):
                print(f"🗂️  Detailed trade log saved to {results['tradelog_path']}")

        except Exception as e:
            print(f"\nCould not generate plots. Error: {e}")
        