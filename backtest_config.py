from dataclasses import dataclass, field
from datetime import datetime
from typing import List

@dataclass
class BacktestConfig:
    """Configuration for backtesting parameters"""
    # --- Core Parameters ---
    initial_capital: float = 1000.0
    max_position: int = 10
    transaction_cost: float = 0.02
    order_expiration: int = 3600
    position_limit_buffer: float = 0.1
    inventory_skew_factor: float = 0.01
    dt: float = 2.0
    strategy: str = 'avellaneda' # Use the A-S model
    
    # --- Fair Value Model Parameters ---
    sma_window: int = 1
    
    # --- SimpleMarketMaker Parameters ---
    fixed_spread: float = 0.06
    
    # --- AvellanedaMarketMaker Parameters ---
    gamma: float = 0.1
    k: float = 1.5
    sigma: float = 0.01
    T: float = 14400
    min_spread: float = 0.05

@dataclass
class HistoricalTrade:
    """Historical trade record from Kalshi API"""
    timestamp: datetime
    price: float
    side: str
    count: int
    trade_id: str

@dataclass
class MarketData:
    """Market data point for backtesting"""
    timestamp: datetime
    yes_bid: float
    yes_ask: float
    no_bid: float
    no_ask: float
    low: float = 0.0   # Add this line
    high: float = 0.0  # Add this line
    volume: int = 0
    trades: List[HistoricalTrade] = field(default_factory=list)

@dataclass
class Trade:
    """Trade execution record"""
    timestamp: datetime
    action: str
    side: str
    price: float
    quantity: int
    order_id: str

