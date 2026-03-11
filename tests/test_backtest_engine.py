import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from pathlib import Path
from uuid import uuid4

from backtest_config import BacktestConfig, MarketData
from backtest_engine import KalshiBacktester, KalshiMarketDataClient, MockTradingAPI


class FakeMarketDataClient(KalshiMarketDataClient):
    def __init__(self, *, cutoff_ts: str, market: dict, event: dict | None = None):
        super().__init__(base_url="https://example.com")
        self.cutoff_ts = cutoff_ts
        self.market = market
        self.event = event or {}
        self.last_request: tuple[str, dict] | None = None

    def make_request(self, method: str, path: str, params=None):
        if path == "/historical/cutoff":
            return {"market_settled_ts": self.cutoff_ts}
        if path.startswith("/markets/"):
            return {"market": self.market}
        if path.startswith("/historical/markets/") and path.endswith("/candlesticks"):
            self.last_request = ("historical", {"path": path, **(params or {})})
            return {"candlesticks": []}
        if path.startswith("/historical/markets/"):
            return {"market": self.market}
        if path.startswith("/series/") and path.endswith("/candlesticks"):
            self.last_request = ("live", {"path": path, **(params or {})})
            return {"candlesticks": []}
        if path.startswith("/events/"):
            return {"event": self.event}
        raise AssertionError(f"Unexpected path: {path}")


class BacktestEngineTests(unittest.TestCase):
    def test_public_client_ignores_live_trading_base_url(self):
        with patch.dict(
            "os.environ",
            {
                "LIVE_KALSHI_BASE_URL": "https://trading-api.kalshi.com/trade-api/v2",
            },
            clear=False,
        ):
            client = KalshiMarketDataClient()
        self.assertEqual("https://api.elections.kalshi.com/trade-api/v2", client.base_url)

    def test_archive_search_uses_report_ticker_as_series_fallback(self):
        temp_root = Path(__file__).resolve().parents[1] / ".tmp-tests"
        temp_root.mkdir(exist_ok=True)
        csv_path = temp_root / f"archive-{uuid4().hex}.csv"
        try:
            csv_path.write_text(
                "ticker_name,status,report_ticker,date\n"
                "GDPW-2023-A2,finalized,GDPW,2025-03-01\n",
                encoding="utf-8",
            )

            backtester = KalshiBacktester(BacktestConfig())
            results = backtester.find_settled_markets(str(csv_path), search_term="GDPW")

            self.assertEqual(1, len(results))
            self.assertEqual("GDPW", results[0]["series_ticker"])
            self.assertEqual("GDPW", results[0]["report_ticker"])
        finally:
            csv_path.unlink(missing_ok=True)

    def test_candle_normalization_prefers_dollar_fields(self):
        backtester = KalshiBacktester(BacktestConfig())
        candle = {
            "end_period_ts": 1700000000,
            "yes_bid": {
                "close": 55,
                "close_dollars": "0.5500",
                "low": 54,
                "low_dollars": "0.5400",
                "high": 57,
                "high_dollars": "0.5700",
            },
            "yes_ask": {
                "close": 57,
                "close_dollars": "0.5700",
                "low": 56,
                "low_dollars": "0.5600",
                "high": 58,
                "high_dollars": "0.5800",
            },
            "price": {"close": 56, "close_dollars": "0.5600"},
            "volume": 12,
        }

        point = backtester._market_data_from_candle(candle)

        self.assertAlmostEqual(0.55, point.yes_bid)
        self.assertAlmostEqual(0.57, point.yes_ask)
        self.assertAlmostEqual(0.56, point.yes_ask_low)
        self.assertAlmostEqual(0.57, point.yes_bid_high)
        self.assertAlmostEqual(0.43, point.no_bid)
        self.assertAlmostEqual(0.45, point.no_ask)
        self.assertEqual(timezone.utc, point.timestamp.tzinfo)

    def test_mock_api_fills_against_quote_ranges(self):
        config = BacktestConfig(initial_capital=1000.0, transaction_cost=0.0)
        market_data = [
            MarketData(
                timestamp=datetime(2025, 1, 1, 12, 0, 0),
                yes_bid=0.55,
                yes_ask=0.57,
                no_bid=0.43,
                no_ask=0.45,
                volume=5,
                yes_bid_low=0.54,
                yes_bid_high=0.56,
                yes_ask_low=0.56,
                yes_ask_high=0.58,
                no_bid_low=0.42,
                no_bid_high=0.44,
                no_ask_low=0.44,
                no_ask_high=0.46,
            )
        ]
        api = MockTradingAPI(market_data, config)
        order_id = api.place_order("buy", "yes", 0.57, 3)

        api.simulate_realistic_fills(market_data[0])

        self.assertNotIn(order_id, api.orders)
        self.assertEqual(3, api.get_position())
        self.assertEqual(1, len(api.trades))
        self.assertAlmostEqual(0.56, api.trades[0].price)

    def test_cutoff_timestamp_parser_accepts_iso8601(self):
        client = KalshiMarketDataClient(base_url="https://example.com")
        parsed = client._parse_api_timestamp("2025-03-07T00:00:00Z")
        self.assertEqual(1741305600, parsed)

    def test_routing_uses_market_settlement_timestamp_not_window_end(self):
        client = FakeMarketDataClient(
            cutoff_ts="2025-03-07T00:00:00Z",
            market={
                "ticker": "TEST-MKT",
                "event_ticker": "TEST-EVENT",
                "series_ticker": "TEST-SERIES",
                "settlement_ts": "2025-03-01T00:00:00Z",
            },
        )
        backtester = KalshiBacktester(BacktestConfig(), market_data_client=client)

        _, metadata = backtester.fetch_historical_data(
            market_ticker="TEST-MKT",
            start_date=datetime(2025, 3, 8, 0, 0, 0),
            end_date=datetime(2025, 3, 8, 12, 0, 0),
            series_ticker="TEST-SERIES",
        )

        self.assertEqual("historical", metadata["candlestick_source"])
        self.assertEqual("historical", client.last_request[0])

    def test_live_routing_can_resolve_series_ticker_from_event(self):
        client = FakeMarketDataClient(
            cutoff_ts="2025-03-07T00:00:00Z",
            market={
                "ticker": "TEST-MKT",
                "event_ticker": "TEST-EVENT",
                "settlement_ts": "2025-03-08T00:00:00Z",
            },
            event={"series_ticker": "RESOLVED-SERIES"},
        )
        backtester = KalshiBacktester(BacktestConfig(), market_data_client=client)

        _, metadata = backtester.fetch_historical_data(
            market_ticker="TEST-MKT",
            start_date=datetime(2025, 3, 8, 0, 0, 0),
            end_date=datetime(2025, 3, 8, 12, 0, 0),
        )

        self.assertEqual("live", metadata["candlestick_source"])
        self.assertEqual("RESOLVED-SERIES", metadata["series_ticker"])
        self.assertEqual("live", client.last_request[0])

    def test_live_routing_prefers_canonical_series_ticker_over_archive_value(self):
        client = FakeMarketDataClient(
            cutoff_ts="2025-03-07T00:00:00Z",
            market={
                "ticker": "TEST-MKT",
                "event_ticker": "TEST-EVENT",
                "series_ticker": "KXGTA6",
                "settlement_ts": "2025-03-08T00:00:00Z",
            },
            event={"series_ticker": "KXGTA6"},
        )
        backtester = KalshiBacktester(BacktestConfig(), market_data_client=client)

        _, metadata = backtester.fetch_historical_data(
            market_ticker="TEST-MKT",
            start_date=datetime(2025, 3, 8, 0, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2025, 3, 8, 12, 0, 0, tzinfo=timezone.utc),
            series_ticker="GTA6",
        )

        self.assertEqual("KXGTA6", metadata["series_ticker"])
        self.assertEqual("/series/KXGTA6/markets/TEST-MKT/candlesticks", client.last_request[1]["path"])


if __name__ == "__main__":
    unittest.main()
