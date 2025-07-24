#!/usr/bin/env python3
"""
Test script to verify Kalshi API authentication
"""

import os
import logging
from mm import KalshiTradingAPI

def test_kalshi_auth():
    """Test Kalshi API authentication"""

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger('AuthTest')

    # Note: No load_dotenv() needed for Replit secrets

    # Check environment variables
    required_vars = ['DEMO_KALSHI_KEY_ID', 'DEMO_KALSHI_PRIVATE_KEY', 'DEMO_KALSHI_BASE_URL']
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"Missing environment variables: {missing_vars}")
        logger.error("Please add these as Replit secrets (lock icon in sidebar)")
        return False

    logger.info("Environment variables found:")
    logger.info(f"  KEY_ID: {os.getenv('DEMO_KALSHI_KEY_ID')}")
    logger.info(f"  BASE_URL: {os.getenv('DEMO_KALSHI_BASE_URL')}")

    # Check private key format
    private_key = os.getenv('DEMO_KALSHI_PRIVATE_KEY')
    logger.info(f"  PRIVATE_KEY: {len(private_key)} characters")

    if not private_key.startswith('-----BEGIN RSA PRIVATE KEY-----'):
        logger.error("❌ Private key doesn't start with proper header")
        return False

    if not private_key.endswith('-----END RSA PRIVATE KEY-----'):
        logger.error("❌ Private key doesn't end with proper footer")
        return False

    # Check if it has newlines OR spaces (Replit sometimes strips newlines)
    if '\n' not in private_key and ' ' not in private_key:
        logger.error("❌ Private key appears to be malformed (no separators)")
        return False

    if '\n' not in private_key:
        logger.warning("⚠️  Private key missing newlines, but code will attempt to fix this")
    else:
        logger.info("✅ Private key format looks correct")

    logger.info("✅ Private key format acceptable (will be auto-fixed if needed)")

    try:
        # Test with a simple market ticker
        test_ticker = "KXQUICKSETTLE-25JUL21H0100-2"

        logger.info(f"Testing authentication with market: {test_ticker}")

        # Create API instance
        api = KalshiTradingAPI(
            market_ticker=test_ticker,
            base_url=os.getenv('DEMO_KALSHI_BASE_URL'),
            logger=logger,
            mode='demo'
        )

        logger.info("✅ API instance created successfully")

        # Test basic API calls
        logger.info("Testing exchange status...")
        try:
            status_response = api.make_request("GET", "/exchange/status")
            logger.info(f"✅ Exchange status: {status_response}")
        except Exception as e:
            logger.error(f"❌ Exchange status failed: {e}")
            return False

        logger.info("Testing market data...")
        try:
            prices = api.get_price()
            logger.info(f"✅ Market prices: {prices}")
        except Exception as e:
            logger.error(f"❌ Market data failed: {e}")
            # Don't return False here as market might not exist

        logger.info("Testing position data...")
        try:
            position = api.get_position()
            logger.info(f"✅ Current position: {position}")
        except Exception as e:
            logger.error(f"❌ Position data failed: {e}")
            return False

        logger.info("Testing orders data...")
        try:
            orders = api.get_orders()
            logger.info(f"✅ Current orders: {len(orders)} orders")
        except Exception as e:
            logger.error(f"❌ Orders data failed: {e}")
            return False

        logger.info("🎉 All authentication tests passed!")
        return True

    except Exception as e:
        logger.error(f"❌ Authentication test failed: {e}")
        logger.exception("Full traceback:")
        return False

def test_market_exists():
    """Test if the configured markets exist"""

    logger = logging.getLogger('MarketTest')

    # Test markets from your config
    test_markets = [
        "KXQUICKSETTLE-25JUL21H0100-2",
        "KXQUICKSETTLE-25JUL21H0100-3"
    ]

    try:
        # Create API instance with first market
        api = KalshiTradingAPI(
            market_ticker=test_markets[0],
            base_url=os.getenv('DEMO_KALSHI_BASE_URL'),
            logger=logger,
            mode='demo'
        )

        for market in test_markets:
            logger.info(f"Testing market: {market}")
            try:
                response = api.make_request("GET", f"/markets/{market}")
                if response.get('market'):
                    logger.info(f"✅ Market {market} exists and is accessible")
                    market_data = response['market']
                    logger.info(f"   Status: {market_data.get('status', 'unknown')}")
                    logger.info(f"   Yes: {market_data.get('yes_bid', 0)/100:.3f}/{market_data.get('yes_ask', 0)/100:.3f}")
                else:
                    logger.warning(f"⚠️  Market {market} response has no market data")
            except Exception as e:
                logger.error(f"❌ Market {market} failed: {e}")

    except Exception as e:
        logger.error(f"Failed to test markets: {e}")

if __name__ == "__main__":
    print("🔧 Testing Kalshi API Authentication...")
    print("=" * 50)

    success = test_kalshi_auth()

    if success:
        print("\n🔧 Testing Market Availability...")
        print("=" * 50)
        test_market_exists()

        print("\n🎉 Authentication working! You can now run your trading bot.")
        print("\nNext steps:")
        print("1. Replace your mm.py file with the fixed version")
        print("2. Replace your runner.py file with the fixed version")  
        print("3. Run: python runner.py --config config.yaml")
    else:
        print("\n❌ Authentication failed. Please check your API keys and try again.")
        print("\nTroubleshooting:")
        print("1. Verify your DEMO_KALSHI_KEY_ID is correct in Replit secrets")
        print("2. Verify your DEMO_KALSHI_PRIVATE_KEY has proper newlines")
        print("3. Make sure you're using Replit secrets, not a .env file")
        print("4. Restart your Repl after updating secrets")

def test_market_exists():
    """Test if the configured markets exist"""

    logger = logging.getLogger('MarketTest')

    # Test markets from your config
    test_markets = [
        "KXQUICKSETTLE-25JUL21H0100-2",
        "KXQUICKSETTLE-25JUL21H0100-3"
    ]

    try:
        # Create API instance with first market
        api = KalshiTradingAPI(
            market_ticker=test_markets[0],
            base_url=os.getenv('DEMO_KALSHI_BASE_URL'),
            logger=logger,
            mode='demo'
        )

        for market in test_markets:
            logger.info(f"Testing market: {market}")
            try:
                response = api.make_request("GET", f"/markets/{market}")
                if response.get('market'):
                    logger.info(f"✅ Market {market} exists and is accessible")
                    market_data = response['market']
                    logger.info(f"   Status: {market_data.get('status', 'unknown')}")
                    logger.info(f"   Yes: {market_data.get('yes_bid', 0)/100:.3f}/{market_data.get('yes_ask', 0)/100:.3f}")
                else:
                    logger.warning(f"⚠️  Market {market} response has no market data")
            except Exception as e:
                logger.error(f"❌ Market {market} failed: {e}")

    except Exception as e:
        logger.error(f"Failed to test markets: {e}")

if __name__ == "__main__":
    print("🔧 Testing Kalshi API Authentication...")
    print("=" * 50)

    success = test_kalshi_auth()

    if success:
        print("\n🔧 Testing Market Availability...")
        print("=" * 50)
        test_market_exists()

        print("\n🎉 Authentication working! You can now run your trading bot.")
        print("\nNext steps:")
        print("1. Replace the fixed mm.py file with your current one")
        print("2. Replace the fixed runner.py file with your current one")  
        print("3. Run: python runner.py --config config.yaml")
    else:
        print("\n❌ Authentication failed. Please check your API keys and try again.")
        print("\nTroubleshooting:")
        print("1. Verify your DEMO_KALSHI_KEY_ID is correct")
        print("2. Verify your DEMO_KALSHI_PRIVATE_KEY is properly formatted")
        print("3. Check that your .env file is in the correct directory")
        print("4. Ensure you're using the demo environment")