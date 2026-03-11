from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from backtest_config import BacktestConfig
from backtest_engine import KalshiBacktester
from download_market_archive import DEFAULT_OUTPUT_PATH, download_market_archive

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

DEFAULT_ARCHIVE_PATH = Path(os.getenv("KALSHI_ARCHIVE_PATH", DEFAULT_OUTPUT_PATH))
DEFAULT_ARCHIVE_LOOKBACK_DAYS = 7
mcp = FastMCP("Kalshi Research", json_response=True)


def _resolve_archive_path(archive_path: str | None) -> Path:
    return (Path(archive_path) if archive_path else DEFAULT_ARCHIVE_PATH).expanduser()


def _archive_directory() -> Path:
    return DEFAULT_ARCHIVE_PATH.expanduser().resolve().parent


def _resolve_archive_candidate_path(archive_path: str | None) -> Path:
    archive_dir = _archive_directory()
    raw_path = (archive_path or "").strip()
    if raw_path:
        requested_path = Path(raw_path).expanduser()
        candidate = requested_path if requested_path.is_absolute() else archive_dir / requested_path
    else:
        candidate = DEFAULT_ARCHIVE_PATH.expanduser()

    resolved = candidate.resolve()
    try:
        resolved.relative_to(archive_dir)
    except ValueError as exc:
        raise ValueError(f"archive path must stay within archive directory {archive_dir}") from exc

    _require(resolved.suffix.lower() == ".csv", "archive path must end with .csv")
    return resolved


def _resolve_archive_output_path(output_path: str | None, allow_overwrite: bool) -> Path:
    resolved = _resolve_archive_candidate_path(output_path)
    if resolved.exists() and not allow_overwrite:
        raise FileExistsError(
            f"Archive output already exists at {resolved}. Pass allow_overwrite=true to replace it."
        )
    return resolved


def _resolve_archive_input_path(archive_path: str | None) -> Path:
    return _resolve_archive_candidate_path(archive_path)


def _parse_iso8601(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _server_version() -> str:
    try:
        return version("kalshi-research-mcp")
    except PackageNotFoundError:
        return "0.1.0"


def _default_archive_window() -> tuple[str, str]:
    resolved_end = date.today() - timedelta(days=1)
    resolved_start = resolved_end - timedelta(days=DEFAULT_ARCHIVE_LOOKBACK_DAYS - 1)
    return resolved_start.isoformat(), resolved_end.isoformat()


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
        "version": _server_version(),
        "focus": "historical market discovery, local archive caching, and backtesting",
        "default_archive_path": str(DEFAULT_ARCHIVE_PATH),
        "default_archive_directory": str(_archive_directory()),
        "download_archive_default_window_days": DEFAULT_ARCHIVE_LOOKBACK_DAYS,
        "download_archive_requires_explicit_overwrite": True,
        "download_archive_output_scope": "Paths must stay within the configured archive directory and end with .csv.",
        "search_archive_input_scope": "archive_path must stay within the configured archive directory and end with .csv.",
        "tools": [
            "server_info",
            "download_archive",
            "search_settled_markets",
            "run_backtest",
        ],
    }


@mcp.tool()
def download_archive(
    start_date: str = "",
    end_date: str = "",
    output_path: str = "",
    allow_overwrite: bool = False,
    allow_incomplete_overwrite: bool = False,
) -> dict[str, Any]:
    """Download the public Kalshi archive CSV used for market discovery."""
    resolved_start_date = start_date.strip() or None
    resolved_end_date = end_date.strip() or None
    if resolved_start_date is None and resolved_end_date is None:
        resolved_start_date, resolved_end_date = _default_archive_window()
    resolved_output_path = _resolve_archive_output_path(output_path, allow_overwrite=allow_overwrite)

    summary = download_market_archive(
        start_date=resolved_start_date,
        end_date=resolved_end_date,
        output_path=str(resolved_output_path),
        allow_incomplete_overwrite=allow_incomplete_overwrite,
        existing_target_exists=resolved_output_path.exists(),
    )
    return summary


@mcp.tool()
def search_settled_markets(
    search_term: str,
    limit: int = 20,
    archive_path: str = "",
) -> list[dict[str, Any]]:
    """Search the local archive CSV for settled markets matching a keyword."""
    search_term = search_term.strip()
    _require(bool(search_term), "search_term is required")
    _require(limit >= 1, "limit must be at least 1")
    path = _resolve_archive_input_path(archive_path or None)
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
    market_ticker = market_ticker.strip()
    _require(bool(market_ticker), "market_ticker is required")
    _require(initial_capital > 0, "initial_capital must be greater than 0")
    _require(max_position > 0, "max_position must be greater than 0")
    _require(transaction_cost >= 0, "transaction_cost must be non-negative")
    _require(gamma >= 0, "gamma must be non-negative")
    _require(k > 0, "k must be greater than 0")
    _require(sigma >= 0, "sigma must be non-negative")
    _require(horizon_seconds > 0, "horizon_seconds must be greater than 0")
    _require(order_expiration > 0, "order_expiration must be greater than 0")
    _require(min_spread >= 0, "min_spread must be non-negative")
    _require(position_limit_buffer >= 0, "position_limit_buffer must be non-negative")
    _require(inventory_skew_factor >= 0, "inventory_skew_factor must be non-negative")
    _require(dt > 0, "dt must be greater than 0")
    _require(period_interval >= 1, "period_interval must be at least 1")
    parsed_start = _parse_iso8601(start_date)
    parsed_end = _parse_iso8601(end_date)
    _require(parsed_end > parsed_start, "end_date must be later than start_date")

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
        start_date=parsed_start,
        end_date=parsed_end,
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


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
