# Kalshi Market Making Algorithm

An automated market-making system for [Kalshi](https://kalshi.com) prediction markets, built around the **Avellaneda-Stoikov model**. Supports live trading, demo trading, backtesting, and parameter optimization via grid search.

## Overview

This project provides:

- **Avellaneda-Stoikov Market Maker** — Dynamically adjusts bid/ask quotes based on inventory, time to expiry, and volatility.
- **Simple Market Maker** — A fixed-spread alternative for simpler strategies.
- **Parallel Strategy Execution** — Run multiple strategies across different markets simultaneously.
- **Backtesting Engine** — Test strategies against historical Kalshi market data.
- **Grid Search Optimization** — Automatically find optimal parameters across a defined search space.
- **Demo & Live Modes** — Safely test on Kalshi's demo environment before going live, with a safety confirmation gate for live trading.

## Project Structure

```
├── mm.py                        # Core: Trading API client + market maker models
├── runner.py                    # Orchestrator: runs strategies in parallel
├── config.yaml                  # Strategy configurations
├── backtester.py                # Interactive CLI for discovering & backtesting markets
├── backtest_engine.py           # Backtesting engine with mock API
├── backtest_config.py           # Backtest parameter definitions
├── grid_search.py               # Automated parameter optimization
├── download_market_archive.py   # Downloads historical data from Kalshi
├── analyze_results.py           # Analyzes backtest/grid search results
├── test_auth.py                 # API authentication verification
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Container build for deployment
└── fly.toml                     # Fly.io deployment config
```

## Setup

### Prerequisites

- Python 3.10+
- A Kalshi account with API access (demo or live)
- Your Kalshi API key ID and RSA private key

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

The system uses environment variables for API credentials. Set the following for **demo** mode:

```
DEMO_KALSHI_KEY_ID=your_demo_key_id
DEMO_KALSHI_PRIVATE_KEY=your_demo_rsa_private_key
DEMO_KALSHI_BASE_URL=https://demo-api.kalshi.co/trade-api/v2   # optional, falls back to default
```

For **live** mode:

```
LIVE_KALSHI_KEY_ID=your_live_key_id
LIVE_KALSHI_PRIVATE_KEY=your_live_rsa_private_key
LIVE_KALSHI_BASE_URL=https://trading-api.kalshi.com/trade-api/v2   # optional, falls back to default
CONFIRM_LIVE=True
```

> **On Replit:** Add these as Secrets via the Secrets tab (lock icon). They are stored securely and never committed to source control.

### 3. Verify Authentication

```bash
python test_auth.py
```

This will confirm your API keys are valid and you can connect to Kalshi.

## Usage

### Running Strategies

1. Define your strategies in `config.yaml`:

```yaml
strategy_name:
  api:
    market_ticker: KXCPI-25JUN-T0.3
    trade_side: "yes"
  market_maker:
    max_position: 5
    order_expiration: 28800
    gamma: 0.1
    k: 1.5
    sigma: 0.001
    T: 28800
    min_spread: 0.0
    position_limit_buffer: 0.1
    inventory_skew_factor: 0.001
  dt: 2.0
  mode: demo
```

2. Run the strategies:

```bash
python runner.py --config config.yaml
```

All strategies defined in the config file run in parallel using threads.

### Configuration Parameters

| Parameter | Description |
|-----------|-------------|
| `market_ticker` | Kalshi market ticker (e.g., `KXCPI-25JUN-T0.3`) |
| `trade_side` | Side to trade: `"yes"` or `"no"` |
| `max_position` | Maximum number of contracts to hold |
| `order_expiration` | How long orders stay active (seconds) |
| `gamma` | Risk aversion parameter (higher = more conservative) |
| `k` | Order arrival rate parameter |
| `sigma` | Estimated market volatility |
| `T` | Time horizon in seconds |
| `min_spread` | Minimum bid-ask spread |
| `position_limit_buffer` | Buffer before hitting position limits |
| `inventory_skew_factor` | How much inventory affects quote skew |
| `dt` | Update interval in seconds |
| `mode` | `demo` or `live` |

### Backtesting

1. Download historical market data:

```bash
python download_market_archive.py
```

This fetches data from Kalshi's public archive and saves it as `kalshi_all_markets_archive.parquet`.

2. Run the interactive backtester:

```bash
python backtester.py
```

Search for settled markets by keyword (e.g., "CPI", "FED"), select a market, and run a backtest with your strategy parameters.

### Grid Search

Optimize strategy parameters automatically:

```bash
python grid_search.py
```

Results are logged to `backtest_results_log.csv` for analysis.

### Analyzing Results

```bash
python analyze_results.py
```

## Architecture

```
config.yaml
    │
    ▼
runner.py  ──▶  KalshiTradingAPI (mm.py)  ──▶  Kalshi API
    │                    │
    ▼                    ▼
AvellanedaMarketMaker   Authentication (RSA signing)
or SimpleMarketMaker    Order management
    │                    Position tracking
    ▼
Parallel execution
(ThreadPoolExecutor)
```

**Key design decisions:**

- **RSA key authentication** — Uses cryptographic signing for API requests (no email/password).
- **Mode separation** — Demo and live credentials are completely isolated with different environment variable prefixes.
- **Live safety gate** — Live trading requires `CONFIRM_LIVE=True` to prevent accidental execution.
- **Configuration-driven** — All strategy parameters live in `config.yaml`, making it easy to add or modify strategies without code changes.

## Deployment

### Fly.io

1. Install the [flyctl CLI](https://fly.io/docs/hands-on/install-flyctl/)
2. Authenticate: `flyctl auth login`
3. Initialize: `flyctl launch`
4. Set secrets:
   ```bash
   flyctl secrets set LIVE_KALSHI_KEY_ID=your_key_id
   flyctl secrets set LIVE_KALSHI_PRIVATE_KEY=your_private_key
   flyctl secrets set LIVE_KALSHI_BASE_URL=https://trading-api.kalshi.com/trade-api/v2
   flyctl secrets set CONFIRM_LIVE=True
   ```
5. Deploy: `flyctl deploy`

### Replit

Secrets are managed through the Secrets tab. The project runs directly without any additional setup.

## License

MIT License — Copyright (c) 2025 Rodney Lafuente Mercado. See [LICENSE.md](LICENSE.md).
