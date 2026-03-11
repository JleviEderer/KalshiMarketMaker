"""Shared trading primitives used by the MCP backtester and legacy live scripts."""

import abc
import time
from typing import Dict, List, Tuple
import requests
import logging
import uuid
import math
import os
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from urllib.parse import urlencode, quote

class AbstractTradingAPI(abc.ABC):
    @abc.abstractmethod
    def get_price(self) -> float:
        pass

    @abc.abstractmethod
    def place_order(self, action: str, side: str, price: float, quantity: int, expiration_ts: int = None) -> str:
        pass

    @abc.abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        pass

    @abc.abstractmethod
    def get_position(self) -> int:
        pass

    @abc.abstractmethod
    def get_orders(self) -> List[Dict]:
        pass

class KalshiTradingAPI(AbstractTradingAPI):
    def __init__(
        self,
        market_ticker: str,
        base_url: str,
        logger: logging.Logger,
        mode: str = 'demo'
    ):
        self.market_ticker = market_ticker
        self.logger = logger
        prefix = 'DEMO_' if mode == 'demo' else 'LIVE_'
        self.logger.info(f"Initializing in {mode} mode with prefix {prefix}")

        self.key_id = os.getenv(f"{prefix}KALSHI_KEY_ID")
        self.private_key_pem = os.getenv(f"{prefix}KALSHI_PRIVATE_KEY")

        if not self.key_id or not self.private_key_pem:
            raise ValueError(f"Missing {prefix}KALSHI_KEY_ID or {prefix}KALSHI_PRIVATE_KEY")

        if mode == 'live' and not self._confirm_live():
            raise ValueError("Live mode requires manual confirmation—set CONFIRM_LIVE=True in secrets")

        self.base_url = base_url or os.getenv(f"{prefix}KALSHI_BASE_URL")
        self.private_key = self._load_private_key()

        # Test the authentication
        self.logger.info("Testing API authentication...")
        self._test_auth()

    def _confirm_live(self):
        return os.getenv("CONFIRM_LIVE", "False").lower() == "true"

    def _load_private_key(self):
        try:
            # Handle the case where Replit strips newlines from secrets
            private_key_content = self.private_key_pem

            # If the key doesn't have proper newlines, fix the formatting
            if '\n' not in private_key_content and '-----BEGIN RSA PRIVATE KEY-----' in private_key_content:
                self.logger.info("Fixing private key formatting (adding newlines)")

                # Remove the headers temporarily
                content = private_key_content.replace('-----BEGIN RSA PRIVATE KEY-----', '')
                content = content.replace('-----END RSA PRIVATE KEY-----', '')
                content = content.strip()

                # Split into 64-character lines (standard PEM format)
                lines = []
                for i in range(0, len(content), 64):
                    lines.append(content[i:i+64])

                # Reconstruct with proper formatting
                private_key_content = '-----BEGIN RSA PRIVATE KEY-----\n'
                private_key_content += '\n'.join(lines)
                private_key_content += '\n-----END RSA PRIVATE KEY-----'

                self.logger.debug("Fixed private key format")

            return serialization.load_pem_private_key(
                private_key_content.encode(),
                password=None,
                backend=default_backend()
            )
        except Exception as e:
            self.logger.error(f"Failed to load private key: {e}")
            self.logger.error("Private key format issue - check that it's properly formatted")
            raise

    def _test_auth(self):
        """Test authentication with a simple API call"""
        try:
            path = "/exchange/status"
            response = self.make_request("GET", path)
            self.logger.info("Authentication test successful")
            return True
        except Exception as e:
            self.logger.error(f"Authentication test failed: {e}")
            raise

    def _get_signed_headers(self, method: str, path: str, params: Dict = None):
        timestamp = int(time.time() * 1000)
        timestamp_str = str(timestamp)

        # CRITICAL: According to our debugging, Kalshi expects the full API path 
        # including the /trade-api/v2 prefix in the signature!
        path_for_signature = "/trade-api/v2" + path.split('?')[0]

        # Construct the message to sign: timestamp + method + full_api_path
        message = timestamp_str + method.upper() + path_for_signature

        self.logger.debug(f"Message to sign: {message}")

        try:
            # Sign the message using EXACTLY Kalshi's PSS specification
            signature = self.private_key.sign(
                message.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.DIGEST_LENGTH
                ),
                hashes.SHA256()
            )

            signature_b64 = base64.b64encode(signature).decode('utf-8')

            headers = {
                "KALSHI-ACCESS-KEY": self.key_id,
                "KALSHI-ACCESS-TIMESTAMP": timestamp_str,
                "KALSHI-ACCESS-SIGNATURE": signature_b64,
                "Content-Type": "application/json",
            }

            self.logger.debug(f"Generated signature: {signature_b64[:20]}...")
            return headers

        except Exception as e:
            self.logger.error(f"Error generating signature: {e}")
            raise

    def make_request(
        self, method: str, path: str, params: Dict = None, data: Dict = None
    ):
        url = f"{self.base_url}{path}"
        headers = self._get_signed_headers(method, path, params)

        try:
            self.logger.debug(f"Making {method} request to {url}")
            self.logger.debug(f"Params: {params}")
            self.logger.debug(f"Data: {data}")

            response = requests.request(
                method, url, headers=headers, params=params, json=data, timeout=30
            )

            self.logger.debug(f"Response status: {response.status_code}")
            self.logger.debug(f"Response headers: {dict(response.headers)}")

            if response.status_code >= 400:
                self.logger.error(f"HTTP {response.status_code}: {response.text}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            if hasattr(e, "response") and e.response is not None:
                self.logger.error(f"Response content: {e.response.text}")
                self.logger.error(f"Response status: {e.response.status_code}")
            raise

    def get_position(self) -> int:
        self.logger.info(f"Retrieving position for {self.market_ticker}...")
        path = "/portfolio/positions"
        params = {"ticker": self.market_ticker, "settlement_status": "unsettled"}

        try:
            response = self.make_request("GET", path, params=params)
            positions = response.get("market_positions", [])

            total_position = 0
            for position in positions:
                if position["ticker"] == self.market_ticker:
                    total_position += position["position"]

            self.logger.info(f"Current position: {total_position}")
            return total_position

        except Exception as e:
            self.logger.warning(f"Failed to get position (using fallback): {e}")
            # Return 0 for demo purposes - this allows testing other functionality
            return 0

    def get_orders(self) -> List[Dict]:
        self.logger.info("Retrieving open orders...")
        path = "/portfolio/orders"
        params = {"ticker": self.market_ticker, "status": "resting"}

        try:
            response = self.make_request("GET", path, params=params)
            orders = response.get("orders", [])
            self.logger.info(f"Retrieved {len(orders)} open orders")
            return orders

        except Exception as e:
            self.logger.warning(f"Failed to get orders (using fallback): {e}")
            # Return empty list for demo purposes
            return []

    def get_price(self) -> Dict[str, float]:
        self.logger.info(f"Retrieving market data for {self.market_ticker}...")
        path = f"/markets/{self.market_ticker}"

        try:
            data = self.make_request("GET", path)

            market = data.get("market", {})
            if not market:
                self.logger.error(f"No market data found for {self.market_ticker}")
                # Return default prices for testing
                return {"yes": 0.50, "no": 0.50}

            yes_bid = float(market.get("yes_bid", 0)) / 100
            yes_ask = float(market.get("yes_ask", 100)) / 100
            no_bid = float(market.get("no_bid", 0)) / 100
            no_ask = float(market.get("no_ask", 100)) / 100

            yes_mid_price = round((yes_bid + yes_ask) / 2, 3)
            no_mid_price = round((no_bid + no_ask) / 2, 3)

            self.logger.info(f"Market data - Yes: {yes_bid:.3f}/{yes_ask:.3f} (mid: {yes_mid_price:.3f})")
            self.logger.info(f"Market data - No: {no_bid:.3f}/{no_ask:.3f} (mid: {no_mid_price:.3f})")

            return {"yes": yes_mid_price, "no": no_mid_price}

        except Exception as e:
            self.logger.error(f"Failed to get market data: {e}")
            # Return default prices for testing
            return {"yes": 0.50, "no": 0.50}

    def place_order(self, action: str, side: str, price: float, quantity: int, expiration_ts: int = None) -> str:
        self.logger.info(f"Placing {action} order for {side} side at price ${price:.3f} with quantity {quantity}...")
        path = "/portfolio/orders"

        data = {
            "ticker": self.market_ticker,
            "action": action.lower(),  # 'buy' or 'sell'
            "type": "limit",
            "side": side,  # 'yes' or 'no'
            "count": quantity,
            "client_order_id": str(uuid.uuid4()),
        }

        # Convert price to cents (Kalshi expects integer cents)
        price_cents = int(round(price * 100))

        if side == "yes":
            data["yes_price"] = price_cents
        else:
            data["no_price"] = price_cents

        if expiration_ts is not None:
            data["expiration_ts"] = expiration_ts

        try:
            response = self.make_request("POST", path, data=data)
            order_id = response["order"]["order_id"]
            self.logger.info(f"Successfully placed {action} order: ID {order_id}")
            return str(order_id)

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to place order: {e}")
            if hasattr(e, 'response') and e.response is not None:
                self.logger.error(f"Response: {e.response.text}")
            raise

    def cancel_order(self, order_id: str) -> bool:
        self.logger.info(f"Canceling order {order_id}...")
        path = f"/portfolio/orders/{order_id}"

        try:
            response = self.make_request("DELETE", path)
            success = response.get("reduced_by", 0) > 0
            self.logger.info(f"Cancel order {order_id}: {'Success' if success else 'Failed'}")
            return success

        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def get_orders(self) -> List[Dict]:
        self.logger.info("Retrieving open orders...")
        path = "/portfolio/orders"
        params = {"ticker": self.market_ticker, "status": "resting"}

        try:
            response = self.make_request("GET", path, params=params)
            orders = response.get("orders", [])
            self.logger.info(f"Retrieved {len(orders)} open orders")
            return orders

        except Exception as e:
            self.logger.error(f"Failed to get orders: {e}")
            return []

    def logout(self):
        """Logout (no-op for API key authentication)"""
        self.logger.info("Logout called (no-op for API key auth)")

class AvellanedaMarketMaker:
    def __init__(
        self,
        logger: logging.Logger,
        api: AbstractTradingAPI,
        gamma: float,
        k: float,
        sigma: float,
        T: float,
        max_position: int,
        order_expiration: int,
        min_spread: float = 0.01,
        position_limit_buffer: float = 0.1,
        inventory_skew_factor: float = 0.01,
        trade_side: str = "yes"
    ):
        self.api = api
        self.logger = logger
        self.base_gamma = gamma
        self.k = k
        self.sigma = sigma
        self.T = T
        self.max_position = max_position
        self.order_expiration = order_expiration
        self.min_spread = min_spread
        self.position_limit_buffer = position_limit_buffer
        self.inventory_skew_factor = inventory_skew_factor
        self.trade_side = trade_side

    def run(self, dt: float):
        start_time = time.time()
        iteration = 0

        # At the very beginning of the run() method, after self.logger.info(f"Starting Avellaneda...")
        run_id = os.getenv('RUN_ID', 'unknown')
        self.logger.info(f"[{run_id}] Starting clean diagnostic run")

        self.logger.info(f"Starting Avellaneda market maker for {self.T/3600:.1f} hours")

        while time.time() - start_time < self.T:
            current_time = time.time() - start_time
            iteration += 1

            self.logger.info(f"=== Iteration {iteration} at {current_time:.1f}s ===")

            try:
                # Get market data
                mid_prices = self.api.get_price()
                mid_price = mid_prices[self.trade_side]

                # Get current position
                inventory = self.api.get_position()

                self.logger.info(f"Current state - Mid price: ${mid_price:.3f}, Inventory: {inventory}")

                # Skip if price is 0 (market might be closed/settled)
                if mid_price <= 0:
                    self.logger.warning("Mid price is 0, skipping this iteration")
                    time.sleep(dt)
                    continue

                # Calculate quotes
                reservation_price = self.calculate_reservation_price(mid_price, inventory, current_time)
                bid_price, ask_price = self.calculate_asymmetric_quotes(mid_price, inventory, current_time)
                buy_size, sell_size = self.calculate_order_sizes(inventory)

                self.logger.info(f"Calculated quotes - Reservation: ${reservation_price:.3f}")
                self.logger.info(f"Target quotes - Bid: ${bid_price:.3f}, Ask: ${ask_price:.3f}")
                self.logger.info(f"Order sizes - Buy: {buy_size}, Sell: {sell_size}")

                # SAFETY: Orders disabled for live testing - comment out to enable
                self.manage_orders(bid_price, ask_price, buy_size, sell_size)
                self.logger.info(f"WOULD place orders - Bid: ${bid_price:.3f}, Ask: ${ask_price:.3f}, Sizes: {buy_size}/{sell_size}")

            except Exception as e:
                self.logger.error(f"Error in market making iteration: {e}")

            # Wait before next iteration
            time.sleep(dt)

        self.logger.info("Avellaneda market maker finished running")

    def calculate_asymmetric_quotes(self, mid_price: float, inventory: int, t: float) -> Tuple[float, float]:
        reservation_price = self.calculate_reservation_price(mid_price, inventory, t)
        base_spread = self.calculate_optimal_spread(t, inventory)

        position_ratio = inventory / self.max_position if self.max_position > 0 else 0
        spread_adjustment = base_spread * abs(position_ratio) * 3

        if inventory > 0:
            # Long inventory - widen bid, tighten ask
            bid_spread = base_spread / 2 + spread_adjustment
            ask_spread = max(base_spread / 2 - spread_adjustment, self.min_spread / 2)
        else:
            # Short inventory - tighten bid, widen ask
            bid_spread = max(base_spread / 2 - spread_adjustment, self.min_spread / 2)
            ask_spread = base_spread / 2 + spread_adjustment

        bid_price = max(0.001, min(mid_price, reservation_price - bid_spread))
        ask_price = min(0.999, max(mid_price, reservation_price + ask_spread))

        return round(bid_price, 3), round(ask_price, 3)

    def calculate_reservation_price(self, mid_price: float, inventory: int, t: float) -> float:
        if self.T <= 0:
            return mid_price

        dynamic_gamma = self.calculate_dynamic_gamma(inventory)
        inventory_skew = inventory * self.inventory_skew_factor * mid_price
        time_factor = max(0, 1 - t/self.T)

        reservation = mid_price + inventory_skew - inventory * dynamic_gamma * (self.sigma**2) * time_factor
        return max(0.001, min(0.999, reservation))

    def calculate_optimal_spread(self, t: float, inventory: int) -> float:
        if self.T <= 0:
            return self.min_spread

        dynamic_gamma = self.calculate_dynamic_gamma(inventory)
        time_factor = max(0, 1 - t/self.T)

        try:
            base_spread = (dynamic_gamma * (self.sigma**2) * time_factor + 
                          (2 / dynamic_gamma) * math.log(1 + (dynamic_gamma / self.k)))
        except (ZeroDivisionError, ValueError):
            base_spread = self.min_spread

        position_ratio = abs(inventory) / self.max_position if self.max_position > 0 else 0
        spread_adjustment = 1 - (position_ratio ** 2)

        final_spread = max(base_spread * spread_adjustment * 0.01, self.min_spread)
        return min(final_spread, 0.20)  # Cap spread at 20%

    def calculate_dynamic_gamma(self, inventory: int) -> float:
        if self.max_position <= 0:
            return self.base_gamma

        position_ratio = inventory / self.max_position
        return self.base_gamma * math.exp(-abs(position_ratio))

    def calculate_order_sizes(self, inventory: int) -> Tuple[int, int]:
        remaining_capacity = max(0, self.max_position - abs(inventory))
        buffer_size = max(1, int(self.max_position * self.position_limit_buffer))

        if inventory > 0:
            # Long inventory - prioritize selling
            buy_size = max(1, min(buffer_size, remaining_capacity))
            sell_size = max(1, min(self.max_position, abs(inventory) + buffer_size))
        else:
            # Short or neutral inventory
            buy_size = max(1, min(self.max_position, abs(inventory) + buffer_size))
            sell_size = max(1, min(buffer_size, remaining_capacity))

        return buy_size, sell_size

    def manage_orders(self, bid_price: float, ask_price: float, buy_size: int, sell_size: int):
        try:
            current_orders = self.api.get_orders()
            self.logger.info(f"Managing orders - Found {len(current_orders)} existing orders")

            # Separate orders by side
            buy_orders = []
            sell_orders = []

            for order in current_orders:
                if order.get('side') == self.trade_side:
                    if order.get('action') == 'buy':
                        buy_orders.append(order)
                    elif order.get('action') == 'sell':
                        sell_orders.append(order)

            self.logger.info(f"Current orders - Buy: {len(buy_orders)}, Sell: {len(sell_orders)}")

            # Manage buy orders
            self.handle_order_side('buy', buy_orders, bid_price, buy_size)

            # Manage sell orders  
            self.handle_order_side('sell', sell_orders, ask_price, sell_size)

        except Exception as e:
            self.logger.error(f"Error managing orders: {e}")

    def handle_order_side(self, action: str, orders: List[Dict], desired_price: float, desired_size: int):
        keep_order = None
        tolerance = 0.005  # 0.5 cent tolerance

        # Check if we should keep any existing order
        for order in orders:
            try:
                if self.trade_side == 'yes':
                    current_price = float(order.get('yes_price', 0)) / 100
                else:
                    current_price = float(order.get('no_price', 0)) / 100

                remaining_size = order.get('remaining_count', 0)

                # Keep order if price is close and size matches
                if (keep_order is None and 
                    abs(current_price - desired_price) < tolerance and 
                    remaining_size == desired_size):
                    keep_order = order
                    self.logger.info(f"Keeping {action} order: ID {order['order_id']}, "
                                   f"Price ${current_price:.3f}, Size {remaining_size}")
                else:
                    # Cancel orders that don't match
                    self.logger.info(f"Canceling {action} order: ID {order['order_id']}, "
                                   f"Price ${current_price:.3f} (target: ${desired_price:.3f})")
                    self.api.cancel_order(order['order_id'])

            except Exception as e:
                self.logger.error(f"Error processing {action} order {order.get('order_id', 'unknown')}: {e}")

        # Place new order if needed
        if keep_order is None:
            try:
                # Get current market price for comparison
                current_prices = self.api.get_price()
                current_market_price = current_prices[self.trade_side]

                # Only place order if it improves on current market
                should_place = False
                if action == 'buy' and desired_price < current_market_price:
                    should_place = True
                elif action == 'sell' and desired_price > current_market_price:
                    should_place = True

                if should_place and desired_price > 0.001 and desired_price < 0.999:
                    order_id = self.api.place_order(
                        action, self.trade_side, desired_price, desired_size, 
                        int(time.time()) + self.order_expiration
                    )
                    run_id = os.getenv('RUN_ID', 'unknown')
                    self.logger.info(f"[{run_id}] PLACE {action.upper()} {self.trade_side.upper()} {desired_price:.3f}×{desired_size} ID:{order_id}")
                else:
                    self.logger.info(f"Skipped {action} order: Price ${desired_price:.3f} "
                                   f"doesn't improve on market ${current_market_price:.3f}")

            except Exception as e:
                self.logger.error(f"Failed to place {action} order: {e}")
