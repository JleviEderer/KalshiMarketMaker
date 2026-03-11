#!/usr/bin/env python3
"""
Optimal Market Scanner - Find markets with 2-5¢ spreads and good volume
"""

import os
import logging
from typing import List, Dict

from _bootstrap import add_repo_root_to_path

add_repo_root_to_path()

from mm import KalshiTradingAPI

class OptimalMarketScanner:
    def __init__(self):
        self.setup_logging()
        self.api = self.create_api()

    def setup_logging(self):
        logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger('OptimalScanner')

    def create_api(self):
        """Create authenticated API instance"""
        try:
            api = KalshiTradingAPI(
                market_ticker="DUMMY",
                base_url=os.getenv('LIVE_KALSHI_BASE_URL'),
                logger=self.logger,
                mode='live'
            )
            print("✅ API authenticated successfully")
            return api
        except Exception as e:
            print(f"❌ API authentication failed: {e}")
            raise

    def scan_for_optimal_markets(self, max_markets: int = 500) -> List[Dict]:
        """Find markets with optimal spreads (2-5¢) and decent volume"""

        print("🎯 SCANNING FOR OPTIMAL MARKET MAKING OPPORTUNITIES")
        print("=" * 60)
        print("Looking for: 2-5¢ spreads + volume + reasonable prices")

        optimal_markets = []
        markets_scanned = 0
        cursor = None

        while markets_scanned < max_markets:
            try:
                # Get active markets only
                params = {"limit": 100, "status": "open"}
                if cursor:
                    params["cursor"] = cursor

                response = self.api.make_request("GET", "/markets", params=params)
                markets = response.get('markets', [])

                if not markets:
                    print(f"✅ Reached end at {markets_scanned} markets")
                    break

                # Analyze this batch
                batch_optimal = self.filter_optimal_markets(markets)
                optimal_markets.extend(batch_optimal)

                markets_scanned += len(markets)
                cursor = response.get('cursor')

                print(f"📊 Scanned {markets_scanned} markets → {len(optimal_markets)} optimal found")

                # Continue until we have enough or reach limit
                if len(optimal_markets) >= 20:  # Good selection
                    print(f"🎯 Found plenty of options - stopping scan")
                    break

            except Exception as e:
                print(f"❌ Error scanning: {e}")
                break

        # Sort by quality score
        optimal_markets.sort(key=lambda x: x.get('quality_score', 0), reverse=True)

        print(f"✅ Found {len(optimal_markets)} optimal markets from {markets_scanned} scanned")
        return optimal_markets

    def filter_optimal_markets(self, markets: List[Dict]) -> List[Dict]:
        """Filter for markets with optimal trading characteristics"""

        optimal_markets = []

        for market in markets:
            try:
                # Basic requirements
                if market.get('status') != 'open':
                    continue

                # Get pricing data
                yes_bid = market.get('yes_bid', 0)
                yes_ask = market.get('yes_ask', 0)
                no_bid = market.get('no_bid', 0)
                no_ask = market.get('no_ask', 0)

                # Must have valid pricing
                if not all([yes_bid, yes_ask, no_bid, no_ask]):
                    continue

                # Calculate spreads (API returns cents)
                yes_spread = (yes_ask - yes_bid) / 100
                no_spread = (no_ask - no_bid) / 100
                avg_spread = (yes_spread + no_spread) / 2

                # OPTIMAL SPREAD FILTER: 2-5¢ spreads
                if not (0.02 <= avg_spread <= 0.05):
                    continue

                # Calculate mid prices
                yes_mid = ((yes_bid + yes_ask) / 2) / 100
                no_mid = ((no_bid + no_ask) / 2) / 100

                # REASONABLE PRICE FILTER: Avoid extreme prices
                if yes_mid < 0.05 or yes_mid > 0.95:
                    continue

                # VOLUME FILTER: Must have some trading activity
                volume_24h = market.get('volume_24h', 0)
                if volume_24h < 5:  # At least 5 contracts traded
                    continue

                # Calculate quality score
                quality_score = self.calculate_optimal_quality_score(market, avg_spread, volume_24h, yes_mid)

                # Only keep high-quality markets
                if quality_score >= 60:
                    optimal_markets.append({
                        'ticker': market.get('ticker', ''),
                        'title': market.get('title', 'Unknown'),
                        'category': market.get('category', 'Unknown'),
                        'yes_bid': yes_bid / 100,
                        'yes_ask': yes_ask / 100,
                        'yes_mid': yes_mid,
                        'yes_spread': yes_spread,
                        'no_bid': no_bid / 100,
                        'no_ask': no_ask / 100,
                        'no_mid': no_mid,
                        'no_spread': no_spread,
                        'avg_spread': avg_spread,
                        'volume_24h': volume_24h,
                        'open_interest': market.get('open_interest', 0),
                        'quality_score': quality_score,
                        'close_time': market.get('close_time', ''),
                        'last_price': market.get('last_price', 0) / 100 if market.get('last_price') else 0
                    })

            except Exception as e:
                continue  # Skip problematic markets

        return optimal_markets

    def calculate_optimal_quality_score(self, market: Dict, avg_spread: float, volume_24h: int, yes_mid: float) -> float:
        """Calculate quality score optimized for market making"""

        score = 0

        # SPREAD SCORE (40 points) - Sweet spot is 2-5¢
        if 0.03 <= avg_spread <= 0.04:  # Perfect range
            score += 40
        elif 0.025 <= avg_spread <= 0.035:  # Very good
            score += 35
        elif 0.02 <= avg_spread <= 0.05:  # Good
            score += 30
        else:
            score += 15

        # PRICE LEVEL SCORE (20 points) - Avoid extremes
        if 0.2 <= yes_mid <= 0.8:  # Sweet spot
            score += 20
        elif 0.15 <= yes_mid <= 0.85:  # Good
            score += 15
        elif 0.1 <= yes_mid <= 0.9:  # OK
            score += 10
        else:
            score += 5

        # VOLUME SCORE (25 points) - Need decent activity
        if volume_24h >= 100:
            score += 25
        elif volume_24h >= 50:
            score += 20
        elif volume_24h >= 20:
            score += 15
        elif volume_24h >= 10:
            score += 10
        else:
            score += 5

        # OPEN INTEREST SCORE (15 points)
        open_interest = market.get('open_interest', 0)
        if open_interest >= 1000:
            score += 15
        elif open_interest >= 500:
            score += 12
        elif open_interest >= 100:
            score += 8
        else:
            score += 3

        return score

    def print_optimal_results(self, markets: List[Dict]):
        """Print optimal trading opportunities"""

        print(f"\n🏆 TOP OPTIMAL MARKET MAKING OPPORTUNITIES")
        print("=" * 70)

        if not markets:
            print("❌ No optimal markets found")
            print("   Try lowering requirements or use Fed Chairman market")
            return

        for i, market in enumerate(markets[:10], 1):
            print(f"\n{i}. {market['ticker']}")
            print(f"   📝 {market['title'][:60]}...")
            print(f"   📂 {market['category']}")
            print(f"   💰 Yes: {market['yes_bid']:.3f}/{market['yes_ask']:.3f} (spread: {market['yes_spread']:.3f})")
            print(f"   💰 No:  {market['no_bid']:.3f}/{market['no_ask']:.3f} (spread: {market['no_spread']:.3f})")
            print(f"   📊 Vol 24h: {market['volume_24h']:,} | OI: {market['open_interest']:,}")
            print(f"   🎯 Mid: {market['yes_mid']:.3f} | Last: {market['last_price']:.3f}")
            print(f"   ⭐ Quality: {market['quality_score']:.0f}/100")

            if market['close_time']:
                print(f"   ⏰ Closes: {market['close_time']}")

    def generate_optimal_configs(self, markets: List[Dict]):
        """Generate configs optimized for the best markets"""

        print(f"\n📋 OPTIMAL CONFIGS (Top 3 Markets)")
        print("=" * 50)

        if not markets:
            print("No markets to configure")
            return

        for i, market in enumerate(markets[:3], 1):
            ticker = market['ticker']
            spread = market['avg_spread']
            volume = market['volume_24h']

            # Optimize parameters based on market characteristics
            max_position = 5 if volume >= 50 else 3 if volume >= 20 else 2
            min_spread = max(0.005, spread * 0.25)  # 25% of current spread

            # Adjust for market type
            if market['category'].lower() in ['politics', 'elections']:
                sigma = 0.003
                order_expiration = 1800
            elif 'sport' in market['category'].lower():
                sigma = 0.004  
                order_expiration = 1200
            else:
                sigma = 0.002
                order_expiration = 3600

            config_name = f"Optimal_{i}_{ticker.replace('-', '_')}"

            print(f"\n{config_name}:")
            print(f"  api:")
            print(f"    market_ticker: {ticker}")
            print(f"    trade_side: \"yes\"")
            print(f"  market_maker:")
            print(f"    max_position: {max_position}")
            print(f"    order_expiration: {order_expiration}")
            print(f"    gamma: 0.05")
            print(f"    k: 1.5")
            print(f"    sigma: {sigma}")
            print(f"    T: 1800  # 30 minutes")
            print(f"    min_spread: {min_spread:.3f}")
            print(f"    position_limit_buffer: 0.1")
            print(f"    inventory_skew_factor: 0.001")
            print(f"  dt: 2.0")
            print(f"  mode: live")

    def run_optimal_scan(self):
        """Run the optimal market scan"""

        print("🎯 OPTIMAL MARKET SCANNER")
        print("Finding markets with 2-5¢ spreads and good volume")
        print("=" * 60)

        try:
            markets = self.scan_for_optimal_markets(500)
            self.print_optimal_results(markets)
            self.generate_optimal_configs(markets)

            if markets:
                best = markets[0]
                print(f"\n🏆 RECOMMENDED MARKET: {best['ticker']}")
                print(f"   📈 {best['avg_spread']:.3f}¢ spread | {best['volume_24h']} volume | Score: {best['quality_score']:.0f}")
                print(f"   🚀 Ready to trade with config above!")
            else:
                print(f"\n⚠️  No optimal markets found")
                print(f"   Recommendation: Use Fed Chairman market KXFEDCHAIRNOM-29-KW")

            return markets

        except Exception as e:
            print(f"❌ Scanner failed: {e}")
            return []

if __name__ == "__main__":
    scanner = OptimalMarketScanner()
    markets = scanner.run_optimal_scan()
