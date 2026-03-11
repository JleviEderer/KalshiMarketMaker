from dataclasses import dataclass, field
from datetime import datetime
from typing import List

@dataclass
class BacktestConfig:
    """Configuration for backtesting parameters"""
    initial_capital: float = 1000.0
    max_position: int = 5
    transaction_cost: float = 1.0
    gamma: float = 0.1
    k: float = 1.5
    sigma: float = 0.001
    T: float = 28800
    order_expiration: int = 3600
    min_spread: float = 0.02
    position_limit_buffer: float = 0.1
    inventory_skew_factor: float = 0.001
    dt: float = 2.0

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
    volume: int = 0
    yes_bid_low: float | None = None
    yes_bid_high: float | None = None
    yes_ask_low: float | None = None
    yes_ask_high: float | None = None
    no_bid_low: float | None = None
    no_bid_high: float | None = None
    no_ask_low: float | None = None
    no_ask_high: float | None = None
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
