#!/usr/bin/env python3
"""
Direct test of KXHIGHMIA and related tickers
"""

import requests
import os
from datetime import datetime

def test_direct_ticker():
    """Test KXHIGHMIA and variations directly"""

    base_url = "https://api.elections.kalshi.com/trade-api/v2"

    print("🔍 TESTING KXHIGHMIA AND VARIATIONS")
    print("=" * 50)

    # Test variations of the Miami weather ticker
    test_tickers = [
        'KXHIGHMIA',           # Your original
        'KXHIGHMIA-JUL21',     # With today's date
        'KXHIGHMIA-25JUL21',   # Full date format
        'KXHIGHMIA-210725',    # Different date format
        'KXHIGHMIAAMI',        # Possible variation
        'KXHIGHMIAMI',         # Another variation
        'KXHIGHMIA25',         # With day
    ]

    print("Testing tickers:")
    for ticker in test_tickers:
        print(f"  • {ticker}")

    print("\nResults:")
    print("-" * 30)

    working_tickers = []

    for ticker in test_tickers:
        try:
            # Test the public endpoint (no auth needed)
            url = f"{base_url}/markets/{ticker}"

            print(f"\n🧪 Testing: {ticker}")

            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                market = data.get('market', {})

                if market:
                    title = market.get('title', 'Unknown')
                    status = market.get('status', 'unknown')
                    yes_bid = market.get('yes_bid', 0) / 100
                    yes_ask = market.get('yes_ask', 100) / 100
                    close_time = market.get('close_time', '')

                    print(f"   ✅ SUCCESS!")
                    print(f"   Title: {title}")
                    print(f"   Status: {status}")
                    print(f"   Yes: {yes_bid:.3f}/{yes_ask:.3f}")
                    if close_time:
                        print(f"   Closes: {close_time}")

                    working_tickers.append({
                        'ticker': ticker,
                        'title': title,
                        'status': status,
                        'yes_bid': yes_bid,
                        'yes_ask': yes_ask,
                        'close_time': close_time
                    })
                else:
                    print(f"   ❌ Empty response")

            elif response.status_code == 404:
                print(f"   ❌ 404 - Market not found")
            else:
                print(f"   ❌ HTTP {response.status_code}: {response.text[:100]}")

        except Exception as e:
            print(f"   ❌ Error: {e}")

    # Summary
    print("\n" + "=" * 50)
    print("📊 SUMMARY")
    print("=" * 50)

    if working_tickers:
        print(f"✅ Found {len(working_tickers)} working ticker(s):")

        for market in working_tickers:
            print(f"\n🎯 {market['ticker']}")
            print(f"   {market['title']}")
            print(f"   Status: {market['status']}")
            spread = market['yes_ask'] - market['yes_bid']
            print(f"   Spread: {spread:.3f}")

            if market['close_time']:
                try:
                    close_dt = datetime.fromisoformat(market['close_time'].replace('Z', '+00:00'))
                    now_dt = datetime.now().astimezone()
                    time_left = close_dt - now_dt
                    print(f"   Time left: {str(time_left).split('.')[0]}")
                except:
                    print(f"   Closes: {market['close_time']}")

        # Generate updated config
        best_ticker = working_tickers[0]['ticker']
        print(f"\n📋 UPDATED CONFIG FOR YOUR BOT:")
        print("-" * 30)
        print(f"WeatherMIA-HighTemp:")
        print(f"  api:")
        print(f"    market_ticker: {best_ticker}")
        print(f"    trade_side: \"yes\"")
        print(f"  market_maker:")
        print(f"    max_position: 5")
        print(f"    order_expiration: 28800")
        print(f"    gamma: 0.05")
        print(f"    k: 1.5")
        print(f"    sigma: 0.001")
        print(f"    T: 28800")
        print(f"    min_spread: 0.03")
        print(f"    position_limit_buffer: 0.1")
        print(f"    inventory_skew_factor: 0.001")
        print(f"  dt: 2.0")
        print(f"  mode: live")

    else:
        print("❌ No working tickers found.")
        print("\nPossible reasons:")
        print("• Weather markets for today already settled")
        print("• Markets use different date format")
        print("• Markets created with different naming convention")
        print("\nRecommendations:")
        print("1. Run the quick_market_finder.py to find active weather markets")
        print("2. Check Kalshi website directly for current weather markets")
        print("3. Use other market categories (economics, politics, etc.)")

def test_live_auth_with_ticker():
    """Test using your live API credentials"""

    print(f"\n🔐 TESTING WITH LIVE CREDENTIALS")
    print("=" * 40)

    try:
        from mm import KalshiTradingAPI
        import logging

        # Setup basic logging
        logging.basicConfig(level=logging.WARNING)  # Reduce noise
        logger = logging.getLogger('TickerTest')

        # Test with your live API
        api = KalshiTradingAPI(
            market_ticker="DUMMY",
            base_url=os.getenv('LIVE_KALSHI_BASE_URL'),
            logger=logger,
            mode='live'
        )

        # Test KXHIGHMIA specifically
        print("Testing KXHIGHMIA with authenticated API...")

        try:
            response = api.make_request("GET", "/markets/KXHIGHMIA")
            market = response.get('market', {})

            if market:
                print("✅ KXHIGHMIA exists with live API!")
                print(f"   Title: {market.get('title', 'Unknown')}")
                print(f"   Status: {market.get('status', 'unknown')}")
            else:
                print("❌ KXHIGHMIA not found with live API")

        except Exception as e:
            print(f"❌ Error with live API: {e}")

    except ImportError:
        print("❌ Cannot import mm.py - run this from your workspace directory")
    except Exception as e:
        print(f"❌ Error with live API test: {e}")

if __name__ == "__main__":
    test_direct_ticker()
    test_live_auth_with_ticker()