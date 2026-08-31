import base64
import json
import logging
import socket
import ssl
import time
import uuid
from typing import Any, Dict, List
from urllib.parse import urlparse

import httpx
from cryptography.hazmat.primitives import serialization

from app.core.settings import settings
from app.ondc.crypto.utils import load_private_key, generate_auth_header, parse_auth_header

logger = logging.getLogger(__name__)


def _bpp_crypto_config() -> Dict[str, str]:
    """Return the active seller credentials when BPP credentials are configured."""
    bpp_private = getattr(settings, "ONDC_BPP_SIGNING_PRIVATE_KEY", None)
    bpp_public = getattr(settings, "ONDC_BPP_SIGNING_PUBLIC_KEY", None)
    bpp_key_id = getattr(settings, "ONDC_BPP_UNIQUE_KEY_ID", None)
    if bpp_private and bpp_public and bpp_key_id:
        return {
            "subscriber_id": settings.ONDC_SUBSCRIBER_ID,
            "unique_key_id": bpp_key_id,
            "private_key": bpp_private,
            "public_key": bpp_public,
            "encryption_public_key": getattr(settings, "ONDC_BPP_ENC_PUBLIC_KEY", None)
            or settings.ONDC_ENC_PUBLIC_KEY,
            "type": "BPP",
        }
    return {
        "subscriber_id": settings.ONDC_SUBSCRIBER_ID,
        "unique_key_id": settings.ONDC_UNIQUE_KEY_ID,
        "private_key": settings.ONDC_SIGNING_PRIVATE_KEY,
        "public_key": settings.ONDC_SIGNING_PUBLIC_KEY,
        "encryption_public_key": settings.ONDC_ENC_PUBLIC_KEY,
        "type": settings.ONDC_TYPE,
    }

def validate_search_payload(payload: Dict[str, Any]) -> List[str]:
    """Validate ONDC v1.2 search payload schema and constraints."""
    errors = []
    if not isinstance(payload, dict):
        return ["Payload must be a JSON object (dictionary)"]

    context = payload.get("context")
    message = payload.get("message")

    if not context:
        errors.append("Missing required root key: 'context'")
    if not message:
        errors.append("Missing required root key: 'message'")

    if context:
        domain = context.get("domain")
        if not domain:
            errors.append("Missing 'context.domain'")
        elif domain != settings.ONDC_DOMAIN:
            errors.append(f"'context.domain' ({domain}) does not match configured settings.ONDC_DOMAIN ({settings.ONDC_DOMAIN})")

        action = context.get("action")
        if not action:
            errors.append("Missing 'context.action'")
        elif action != "search":
            errors.append(f"'context.action' must be 'search', got '{action}'")

        if not context.get("country"):
            errors.append("Missing 'context.country'")

        if not context.get("city"):
            errors.append("Missing 'context.city'")

        version = context.get("core_version")
        if not version:
            errors.append("Missing 'context.core_version'")
        elif version != "1.2.0":
            errors.append(f"'context.core_version' must be '1.2.0' for ONDC v1.2, got '{version}'")

        bap_id = context.get("bap_id")
        if not bap_id:
            errors.append("Missing 'context.bap_id'")
        elif bap_id != settings.ONDC_SUBSCRIBER_ID:
            errors.append(f"'context.bap_id' ({bap_id}) does not match ONDC_SUBSCRIBER_ID ({settings.ONDC_SUBSCRIBER_ID})")

        bap_uri = context.get("bap_uri")
        if not bap_uri:
            errors.append("Missing 'context.bap_uri'")
        elif bap_uri != settings.ONDC_SUBSCRIBER_URI:
            errors.append(f"'context.bap_uri' ({bap_uri}) does not match ONDC_SUBSCRIBER_URI ({settings.ONDC_SUBSCRIBER_URI})")

        if not context.get("transaction_id"):
            errors.append("Missing 'context.transaction_id'")

        if not context.get("message_id"):
            errors.append("Missing 'context.message_id'")

        if not context.get("timestamp"):
            errors.append("Missing 'context.timestamp'")

        if not context.get("ttl"):
            errors.append("Missing 'context.ttl'")

    if message:
        intent = message.get("intent")
        if not intent:
            errors.append("Missing 'message.intent'")
        else:
            item = intent.get("item")
            provider = intent.get("provider")
            category = intent.get("category")
            fulfillment = intent.get("fulfillment")
            if not any([item, provider, category, fulfillment]):
                errors.append("Search intent must contain at least one of: 'item', 'provider', 'category', 'fulfillment'")

    return errors


def verify_ssl_cert(url_str: str) -> Dict[str, Any]:
    result = {"dns": "FAIL", "https": "FAIL", "certificate": "FAIL", "ip": None, "error": None}
    if not url_str:
        result["error"] = "URL is empty"
        return result
    try:
        parsed = urlparse(url_str)
        if parsed.scheme == "https":
            result["https"] = "PASS"
        else:
            result["https"] = "FAIL"
            result["error"] = f"URL scheme is {parsed.scheme}, not https"
            return result
            
        hostname = parsed.hostname
        if not hostname:
            result["error"] = "Invalid hostname in URL"
            return result
            
        try:
            ip = socket.gethostbyname(hostname)
            result["dns"] = "PASS"
            result["ip"] = ip
        except Exception as de:
            result["dns"] = "FAIL"
            result["dns_error"] = str(de)
            result["error"] = f"DNS resolution failed: {str(de)}"
            return result
            
        port = parsed.port or 443
        context = ssl.create_default_context()
        try:
            with socket.create_connection((hostname, port), timeout=4.0) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    ssock.getpeercert()
                    result["certificate"] = "PASS"
        except ssl.SSLError as se:
            result["certificate"] = "FAIL"
            result["certificate_error"] = str(se)
            result["error"] = f"SSL handshake or validation failed: {str(se)}"
        except Exception as ce:
            result["certificate"] = "FAIL"
            result["certificate_error"] = str(ce)
            result["error"] = f"Connection failed during SSL check: {str(ce)}"
    except Exception as e:
        result["error"] = str(e)
    return result


async def check_callback_endpoints(base_uri: str) -> Dict[str, Any]:
    endpoints = [
        "/on_search",
        "/on_select",
        "/on_init",
        "/on_confirm",
        "/on_status",
        "/on_track",
        "/on_cancel",
        "/on_support"
    ]
    results = {}
    parsed = urlparse(base_uri)
    if not parsed.netloc:
        return results
        
    async with httpx.AsyncClient() as client:
        for ep in endpoints:
            url = f"{parsed.scheme}://{parsed.netloc}/api/v1/ondc{ep}"
            endpoint_res = {}
            try:
                res_get = await client.get(url, timeout=4.0)
                endpoint_res["get_status"] = res_get.status_code
            except Exception as e:
                endpoint_res["get_status"] = None
                endpoint_res["get_error"] = str(e)
                
            try:
                res_opt = await client.options(url, timeout=4.0)
                endpoint_res["options_status"] = res_opt.status_code
            except Exception as e:
                endpoint_res["options_status"] = None
                endpoint_res["options_error"] = str(e)
                
            results[f"/api/v1/ondc{ep}"] = endpoint_res
    return results


async def verify_public_domains() -> Dict[str, Any]:
    urls = [
        "https://ondc.fromnear.app",
        "https://ondc.fromnear.app/api",
        "https://ondc.fromnear.app/api/v1/ondc"
    ]
    results = {}
    async with httpx.AsyncClient() as client:
        for url in urls:
            try:
                res = await client.get(url, timeout=4.0)
                results[url] = {"status": res.status_code}
            except Exception as e:
                results[url] = {"status": None, "error": str(e)}
    return results


async def run_diagnostics() -> Dict[str, Any]:
    """Execute complete ONDC diagnostics checks and return a unified PASS/FAIL report."""
    crypto = _bpp_crypto_config()
    report = {
        "configuration": "FAIL",
        "registry": "FAIL",
        "gateway": "FAIL",
        "signature": "FAIL",
        "subscriber": "FAIL",
        "callback": "FAIL",
        "payload": "FAIL",
        "recommendations": [],
        "details": {}
    }

    # 1. Configuration Check
    config_details = {
        "ONDC_SUBSCRIBER_ID": settings.ONDC_SUBSCRIBER_ID,
        "ONDC_SUBSCRIBER_URI": settings.ONDC_SUBSCRIBER_URI,
        "ONDC_GATEWAY_URL": settings.ONDC_GATEWAY_URL,
        "ONDC_REGISTRY_URL": settings.ONDC_REGISTRY_URL,
        "ONDC_DOMAIN": settings.ONDC_DOMAIN,
        "ONDC_COUNTRY": settings.ONDC_COUNTRY,
        "ONDC_CITY": settings.ONDC_CITY,
        "ONDC_VERSION": settings.ONDC_VERSION,
        "ONDC_SIGNING_PUBLIC_KEY": crypto["public_key"],
        "ONDC_UNIQUE_KEY_ID": crypto["unique_key_id"],
        "ONDC_ENC_PUBLIC_KEY": crypto["encryption_public_key"],
        "ONDC_PARTICIPANT_TYPE": crypto["type"],
        "active_credential_set": crypto["type"],
    }
    
    # Check for empty/default values
    missing_config = []
    defaults = {
        "ONDC_SUBSCRIBER_ID": "bap.fromnear.com",
        "ONDC_SUBSCRIBER_URI": "https://bap.fromnear.com/api/v1/ondc",
        "ONDC_UNIQUE_KEY_ID": "bap-unique-key-id"
    }
    
    for k, v in config_details.items():
        if not v or v.startswith("INSERT_") or v.startswith("YOUR_"):
            missing_config.append(f"{k} is empty or placeholder")
        elif k in defaults and v == defaults[k]:
            missing_config.append(f"{k} has default placeholder value '{v}'")

    if not missing_config:
        report["configuration"] = "PASS"
    else:
        report["configuration"] = "FAIL"
        report["recommendations"].append(f"Configure ONDC settings in .env: {', '.join(missing_config)}")
    report["details"]["configuration"] = {
        "status": report["configuration"],
        "values": config_details,
        "errors": missing_config
    }

    # 2. Signature and Key Validation
    sig_details = {}
    priv_key_str = crypto["private_key"]
    pub_key_str = crypto["public_key"]

    try:
        if not priv_key_str:
            sig_details["error"] = "Private key is not configured"
            report["signature"] = "FAIL"
        else:
            priv_key = load_private_key(priv_key_str)
            pub_derived = priv_key.public_key()
            raw_bytes = pub_derived.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            der_bytes = pub_derived.public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            raw_b64 = base64.b64encode(raw_bytes).decode("utf-8")
            der_b64 = base64.b64encode(der_bytes).decode("utf-8")
            
            sig_details["private_key_readable"] = True
            sig_details["derived_public_key"] = raw_b64
            sig_details["configured_public_key"] = pub_key_str
            
            if pub_key_str.strip() in {raw_b64, der_b64}:
                report["signature"] = "PASS"
                sig_details["match"] = True
            else:
                report["signature"] = "FAIL"
                sig_details["match"] = False
                sig_details["error"] = "Derived public key does not match the active configured signing public key"
                report["recommendations"].append("Mismatched signing private/public key pair for the active participant.")
    except Exception as e:
        report["signature"] = "FAIL"
        sig_details["private_key_readable"] = False
        sig_details["error"] = f"Failed to load or validate keys: {str(e)}"
        report["recommendations"].append(f"Key validation error: {str(e)}")

    report["details"]["signature"] = sig_details

    # 3. Connectivity Tests
    connectivity_details = {}
    
    async def check_dns_tls(url_str: str) -> Dict[str, Any]:
        result = {"dns": "FAIL", "tls": "FAIL"}
        if not url_str:
            result["error"] = "URL is empty"
            return result
        try:
            parsed = urlparse(url_str)
            hostname = parsed.hostname
            if not hostname:
                result["error"] = f"Invalid hostname in URL: {url_str}"
                return result
                
            try:
                ip = socket.gethostbyname(hostname)
                result["dns"] = "PASS"
                result["ip"] = ip
            except Exception as de:
                result["dns_error"] = str(de)
                
            if result["dns"] == "PASS":
                try:
                    port = parsed.port or (443 if parsed.scheme == "https" else 80)
                    context = ssl.create_default_context()
                    # If localhost or testing environment, handle appropriately
                    with socket.create_connection((hostname, port), timeout=3.0) as sock:
                        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                            result["tls"] = "PASS"
                except Exception as te:
                    result["tls_error"] = str(te)
        except Exception as e:
            result["error"] = str(e)
        return result

    connectivity_details["gateway"] = await check_dns_tls(settings.ONDC_GATEWAY_URL)
    connectivity_details["registry"] = await check_dns_tls(settings.ONDC_REGISTRY_URL)
    connectivity_details["callback"] = await check_dns_tls(settings.ONDC_SUBSCRIBER_URI)
    
    # 4. Registry Validation (Lookup BAP) - Upgraded to Registry Verification Tool (Task 1, 2, 3, 8)
    registry_details = {}
    subscriber_details = {"subscriber_found": False}
    
    urls_to_try = [
        "https://preprod.registry.ondc.org/v2.0/lookup",
        "https://preprod.registry.ondc.org/ondc/lookup"
    ]
    
    lookup_payload = {
        "subscriber_id": crypto["subscriber_id"],
        "domain": settings.ONDC_DOMAIN,
        "ukId": crypto["unique_key_id"],
        "country": settings.ONDC_COUNTRY,
        "city": settings.ONDC_CITY,
        "type": crypto["type"],
    }
    
    registry_details["payload"] = lookup_payload
    registry_details["attempts"] = []
    
    headers = {"Content-Type": "application/json"}
    content_bytes = None
    if report["signature"] == "PASS" and report["configuration"] == "PASS":
        try:
            content_bytes = json.dumps(lookup_payload, separators=(',', ':')).encode("utf-8")
            auth_header = generate_auth_header(
                body=content_bytes,
                subscriber_id=crypto["subscriber_id"],
                unique_key_id=crypto["unique_key_id"],
                private_key_str=crypto["private_key"]
            )
            headers["Authorization"] = auth_header
        except Exception as sign_err:
            logger.warning(f"Could not sign registry lookup request: {str(sign_err)}")
            
    successful_res = None
    successful_url = None
    
    async with httpx.AsyncClient() as client:
        for url in urls_to_try:
            attempt = {
                "url": url,
                "status": None,
                "headers": None,
                "body": None,
                "error": None
            }
            try:
                if content_bytes is not None and "Authorization" in headers:
                    res = await client.post(url, content=content_bytes, headers=headers, timeout=8.0)
                else:
                    res = await client.post(url, json=lookup_payload, headers=headers, timeout=8.0)
                attempt["status"] = res.status_code
                attempt["headers"] = dict(res.headers)
                attempt["body"] = res.text
                
                if 200 <= res.status_code < 300:
                    successful_res = res
                    successful_url = url
                    registry_details["attempts"].append(attempt)
                    break
            except Exception as e:
                attempt["error"] = str(e)
            registry_details["attempts"].append(attempt)

    found_sub = None
    if successful_res is not None:
        try:
            data = successful_res.json()
            subscribers = data
            if isinstance(data, dict) and "subscribers" in data:
                subscribers = data["subscribers"]
            elif isinstance(data, dict) and "data" in data:
                subscribers = data["data"]
                
            if isinstance(subscribers, list):
                for sub in subscribers:
                    if sub.get("subscriber_id") == settings.ONDC_SUBSCRIBER_ID:
                        found_sub = sub
                        break
                        
            if found_sub:
                subscriber_details["subscriber_found"] = True
                report["subscriber"] = "PASS"
                
                status_in_reg = found_sub.get("status")
                subscriber_details["status_in_registry"] = status_in_reg
                
                status_active = status_in_reg in ["SUBSCRIBED", "ACTIVE", "Active"]
                subscriber_details["status_active"] = status_active
                
                # Cross Validation (Task 3)
                reg_sub_id = found_sub.get("subscriber_id")
                reg_uk_id = found_sub.get("ukId") or found_sub.get("unique_key_id") or found_sub.get("key_id")
                reg_sig_pub = found_sub.get("signing_public_key")
                reg_sub_uri = found_sub.get("subscriber_url") or found_sub.get("subscriber_uri")
                
                def normalize_val(v):
                    return str(v).strip().rstrip("/") if v is not None else ""
                
                cross_validation = {
                    "subscriber_id": {
                        "local": settings.ONDC_SUBSCRIBER_ID,
                        "registry": reg_sub_id,
                        "match": (normalize_val(reg_sub_id) == normalize_val(settings.ONDC_SUBSCRIBER_ID))
                    },
                    "unique_key_id": {
                        "local": crypto["unique_key_id"],
                        "registry": reg_uk_id,
                        "match": (normalize_val(reg_uk_id) == normalize_val(crypto["unique_key_id"]))
                    },
                    "signing_public_key": {
                        "local": crypto["public_key"],
                        "registry": reg_sig_pub,
                        "match": (normalize_val(reg_sig_pub) == normalize_val(crypto["public_key"]))
                    },
                    "subscriber_uri": {
                        "local": settings.ONDC_SUBSCRIBER_URI,
                        "registry": reg_sub_uri,
                        "match": (normalize_val(reg_sub_uri) == normalize_val(settings.ONDC_SUBSCRIBER_URI))
                    }
                }
                registry_details["cross_validation"] = cross_validation
                
                enc_key_in_reg = found_sub.get("enc_public_key")
                subscriber_details["encryption_key_in_registry"] = enc_key_in_reg
                enc_key_matches = (
                    enc_key_in_reg
                    and enc_key_in_reg.strip() == crypto["encryption_public_key"].strip()
                )
                subscriber_details["encryption_key_matches"] = enc_key_matches
                
                if (status_active and 
                    cross_validation["subscriber_id"]["match"] and 
                    cross_validation["unique_key_id"]["match"] and 
                    cross_validation["signing_public_key"]["match"] and 
                    cross_validation["subscriber_uri"]["match"]):
                    report["registry"] = "PASS"
                else:
                    report["registry"] = "FAIL"
                    if not status_active:
                        report["recommendations"].append(f"Subscriber {settings.ONDC_SUBSCRIBER_ID} is inactive/unsubscribed in ONDC registry (Status: {status_in_reg}).")
                    if not cross_validation["subscriber_id"]["match"]:
                        report["recommendations"].append("Subscriber ID mismatch between configuration and ONDC Registry.")
                    if not cross_validation["unique_key_id"]["match"]:
                        report["recommendations"].append("Unique Key ID (ukId) mismatch between configuration and ONDC Registry.")
                    if not cross_validation["signing_public_key"]["match"]:
                        report["recommendations"].append("Signing Public Key mismatch between configuration and ONDC Registry.")
                    if not cross_validation["subscriber_uri"]["match"]:
                        report["recommendations"].append("Subscriber URI mismatch between configuration and ONDC Registry.")
            else:
                report["registry"] = "FAIL"
                report["subscriber"] = "FAIL"
                registry_details["error"] = f"Subscriber ID '{settings.ONDC_SUBSCRIBER_ID}' was not found in registry response."
                report["recommendations"].append("Subscriber ID is not registered in the ONDC pre-prod Registry.")
        except Exception as parse_err:
            report["registry"] = "FAIL"
            registry_details["error"] = f"Failed to parse registry lookup body: {str(parse_err)}"
            report["recommendations"].append("Registry lookup returned non-standard/malformed payload.")
    else:
        report["registry"] = "FAIL"
        registry_details["error"] = "All Registry lookup endpoints failed or returned non-2xx status."
        report["recommendations"].append("Registry lookup failed. Possible reasons include network blocks, invalid keys, or registration failure.")

    # Registry Authentication Debugging (Task 8)
    has_auth_failure = any(a.get("status") in [401, 403] for a in registry_details["attempts"]) or (successful_res is not None and not found_sub)
    if has_auth_failure:
        registry_details["possible_causes"] = [
            "Subscriber not registered",
            "Wrong environment (e.g. querying preprod registry with production key, or vice-versa)",
            "Signing key not propagated yet (propagation takes time)",
            "Unique Key ID mismatch between portal registration and .env",
            "Subscriber inactive (status is not SUBSCRIBED or ACTIVE)",
            "Callback URL mismatch",
            "Registry endpoint deprecated or under maintenance"
        ]
        
    report["details"]["registry"] = registry_details
    report["details"]["subscriber"] = subscriber_details

    # 5. Payload Validation
    # Build minimal payload
    transaction_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    
    test_payload = {
        "context": {
            "domain": settings.ONDC_DOMAIN,
            "country": settings.ONDC_COUNTRY,
            "city": settings.ONDC_CITY,
            "action": "search",
            "core_version": settings.ONDC_VERSION,
            "bap_id": settings.ONDC_SUBSCRIBER_ID,
            "bap_uri": settings.ONDC_SUBSCRIBER_URI,
            "transaction_id": transaction_id,
            "message_id": message_id,
            "timestamp": timestamp,
            "ttl": "PT30S"
        },
        "message": {
            "intent": {
                "item": {
                    "descriptor": {
                        "name": "diagnostic_test"
                    }
                },
                "fulfillment": {
                    "type": "Delivery"
                },
                "payment": {
                    "@ondc/org/buyer_app_finder_fee_type": "percent",
                    "@ondc/org/buyer_app_finder_fee_amount": "3"
                }
            }
        }
    }

    payload_errors = validate_search_payload(test_payload)
    if not payload_errors:
        report["payload"] = "PASS"
    else:
        report["payload"] = "FAIL"
        for err in payload_errors:
            report["recommendations"].append(f"Payload validation issue: {err}")
    report["details"]["payload"] = {
        "status": report["payload"],
        "errors": payload_errors,
        "validated_payload": test_payload
    }

    # 6. Gateway Validation and Auth Header Inspection (Task 4, 5)
    gateway_details = {}
    auth_header_details = {}
    
    if report["signature"] == "PASS" and report["configuration"] == "PASS":
        try:
            body_bytes = json.dumps(test_payload, separators=(',', ':')).encode("utf-8")
            auth_header = generate_auth_header(
                body=body_bytes,
                subscriber_id=crypto["subscriber_id"],
                unique_key_id=crypto["unique_key_id"],
                private_key_str=crypto["private_key"]
            )
            
            parsed_header = parse_auth_header(auth_header)
            key_id_val = parsed_header.get("keyId", "")
            expected_key_id = f"{crypto['subscriber_id']}|{crypto['unique_key_id']}|ed25519"
            key_id_match = (key_id_val == expected_key_id)
            
            key_id_parts = key_id_val.split("|")
            decoded_subscriber_id = key_id_parts[0] if len(key_id_parts) > 0 else None
            decoded_unique_key_id = key_id_parts[1] if len(key_id_parts) > 1 else None
            decoded_algorithm = key_id_parts[2] if len(key_id_parts) > 2 else parsed_header.get("algorithm")
            
            auth_header_details = {
                "created": parsed_header.get("created"),
                "expires": parsed_header.get("expires"),
                "key_id": key_id_val,
                "digest": parsed_header.get("digest"),
                "signature": parsed_header.get("signature"),
                "algorithm": parsed_header.get("algorithm"),
                "header_string": auth_header,
                "key_id_match": key_id_match,
                "expected_key_id": expected_key_id,
                "decoded": {
                    "subscriber_id": decoded_subscriber_id,
                    "unique_key_id": decoded_unique_key_id,
                    "algorithm": decoded_algorithm or parsed_header.get("algorithm"),
                    "created": parsed_header.get("created"),
                    "expires": parsed_header.get("expires"),
                    "digest": parsed_header.get("digest"),
                    "signature": parsed_header.get("signature")
                }
            }
            
            # Now send signed test search request
            gateway_url = settings.ONDC_GATEWAY_URL
            
            # Detect double /search append
            if gateway_url.endswith("/search"):
                report["recommendations"].append(
                    "Mismatched Gateway endpoint: ONDC_GATEWAY_URL in .env ends with '/search'. "
                    "The codebase appends '/search' automatically during search broadcasts, leading to "
                    f"calls to '{gateway_url}/search'. Please change ONDC_GATEWAY_URL to 'https://preprod.gateway.ondc.org'."
                )
                # Let's normalize it to just hit the actual endpoint for the test
                # Wait, if we test the exact configured URL, it will fail.
                # Let's test the EXACT configured url to show the user it fails, 
                # but also run a test with the corrected URL.
                gateway_url_to_test = gateway_url
            else:
                gateway_url_to_test = f"{gateway_url.rstrip('/')}/search"
                
            gateway_details["url_called"] = gateway_url_to_test
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": auth_header
            }
            
            async with httpx.AsyncClient() as client:
                res = await client.post(gateway_url_to_test, content=body_bytes, headers=headers, timeout=8.0)
                gateway_details["http_status"] = res.status_code
                gateway_details["headers"] = dict(res.headers)
                gateway_details["body"] = res.text
                
                # Check for registry mismatch inside body or gateway response
                if res.status_code == 200:
                    report["gateway"] = "PASS"
                else:
                    report["gateway"] = "FAIL"
                    gateway_details["error"] = f"Gateway returned HTTP status {res.status_code}"
                    
                    # Highlight common 403 / 401 issues
                    if res.status_code == 403:
                        report["recommendations"].append(
                            "ONDC Gateway returned 403 Forbidden. This is typically caused by: "
                            "1) Mismatched keys (derived vs ONDC Registry), "
                            "2) Incorrect/expired signature header, "
                            "3) Incorrect subscriber ID or unique key ID in the registry, or "
                            "4) Mismatched domain, country, or city values."
                        )
                    elif res.status_code == 404:
                        report["recommendations"].append(
                            f"ONDC Gateway returned 404 Not Found at {gateway_url_to_test}. "
                            "Verify if the endpoint path is correct."
                        )
        except Exception as e:
            report["gateway"] = "FAIL"
            gateway_details["error"] = f"Gateway connection failed: {str(e)}"
            report["recommendations"].append(f"Unable to connect to Gateway: {str(e)}")
    else:
        report["gateway"] = "FAIL"
        gateway_details["error"] = "Gateway request skipped due to configuration or signature failure."
        report["recommendations"].append("Skipped Gateway check because configuration/signature check failed.")

    report["details"]["gateway"] = gateway_details
    report["details"]["auth_header"] = auth_header_details

    # 7. Callback Routes Verification
    callback_details = {}
    from app.main import app
    
    def get_routes_recursively(router_or_app, current_prefix=""):
        routes = []
        for route in getattr(router_or_app, "routes", []):
            type_name = type(route).__name__
            if type_name == "_IncludedRouter":
                context = getattr(route, "include_context", None)
                orig = getattr(route, "original_router", None)
                if context and orig:
                    prefix = getattr(context, "prefix", "")
                    routes.extend(get_routes_recursively(orig, current_prefix + prefix))
            elif hasattr(route, "path"):
                routes.append(current_prefix + route.path)
        return routes
        
    app_routes = get_routes_recursively(app)
            
    required_callbacks = [
        "/on_search",
        "/on_select",
        "/on_init",
        "/on_confirm",
        "/on_status",
        "/on_track",
        "/on_cancel",
        "/on_support"
    ]
    
    route_checks = {}
    mismatches = []
    
    # We parse current ONDC_SUBSCRIBER_URI to get its path.
    # E.g. "https://ondc.fromnear.app/api" -> path is "/api"
    # The callback routes will be called by gateway as: subscriber_uri + "/" + callback_path
    # E.g. "https://ondc.fromnear.app/api/on_search"
    # We need to make sure that the path portion "/api/on_search" is registered in our FastAPI routes.
    parsed_uri = urlparse(settings.ONDC_SUBSCRIBER_URI)
    uri_path = parsed_uri.path.rstrip("/")
    
    for cb in required_callbacks:
        expected_path = f"{uri_path}{cb}"
        # Check if any app route matches expected_path exactly
        found_exact = expected_path in app_routes
        
        # Check if it matches at all
        found_suffix = False
        matching_path = None
        for path in app_routes:
            if path.endswith(cb):
                found_suffix = True
                matching_path = path
                break
                
        route_checks[cb] = {
            "expected_callback_path": expected_path,
            "exact_match_found": found_exact,
            "registered_under_any_path": found_suffix,
            "actual_registered_path": matching_path
        }
        
        if not found_exact:
            mismatches.append(cb)
            
    if not mismatches:
        report["callback"] = "PASS"
    else:
        report["callback"] = "FAIL"
        report["recommendations"].append(
            f"Callback path routing mismatch. Your ONDC_SUBSCRIBER_URI is '{settings.ONDC_SUBSCRIBER_URI}', "
            f"so external callbacks will call paths like '{uri_path}/on_search'. "
            f"However, FastAPI registers routes at paths like '/api/v1/ondc/on_search'. "
            "Please align ONDC_SUBSCRIBER_URI (e.g. set it to 'https://ondc.fromnear.app/api/v1/ondc') "
            "or adjust callback routing prefixes in the FastAPI router."
        )

    callback_details["route_checks"] = route_checks
    callback_details["app_registered_routes"] = app_routes
    callback_details["mismatched_callbacks"] = mismatches
    
    # Check if subscriber_uri is reachable publicly
    callback_details["subscriber_uri_reachability"] = connectivity_details["callback"]
    
    # Add callback URL validation (Task 6)
    callback_details["ssl_check"] = verify_ssl_cert(settings.ONDC_SUBSCRIBER_URI)
    callback_details["endpoint_checks"] = await check_callback_endpoints(settings.ONDC_SUBSCRIBER_URI)
    
    # Add public domain verification (Task 7)
    callback_details["public_domain_verification"] = await verify_public_domains()
    
    report["details"]["callback"] = callback_details
    report["details"]["connectivity"] = connectivity_details

    return report
