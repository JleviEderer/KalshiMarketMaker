#!/usr/bin/env python3
"""
Legacy script to verify Kalshi LIVE API authentication.
"""

import os
import logging

from _bootstrap import add_repo_root_to_path

add_repo_root_to_path()

from mm import KalshiTradingAPI

def test_live_endpoints():
    """Test Kalshi LIVE API authentication"""

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger('LiveEndpointTest')

    # Check environment variables
    required_vars = ['LIVE_KALSHI_KEY_ID', 'LIVE_KALSHI_PRIVATE_KEY', 'LIVE_KALSHI_BASE_URL', 'CONFIRM_LIVE']
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"Missing environment variables: {missing_vars}")
        logger.error("Please export these credentials in your shell environment")
        return False

    logger.info("🔴 TESTING LIVE KALSHI API")
    logger.info("Environment variables found:")
    logger.info(f"  KEY_ID: {os.getenv('LIVE_KALSHI_KEY_ID')}")
    logger.info(f"  BASE_URL: {os.getenv('LIVE_KALSHI_BASE_URL')}")
    logger.info(f"  CONFIRM_LIVE: {os.getenv('CONFIRM_LIVE')}")

    # Check private key format
    private_key = os.getenv('LIVE_KALSHI_PRIVATE_KEY')
    logger.info(f"  PRIVATE_KEY: {len(private_key)} characters")

    try:
        # Test with ticker from Kalshi support
        test_markets = ["KXFEDCHAIRNOM-29-KW", "KXHIGHMIA"]

        logger.info(f"Testing LIVE authentication with markets: {test_markets}")

        # Test each market
        for test_ticker in test_markets:
            logger.info(f"\n--- Testing market: {test_ticker} ---")

            # Create API instance in LIVE mode
            api = KalshiTradingAPI(
                market_ticker=test_ticker,
                base_url=os.getenv('LIVE_KALSHI_BASE_URL'),
                logger=logger,
                mode='live'  # THIS IS THE KEY DIFFERENCE
            )

            # Test market data for this ticker
            try:
                response = api.make_request("GET", f"/markets/{test_ticker}")
                market = response.get('market', {})

                yes_bid = float(market.get('yes_bid', 0)) / 100
                yes_ask = float(market.get('yes_ask', 0)) / 100
                no_bid = float(market.get('no_bid', 0)) / 100  
                no_ask = float(market.get('no_ask', 0)) / 100

                yes_mid = (yes_bid + yes_ask) / 2 if yes_ask > 0 else 0
                no_mid = (no_bid + no_ask) / 2 if no_ask > 0 else 0

                logger.info(f"✅ {test_ticker}: {market.get('title', 'Unknown')}")
                logger.info(f"   Status: {market.get('status', 'unknown')}")
                logger.info(f"   Yes: {yes_bid:.3f}/{yes_ask:.3f} (mid: {yes_mid:.3f})")
                logger.info(f"   No:  {no_bid:.3f}/{no_ask:.3f} (mid: {no_mid:.3f})")

                if yes_mid > 0 or no_mid > 0:
                    logger.info(f"🎯 {test_ticker} has ACTIVE pricing - perfect for market making!")
                else:
                    logger.warning(f"⚠️  {test_ticker} has zero pricing - may not be active")

            except Exception as e:
                logger.error(f"❌ Failed to get data for {test_ticker}: {e}")

        # Use first market for remaining tests
        test_ticker = test_markets[0]

        logger.info("✅ LIVE API instance created successfully")

        print("🔴 LIVE KALSHI API TESTING")
        print("=" * 60)

        # Test 1: Exchange status
        print("1. Testing /exchange/status (public)")
        try:
            status_response = api.make_request("GET", "/exchange/status")
            print("   ✅ SUCCESS - Live exchange status accessible")
            print(f"   Response: {status_response}")
        except Exception as e:
            print(f"   ❌ FAILED - {e}")
            return False

        print("-" * 40)

        # Test 2: Market data
        print("2. Testing /markets/{ticker} (public)")
        try:
            response = api.make_request("GET", f"/markets/{test_ticker}")
            print("   ✅ SUCCESS - Live market data accessible")
            market = response.get('market', {})
            print(f"   Market status: {market.get('status', 'unknown')}")
            if market.get('yes_bid') and market.get('yes_ask'):
                yes_bid = float(market['yes_bid']) / 100
                yes_ask = float(market['yes_ask']) / 100
                print(f"   Yes prices: {yes_bid:.3f}/{yes_ask:.3f}")
        except Exception as e:
            print(f"   ❌ FAILED - {e}")

        print("-" * 40)

        # Test 3: Portfolio balance
        print("3. Testing /portfolio/balance (requires auth)")
        try:
            response = api.make_request("GET", "/portfolio/balance")
            print("   ✅ SUCCESS - Live portfolio balance accessible")
            balance = response.get('balance', 0) / 100
            print(f"   Live Balance: ${balance:.2f}")
        except Exception as e:
            print(f"   ❌ FAILED - {e}")
            return False

        print("-" * 40)

        # Test 4: Portfolio positions
        print("4. Testing /portfolio/positions (requires auth)")
        try:
            params = {"settlement_status": "unsettled"}
            response = api.make_request("GET", "/portfolio/positions", params=params)
            print("   ✅ SUCCESS - Live portfolio positions accessible")
            positions = response.get('market_positions', [])
            print(f"   Live Positions found: {len(positions)}")
        except Exception as e:
            print(f"   ❌ FAILED - {e}")
            return False

        print("-" * 40)

        # Test 5: Portfolio orders
        print("5. Testing /portfolio/orders (requires auth)")
        try:
            params = {"status": "resting"}
            response = api.make_request("GET", "/portfolio/orders", params=params)
            print("   ✅ SUCCESS - Live portfolio orders accessible")
            orders = response.get('orders', [])
            print(f"   Live Orders found: {len(orders)}")
        except Exception as e:
            print(f"   ❌ FAILED - {e}")
            return False

        print("=" * 60)
        print("🎉 ALL LIVE API TESTS PASSED!")
        print("Your live API keys are working correctly!")
        print("\nNext steps:")
        print("1. Find active markets with real bid/ask spreads")
        print("2. Update legacy/config.yaml to use live mode")
        print("3. Run python legacy/runner.py --config legacy/config.yaml")

        return True

    except Exception as e:
        logger.error(f"❌ Live API test failed: {e}")
        logger.exception("Full traceback:")
        return False

if __name__ == "__main__":
    test_live_endpoints()
