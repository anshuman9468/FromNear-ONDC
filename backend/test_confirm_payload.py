import json
import logging
from app.ondc.bpp.client import bpp_client
from app.core.settings import settings

# Mock incoming /confirm payload from Pramaan (BAP)
incoming_confirm_payload = {
    "context": {
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
    },
    "message": {
        "order": {
            "id": "2026-07-27-1001",
            "state": "Created",
            "provider": {
                "id": "P1",
                "locations": [{"id": "L1"}]
            },
            "items": [
                {"id": "I1", "fulfillment_id": "F1", "quantity": {"count": 1}},
                {"id": "I2", "fulfillment_id": "F1", "quantity": {"count": 1}}
            ],
            "billing": {
                "name": "John Doe",
                "phone": "9876543210",
                "address": {"door": "123", "building": "Apt 1", "street": "MG Road", "city": "Bengaluru", "state": "Karnataka", "area_code": "560001"}
            },
            "fulfillments": [
                {
                    "id": "F1",
                    "type": "Delivery",
                    "tracking": False,
                    "end": {
                        "location": {
                            "gps": "12.9715987,77.5945627",
                            "address": {"area_code": "560001"}
                        },
                        "contact": {"phone": "9876543210"}
                    }
                }
            ],
            "payment": {
                "type": "ON-ORDER",
                "status": "PAID",
                "collected_by": "BAP",
                "@ondc/org/buyer_app_finder_fee_type": "percent",
                "@ondc/org/buyer_app_finder_fee_amount": "3",
                "@ondc/org/settlement_details": [
                    {
                        "settlement_counterparty": "buyer-app",
                        "settlement_phase": "completed",
                        "settlement_type": "upi",
                        "upi_address": "gpay@okicici",
                        "settlement_bank_account_no": "XXXXXXXXXX",
                        "settlement_ifsc_code": "XXXXXXXXX",
                        "beneficiary_name": "Test Name",
                        "bank_name": "Test Bank",
                        "branch_name": "Test Branch"
                    }
                ]
            }
        }
    }
}

print("=== INCOMING PAYMENT SETTLEMENT DETAILS ===")
print(json.dumps(incoming_confirm_payload["message"]["order"]["payment"], indent=2))
