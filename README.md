# Kalshi Research MCP

This repo now includes a local MCP server for Kalshi historical data and backtesting.

In simple terms:

- `server.py` is the tool program
- Claude Code or another MCP client can launch it
- the tools let an AI download archive data, search settled markets, and run backtests

This is for research. It is not a live-trading MCP.

## What This Repo Is

The MCP server exposes a small set of read-only tools:

- `server_info`
- `download_archive`
- `search_settled_markets`
- `run_backtest`

The repo still contains older live-trading scripts such as `mm.py` and `runner.py`, but the MCP path is focused on:

- historical market discovery
- public archive download
- historical candlestick research
- backtesting summaries for AI clients

## Plain-English Explanation

If you are not a programmer, the easiest mental model is:

- this repo is a toolbox
- `server.py` is the box that opens the tools
- Claude Code is the app that uses those tools
- MCP is the connection between Claude and the toolbox

After setup, Claude can do things like:

- download Kalshi archive data
- search for old settled markets
- run a backtest on a market window

## What It Is Not

This project is not:

- a public website
- a browser app
- a hosted API service by default
- a live-trading MCP

By default, this is a local MCP server. Someone uses it by cloning the repo, installing dependencies, and adding it to an MCP client such as Claude Code.

## Quick Start

### 1. Create a virtual environment

Using a virtual environment is the safest path, especially on Windows.

```bash
python -m venv .venv
```

Activate it:

```bash
.venv\Scripts\activate
```

### 2. Open a terminal in this folder

```bash
cd KalshiMarketMaker
```

### 3. Install the package

For a local clone:

```bash
pip install .
```

Optional legacy extras:

```bash
pip install ".[legacy]"
```

For a direct GitHub install:

```bash
pip install "git+https://github.com/JleviEderer/KalshiMarketMaker.git@main"
```

### 4. Install MCP runtime dependencies manually if you are not using package install

```bash
pip install -r requirements.txt
```

That installs the MCP server runtime and research/backtest dependencies.

If you also want the older plotting, notebook, or legacy trading scripts:

```bash
pip install -r requirements-legacy.txt
```

### 5. Set the market-data base URL

Use the public Kalshi market-data host for the research MCP:

```bash
set KALSHI_MARKET_DATA_BASE_URL=https://api.elections.kalshi.com/trade-api/v2
```

Optional archive path:

```bash
set KALSHI_ARCHIVE_PATH=.\kalshi_all_markets_archive.csv
```

### 6. Run the MCP server locally

```bash
kalshi-research-mcp
```

That starts the MCP server over `stdio`, which is the normal local setup for Claude Code.

## Dependency Notes

- `requirements.txt` is the publishable MCP-first install path.
- `requirements-legacy.txt` adds optional dependencies used by old plotting or live/demo scripts.
- The original pinned `pandas==2.2.2` install path is not reliable on Windows Python 3.13 because it can fall back to a failing source build. The current version range in `requirements.txt` is chosen to allow binary wheels on modern Python versions.

## Connect It To Claude Code

Add this repo as an MCP server in your Claude Code MCP config:

```json
{
  "mcpServers": {
    "kalshi-research": {
      "command": "python",
      "args": [
        "server.py"
      ],
      "cwd": "C:\\path\\to\\KalshiMarketMaker",
      "env": {
        "KALSHI_MARKET_DATA_BASE_URL": "https://api.elections.kalshi.com/trade-api/v2",
        "KALSHI_ARCHIVE_PATH": "C:\\path\\to\\KalshiMarketMaker\\kalshi_all_markets_archive.csv"
      }
    }
  }
}
```

After that, Claude Code can call the MCP tools directly.

## Connect It To Codex

Codex can also use MCP servers.

The idea is the same:

- Codex launches `server.py`
- the MCP connection gives Codex access to the tools
- you can then ask Codex to use the Kalshi research tools

If your Codex setup supports MCP config directly, use the same values as the Claude Code example above:

- command: `python`
- args: `server.py`
- working folder: this repo
- env:
  - `KALSHI_MARKET_DATA_BASE_URL=https://api.elections.kalshi.com/trade-api/v2`
  - `KALSHI_ARCHIVE_PATH=./kalshi_all_markets_archive.csv`

If you use the Codex CLI, OpenAI also documents MCP commands such as:

```bash
codex mcp list
```

and MCP server registration commands such as:

```bash
codex mcp add kalshi-research --command kalshi-research-mcp
```

The exact Codex config screen or command can vary by client version, but the important point is:

- this repo is not only for Claude Code
- it can also be plugged into Codex as an MCP server

## Example MCP Flow

Typical usage looks like this:

1. Ask Claude to run `download_archive`
2. Ask Claude to run `search_settled_markets` for something like `CPI` or `FED`
3. Pick a market
4. Ask Claude to run `run_backtest`

## Tools

### `server_info`

Shows:

- server name
- default archive path
- available tools

### `download_archive`

Downloads the public daily Kalshi market archive and writes a CSV locally.

Example parameters:

- `start_date`
- `end_date`
- `output_path`

### `search_settled_markets`

Searches the local archive CSV for settled markets matching a term.

Example parameters:

- `search_term`
- `limit`
- `archive_path`

### `run_backtest`

Runs an Avellaneda-style backtest over a historical market window.

Example parameters:

- `market_ticker`
- `start_date`
- `end_date`
- `series_ticker`
- strategy settings like `gamma`, `k`, `sigma`, `max_position`, and `order_expiration`

The MCP response includes routing metadata such as:

- `candlestick_source`
- `cutoff_ts`
- resolved `series_ticker`

## How The Data Routing Works

Kalshi currently has a split between live and historical data.

This MCP server:

- checks the historical cutoff
- fetches market metadata
- uses settlement metadata to decide whether to call the live or historical candlestick endpoint
- resolves `series_ticker` from market or event metadata when needed

That is important because some older settled markets only exist on the historical endpoints.

## Share It With Other People

Yes, you can share the GitHub repo and say you made an MCP server for Kalshi historical data and backtesting.

The accurate way to describe it is:

"I built a local MCP server for Kalshi historical data and backtesting that works with Claude Code and Codex."

That wording is better because:

- it is true
- it tells people what the project actually does
- it does not imply you built a public hosted service

## What Someone Else Has To Do

If another person wants to use it, they need to:

1. clone the repo
2. run `pip install -r requirements.txt`
3. add `server.py` to their MCP client config
4. start using the tools through Claude Code

## Local Testing

Run the unit tests:

```bash
python -m unittest discover -s tests -v
```

Build the package:

```bash
python -m build
```

That suite now includes an MCP stdio integration smoke test that launches `server.py` and exercises:

- `server_info`
- `search_settled_markets`
- `run_backtest`

Check syntax:

```bash
python -m py_compile backtest_engine.py backtest_config.py server.py download_market_archive.py
```

## Important Files

- `server.py`: FastMCP entrypoint and tool definitions
- `backtest_engine.py`: market-data client, routing logic, candlestick normalization, synthetic fills, backtest engine
- `backtest_config.py`: backtest data classes
- `download_market_archive.py`: reusable public archive downloader
- `tests/test_backtest_engine.py`: focused unit tests for routing and normalization
- `tests/test_mcp_server.py`: MCP stdio integration smoke test for the local server
- `requirements.txt`: MCP-first runtime dependencies
- `requirements-legacy.txt`: optional extras for plotting and legacy trading scripts
- `mm.py`: legacy live-trading API client and strategy logic used by the backtester's market-maker model

## Legacy Live-Trading Scripts

The repo still includes older live/demo trading pieces:

- `mm.py`
- `runner.py`
- `config.yaml`

Those are separate from the research MCP path. If you are using this repo as an MCP server, start with `server.py`, not `runner.py`.

## Current Caveats

- This is a local MCP server, not a hosted service.
- The synthetic fill model is a research approximation, not an execution replay.
- The repo still contains legacy live-trading docs and scripts, so be careful to follow the MCP instructions above for research use.
- The canonical install path is now `pip install .` or a GitHub package install, not ad hoc execution from a personal filesystem path.

## License

MIT License. See `LICENSE.md`.
