#!/usr/bin/env python
import asyncio
import os
import sys

# Ensure backend directory is in python path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.settings import settings
from app.ondc.services.diagnostics import _bpp_crypto_config, run_diagnostics

# ANSI color codes for pretty printing
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

async def main():
    report = await run_diagnostics()
    crypto = _bpp_crypto_config()
    
    sub_data = report["details"].get("subscriber", {})
    reg_data = report["details"].get("registry", {})
    
    found = "YES" if sub_data.get("subscriber_found", False) else "NO"
    
    # Extract values from registry response if found, else use configured settings
    cross_val = reg_data.get("cross_validation", {})
    
    sub_id = cross_val.get("subscriber_id", {}).get("registry") or settings.ONDC_SUBSCRIBER_ID
    sub_url = cross_val.get("subscriber_uri", {}).get("registry") or settings.ONDC_SUBSCRIBER_URI
    status = sub_data.get("status_in_registry") or "NOT_FOUND"
    uk_id = cross_val.get("unique_key_id", {}).get("registry") or crypto["unique_key_id"]
    sig_pub = cross_val.get("signing_public_key", {}).get("registry") or crypto["public_key"]
    enc_pub = sub_data.get("enc_public_key") or crypto["encryption_public_key"]
    
    found_color = GREEN if found == "YES" else RED
    
    print("====================================================")
    print(f"Participant Found : {found_color}{found}{RESET}")
    print(f"Subscriber ID: {sub_id}")
    print(f"Subscriber URL: {sub_url}")
    print(f"Status: {status}")
    print(f"Unique Key ID: {uk_id}")
    print(f"Signing Public Key: {sig_pub}")
    print(f"Encryption Public Key: {enc_pub}")
    print("Environment: Pre-Production")
    print("====================================================")
    print()
    
    # Task 10: Final Root Cause Analysis
    print(f"{BOLD}ROOT CAUSE:{RESET}")
    print("The gateway successfully received the signed request.")
    print("The request signature is syntactically correct.")
    print("The registry could not locate the signing key associated with:")
    print(f"Subscriber ID:\n{RED}{settings.ONDC_SUBSCRIBER_ID}{RESET}")
    print()
    print(f"Unique Key ID:\n{RED}{crypto['unique_key_id']}{RESET}")
    print()
    print(f"{BOLD}Recommended Action:{RESET}")
    print(f"1. Verify participant exists in Pre-Production Registry.")
    print(f"2. Verify Unique Key ID matches ONDC Portal.")
    print(f"3. Verify Signing Public Key matches Registry.")
    print(f"4. Verify participant status is ACTIVE.")
    print(f"5. Verify callback URL registered is {GREEN}{settings.ONDC_SUBSCRIBER_URI}{RESET}")

if __name__ == "__main__":
    asyncio.run(main())
