#!/usr/bin/env python
import asyncio
import json
import os
import sys

# Ensure backend directory is in python path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.ondc.services.diagnostics import run_diagnostics

# ANSI color codes for pretty printing
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_section(title: str):
    print(f"\n{BOLD}{BLUE}=== {title} ==={RESET}")

def print_result(label: str, status: str, details: str = ""):
    if status == "PASS":
        status_str = f"{GREEN}[PASS]{RESET}"
    elif status == "WARNING":
        status_str = f"{YELLOW}[WARN]{RESET}"
    else:
        status_str = f"{RED}[FAIL]{RESET}"
    
    print(f"{status_str} {BOLD}{label}{RESET}")
    if details:
        for line in details.strip().split("\n"):
            print(f"  {line}")

async def main():
    print(f"{BOLD}=================================================={RESET}")
    print(f"{BOLD}       ONDC BUYER NP DIAGNOSTIC UTILITY           {RESET}")
    print(f"{BOLD}=================================================={RESET}")

    report = await run_diagnostics()

    # 1. Configuration Check
    print_section("1. CONFIGURATION INTEGRITY")
    config_data = report["details"]["configuration"]
    if config_data["status"] == "PASS":
        print_result("Mandatory Configuration Settings", "PASS", "All keys configured with non-default values.")
    else:
        errs = "\n".join([f"- {e}" for e in config_data["errors"]])
        print_result("Mandatory Configuration Settings", "FAIL", f"Missing or placeholder configuration found:\n{errs}")

    # 2. Cryptographic Keys
    print_section("2. CRYPTOGRAPHIC SIGNING KEYS")
    sig_data = report["details"]["signature"]
    if report["signature"] == "PASS":
        print_result("Key Derivation & Match", "PASS", 
                     f"Private key loaded successfully.\n"
                     f"Configured Public Key: {sig_data.get('configured_public_key')}\n"
                     f"Derived Public Key:    {sig_data.get('derived_public_key')}")
    else:
        print_result("Key Derivation & Match", "FAIL", f"Error: {sig_data.get('error')}")

    # 3. Connectivity Checks
    print_section("3. NETWORK CONNECTIVITY & DNS/TLS")
    conn_data = report["details"]["connectivity"]
    for service, check in conn_data.items():
        details = []
        status = "PASS"
        if check.get("dns") == "PASS":
            details.append(f"DNS Resolution: PASS (IP: {check.get('ip')})")
        else:
            details.append(f"DNS Resolution: FAIL ({check.get('dns_error')})")
            status = "FAIL"
            
        if check.get("tls") == "PASS":
            details.append("TLS Handshake:  PASS")
        else:
            details.append(f"TLS Handshake:  FAIL ({check.get('tls_error')})")
            status = "FAIL"
            
        if check.get("error"):
            details.append(f"Error: {check.get('error')}")
            status = "FAIL"
            
        print_result(f"Service {service.upper()} reachability check", status, "\n".join(details))

    # 4. Registry Validation
    print_section("4. ONDC REGISTRY STATUS")
    reg_data = report["details"]["registry"]
    sub_data = report["details"]["subscriber"]
    if report["registry"] == "PASS":
        print_result("Registry Lookup & Subscription Status", "PASS", 
                     f"Subscriber found in Registry.\n"
                     f"Registry Status: {sub_data.get('status_in_registry')}\n"
                     f"Keys match: YES\n"
                     f"Callback URL matches: YES")
    else:
        details = []
        if sub_data.get("subscriber_found"):
            details.append(f"Subscriber Found: YES (Status: {sub_data.get('status_in_registry')})")
            details.append(f"Signing Key matches: {'YES' if sub_data.get('signing_key_matches') else 'NO (Registry: ' + str(sub_data.get('signing_key_in_registry')) + ')'}")
            details.append(f"Encryption Key matches: {'YES' if sub_data.get('encryption_key_matches') else 'NO (Registry: ' + str(sub_data.get('enc_public_key')) + ')'}")
            details.append(f"Callback URL matches: {'YES' if sub_data.get('callback_url_matches') else 'NO (Registry: ' + str(sub_data.get('callback_url_in_registry')) + ')'}")
        else:
            details.append("Subscriber Found: NO")
            
        if reg_data.get("error"):
            details.append(f"Lookup Error: {reg_data.get('error')}")
        if reg_data.get("http_status"):
            details.append(f"HTTP Response: {reg_data.get('http_status')}")
            
        print_result("Registry Lookup & Subscription Status", "FAIL", "\n".join(details))

    # 5. Schema and Payload Checks
    print_section("5. SEARCH SCHEMA VALIDATION")
    pay_data = report["details"]["payload"]
    if report["payload"] == "PASS":
        print_result("Outgoing Search Payload Format", "PASS", "ONDC v1.2 schema validation constraints passed.")
    else:
        errs = "\n".join([f"- {e}" for e in pay_data["errors"]])
        print_result("Outgoing Search Payload Format", "FAIL", f"Errors:\n{errs}")

    # 6. Gateway Interaction & Response Code
    print_section("6. ONDC GATEWAY LIVE INTERACTION")
    gate_data = report["details"]["gateway"]
    auth_data = report["details"]["auth_header"]
    if report["gateway"] == "PASS":
        print_result("Broadcast Request to Gateway", "PASS", 
                     f"Gateway returned: HTTP {gate_data.get('http_status')}\n"
                     f"Request ID: {gate_data.get('gateway_request_id')}")
    else:
        details = [
            f"Target URL:  {gate_data.get('url_called')}",
            f"HTTP Status: {gate_data.get('http_status')}",
        ]
        if gate_data.get("error"):
            details.append(f"Error:       {gate_data.get('error')}")
        if gate_data.get("body"):
            details.append(f"Gateway Raw Response:\n{gate_data.get('body')}")
        print_result("Broadcast Request to Gateway", "FAIL", "\n".join(details))

    # 7. Authorization Header
    print_section("7. AUTHORIZATION HEADER DETAILS")
    if auth_data:
        details = [
            f"Algorithm:   {auth_data.get('algorithm')}",
            f"KeyID:       {auth_data.get('key_id')}",
            f"Digest:      {auth_data.get('digest')}",
            f"Signature:   {auth_data.get('signature')}",
            f"Created:     {auth_data.get('created')}",
            f"Expires:     {auth_data.get('expires')}",
            f"Raw Header:  {auth_data.get('header_string')}"
        ]
        print_result("Generated Auth Header Details", "PASS", "\n".join(details))
    else:
        print_result("Generated Auth Header Details", "FAIL", "Auth Header could not be generated.")

    # 8. Callback URL Routing Checks
    print_section("8. CALLBACK ROUTES ALIGNMENT")
    cb_data = report["details"]["callback"]
    if report["callback"] == "PASS":
        print_result("Callback Route Alignment", "PASS", "All external callback endpoints align with internal routes.")
    else:
        details = []
        for cb, val in cb_data["route_checks"].items():
            route_status = f"{GREEN}VALID{RESET}" if val["exact_match_found"] else f"{RED}MISMATCH{RESET}"
            details.append(f"Callback {cb}: {route_status}")
            details.append(f"  - Expected path mapping:  {val['expected_callback_path']}")
            if val["registered_under_any_path"]:
                details.append(f"  - Registered route path:  {val['actual_registered_path']}")
            else:
                details.append(f"  - Registered route path:  NOT REGISTERED")
        print_result("Callback Route Alignment", "FAIL", "\n".join(details))

    # 9. Recommendations Summary
    print_section("RECOMMENDATIONS & ACTION ITEMS")
    if report["recommendations"]:
        for i, rec in enumerate(report["recommendations"], 1):
            print(f"{i}. {YELLOW}{rec}{RESET}")
    else:
        print(f"{GREEN}All checks passed. System is ready for ONDC transaction integration.{RESET}")

    print(f"\n{BOLD}=================================================={RESET}")

if __name__ == "__main__":
    asyncio.run(main())
