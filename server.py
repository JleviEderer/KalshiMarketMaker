from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from backtest_config import BacktestConfig
from backtest_engine import KalshiBacktester
from download_market_archive import DEFAULT_OUTPUT_PATH, download_market_archive

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

DEFAULT_ARCHIVE_PATH = Path(os.getenv("KALSHI_ARCHIVE_PATH", DEFAULT_OUTPUT_PATH))
mcp = FastMCP("Kalshi Research", json_response=True)


def _resolve_archive_path(archive_path: str | None) -> Path:
    return Path(archive_path) if archive_path else DEFAULT_ARCHIVE_PATH


def _parse_iso8601(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _to_utc_iso8601(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _serialize_trade(trade: Any) -> dict[str, Any]:
    return {
        "timestamp": _to_utc_iso8601(trade.timestamp),
        "action": trade.action,
        "side": trade.side,
        "price": trade.price,
        "quantity": trade.quantity,
        "order_id": trade.order_id,
    }


@mcp.tool()
def server_info() -> dict[str, Any]:
    """Describe the MCP server surface and defaults."""
    return {
        "server": "kalshi-research-mcp",
        "focus": "historical market discovery, archive download, and backtesting",
        "default_archive_path": str(DEFAULT_ARCHIVE_PATH),
        "tools": [
            "server_info",
            "download_archive",
            "search_settled_markets",
            "run_backtest",
        ],
    }


@mcp.tool()
def download_archive(
    start_date: str = "2021-06-30",
    end_date: str = "",
    output_path: str = "",
) -> dict[str, Any]:
    """Download the public Kalshi archive CSV used for market discovery."""
    summary = download_market_archive(
        start_date=start_date,
        end_date=end_date or None,
        output_path=output_path or str(DEFAULT_ARCHIVE_PATH),
    )
    return summary


@mcp.tool()
def search_settled_markets(
    search_term: str,
    limit: int = 20,
    archive_path: str = "",
) -> list[dict[str, Any]]:
    """Search the local archive CSV for settled markets matching a keyword."""
    path = _resolve_archive_path(archive_path or None)
    if not path.exists():
        raise FileNotFoundError(f"Archive not found at {path}. Run download_archive first.")

    backtester = KalshiBacktester(BacktestConfig())
    matches = backtester.find_settled_markets(str(path), search_term=search_term)
    matches.sort(key=lambda item: item.get("close_time") or "", reverse=True)
    return matches[: max(1, min(limit, 100))]


@mcp.tool()
def run_backtest(
    market_ticker: str,
    start_date: str,
    end_date: str,
    series_ticker: str = "",
    initial_capital: float = 1000.0,
    max_position: int = 5,
    transaction_cost: float = 1.0,
    gamma: float = 0.1,
    k: float = 1.5,
    sigma: float = 0.001,
    horizon_seconds: float = 14_400.0,
    order_expiration: int = 3600,
    min_spread: float = 0.02,
    position_limit_buffer: float = 0.1,
    inventory_skew_factor: float = 0.001,
    dt: float = 2.0,
    period_interval: int = 1,
) -> dict[str, Any]:
    """Run an Avellaneda-style backtest over a historical Kalshi market window."""
    config = BacktestConfig(
        initial_capital=initial_capital,
        max_position=max_position,
        transaction_cost=transaction_cost,
        gamma=gamma,
        k=k,
        sigma=sigma,
        T=horizon_seconds,
        order_expiration=order_expiration,
        min_spread=min_spread,
        position_limit_buffer=position_limit_buffer,
        inventory_skew_factor=inventory_skew_factor,
        dt=dt,
    )
    backtester = KalshiBacktester(config)
    results = backtester.run_backtest(
        market_ticker=market_ticker,
        start_date=_parse_iso8601(start_date),
        end_date=_parse_iso8601(end_date),
        series_ticker=series_ticker or None,
        period_interval=period_interval,
    )

    return {
        "market_ticker": market_ticker,
        "series_ticker": results.get("series_ticker") or series_ticker or None,
        "start_date": start_date,
        "end_date": end_date,
        "candlestick_source": results.get("candlestick_source"),
        "cutoff_ts": results.get("cutoff_ts"),
        "data_points": len(results["timestamps"]),
        "total_trades": results["total_trades"],
        "final_pnl": results["final_pnl"],
        "report": backtester.generate_report(results, market_ticker),
        "sample_trades": [_serialize_trade(trade) for trade in results["trades"][:10]],
    }


if __name__ == "__main__":
    mcp.run()
