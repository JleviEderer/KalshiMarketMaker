# MCP Refactor Plan

## Goal

Turn this repo into a read-focused `kalshi-research-mcp` server for:

- historical market discovery
- public archive download
- historical candlestick-backed backtesting
- compact result summaries for LLM clients

This first pass keeps the existing strategy math and backtest scaffolding, and avoids exposing live order placement as MCP tools.

## V1 File Layout

```text
server.py                    # FastMCP entrypoint
backtest_engine.py           # Programmatic backtest engine
backtest_config.py           # Backtest dataclasses
download_market_archive.py   # Importable archive downloader
mm.py                        # Existing Kalshi client + market-making logic
README.md                    # User-facing setup docs
```

## V1 MCP Tools

`server_info`
- Describes the server, focus, defaults, and exposed tools.

`download_archive`
- Downloads the public Kalshi archive CSV used for offline market discovery.

`search_settled_markets`
- Searches the local archive for settled markets matching a term.

`run_backtest`
- Runs an Avellaneda-style backtest on a historical market window using Kalshi candlesticks.

## Why This Boundary

- It matches the product idea: historical data and backtesting.
- It avoids risky live-trading MCP actions.
- It turns the repo's current scripts into callable server tools instead of interactive-only workflows.

## Next Refactors

1. Split `mm.py` into `kalshi_client.py` and `strategies/avellaneda.py`.
2. Add a dedicated historical-data module for candlesticks, trades, and archive normalization.
3. Convert `backtester.py` from CLI prompts to reusable helper functions.
4. Keep the MCP stdio smoke test green and extend it before adding new network-dependent tools.
5. Add optional tools for historical trades and direct market metadata lookup.

## Run Notes

Install dependencies:

```bash
pip install -r requirements.txt
```

Optional extras for plotting and legacy scripts:

```bash
pip install -r requirements-legacy.txt
```

Run the MCP server directly:

```bash
python server.py
```

Use MCP dev tooling:

```bash
mcp dev server.py
```
