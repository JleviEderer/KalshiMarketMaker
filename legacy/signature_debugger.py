#!/usr/bin/env python3
"""
Legacy utility to debug Kalshi API signature generation step by step.
"""

import os
import time
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
import requests

def debug_signature_generation():
    """Debug signature generation step by step"""

    print("🔧 KALSHI SIGNATURE DEBUGGING")
    print("=" * 50)

    # Load credentials
    key_id = os.getenv('DEMO_KALSHI_KEY_ID')
    private_key_pem = os.getenv('DEMO_KALSHI_PRIVATE_KEY')

    if not key_id or not private_key_pem:
        print("❌ Missing environment variables!")
        print("Please ensure DEMO_KALSHI_KEY_ID and DEMO_KALSHI_PRIVATE_KEY are set")
        return

    print(f"✅ Key ID: {key_id}")
    print(f"✅ Private Key Length: {len(private_key_pem)} characters")

    # Fix private key formatting if needed
    if '\n' not in private_key_pem and '-----BEGIN RSA PRIVATE KEY-----' in private_key_pem:
        print("🔧 Fixing private key formatting...")
        content = private_key_pem.replace('-----BEGIN RSA PRIVATE KEY-----', '')
        content = content.replace('-----END RSA PRIVATE KEY-----', '')
        content = content.strip()

        lines = []
        for i in range(0, len(content), 64):
            lines.append(content[i:i+64])

        private_key_pem = '-----BEGIN RSA PRIVATE KEY-----\n'
        private_key_pem += '\n'.join(lines)
        private_key_pem += '\n-----END RSA PRIVATE KEY-----'
        print("✅ Private key formatting fixed")

    # Load private key
    try:
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode(),
            password=None,
            backend=default_backend()
        )
        print("✅ Private key loaded successfully")
        print(f"✅ Key size: {private_key.key_size} bits")
    except Exception as e:
        print(f"❌ Failed to load private key: {e}")
        return

    # Test signature generation for a simple endpoint
    print("\n" + "=" * 50)
    print("TESTING SIGNATURE FOR /portfolio/balance")
    print("=" * 50)

    timestamp = int(time.time() * 1000)
    timestamp_str = str(timestamp)
    method = "GET"
    path = "/portfolio/balance"

    print(f"Timestamp: {timestamp_str}")
    print(f"Method: {method}")
    print(f"Path: {path}")

    # Create message to sign
    message = timestamp_str + method + path
    print(f"Message to sign: '{message}'")
    print(f"Message length: {len(message)} characters")
    print(f"Message bytes: {message.encode('utf-8')}")

    # Test different PSS configurations
    pss_configs = [
        ("DIGEST_LENGTH", padding.PSS.DIGEST_LENGTH),
        ("MAX_LENGTH", padding.PSS.MAX_LENGTH),
        ("AUTO", padding.PSS.AUTO)
    ]

    working_config = None

    for config_name, salt_length in pss_configs:
        try:
            print(f"\n--- Testing PSS with {config_name} ---")
            signature = private_key.sign(
                message.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=salt_length
                ),
                hashes.SHA256()
            )

            signature_b64 = base64.b64encode(signature).decode('utf-8')
            print(f"✅ Signature generated with {config_name}")
            print(f"Signature (first 50 chars): {signature_b64[:50]}...")
            print(f"Signature length: {len(signature_b64)} characters")

            # Test the signature with actual API call
            headers = {
                "KALSHI-ACCESS-KEY": key_id,
                "KALSHI-ACCESS-TIMESTAMP": timestamp_str,
                "KALSHI-ACCESS-SIGNATURE": signature_b64,
                "Content-Type": "application/json",
            }

            url = "https://demo-api.kalshi.co/trade-api/v2/portfolio/balance"

            try:
                print(f"🌐 Testing API call with {config_name}...")
                response = requests.get(url, headers=headers, timeout=10)
                print(f"Status: {response.status_code}")

                if response.status_code == 200:
                    print(f"🎉 SUCCESS with {config_name}!")
                    print(f"Response: {response.json()}")
                    working_config = config_name
                    break
                elif response.status_code == 401:
                    response_text = response.text[:200] if response.text else "No response body"
                    print(f"❌ 401 Unauthorized with {config_name}")
                    print(f"Response: {response_text}")
                else:
                    print(f"⚠️  Unexpected status {response.status_code} with {config_name}")
                    print(f"Response: {response.text[:200]}")

            except requests.exceptions.RequestException as e:
                print(f"❌ Request failed with {config_name}: {e}")

        except Exception as e:
            print(f"❌ Failed to generate signature with {config_name}: {e}")

    if working_config:
        print(f"\n🎉 FOUND WORKING CONFIGURATION: {working_config}")
        return True

    print("\n" + "=" * 50)
    print("TESTING ALTERNATIVE MESSAGE FORMATS")
    print("=" * 50)

    # Test with different message formats
    alternative_messages = [
        # Different timestamp formats
        (str(int(time.time())), "Unix timestamp in seconds"),
        (str(timestamp), "Current timestamp format"),

        # Different path formats
        (timestamp_str + method.upper() + path, "Uppercase method"),
        (timestamp_str + method.lower() + path, "Lowercase method"),

        # With base URL
        (timestamp_str + method + "https://demo-api.kalshi.co/trade-api/v2" + path, "Full URL"),
        (timestamp_str + method + "/trade-api/v2" + path, "API path prefix"),
    ]

    for alt_message, description in alternative_messages:
        try:
            print(f"\n--- Testing: {description} ---")
            print(f"Message: '{alt_message}'")

            signature = private_key.sign(
                alt_message.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.DIGEST_LENGTH
                ),
                hashes.SHA256()
            )

            signature_b64 = base64.b64encode(signature).decode('utf-8')

            headers = {
                "KALSHI-ACCESS-KEY": key_id,
                "KALSHI-ACCESS-TIMESTAMP": timestamp_str,
                "KALSHI-ACCESS-SIGNATURE": signature_b64,
                "Content-Type": "application/json",
            }

            response = requests.get(url, headers=headers, timeout=10)
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                print(f"🎉 SUCCESS with alternative format!")
                print(f"Working message format: {description}")
                return True
            elif response.status_code != 401:
                print(f"Response: {response.text[:100]}")

        except Exception as e:
            print(f"❌ Failed: {e}")

    print("\n" + "=" * 50)
    print("DIAGNOSIS COMPLETE - NO WORKING CONFIGURATION FOUND")
    print("=" * 50)
    print("Recommendations:")
    print("1. Verify your demo account is fully set up and funded")
    print("2. Regenerate your API key in the Kalshi demo portal")
    print("3. Contact Kalshi support about demo API access")
    print("4. Try with live API keys (won't place orders)")

    return False

if __name__ == "__main__":
    debug_signature_generation()
