import argparse
import logging
from concurrent.futures import ThreadPoolExecutor
import yaml
import os
from typing import Dict

# Note: No need for load_dotenv() when using Replit secrets

# Import from the fixed mm.py file
from mm import KalshiTradingAPI, AvellanedaMarketMaker

def load_config(config_file):
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)

def create_api(api_config, logger, mode='demo'):
    """Create Kalshi API instance"""
    base_url_key = f"{mode.upper()}_KALSHI_BASE_URL"
    base_url = os.getenv(base_url_key)

    if not base_url:
        # Fallback URLs
        if mode == 'demo':
            base_url = "https://demo-api.kalshi.co/trade-api/v2"
        else:
            base_url = "https://trading-api.kalshi.com/trade-api/v2"

    logger.info(f"Using base URL: {base_url}")

    return KalshiTradingAPI(
        market_ticker=api_config['market_ticker'],
        base_url=base_url,
        logger=logger,
        mode=mode
    )

def create_market_maker(mm_config, api, logger):
    """Create market maker instance"""
    return AvellanedaMarketMaker(
        logger=logger,
        api=api,
        gamma=mm_config.get('gamma', 0.1),
        k=mm_config.get('k', 1.5),
        sigma=mm_config.get('sigma', 0.001),  # Fixed default
        T=mm_config.get('T', 3600),
        max_position=mm_config.get('max_position', 5),
        order_expiration=mm_config.get('order_expiration', 3600),
        min_spread=mm_config.get('min_spread', 0.01),
        position_limit_buffer=mm_config.get('position_limit_buffer', 0.1),
        inventory_skew_factor=mm_config.get('inventory_skew_factor', 0.001),
        trade_side=mm_config.get('trade_side', 'yes')
    )

def run_strategy(config_name: str, config: Dict):
    """Run a single strategy"""
    # Create logger for this strategy
    logger = logging.getLogger(f"Strategy_{config_name}")
    logger.setLevel(config.get('log_level', 'INFO'))

    # Create file handler
    fh = logging.FileHandler(f"{config_name}.log")
    fh.setLevel(config.get('log_level', 'INFO'))

    # Create console handler
    ch = logging.StreamHandler()
    ch.setLevel(config.get('log_level', 'INFO'))

    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # Add handlers to logger
    logger.addHandler(fh)
    logger.addHandler(ch)

    logger.info(f"Starting strategy: {config_name}")

    try:
        # Get mode from config
        mode = config.get('mode', 'demo')
        logger.info(f"Running in {mode} mode")

        # Create API
        api = create_api(config['api'], logger, mode)

        # Create market maker
        market_maker = create_market_maker(config['market_maker'], api, logger)

        # Run market maker
        market_maker.run(config.get('dt', 2.0))

    except KeyboardInterrupt:
        logger.info("Market maker stopped by user")
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        logger.exception("Full traceback:")
    finally:
        try:
            api.logout()
        except:
            pass  # Logout might fail, that's ok

def validate_environment():
    """Validate required environment variables"""
    required_demo_vars = [
        'DEMO_KALSHI_KEY_ID',
        'DEMO_KALSHI_PRIVATE_KEY'
    ]

    missing_vars = []
    for var in required_demo_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print("ERROR: Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nPlease set these in your .env file or environment.")
        return False

    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kalshi Market Making Algorithm")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to config file")
    parser.add_argument("--dry-run", action="store_true", help="Validate config without running")
    args = parser.parse_args()

    # Note: No load_dotenv() needed for Replit secrets

    # Validate environment
    if not validate_environment():
        exit(1)

    # Load configurations
    try:
        configs = load_config(args.config)
    except FileNotFoundError:
        print(f"ERROR: Config file {args.config} not found")
        exit(1)
    except yaml.YAMLError as e:
        print(f"ERROR: Invalid YAML in config file: {e}")
        exit(1)

    print("Starting the following strategies:")
    for config_name in configs:
        mode = configs[config_name].get('mode', 'demo')
        market = configs[config_name]['api']['market_ticker']
        print(f"  - {config_name} ({mode} mode, market: {market})")

    if args.dry_run:
        print("Dry run mode - configuration validated successfully")
        exit(0)

    # Run strategies in parallel
    try:
        with ThreadPoolExecutor(max_workers=len(configs)) as executor:
            futures = []
            for config_name, config in configs.items():
                future = executor.submit(run_strategy, config_name, config)
                futures.append((config_name, future))

            # Wait for all strategies to complete
            for config_name, future in futures:
                try:
                    future.result()
                except Exception as e:
                    print(f"Strategy {config_name} failed: {e}")

    except KeyboardInterrupt:
        print("\nShutting down all strategies...")
    except Exception as e:
        print(f"Error running strategies: {e}")