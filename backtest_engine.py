from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

import pandas as pd
import requests

from backtest_config import BacktestConfig, MarketData, Trade
from http_utils import build_retry_session
from mm import AbstractTradingAPI, AvellanedaMarketMaker

REQUIRED_ARCHIVE_COLUMNS = {"ticker_name", "status", "date"}


class KalshiMarketDataClient:
    """Public read-only client for market metadata and candlesticks."""

    def __init__(self, base_url: str | None = None, timeout: int = 30, logger: logging.Logger | None = None):
        self.base_url = (
            base_url
            or os.getenv("KALSHI_MARKET_DATA_BASE_URL")
            or "https://api.elections.kalshi.com/trade-api/v2"
        )
        self.timeout = timeout
        self.logger = logger or logging.getLogger("KalshiMarketData")
        self.session = build_retry_session()

    def make_request(self, method: str, path: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        response = self.session.request(
            method=method,
            url=f"{self.base_url}{path}",
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def get_historical_cutoff(self) -> Dict[str, Any]:
        return self.make_request("GET", "/historical/cutoff")

    def get_market(self, market_ticker: str) -> Dict[str, Any]:
        return self.make_request("GET", f"/markets/{market_ticker}")

    def get_historical_market(self, market_ticker: str) -> Dict[str, Any]:
        return self.make_request("GET", f"/historical/markets/{market_ticker}")

    def get_event(self, event_ticker: str) -> Dict[str, Any]:
        return self.make_request("GET", f"/events/{event_ticker}")

    def get_market_details(self, market_ticker: str) -> dict[str, Any]:
        live_market = None
        historical_market = None

        try:
            live_market = self.get_market(market_ticker).get("market")
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code != 404:
                raise

        if live_market is None:
            historical_market = self.get_historical_market(market_ticker).get("market")

        market = live_market or historical_market or {}
        event_ticker = market.get("event_ticker")
        series_ticker = market.get("series_ticker")

        if not series_ticker and event_ticker:
            try:
                event = self.get_event(event_ticker).get("event", {})
                series_ticker = event.get("series_ticker")
            except requests.HTTPError:
                series_ticker = None

        settlement_ts = self._parse_api_timestamp(market.get("settlement_ts") or market.get("close_time"))

        return {
            "market": market,
            "series_ticker": series_ticker,
            "event_ticker": event_ticker,
            "settlement_ts": settlement_ts,
            "market_source": "historical" if historical_market is not None else "live",
        }

    def get_market_candlesticks(
        self,
        market_ticker: str,
        start_ts: int,
        end_ts: int,
        period_interval: int,
        series_ticker: str | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        cutoff = self.get_historical_cutoff()
        cutoff_ts = self._parse_api_timestamp(cutoff.get("market_settled_ts"))
        market_details = self.get_market_details(market_ticker)
        settlement_ts = int(market_details.get("settlement_ts") or 0)
        resolved_series_ticker = market_details.get("series_ticker") or series_ticker
        source = "historical" if settlement_ts and settlement_ts < cutoff_ts else "live"

        if source == "live":
            if not resolved_series_ticker:
                raise ValueError("series_ticker is required for live candlestick queries")
            endpoint = f"/series/{resolved_series_ticker}/markets/{market_ticker}/candlesticks"
            params = {
                "start_ts": start_ts,
                "end_ts": end_ts,
                "period_interval": period_interval,
                "include_latest_before_start": "true",
            }
        else:
            endpoint = f"/historical/markets/{market_ticker}/candlesticks"
            params = {
                "start_ts": start_ts,
                "end_ts": end_ts,
                "period_interval": period_interval,
            }

        response = self.make_request("GET", endpoint, params=params)
        return response.get("candlesticks", []), {
            "candlestick_source": source,
            "cutoff_ts": cutoff_ts,
            "series_ticker": resolved_series_ticker,
            "event_ticker": market_details.get("event_ticker"),
            "settlement_ts": settlement_ts,
            "market_source": market_details.get("market_source"),
        }

    def _parse_api_timestamp(self, value: Any) -> int:
        if value in (None, ""):
            return 0
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            if value.isdigit():
                return int(value)
            return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
        raise ValueError(f"Unsupported timestamp value: {value!r}")


class MockTradingAPI(AbstractTradingAPI):
    """Mock API for backtesting that simulates fills from candlestick quote ranges."""

    def __init__(self, market_data: List[MarketData], config: BacktestConfig):
        self.market_data = market_data
        self.config = config
        self.current_idx = 0
        self.position = 0
        self.cash = config.initial_capital
        self.orders: dict[str, dict[str, Any]] = {}
        self.trades: list[Trade] = []
        self.order_counter = 0

    def get_current_data(self) -> MarketData:
        return self.market_data[min(self.current_idx, len(self.market_data) - 1)]

    def get_price(self) -> Dict[str, float]:
        data = self.get_current_data()
        yes_mid = (data.yes_bid + data.yes_ask) / 2
        no_mid = (data.no_bid + data.no_ask) / 2
        return {"yes": yes_mid, "no": no_mid}

    def place_order(
        self,
        action: str,
        side: str,
        price: float,
        quantity: int,
        expiration_ts: int | None = None,
    ) -> str:
        order_id = str(self.order_counter)
        self.order_counter += 1
        self.orders[order_id] = {
            "order_id": order_id,
            "action": action,
            "side": side,
            "price": price,
            "quantity": quantity,
            "remaining_count": quantity,
            "expiration_ts": expiration_ts,
        }
        return order_id

    def cancel_order(self, order_id: str) -> bool:
        if order_id not in self.orders:
            return False
        del self.orders[order_id]
        return True

    def get_position(self) -> int:
        return self.position

    def get_orders(self) -> List[Dict]:
        return list(self.orders.values())

    def simulate_realistic_fills(self, current_data: MarketData) -> None:
        remaining_volume = max(0, current_data.volume)
        if remaining_volume <= 0:
            return

        for order_id, order in list(self.orders.items()):
            if remaining_volume <= 0:
                break

            fill_price = self._get_fill_price(order, current_data)
            if fill_price is None:
                continue

            fill_quantity = min(order["remaining_count"], remaining_volume)
            self._execute_fill(order, fill_quantity, fill_price)
            order["remaining_count"] -= fill_quantity
            remaining_volume -= fill_quantity

            if order["remaining_count"] <= 0:
                self.orders.pop(order_id, None)

    def _get_fill_price(self, order: Dict[str, Any], current_data: MarketData) -> float | None:
        if order["side"] == "yes":
            buy_touch = current_data.yes_ask_low
            sell_touch = current_data.yes_bid_high
        else:
            buy_touch = current_data.no_ask_low
            sell_touch = current_data.no_bid_high

        if order["action"] == "buy":
            if buy_touch is None or order["price"] < buy_touch:
                return None
            return min(order["price"], buy_touch)

        if sell_touch is None or order["price"] > sell_touch:
            return None
        return max(order["price"], sell_touch)

    def _execute_fill(self, order: Dict[str, Any], quantity: int, actual_trade_price: float) -> None:
        trade_record = Trade(
            timestamp=self.get_current_data().timestamp,
            action=order["action"],
            side=order["side"],
            price=actual_trade_price,
            quantity=quantity,
            order_id=order["order_id"],
        )
        self.trades.append(trade_record)

        if order["action"] == "buy":
            self.position += quantity
            self.cash -= quantity * actual_trade_price + self.config.transaction_cost
        else:
            self.position -= quantity
            self.cash += quantity * actual_trade_price - self.config.transaction_cost


class KalshiBacktester:
    """Backtesting engine backed by Kalshi live and historical candlestick data."""

    def __init__(self, config: BacktestConfig, market_data_client: KalshiMarketDataClient | None = None):
        self.config = config
        self.logger = logging.getLogger("Backtester")
        self.market_data_client = market_data_client or KalshiMarketDataClient(logger=logging.getLogger("MarketData"))

    def find_settled_markets(self, file_path: str, search_term: str | None = None) -> List[Dict]:
        self.logger.info("Searching for '%s' in %s", search_term, file_path)
        market_info: dict[str, dict[str, Any]] = {}

        try:
            with pd.read_csv(file_path, chunksize=10_000, low_memory=False) as reader:
                for chunk in reader:
                    missing_columns = REQUIRED_ARCHIVE_COLUMNS.difference(chunk.columns)
                    if missing_columns:
                        missing = ", ".join(sorted(missing_columns))
                        raise ValueError(f"Archive file is missing required columns: {missing}")

                    settled_chunk = chunk[chunk["status"].isin(["settled", "closed", "finalized"])].copy()
                    if search_term:
                        settled_chunk = settled_chunk[
                            settled_chunk["ticker_name"].str.upper().str.contains(search_term.upper(), na=False)
                        ]

                    for _, row in settled_chunk.iterrows():
                        ticker = row["ticker_name"]
                        candidate = {
                            "ticker": ticker,
                            "title": row["ticker_name"],
                            "series_ticker": row.get("series_ticker") or row.get("report_ticker"),
                            "report_ticker": row.get("report_ticker"),
                            "close_time": row.get("date"),
                        }
                        existing = market_info.get(ticker)
                        if existing is None or (candidate["close_time"] or "") >= (existing.get("close_time") or ""):
                            if existing:
                                candidate["series_ticker"] = candidate["series_ticker"] or existing.get("series_ticker")
                                candidate["report_ticker"] = candidate["report_ticker"] or existing.get("report_ticker")
                            market_info[ticker] = candidate
        except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
            raise ValueError(f"Archive file could not be parsed as CSV: {exc}") from exc

        return list(market_info.values())

    def fetch_historical_data(
        self,
        market_ticker: str,
        start_date: datetime,
        end_date: datetime,
        *,
        series_ticker: str | None = None,
        period_interval: int = 1,
    ) -> tuple[List[MarketData], Dict[str, Any]]:
        candles, metadata = self.market_data_client.get_market_candlesticks(
            market_ticker=market_ticker,
            start_ts=int(start_date.timestamp()),
            end_ts=int(end_date.timestamp()),
            period_interval=period_interval,
            series_ticker=series_ticker,
        )
        historical_data = [self._market_data_from_candle(candle) for candle in candles]
        historical_data.sort(key=lambda entry: entry.timestamp)
        return historical_data, metadata

    def _market_data_from_candle(self, candle: dict[str, Any]) -> MarketData:
        price_block = candle.get("price", {})
        yes_bid_block = candle.get("yes_bid", {})
        yes_ask_block = candle.get("yes_ask", {})

        fallback_price = self._normalize_price_block(price_block, "close", default=0.5)
        yes_bid = self._normalize_price_block(yes_bid_block, "close", default=fallback_price)
        yes_ask = self._normalize_price_block(yes_ask_block, "close", default=fallback_price)
        yes_bid_low = self._normalize_price_block(yes_bid_block, "low", default=yes_bid)
        yes_bid_high = self._normalize_price_block(yes_bid_block, "high", default=yes_bid)
        yes_ask_low = self._normalize_price_block(yes_ask_block, "low", default=yes_ask)
        yes_ask_high = self._normalize_price_block(yes_ask_block, "high", default=yes_ask)

        if yes_ask < yes_bid:
            yes_bid, yes_ask = yes_ask, yes_bid
        if yes_ask_low < yes_bid_low:
            yes_bid_low, yes_ask_low = yes_ask_low, yes_bid_low
        if yes_ask_high < yes_bid_high:
            yes_bid_high, yes_ask_high = yes_ask_high, yes_bid_high

        no_bid = max(0.0, 1 - yes_ask)
        no_ask = min(1.0, 1 - yes_bid)
        no_bid_low = max(0.0, 1 - yes_ask_high)
        no_bid_high = min(1.0, 1 - yes_ask_low)
        no_ask_low = max(0.0, 1 - yes_bid_high)
        no_ask_high = min(1.0, 1 - yes_bid_low)
        volume = int(float(candle.get("volume", 0) or 0))

        return MarketData(
            timestamp=datetime.fromtimestamp(int(candle.get("end_period_ts", 0)), tz=timezone.utc),
            yes_bid=max(0.0, yes_bid),
            yes_ask=min(1.0, yes_ask),
            no_bid=no_bid,
            no_ask=no_ask,
            volume=volume,
            yes_bid_low=max(0.0, yes_bid_low),
            yes_bid_high=min(1.0, yes_bid_high),
            yes_ask_low=max(0.0, yes_ask_low),
            yes_ask_high=min(1.0, yes_ask_high),
            no_bid_low=no_bid_low,
            no_bid_high=no_bid_high,
            no_ask_low=no_ask_low,
            no_ask_high=no_ask_high,
            trades=[],
        )

    def _normalize_price_block(self, block: dict[str, Any], field: str, default: float) -> float:
        dollars_key = f"{field}_dollars"
        if dollars_key in block and block[dollars_key] not in (None, ""):
            return float(block[dollars_key])
        if field in block and block[field] is not None:
            value = float(block[field])
            return value / 100 if value > 1 else value
        return default

    def run_backtest(
        self,
        market_ticker: str,
        start_date: datetime,
        end_date: datetime,
        series_ticker: str | None = None,
        period_interval: int = 1,
    ) -> Dict[str, Any]:
        market_data, fetch_metadata = self.fetch_historical_data(
            market_ticker=market_ticker,
            start_date=start_date,
            end_date=end_date,
            series_ticker=series_ticker,
            period_interval=period_interval,
        )
        if not market_data:
            results = self._empty_results()
            results.update(fetch_metadata)
            return results

        mock_api = MockTradingAPI(market_data, self.config)
        mm_params = {
            key: value
            for key, value in self.config.__dict__.items()
            if key not in {"initial_capital", "transaction_cost", "dt"}
        }
        market_maker = AvellanedaMarketMaker(
            logger=self.logger,
            api=mock_api,
            trade_side="yes",
            **mm_params,
        )
        results = self._simulate_strategy(market_maker, mock_api, market_data)
        results.update(fetch_metadata)
        return results

    def _simulate_strategy(
        self,
        market_maker: AvellanedaMarketMaker,
        mock_api: MockTradingAPI,
        market_data: list[MarketData],
    ) -> Dict[str, Any]:
        results = self._empty_results()
        initial_cash = mock_api.cash
        cadence = max(1, int(round(self.config.dt)))

        for idx, current_data in enumerate(market_data):
            mock_api.current_idx = idx
            mock_api.simulate_realistic_fills(current_data)

            mid_price = mock_api.get_price().get("yes", 0.50)
            if idx % cadence == 0:
                inventory = mock_api.get_position()
                time_elapsed = (current_data.timestamp - market_data[0].timestamp).total_seconds()
                bid_price, ask_price = market_maker.calculate_asymmetric_quotes(mid_price, inventory, time_elapsed)
                buy_size, sell_size = market_maker.calculate_order_sizes(inventory)
                market_maker.manage_orders(bid_price, ask_price, buy_size, sell_size)

            current_pnl = mock_api.cash + (mock_api.position * mid_price) - initial_cash
            results["timestamps"].append(current_data.timestamp)
            results["pnl_series"].append(current_pnl)
            results["position_series"].append(mock_api.position)

        results["trades"] = mock_api.trades
        results["total_trades"] = len(mock_api.trades)
        results["final_pnl"] = results["pnl_series"][-1] if results["pnl_series"] else 0.0
        return results

    def _empty_results(self) -> Dict[str, Any]:
        return {
            "trades": [],
            "pnl_series": [],
            "position_series": [],
            "timestamps": [],
            "final_pnl": 0.0,
            "total_trades": 0,
            "win_rate": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
        }

    def generate_report(self, results: Dict[str, Any], market_ticker: str) -> str:
        if not results.get("timestamps"):
            return f"No data available for market: {market_ticker}"

        final_pnl = results.get("final_pnl", 0.0)
        return (
            "KALSHI BACKTEST REPORT\n"
            "=====================================\n"
            f"Market: {market_ticker}\n"
            f"Period: {len(results['timestamps'])} data points\n"
            f"Initial Capital: ${self.config.initial_capital:,.2f}\n\n"
            "PERFORMANCE METRICS\n"
            "-------------------\n"
            f"Final PnL: ${final_pnl:,.2f}\n"
            f"Return: {(final_pnl / self.config.initial_capital) * 100:.2f}%\n"
            f"Total Trades: {results.get('total_trades', 0)}"
        )
