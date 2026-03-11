# Kalshi Research MCP

Local MCP server for Kalshi historical market discovery and backtesting.

Install it locally, connect it to Claude Code or Codex, and use the MCP tools
through your client.

## Quickstart

Local clone:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install .
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install .
```

Or install directly from GitHub:

```bash
pip install "git+https://github.com/JleviEderer/KalshiMarketMaker.git@main"
```

That gives you:

- command: `kalshi-research-mcp`
- tools: `server_info`, `download_archive`, `search_settled_markets`, `run_backtest`

Set the required environment variables:

Windows `cmd.exe`:

```bash
set KALSHI_MARKET_DATA_BASE_URL=https://api.elections.kalshi.com/trade-api/v2
set KALSHI_ARCHIVE_PATH=C:\path\to\KalshiData\kalshi_all_markets_archive.csv
```

macOS/Linux:

```bash
export KALSHI_MARKET_DATA_BASE_URL=https://api.elections.kalshi.com/trade-api/v2
export KALSHI_ARCHIVE_PATH=/path/to/KalshiData/kalshi_all_markets_archive.csv
```

`KALSHI_ARCHIVE_PATH` is the local archive CSV this MCP will manage.

## Claude Code

If your Claude Code client uses JSON MCP config, add:

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

## Codex

Codex CLI supports a direct one-liner:

```bash
codex mcp add kalshi-research --env KALSHI_MARKET_DATA_BASE_URL=https://api.elections.kalshi.com/trade-api/v2 --env KALSHI_ARCHIVE_PATH=/path/to/KalshiData/kalshi_all_markets_archive.csv -- kalshi-research-mcp
```

If you configure Codex another way, use the same command and env values.

## Tool Summary

- `server_info`: describes server defaults and archive boundaries
- `download_archive`: downloads public Kalshi archive data to your local archive CSV
- `search_settled_markets`: searches the local archive for settled markets by keyword
- `run_backtest`: runs an Avellaneda-style backtest on a historical market window

Archive safety rules:

- archive reads and writes stay within the configured archive directory
- archive files must be `.csv`
- overwriting existing archives requires `allow_overwrite=true`
- incomplete refreshes require `allow_incomplete_overwrite=true`

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

## Local Validation

Run tests:

```bash
python -m unittest discover -s tests -v
```

Build the package:

```bash
python -m build
```

## Legacy

Older live/demo trading and research scripts are kept under [`legacy/`](legacy/README.md).
`mm.py` stays at the repo root only because the backtester still imports its
shared strategy primitives.

If you are here to use the MCP, the public entrypoint is `kalshi-research-mcp`.
