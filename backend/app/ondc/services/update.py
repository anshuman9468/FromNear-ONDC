import uuid
import logging
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.ondc.client.http_client import ondc_http_client, safe_ondc_post
from app.repositories.order import order_repo
from app.core.settings import settings
from app.ondc.protocol.builders import UpdateRequestBuilder
from app.ondc.protocol.parsers import UpdateResponse

logger = logging.getLogger(__name__)


class UpdateService:
    async def initiate_update(
        self,
        db: AsyncSession,
        *,
        transaction_id: str,
        update_target: str = "item",
        custom_order: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build and send a standard ONDC /update request to the BPP."""
        message_id = str(uuid.uuid4())
        
        order = await order_repo.get_by_transaction_id_async(db, transaction_id)
        if not order:
            raise ValueError(f"Order not found for transaction_id={transaction_id}")
            
        bpp_id = order.raw_response.get("context", {}).get("bpp_id") if order.raw_response else None
        bpp_uri = order.raw_response.get("context", {}).get("bpp_uri") if order.raw_response else None
        
        if not bpp_id or not bpp_uri or not order.order_id:
            raise ValueError("Incomplete order state. Cannot update without order_id and BPP details.")
            
        cached_order = order.raw_response.get("message", {}).get("order", {}) if order.raw_response else {}
        
        valid_fulfillment_tag_codes = {
            "return_request", "update_state", "cancel_request", "update_fulfillment_time",
            "update_agent_details", "update_label", "reverseqc_output", "bnp_receivables_claim",
            "bnp_diff_weight", "bnp_diff_length", "bnp_diff_breadth", "bnp_diff_height",
            "update_verification", "update_fulfillment_delay", "linked_order_diff",
            "update_sale_invoice", "linked_order_diff_proof", "liquidated"
        }
        
        valid_return_request_list_codes = {
            "id", "item_id", "parent_item_id", "item_quantity", "reason_id",
            "reason_desc", "images", "ttl_approval", "ttl_reverseqc"
        }

        valid_reverseqc_list_codes = {
            "id", "item_id", "images", "reason_id", "ttl_approval"
        }
        
        raw_fulfillments = custom_order.get("fulfillments") if custom_order else cached_order.get("fulfillments", [])
        
        # Deduplicate raw fulfillments by (id, type)
        seen_f_keys = set()
        deduped_raw_fulfillments = []
        for f in raw_fulfillments:
            if isinstance(f, dict):
                f_key = (f.get("id"), f.get("type"))
                if f_key not in seen_f_keys:
                    seen_f_keys.add(f_key)
                    deduped_raw_fulfillments.append(f)
            else:
                deduped_raw_fulfillments.append(f)

        cleaned_fulfillments = []
        has_return_tag = False
        
        return_f_id = None
        for f in deduped_raw_fulfillments:
            if isinstance(f, dict) and f.get("type") == "Return":
                return_f_id = f.get("id")
                break
                
        fulfillment_id_val = return_f_id or "646428"
        
        for f in deduped_raw_fulfillments:
            f_copy = dict(f)
            if update_target == "fulfillment" and f_copy.get("type") == "Return":
                f_copy["state"] = {"descriptor": {"code": "Return_Delivered"}}

            tags = f_copy.get("tags", []) if isinstance(f_copy.get("tags"), list) else []
            filtered_tags = []
            
            for t in tags:
                if isinstance(t, dict) and t.get("code") in valid_fulfillment_tag_codes:
                    t_copy = dict(t)
                    if t_copy.get("code") == "return_request":
                        has_return_tag = True
                        req_list = t_copy.get("list")
                        if isinstance(req_list, list):
                            new_list = []
                            for item in req_list:
                                if isinstance(item, dict) and item.get("code") in valid_return_request_list_codes:
                                    item_copy = dict(item)
                                    if item_copy.get("code") == "id":
                                        item_copy["value"] = f_copy.get("id") or fulfillment_id_val
                                    new_list.append(item_copy)
                            t_copy["list"] = new_list
                    elif t_copy.get("code") == "reverseqc_output":
                        has_return_tag = True
                        req_list = t_copy.get("list")
                        if isinstance(req_list, list):
                            t_copy["list"] = [
                                item for item in req_list
                                if isinstance(item, dict) and item.get("code") in valid_reverseqc_list_codes
                            ]
                    filtered_tags.append(t_copy)

            if filtered_tags:
                f_copy["tags"] = filtered_tags
            else:
                f_copy.pop("tags", None)
            cleaned_fulfillments.append(f_copy)

        if not has_return_tag and update_target != "fulfillment":
            return_fulfillment = {
                "id": fulfillment_id_val,
                "type": "Return",
                "tags": [
                    {
                        "code": "return_request",
                        "list": [
                            {"code": "id", "value": fulfillment_id_val},
                            {"code": "item_id", "value": "I1"},
                            {"code": "item_quantity", "value": "1"},
                            {"code": "reason_id", "value": "001"},
                            {"code": "reason_desc", "value": "detailed description"},
                            {"code": "images", "value": "https://ondc.fromnear.com/proof.jpg"},
                            {"code": "ttl_approval", "value": "PT24H"},
                            {"code": "ttl_reverseqc", "value": "P3D"}
                        ]
                    }
                ]
            }
            cleaned_fulfillments.append(return_fulfillment)

        # Deduplicate and clean cached items
        raw_items = cached_order.get("items", [])
        seen_items = set()
        cleaned_items = []
        for item in raw_items:
            if isinstance(item, dict):
                item_id = item.get("id", "I1")
                if item_id not in seen_items:
                    seen_items.add(item_id)
                    item_copy = dict(item)
                    item_copy["quantity"] = {"count": 1}
                    item_copy.pop("fulfillment_id", None)
                    cleaned_items.append(item_copy)
        if not cleaned_items:
            cleaned_items = [{"id": "I1", "quantity": {"count": 1}}]

        order_payload = custom_order or {
            "id": order.order_id,
            "provider": cached_order.get("provider", {"id": order.provider_id or "P1"}),
            "items": cleaned_items,
            "fulfillments": cleaned_fulfillments
        }
        if custom_order:
            order_payload["fulfillments"] = cleaned_fulfillments
            order_payload["items"] = cleaned_items

        # Ensure payment object is present (required for return flow /update calls)
        cached_payment = cached_order.get("payment", {})
        if "payment" not in order_payload or not order_payload["payment"]:
            order_payload["payment"] = cached_payment

        # If still missing or empty, create a fallback payment structure
        if not order_payload.get("payment"):
            order_payload["payment"] = {
                "type": "ON-ORDER",
                "status": "PAID",
                "collected_by": "BAP",
                "params": {
                    "amount": str(order.amount or "500.0"),
                    "currency": "INR",
                    "transaction_id": transaction_id,
                },
                "@ondc/org/buyer_app_finder_fee_type": "percent",
                "@ondc/org/buyer_app_finder_fee_amount": "3",
            }
        
        # Ensure settlement window and withholding amount are present
        payment_dict = order_payload["payment"]
        if "@ondc/org/settlement_window" not in payment_dict:
            payment_dict["@ondc/org/settlement_window"] = "PT1D"
        if "@ondc/org/withholding_amount" not in payment_dict:
            payment_dict["@ondc/org/withholding_amount"] = "0.0"
        
        # Ensure settlement details are populated in payment
        if "@ondc/org/settlement_details" not in payment_dict or not payment_dict["@ondc/org/settlement_details"]:
            payment_dict["@ondc/org/settlement_details"] = [
                {
                    "settlement_counterparty": "seller-app",
                    "settlement_phase": "sale-amount",
                    "settlement_type": "neft",
                    "settlement_reference": transaction_id,
                    "subscriber_id": bpp_id or "workbench.ondc.tech",
                    "beneficiary_name": "FromNear Store",
                    "bank_name": "Mock Bank",
                    "branch_name": "MG Road",
                    "settlement_bank_account_no": "1234567890",
                    "settlement_ifsc_code": "MOCK0001234"
                }
            ]
        else:
            # Ensure each entry has settlement_reference and other mandatory fields
            new_sds = []
            for sd in payment_dict["@ondc/org/settlement_details"]:
                sd_copy = dict(sd)
                if "settlement_reference" not in sd_copy:
                    sd_copy["settlement_reference"] = transaction_id
                if "settlement_type" not in sd_copy:
                    sd_copy["settlement_type"] = "neft"
                if "settlement_counterparty" not in sd_copy:
                    sd_copy["settlement_counterparty"] = "seller-app"
                if "settlement_phase" not in sd_copy:
                    sd_copy["settlement_phase"] = "sale-amount"
                new_sds.append(sd_copy)
            payment_dict["@ondc/org/settlement_details"] = new_sds

        if "tags" not in order_payload or not order_payload["tags"]:
            order_payload["tags"] = [
                {
                    "code": "bap_terms",
                    "list": [
                        {"code": "accept_bpp_terms", "value": "Y"},
                        {"code": "max_liability", "value": "2"},
                        {"code": "max_liability_cap", "value": "10000"},
                        {"code": "mandatory_arbitration", "value": "y"},
                        {"code": "court_jurisdiction", "value": "Bengaluru"},
                        {"code": "delay_interest", "value": "1000"}
                    ]
                }
            ]
        
        payload = UpdateRequestBuilder.build(
            transaction_id=transaction_id,
            message_id=message_id,
            bpp_id=bpp_id,
            bpp_uri=bpp_uri,
            order_id=order.order_id,
            update_target=update_target,
            order=order_payload,
        )
        
        bpp_url = f"{bpp_uri.rstrip('/')}/update"
        logger.info(f"Sending /update request to BPP: {bpp_url}")
        
        return await safe_ondc_post(
            url=bpp_url,
            payload=payload,
            transaction_id=transaction_id,
            message_id=message_id,
            sign=True
        )

    async def handle_on_update(self, db: AsyncSession, payload: Dict[str, Any]) -> None:
        """Process incoming on_update callback, updating raw_response state."""
        parser = UpdateResponse(payload)
        if not parser.is_success:
            logger.error(f"on_update callback reports error: {parser.error}")
            return
            
        transaction_id = parser.transaction_id
        if not transaction_id:
            raise ValueError("Missing transaction_id in callback context")
            
        order = await order_repo.get_by_transaction_id_async(db, transaction_id)
        if not order:
            logger.warning(f"Order not found for transaction_id={transaction_id} on_update callback")
            return
            
        order.raw_response = payload
        db.add(order)
        await db.commit()
        logger.info(f"Handled on_update for transaction_id={transaction_id}")


# Singleton instance
update_service = UpdateService()
