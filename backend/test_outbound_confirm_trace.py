import json
import time
import base64
from app.ondc.crypto.utils import generate_auth_header, parse_auth_header
from app.core.settings import settings

# Incoming request context from Pramaan (BAP)
request_context = {
    "domain": "ONDC:RET10",
    "country": "IND",
    "city": "std:080",
    "action": "confirm",
    "core_version": "1.2.0",
    "bap_id": "workbench.ondc.tech",
    "bap_uri": "https://workbench.ondc.tech/api-service/ONDC:RET10/1.2.0/buyer",
    "bpp_id": "ondc.fromnear.com",
    "bpp_uri": "https://ondc.fromnear.com/api/v1/ondc",
    "transaction_id": "48813e2f-8767-4899-b957-767d808e34e8",
    "message_id": "037b6559-25b3-47c1-ad17-88eafef42df7",
    "timestamp": "2026-07-27T17:45:23.840Z",
    "ttl": "PT30S"
}

# 1. Build response context (echoes message_id)
response_context = request_context.copy()
response_context["action"] = "on_confirm"
response_context["bpp_id"] = settings.ONDC_SUBSCRIBER_ID
response_context["bpp_uri"] = settings.ONDC_SUBSCRIBER_URI
response_context["timestamp"] = "2026-07-27T17:45:24.000Z"

# 2. Build order payment with FIXED settlement details
bap_id = request_context.get("bap_id", "workbench.ondc.tech")
bpp_id = settings.ONDC_SUBSCRIBER_ID

settlement_details = [
    {
        "settlement_counterparty": "seller-app",
        "settlement_phase": "sale-amount",
        "settlement_type": "neft",
        "subscriber_id": bpp_id,
        "beneficiary_name": "FromNear Store",
        "bank_name": "Mock Bank",
        "branch_name": "MG Road",
        "settlement_bank_account_no": "1234567890",
        "settlement_ifsc_code": "MOCK0001234"
    },
    {
        "settlement_counterparty": "buyer-app",
        "settlement_phase": "completed",
        "settlement_type": "upi",
        "subscriber_id": bap_id,
        "upi_address": "gpay@okicici",
        "settlement_bank_account_no": "XXXXXXXXXX",
        "settlement_ifsc_code": "XXXXXXXXX",
        "beneficiary_name": "Test Name",
        "bank_name": "Test Bank",
        "branch_name": "Test Branch"
    }
]

response_payload = {
    "context": response_context,
    "message": {
        "order": {
            "id": "2026-07-27-1001",
            "state": "Accepted",
            "provider": {"id": "P1", "locations": [{"id": "L1"}]},
            "items": [
                {"id": "I1", "fulfillment_id": "F1", "quantity": {"count": 1}},
                {"id": "I2", "fulfillment_id": "F1", "quantity": {"count": 1}}
            ],
            "billing": {"name": "John Doe", "phone": "9876543210"},
            "fulfillments": [
                {
                    "id": "F1",
                    "type": "Delivery",
                    "@ondc/org/provider_name": "FromNear Delivery",
                    "tracking": False,
                    "@ondc/org/category": "Standard Delivery",
                    "@ondc/org/TAT": "PT45M",
                    "state": {"descriptor": {"code": "Packed"}}
                }
            ],
            "quote": {
                "price": {"currency": "INR", "value": "750.00"},
                "breakup": [
                    {
                        "@ondc/org/item_id": "I1",
                        "@ondc/org/item_quantity": {"count": 1},
                        "title": "Atta (Whole Wheat Flour) 5kg",
                        "@ondc/org/title_type": "item",
                        "price": {"currency": "INR", "value": "250.00"},
                        "item": {
                            "price": {"currency": "INR", "value": "250.00"},
                            "quantity": {"available": {"count": "100"}, "maximum": {"count": "5"}}
                        }
                    },
                    {
                        "@ondc/org/item_id": "I2",
                        "@ondc/org/item_quantity": {"count": 1},
                        "title": "Basmati Rice 5kg",
                        "@ondc/org/title_type": "item",
                        "price": {"currency": "INR", "value": "450.00"},
                        "item": {
                            "price": {"currency": "INR", "value": "450.00"},
                            "quantity": {"available": {"count": "50"}, "maximum": {"count": "2"}}
                        }
                    },
                    {
                        "@ondc/org/item_id": "F1",
                        "title": "Delivery charges",
                        "@ondc/org/title_type": "delivery",
                        "price": {"currency": "INR", "value": "50.00"}
                    }
                ],
                "ttl": "PT15M"
            },
            "payment": {
                "type": "ON-ORDER",
                "status": "PAID",
                "collected_by": "BAP",
                "@ondc/org/buyer_app_finder_fee_type": "percent",
                "@ondc/org/buyer_app_finder_fee_amount": "3",
                "@ondc/org/settlement_details": settlement_details
            },
            "created_at": "2026-07-27T17:45:24.000Z",
            "updated_at": "2026-07-27T17:45:24.000Z"
        }
    }
}

body_bytes = json.dumps(response_payload, separators=(',', ':')).encode('utf-8')
auth_header = generate_auth_header(body_bytes)
parsed_auth = parse_auth_header(auth_header)

url = f"{response_context['bap_uri'].rstrip('/')}/on_confirm"

print(f"URL: {url}")
print(f"Headers: Content-Type: application/json, Authorization: {auth_header}")
print(f"Authorization Header: {auth_header}")
print(f"keyId: {parsed_auth.get('keyId')}")
print(f"created: {parsed_auth.get('created')}")
print(f"expires: {parsed_auth.get('expires')}")
print(f"context: {json.dumps(response_context, indent=2)}")
print(f"bap_id: {response_context['bap_id']}")
print(f"bap_uri: {response_context['bap_uri']}")
print(f"bpp_id: {response_context['bpp_id']}")
print(f"bpp_uri: {response_context['bpp_uri']}")
print(f"transaction_id: {response_context['transaction_id']}")
print(f"message_id: {response_context['message_id']}")
print(f"payload: {json.dumps(response_payload, indent=2)}")
