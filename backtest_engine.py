import pandas as pd
import numpy as np
import time
from typing import Dict, List
from datetime import datetime
import logging
import os

from mm import AvellanedaMarketMaker, AbstractTradingAPI
from backtest_config import BacktestConfig, MarketData, HistoricalTrade, Trade

class MockTradingAPI(AbstractTradingAPI):
    """Mock API for backtesting that simulates realistic market behavior"""
    def __init__(self, market_data: List[MarketData], config: BacktestConfig):
        self.market_data = market_data
        self.config = config
        self.current_idx = 0
        self.position = 0
        self.cash = config.initial_capital
        self.orders = {}
        self.trades = []
        self.order_counter = 0

    def get_current_data(self) -> MarketData:
        return self.market_data[self.current_idx] if self.current_idx < len(self.market_data) else self.market_data[-1]

    def advance_time(self):
        if self.current_idx < len(self.market_data) - 1:
            self.current_idx += 1

    def get_price(self) -> Dict[str, float]:
        data = self.get_current_data()
        yes_mid = (data.yes_bid + data.yes_ask) / 2
        no_mid = (data.no_bid + data.no_ask) / 2
        return {"yes": yes_mid, "no": no_mid}

    def place_order(self, action: str, side: str, price: float, quantity: int, expiration_ts: int = None) -> str:
        order_id = str(self.order_counter)
        self.order_counter += 1
        order = {'order_id': order_id, 'action': action, 'side': side, 'price': price, 'quantity': quantity, 'remaining_count': quantity}
        self.orders[order_id] = order
        return order_id

    def cancel_order(self, order_id: str) -> bool:
        if order_id in self.orders:
            del self.orders[order_id]
            return True
        return False

    def get_position(self) -> int:
        return self.position

    def get_orders(self) -> List[Dict]:
        return list(self.orders.values())

    def simulate_realistic_fills(self, current_data: MarketData):
        if not current_data.trades:
            return
        for order_id, order in list(self.orders.items()):
            for trade in current_data.trades:
                if self._would_order_fill(order, trade):
                    fill_quantity = min(order['remaining_count'], trade.count)
                    self._execute_fill(order, fill_quantity, trade.price)
                    order['remaining_count'] -= fill_quantity
                    if order['remaining_count'] <= 0:
                        if order_id in self.orders:
                            del self.orders[order_id]
                        break

    def _would_order_fill(self, order: Dict, trade: HistoricalTrade) -> bool:
        if order['side'] != trade.side:
            return False
        return (trade.price <= order['price']) if order['action'] == 'buy' else (trade.price >= order['price'])

    def _execute_fill(self, order: Dict, quantity: int, actual_trade_price: float):
        trade_record = Trade(timestamp=self.get_current_data().timestamp, action=order['action'], side=order['side'], price=actual_trade_price, quantity=quantity, order_id=order['order_id'])
        self.trades.append(trade_record)
        if order['action'] == 'buy':
            self.position += quantity
            self.cash -= quantity * actual_trade_price + self.config.transaction_cost
        else:
            self.position -= quantity
            self.cash += quantity * actual_trade_price - self.config.transaction_cost

class KalshiBacktester:
    """Main backtesting engine"""
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.logger = logging.getLogger('Backtester')

    def find_settled_markets(self, file_path: str, search_term: str = None) -> List[Dict]:
        """
        Reads our local CSV of all historical markets to find unique settled tickers.
        """
        self.logger.info(f"Searching for '{search_term}' in local file: {file_path}...")
        try:
            market_info = {} # Use a dictionary to automatically handle duplicates
            chunk_size = 10000
            dtype_spec = {'old_ticker_name': 'str'}

            for chunk in pd.read_csv(file_path, chunksize=chunk_size, dtype=dtype_spec, low_memory=False):
                settled_chunk = chunk[chunk['status'].isin(['settled', 'closed', 'finalized'])].copy()
                if search_term:
                    search_upper = search_term.upper()
                    # CORRECTED: Only searches the 'ticker_name' column which we know exists
                    settled_chunk = settled_chunk[settled_chunk['ticker_name'].str.upper().str.contains(search_upper, na=False)]

                for index, row in settled_chunk.iterrows():
                    ticker = row['ticker_name']
                    if ticker not in market_info:
                        market_info[ticker] = {
                            'ticker': ticker,
                            'title': row['ticker_name'],
                            'series_ticker': row['series_ticker'], # Add this line
                            'close_time': row.get('date')
                        }

            unique_markets = list(market_info.values())
            self.logger.info(f"Found {len(unique_markets)} unique markets matching '{search_term}'.")
            return unique_markets

        except Exception as e:
            self.logger.error(f"Failed to read or parse market file: {e}")
            return []

    def fetch_historical_data(self, market_ticker: str, start_date: datetime, end_date: datetime) -> List[MarketData]:
        from mm import KalshiTradingAPI
        logger = logging.getLogger('HistoricalData')

        # Initialize the API as before.
        api = KalshiTradingAPI(market_ticker=market_ticker, base_url=os.getenv('LIVE_KALSHI_BASE_URL'), logger=logger, mode='live')

        min_ts = int(start_date.timestamp())
        max_ts = int(end_date.timestamp())

        logger.info(f"Fetching historical data for {market_ticker} from {start_date} to {end_date}")

        # Call our new candlestick function instead of the old fetchers.
        candlesticks = self._fetch_candlestick_data(api, market_ticker, min_ts, max_ts)

        if not candlesticks:
            self.logger.warning(f"No candlestick data found for {market_ticker}.")
            return []

        # Convert candlestick data into the MarketData format the backtester expects.
        historical_data = []
        for candle in candlesticks:
            ts = datetime.fromtimestamp(candle.get('ts', 0))

            # Use the closing price as the basis for our bid/ask spread.
            # This is an assumption, as candlesticks don't provide explicit bid/ask data.
            yes_close = float(candle.get('close', 50)) / 100

            # Create a synthetic, small spread around the close price.
            yes_ask = yes_close + 0.005
            yes_bid = yes_close - 0.005

            # The 'no' side is the inverse of 'yes'.
            no_ask = 1 - yes_bid
            no_bid = 1 - yes_ask

            volume = candle.get('volume', 0)

            market_data_point = MarketData(
                timestamp=ts,
                yes_bid=yes_bid,
                yes_ask=yes_ask,
                no_bid=no_bid,
                no_ask=no_ask,
                volume=volume,
                trades=[] # We no longer have individual trades from this endpoint.
            )
            historical_data.append(market_data_point)

        if not historical_data:
            return []

        historical_data.sort(key=lambda x: x.timestamp)
        logger.info(f"Successfully converted {len(historical_data)} candlestick data points.")
        return historical_data


    def _fetch_candlestick_data(self, api, market_ticker: str, min_ts: int, max_ts: int) -> List[Dict]:
        """Fetches candlestick data for a given market and time range."""
        self.logger.info(f"Fetching candlestick data for {market_ticker}...")
        candlesticks = []
        cursor = None
        # Let's assume a 1-minute interval for the candlesticks.
        params = {'min_ts': min_ts, 'max_ts': max_ts, 'limit': 1000, 'period': '1m'}
        endpoint = f"/markets/{market_ticker}/candlesticks"

        while True:
            try:
                if cursor:
                    params['cursor'] = cursor

                response = api.make_request("GET", endpoint, params=params)

                history_points = response.get('candlesticks', [])
                if not history_points:
                    break

                candlesticks.extend(history_points)
                cursor = response.get('cursor')

                if not cursor:
                    break
            except Exception as e:
                self.logger.error(f"Error fetching candlestick batch: {e}")
                if '404' in str(e):
                    self.logger.warning(f"Endpoint {endpoint} returned 404. Candlestick data may not be available for this market.")
                break

        return candlesticks
    

    def _fetch_market_history(self, api, market_ticker: str, min_ts: int, max_ts: int) -> List[Dict]:
        market_snapshots = []
        cursor = None
        while True:
            try:
                params = {'limit': 1000, 'min_ts': min_ts, 'max_ts': max_ts}
                if cursor:
                    params['cursor'] = cursor
                response = api.make_request("GET", f"/markets/{market_ticker}/history", params=params)
                history_points = response.get('history', [])
                if not history_points:
                    break
                market_snapshots.extend(history_points)
                cursor = response.get('cursor')
                if not cursor:
                    break
            except Exception as e:
                self.logger.error(f"Error fetching market history batch: {e}")
                break
        return market_snapshots

    def _fetch_trade_history(self, api, market_ticker: str, min_ts: int, max_ts: int) -> List[HistoricalTrade]:
        historical_trades = []
        cursor = None
        endpoint = f"/markets/{market_ticker}/trades"
        while True:
            try:
                params = {'limit': 1000, 'min_ts': min_ts, 'max_ts': max_ts}
                if cursor:
                    params['cursor'] = cursor
                response = api.make_request("GET", endpoint, params=params)
                trades = response.get('trades', [])
                if not trades:
                    break
                for trade in trades:
                    historical_trades.append(HistoricalTrade(timestamp=datetime.fromtimestamp(trade.get('ts', 0)), price=float(trade.get('yes_price', 0))/100, side=trade.get('side', 'yes'), count=trade.get('count', 0), trade_id=trade.get('trade_id', '')))
                cursor = response.get('cursor')
                if not cursor:
                    break
            except Exception as e:
                self.logger.error(f"Error fetching trade history batch: {e}")
                break
        return historical_trades

    def _merge_market_and_trade_data(self, market_snapshots: List[Dict], trades: List[HistoricalTrade]) -> List[MarketData]:
        if not market_snapshots:
            return []
        df_snapshots = pd.DataFrame(market_snapshots)
        df_snapshots['timestamp'] = pd.to_datetime(df_snapshots['ts'], unit='s').dt.round('s')

        df_trades = pd.DataFrame(trades)
        if not df_trades.empty:
            df_trades['timestamp'] = pd.to_datetime(df_trades['timestamp']).dt.round('s')

        merged_data = []
        for index, row in df_snapshots.iterrows():
            ts = row['timestamp']
            relevant_trades = []
            if not df_trades.empty:
                trade_rows = df_trades[df_trades['timestamp'] == ts]
                for _, trade_row in trade_rows.iterrows():
                     relevant_trades.append(HistoricalTrade(**trade_row.to_dict()))
            merged_data.append(MarketData(timestamp=ts, yes_bid=row['yes_bid']/100, yes_ask=row['yes_ask']/100, no_bid=row['no_bid']/100, no_ask=row['no_ask']/100, trades=relevant_trades))
        return merged_data

        def run_backtest(self, series_ticker: str, market_ticker: str, start_date: datetime, end_date: datetime) -> Dict:
        # Pass both tickers to the data fetcher
        market_data = self.fetch_historical_data(market_ticker, start_date, end_date)
        
        if not market_data:
            return {'total_trades': 0, 'pnl_series': [], 'position_series': [], 'timestamps': [], 'final_pnl': 0, 'trades': [], 'win_rate': 0, 'sharpe_ratio': 0, 'max_drawdown': 0}

        mock_api = MockTradingAPI(market_data, self.config)

        mm_params = {k: v for k, v in self.config.__dict__.items() if k not in ['initial_capital', 'transaction_cost']}

        market_maker = AvellanedaMarketMaker(logger=self.logger, api=mock_api, trade_side="yes", **mm_params)
        return self._simulate_strategy(market_maker, mock_api, market_data)

    def _simulate_strategy(self, market_maker, mock_api, market_data) -> Dict:
        results = {'trades': [], 'pnl_series': [], 'position_series': [], 'timestamps': [], 'final_pnl': 0, 'total_trades': 0, 'win_rate': 0, 'sharpe_ratio': 0, 'max_drawdown': 0}
        initial_cash = mock_api.cash

        for i in range(len(market_data)):
            mock_api.current_idx = i
            current_data = mock_api.get_current_data()
            mock_api.simulate_realistic_fills(current_data)

            mid_prices = mock_api.get_price()
            mid_price = mid_prices.get("yes", 0.50)

            if i % int(self.config.dt) == 0:
                inventory = mock_api.get_position()
                time_elapsed = (current_data.timestamp - market_data[0].timestamp).total_seconds()
                bid_price, ask_price = market_maker.calculate_asymmetric_quotes(mid_price, inventory, time_elapsed)
                buy_size, sell_size = market_maker.calculate_order_sizes(inventory)
                market_maker.manage_orders(bid_price, ask_price, buy_size, sell_size)

            current_pnl = mock_api.cash + mock_api.position * mid_price - initial_cash
            results['timestamps'].append(current_data.timestamp)
            results['pnl_series'].append(current_pnl)
            results['position_series'].append(mock_api.position)

        results.update({
            'trades': mock_api.trades,
            'total_trades': len(mock_api.trades),
            'final_pnl': results['pnl_series'][-1] if results['pnl_series'] else 0
        })
        return results

    def generate_report(self, results: Dict, market_ticker: str) -> str:
        if not results or not results.get('timestamps'):
             return f"No data available for market: {market_ticker}"
        report = f"""
KALSHI BACKTEST REPORT
=====================================
Market: {market_ticker}
Period: {len(results['timestamps'])} data points
Initial Capital: ${self.config.initial_capital:,.2f}

PERFORMANCE METRICS
-------------------
Final PnL: ${results.get('final_pnl', 0):,.2f}
Return: {(results.get('final_pnl', 0) / self.config.initial_capital) * 100:.2f}%
Total Trades: {results.get('total_trades', 0)}
"""
        return report.strip()