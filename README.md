# Kalshi Research MCP

Local MCP server for Kalshi historical market discovery and backtesting.

This is meant to be installed locally and connected to an MCP client such as Claude Code or Codex.

## What You Get

After install, the MCP exposes these tools:

- `server_info`
- `download_archive`
- `search_settled_markets`
- `run_backtest`

That lets Claude Code or Codex help with things like:

- downloading Kalshi public archive data
- finding old settled markets by keyword
- running backtests on specific market windows

## Fastest Install

From a local clone:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install the package:

```bash
pip install .
```

Or install directly from GitHub:

```bash
pip install "git+https://github.com/JleviEderer/KalshiMarketMaker.git@main"
```

The installed command is:

```bash
kalshi-research-mcp
```

## Required Environment Variables

Set the public Kalshi market-data host:

Windows:

```bash
set KALSHI_MARKET_DATA_BASE_URL=https://api.elections.kalshi.com/trade-api/v2
set KALSHI_ARCHIVE_PATH=C:\path\to\KalshiData\kalshi_all_markets_archive.csv
```

macOS/Linux:

```bash
export KALSHI_MARKET_DATA_BASE_URL=https://api.elections.kalshi.com/trade-api/v2
export KALSHI_ARCHIVE_PATH=/path/to/KalshiData/kalshi_all_markets_archive.csv
```

`KALSHI_ARCHIVE_PATH` is the local archive file this MCP will manage.

## Claude Code Setup

Add this MCP server to your Claude Code config:

```json
{
  "mcpServers": {
    "kalshi-research": {
      "command": "kalshi-research-mcp",
      "env": {
        "KALSHI_MARKET_DATA_BASE_URL": "https://api.elections.kalshi.com/trade-api/v2",
        "KALSHI_ARCHIVE_PATH": "C:\\path\\to\\KalshiData\\kalshi_all_markets_archive.csv"
      }
    }
  }
}
```

Once added, Claude Code can call the Kalshi research tools directly.

## Codex Setup

If your Codex client supports MCP config, use the same command and env values:

- command: `kalshi-research-mcp`
- env:
  - `KALSHI_MARKET_DATA_BASE_URL=https://api.elections.kalshi.com/trade-api/v2`
  - `KALSHI_ARCHIVE_PATH=...your local archive path...`

If you use the Codex CLI, a typical registration command is:

```bash
codex mcp add kalshi-research --command kalshi-research-mcp
```

## What To Ask After Install

Examples:

1. "Use `download_archive` to pull the last 7 completed days of Kalshi archive data."
2. "Search settled Kalshi markets for CPI."
3. "Run a backtest on market `...` from `...` to `...`."
4. "Find settled Fed markets, then help me choose one to backtest."

## Tool Summary

### `download_archive`

Downloads public Kalshi archive data to your local archive path.

Defaults:

- if no dates are passed, it downloads the last 7 completed days

Important behavior:

- writes are limited to the configured archive directory
- archive files must be `.csv`
- existing files require `allow_overwrite=true`
- incomplete refreshes require `allow_incomplete_overwrite=true` before replacing an existing archive
- responses include `complete_window` and `missing_days`

### `search_settled_markets`

Searches the local archive CSV for settled markets matching a keyword.

Important behavior:

- `archive_path` is limited to the configured archive directory
- `archive_path` must point to a `.csv`

### `run_backtest`

Runs an Avellaneda-style backtest over a historical Kalshi market window.

Typical inputs:

- `market_ticker`
- `start_date`
- `end_date`
- `series_ticker`
- strategy settings such as `gamma`, `k`, `sigma`, `max_position`, and `order_expiration`

## Who This Is For

This is useful if you want Claude Code or Codex to help with:

- Kalshi historical market research
- market selection
- archive-driven exploration
- basic backtesting loops while building your own market-making or research workflow

## Local Development

The public path is `pip install .` plus `kalshi-research-mcp`.

If you are developing locally from source instead:

```bash
pip install -r requirements.txt
python server.py
```

Legacy/manual-trading extras live under [`legacy/`](legacy/README.md):

```bash
pip install ".[legacy]"
```

Legacy entrypoints:

```bash
python legacy/test_auth.py
python legacy/runner.py --config legacy/config.yaml --dry-run
```

## Local Validation

Run tests:

```bash
python -m unittest discover -s tests -v
```

Build the package:

```bash
python -m build
```

## Legacy Trading Files

Older live/demo trading scripts are kept under [`legacy/`](legacy/README.md).
`mm.py` stays at the repo root only because the backtester still imports its
shared strategy primitives.

If you are here to use the MCP, the public entrypoint is `kalshi-research-mcp`.
