
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Load the backtest results
df = pd.read_csv('backtest_results_log.csv')

print("🔍 BACKTEST RESULTS ANALYSIS")
print("=" * 50)

# Basic statistics
print(f"\nTotal runs: {len(df)}")
print(f"Unique markets: {df['market_ticker'].nunique()}")
print(f"Date range: {df['start_date'].min()} to {df['end_date'].max()}")

# Performance summary
print(f"\nPERFORMANCE SUMMARY")
print(f"Average PnL: ${df['final_pnl'].mean():.2f}")
print(f"Average Return: {df['return_pct'].mean():.2f}%")
print(f"Win Rate: {df['win_rate'].mean():.2%}")
print(f"Average Sharpe: {df['sharpe_ratio'].mean():.2f}")

# Best and worst performing runs
print(f"\nBEST PERFORMING RUN:")
best_run = df.loc[df['final_pnl'].idxmax()]
print(f"Market: {best_run['market_ticker']}")
print(f"PnL: ${best_run['final_pnl']:.2f}")
print(f"Return: {best_run['return_pct']:.2f}%")

print(f"\nWORST PERFORMING RUN:")
worst_run = df.loc[df['final_pnl'].idxmin()]
print(f"Market: {worst_run['market_ticker']}")
print(f"PnL: ${worst_run['final_pnl']:.2f}")
print(f"Return: {worst_run['return_pct']:.2f}%")

# Parameter analysis
print(f"\nPARAMETER ANALYSIS")
numeric_cols = ['sma_window', 'min_spread', 'gamma', 'sigma', 'k', 'inventory_skew_factor']
for col in numeric_cols:
    if col in df.columns:
        corr = df[col].corr(df['final_pnl'])
        print(f"{col} correlation with PnL: {corr:.3f}")
