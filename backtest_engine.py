import pandas as pd
import numpy as np
import time
from typing import Dict, List
from datetime import datetime, timedelta
import logging
import os

from mm import AvellanedaMarketMaker, AbstractTradingAPI, SimpleMarketMaker
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
        order = {
            'order_id': order_id, 'action': action, 'side': side,
            'count': quantity, 'remaining_count': quantity
        }
        price_in_cents = int(round(price * 100))
        if side == 'yes':
            order['yes_price'] = price_in_cents
        else:
            order['no_price'] = price_in_cents
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
        order_price_in_dollars = (order.get('yes_price', 0) or order.get('no_price', 0)) / 100.0
        return (trade.price <= order_price_in_dollars) if order['action'] == 'buy' else (trade.price >= order_price_in_dollars)

    def _execute_fill(self, order: Dict, quantity: int, actual_trade_price: float):
        trade_record = Trade(timestamp=self.get_current_data().timestamp, action=order['action'], side=order['side'], price=actual_trade_price, quantity=quantity, order_id=order['order_id'])
        self.trades.append(trade_record)
        if order['action'] == 'buy':
            self.position += quantity
            self.cash -= quantity * actual_trade_price
        else: # sell
            self.position -= quantity
            self.cash += quantity * actual_trade_price
        # Transaction costs are applied to every fill
        self.cash -= self.config.transaction_cost

as()

                settled_chunk = df_chunk[df_chunk['status'].isin(['settled', 'closed', 'finalized'])].copy()

                if search_term:
                    search_upper = search_term.upper()
                    settled_chunk = settled_chunk[settled_chunk['ticker_name'].str.upper().str.contains(search_upper, na=False)]

                for index, row in settled_chunk.iterrows():
                    ticker = row['ticker_name']
                    # If we haven't already added this ticker, add it now
                    if ticker not in found_tickers:
                        unique_markets.append({
                            'ticker': ticker,
                            'title': ticker,
                            'close_time': row.get('date')
                        })
                        found_tickers.add(ticker)

            self.logger.info(f"Found {len(unique_markets)} unique markets matching '{search_term}'.")
            return unique_markets

        except Exception as e:
            self.logger.error(f"Failed to read or parse market file: {e}")
            return []
    def fetch_historical_data(self, market_ticker: str, start_date: datetime, end_date: datetime) -> List[MarketData]:
        from mm import KalshiTradingAPI
        logger = logging.getLogger('HistoricalData')
        api = KalshiTradingAPI(market_ticker=market_ticker, base_url=os.getenv('LIVE_KALSHI_BASE_URL'), logger=logger, mode='live')
        min_ts = int(start_date.timestamp())
        max_ts = int(end_date.timestamp())
        logger.info(f"Fetching historical data for {market_ticker} from {start_date} to {end_date}")
        raw_trades = self._fetch_filtered_trades(api, market_ticker, min_ts, max_ts)
        if not raw_trades:
            self.logger.warning(f"No trade data found for {market_ticker}.")
            return []
        logger.info(f"Successfully fetched {len(raw_trades)} trades. Reconstructing market data...")
        df = pd.DataFrame(raw_trades)
        df['price'] = df['yes_price'] / 100.0
        df['timestamp'] = pd.to_datetime(df['created_time'])
        df = df.set_index('timestamp')
        price_resampled = df['price'].resample('min').agg(['first', 'max', 'min', 'last'])
        price_resampled.columns = ['open', 'high', 'low', 'close']
        volume_resampled = df['count'].resample('min').sum()
        volume_resampled.name = 'volume'
        market_snapshots = pd.concat([price_resampled, volume_resampled], axis=1).dropna(subset=['close'])
        trades_grouped = df.groupby(pd.Grouper(freq='min'))
        historical_data = []
        for ts, snapshot in market_snapshots.iterrows():
            raw_trades_for_minute = trades_grouped.get_group(ts).to_dict('records')
            trade_objects = [
                HistoricalTrade(
                    timestamp=pd.to_datetime(t['created_time']),
                    price=t['yes_price'] / 100.0,
                    side=t['taker_side'], count=t['count'], trade_id=t['trade_id']
                ) for t in raw_trades_for_minute
            ]
            yes_close = snapshot['close']
            yes_ask = yes_close + 0.005
            yes_bid = yes_close - 0.005
            market_data_point = MarketData(
                timestamp=ts,
                yes_bid=yes_bid, yes_ask=yes_ask,
                no_bid=1 - yes_ask, no_ask=1 - yes_bid,
                low=snapshot['low'], high=snapshot['high'],
                volume=int(snapshot['volume']),
                trades=trade_objects
            )
            historical_data.append(market_data_point)
        historical_data.sort(key=lambda x: x.timestamp)
        logger.info(f"Successfully reconstructed {len(historical_data)} market data points.")
        return historical_data, len(raw_trades) if raw_trades else 0

    def _fetch_filtered_trades(self, api, market_ticker: str, min_ts: int, max_ts: int) -> List[Dict]:
        self.logger.info(f"Fetching filtered trades for {market_ticker}...")
        trades = []
        cursor = None
        endpoint = "/markets/trades"
        params = { 'ticker': market_ticker, 'start_ts': min_ts, 'end_ts': max_ts, 'limit': 1000 }
        while True:
            try:
                if cursor: params['cursor'] = cursor
                response = api.make_request("GET", endpoint, params=params)
                trade_points = response.get('trades', [])
                if not trade_points: break
                trades.extend(trade_points)
                cursor = response.get('cursor')
                if not cursor: break
            except Exception as e:
                self.logger.error(f"Error fetching filtered trades batch: {e}")
                break
        return trades

    def run_backtest(self, market_ticker: str, start_date: datetime, end_date: datetime) -> Dict:
        market_data, total_market_trades = self.fetch_historical_data(market_ticker, start_date, end_date)
        if not market_data:
            return {'total_trades': 0, 'pnl_series': [], 'position_series': [], 'timestamps': [], 'final_pnl': 0, 'trades': [], 'win_rate': 0, 'sharpe_ratio': 0, 'max_drawdown': 0}

        mock_api = MockTradingAPI(market_data, self.config)

        if self.config.strategy == 'simple':
            self.logger.info("Running with SimpleMarketMaker strategy")
            mm_params = {
                'fixed_spread': self.config.fixed_spread,
                'max_position': self.config.max_position,
                'order_expiration': self.config.order_expiration,
                'position_limit_buffer': self.config.position_limit_buffer,
                'inventory_skew_factor': self.config.inventory_skew_factor
            }
            market_maker = SimpleMarketMaker(logger=self.logger, api=mock_api, trade_side="yes", **mm_params)

        elif self.config.strategy == 'avellaneda':
            self.logger.info("Running with AvellanedaMarketMaker strategy")
            mm_params = {
                'gamma': self.config.gamma,
                'k': self.config.k,
                'sigma': self.config.sigma,
                'T': self.config.T,
                'min_spread': self.config.min_spread,
                'max_position': self.config.max_position,
                'order_expiration': self.config.order_expiration,
                'position_limit_buffer': self.config.position_limit_buffer,
                'inventory_skew_factor': self.config.inventory_skew_factor
            }
            market_maker = AvellanedaMarketMaker(logger=self.logger, api=mock_api, trade_side="yes", **mm_params)

        else:
            raise ValueError(f"Unknown strategy: {self.config.strategy}")

        results = self._simulate_strategy(market_maker, mock_api, market_data)

        results['total_market_trades'] = total_market_trades
                
        if results['trades']:
            trades_df = pd.DataFrame([vars(t) for t in results['trades']])
            tradelog_path = f"tradelog_{market_ticker}.csv"
            trades_df.to_csv(tradelog_path, index=False)
            results['tradelog_path'] = tradelog_path

        return results

    def _simulate_strategy(self, market_maker, mock_api, market_data) -> Dict:
        results = {'trades': [], 'pnl_series': [], 'position_series': [], 'timestamps': [], 'final_pnl': 0}
        initial_cash = mock_api.cash
        mid_price_history = []
        fair_value_history = []
        sma_usage_count = 0

        for i in range(len(market_data)):
            mock_api.current_idx = i
            current_data = mock_api.get_current_data()
            mock_api.simulate_realistic_fills(current_data)

            mid_prices = mock_api.get_price()
            mid_price = mid_prices.get("yes", 0.50)
            mid_price_history.append(mid_price)
            fair_value = mid_price # Default to mid_price

            # Only calculate SMA if we have enough data points
            if len(mid_price_history) >= self.config.sma_window: # We can reuse the sma_window parameter name for now
                price_series = pd.Series(mid_price_history)
                # Calculate EMA instead of SMA
                ema = price_series.ewm(span=self.config.sma_window, adjust=False).mean().iloc[-1]
                if pd.notna(ema):
                    fair_value = ema
                sma_usage_count += 1 # Add this line

            fair_value_history.append(fair_value)

            if i % int(self.config.dt) == 0:
                inventory = mock_api.get_position()
                time_elapsed = (current_data.timestamp - market_data[0].timestamp).total_seconds()

                # Use the raw mid_price directly, as the A-S model was designed
                bid_price, ask_price = market_maker.calculate_asymmetric_quotes(fair_value, inventory, time_elapsed)

                buy_size, sell_size = market_maker.calculate_order_sizes(inventory)
                market_maker.manage_orders(bid_price, ask_price, buy_size, sell_size)

            current_pnl = mock_api.cash + mock_api.position * mid_price - initial_cash
            results['timestamps'].append(current_data.timestamp)
            results['pnl_series'].append(current_pnl)
            results['position_series'].append(mock_api.position)

        pnl_series = pd.Series(results['pnl_series'])
        final_market_price = mid_price_history[-1] if mid_price_history else 0

        # --- ADD THIS BLOCK to calculate the new metrics ---
        round_trip_pnls = self._calculate_trade_pnls(mock_api.trades, final_market_price)
        final_position = results['position_series'][-1] if results['position_series'] else 0
        # --- END OF BLOCK ---

        # --- ADD THIS BLOCK FOR INTRA-DAY PNL CALCULATION ---
        pnl_series = pd.Series(results['pnl_series'], index=results['timestamps'])
        if not pnl_series.empty:
            first_hour_end = pnl_series.index[0] + timedelta(hours=1)
            last_hour_start = pnl_series.index[-1] - timedelta(hours=1)

            first_hour_pnl = pnl_series.loc[pnl_series.index <= first_hour_end]
            middle_pnl = pnl_series.loc[(pnl_series.index > first_hour_end) & (pnl_series.index < last_hour_start)]
            last_hour_pnl = pnl_series.loc[pnl_series.index >= last_hour_start]

            results['pnl_first_hour'] = first_hour_pnl.iloc[-1] - pnl_series.iloc[0] if not first_hour_pnl.empty else 0
            results['pnl_middle'] = middle_pnl.iloc[-1] - first_hour_pnl.iloc[-1] if not middle_pnl.empty and not first_hour_pnl.empty else 0
            results['pnl_last_hour'] = pnl_series.iloc[-1] - middle_pnl.iloc[-1] if not last_hour_pnl.empty and not middle_pnl.empty else 0
        else:
            results['pnl_first_hour'] = 0
            results['pnl_middle'] = 0
            results['pnl_last_hour'] = 0
        # --- END OF BLOCK ---

        results.update({
            'trades': mock_api.trades,
            'total_trades': len(mock_api.trades),
            'final_pnl': pnl_series.iloc[-1] if not pnl_series.empty else 0,
            'sharpe_ratio': self._calculate_sharpe_ratio(round_trip_pnls),
            'max_drawdown': self._calculate_max_drawdown(pnl_series),
            'win_rate': self._calculate_win_rate(round_trip_pnls),
            'round_trip_trades': len(round_trip_pnls), # Add this
            'final_position': final_position # Add this
        })
        # --- ADD THIS ENTIRE BLOCK BEFORE THE RETURN STATEMENT ---
        print("\n" + "-"*50)
        print("🔬 FAIR VALUE ANALYSIS REPORT")
        print("-"*50)

        total_steps = len(fair_value_history)
        if total_steps > 0:
            sma_usage_pct = (sma_usage_count / total_steps) * 100
            print(f"SMA was used as fair_value in {sma_usage_count} of {total_steps} steps ({sma_usage_pct:.2f}%).")

            # Convert to numpy arrays for easier calculation
            fair_values = np.array(fair_value_history)
            mid_prices = np.array(mid_price_history)

            avg_fair_value = np.mean(fair_values)
            avg_mid_price = np.mean(mid_prices)
            avg_deviation = np.mean(np.abs(fair_values - mid_prices))

            print(f"Average Fair Value: ${avg_fair_value:.4f}")
            print(f"Average Mid Price:  ${avg_mid_price:.4f}")
            print(f"Average Deviation:  ${avg_deviation:.4f}")
        else:
            print("No data points to analyze.")
        print("-"*50)
        # --- END OF BLOCK ---

        return results

    def generate_report(self, results: Dict, market_ticker: str, start_date: datetime, end_date: datetime) -> str:
        if not results or not results.get('timestamps'):
             return f"No data available for market: {market_ticker}"
        series_ticker = '-'.join(market_ticker.split('-')[:-1])

        # Determine which strategy parameters to show
        if self.config.strategy == 'simple':
            strategy_params = f"""
    Strategy: Simple
    Fixed Spread: {self.config.fixed_spread:.2%}
    Max Position: {self.config.max_position}
    SMA Window: {self.config.sma_window} minutes
    """
        elif self.config.strategy == 'avellaneda':
            strategy_params = f"""
    Strategy: Avellaneda-Stoikov
    Sigma: {self.config.sigma}
    Gamma: {self.config.gamma}
    Min Spread: {self.config.min_spread:.2%}
    """
        else:
            strategy_params = "Strategy: Unknown"

        report = f"""
    KALSHI BACKTEST REPORT
    =====================================
    Series: {series_ticker}
    Market: {market_ticker}
    Window: {start_date.strftime('%Y-%m-%d %H:%M')} to {end_date.strftime('%Y-%m-%d %H:%M')} UTC
    Period: {len(results['timestamps'])} data points
    Initial Capital: ${self.config.initial_capital:,.2f}

    STRATEGY PARAMETERS
    -------------------
    {strategy_params.strip()}

    PERFORMANCE METRICS
    -------------------
    Final PnL: ${results.get('final_pnl', 0):,.2f}
    Return: {(results.get('final_pnl', 0) / self.config.initial_capital) * 100:.2f}%
    Total Fills: {results.get('total_trades', 0)}
    Round-Trip Trades: {results.get('round_trip_trades', 0)}
    Final Position: {results.get('final_position', 0)} contracts
    Win Rate: {results.get('win_rate', 0):.2%}
    Sharpe Ratio: {results.get('sharpe_ratio', 0):.2f}
    Max Drawdown: ${results.get('max_drawdown', 0):,.2f}
    """
        return report.strip()

    # In backtest_engine.py

    def log_results_to_csv(self, results: Dict, market_ticker: str, start_date: datetime, end_date: datetime, log_file: str = "backtest_results_log.csv"):
        """Appends the results of a backtest run to a master CSV log file."""

        # --- DEFINE THE MASTER COLUMN ORDER ---
        header = [
            'run_timestamp', 'market_ticker', 'strategy', 'start_date', 'end_date',
            'final_pnl', 'return_pct', 'win_rate', 'sharpe_ratio', 'max_drawdown',
            'total_fills', 'total_market_trades', 'round_trip_trades', 'final_position',
            'pnl_first_hour', 'pnl_middle', 'pnl_last_hour',
            'sma_window', 'fixed_spread', 'gamma', 'sigma', 'k', 'min_spread',
            'inventory_skew_factor', 'max_position'
        ]

        log_data = {
            'run_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'market_ticker': market_ticker,
            'strategy': self.config.strategy,
            'start_date': start_date.strftime('%Y-%m-%d %H:%M'),
            'end_date': end_date.strftime('%Y-%m-%d %H:%M'),
            'final_pnl': results.get('final_pnl', 0),
            'return_pct': (results.get('final_pnl', 0) / self.config.initial_capital) * 100,
            'win_rate': results.get('win_rate', 0),
            'sharpe_ratio': results.get('sharpe_ratio', 0),
            'max_drawdown': results.get('max_drawdown', 0),
            'total_fills': results.get('total_trades', 0),
            'total_market_trades': results.get('total_market_trades', 0),
            'round_trip_trades': results.get('round_trip_trades', 0),
            'final_position': results.get('final_position', 0),
            'pnl_first_hour': results.get('pnl_first_hour', 0),
            'pnl_middle': results.get('pnl_middle', 0),
            'pnl_last_hour': results.get('pnl_last_hour', 0),
            'sma_window': self.config.sma_window,
            'fixed_spread': self.config.fixed_spread if self.config.strategy == 'simple' else None,
            'gamma': self.config.gamma if self.config.strategy == 'avellaneda' else None,
            'sigma': self.config.sigma if self.config.strategy == 'avellaneda' else None,
            'k': self.config.k if self.config.strategy == 'avellaneda' else None,
            'min_spread': self.config.min_spread if self.config.strategy == 'avellaneda' else None,
            'inventory_skew_factor': self.config.inventory_skew_factor,
            'max_position': self.config.max_position,
        }

        try:
            # Create a DataFrame with the specified column order
            df = pd.DataFrame([log_data], columns=header)

            file_exists = os.path.exists(log_file)

            # Write with header only if the file is new
            df.to_csv(log_file, index=False, header=not file_exists, mode='a')

            self.logger.info(f"Results for {market_ticker} appended to {log_file}")

        except Exception as e:
            self.logger.error(f"Failed to log results to CSV: {e}")
            raise e
            
    def _calculate_trade_pnls(self, trades: List[Trade], final_market_price: float) -> List[float]:
        """
        Processes a flat list of fills into NET PnLs for each round-trip trade.
        """
        if not trades:
            return []

        trade_pnls = []
        current_trip_fills = []
        position = 0

        for fill in trades:
            current_trip_fills.append(fill)
            position_delta = fill.quantity if fill.action == 'buy' else -fill.quantity
            position += position_delta

            if position == 0 and current_trip_fills:
                buy_cost = sum(f.price * f.quantity for f in current_trip_fills if f.action == 'buy')
                sell_proceeds = sum(f.price * f.quantity for f in current_trip_fills if f.action == 'sell')
                # CORRECTED: Include transaction costs
                costs = len(current_trip_fills) * self.config.transaction_cost
                trade_pnls.append(sell_proceeds - buy_cost - costs)
                current_trip_fills = []

        # Handle any remaining open position at the end
        if current_trip_fills:
            buy_cost = sum(f.price * f.quantity for f in current_trip_fills if f.action == 'buy')
            sell_proceeds = sum(f.price * f.quantity for f in current_trip_fills if f.action == 'sell')
            # CORRECTED: Include transaction costs
            costs = len(current_trip_fills) * self.config.transaction_cost
            final_position_value = position * final_market_price
            final_trip_pnl = sell_proceeds + final_position_value - buy_cost - costs
            trade_pnls.append(final_trip_pnl)

        return trade_pnls
    def _calculate_sharpe_ratio(self, round_trip_pnls: List[float]) -> float:
        """Calculates the Sharpe ratio from a list of round-trip trade PnLs."""
        trade_pnls = pd.Series(round_trip_pnls)

        # Handle cases with insufficient trades for a meaningful standard deviation
        if len(trade_pnls) < 2:
            return 0.0

        if trade_pnls.std() == 0:
            # If PnL is positive with no volatility, it's a good return
            return 10.0 if trade_pnls.mean() > 0 else 0.0

        return trade_pnls.mean() / trade_pnls.std()

    def _calculate_max_drawdown(self, pnl_series: pd.Series) -> float:
        if pnl_series.empty: return 0.0
        high_water_mark = pnl_series.cummax()
        drawdown = high_water_mark - pnl_series
        return drawdown.max()

    def _calculate_win_rate(self, round_trip_pnls: List[float]) -> float:
        """Calculates the win rate from a list of round-trip trade PnLs."""
        if not round_trip_pnls:
            return 0.0
        wins = sum(1 for pnl in round_trip_pnls if pnl > 0)
        return wins / len(round_trip_pnls)
