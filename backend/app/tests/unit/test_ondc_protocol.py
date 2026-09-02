import json
import time
from datetime import datetime, timezone, timedelta
from app.ondc.crypto.utils import (
    calculate_blake2b_digest,
    generate_auth_header,
    verify_auth_header,
    load_private_key,
    load_public_key,
)
from app.ondc.validators.protocol import validate_timestamp, parse_iso_datetime
from app.ondc.mapper.search import SearchMapper
from app.core.settings import settings


def test_blake2b_digest():
    body = b'{"test": "data"}'
    digest = calculate_blake2b_digest(body)
    assert isinstance(digest, str)
    assert len(digest) > 0


def test_signature_generation_and_verification():
    body = b'{"context": {"action": "search"}, "message": {}}'
    
    # Generate ONDC compliant authorization header
    auth_header = generate_auth_header(
        body=body,
        subscriber_id=settings.ONDC_SUBSCRIBER_ID,
        unique_key_id=settings.ONDC_UNIQUE_KEY_ID,
        private_key_str=settings.ONDC_SIGNING_PRIVATE_KEY,
    )
    
    assert auth_header.startswith("Signature ")
    assert 'keyId="' in auth_header
    assert 'signature="' in auth_header
    
    # Verify the generated header using the corresponding public key
    is_valid = verify_auth_header(
        header=auth_header,
        body=body,
        public_key_str=settings.ONDC_SIGNING_PUBLIC_KEY,
    )
    assert is_valid is True


def test_timestamp_validation():
    # 1. Test current timestamp (valid)
    now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    is_valid, err = validate_timestamp(now_str)
    assert is_valid is True
    assert err == ""

    # 2. Test expired timestamp
    old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    old_str = old_time.isoformat().replace("+00:00", "Z")
    is_valid, err = validate_timestamp(old_str)
    assert is_valid is False
    assert "outside acceptable skew window" in err

    # 3. Test future timestamp
    future_time = datetime.now(timezone.utc) + timedelta(minutes=10)
    future_str = future_time.isoformat().replace("+00:00", "Z")
    is_valid, err = validate_timestamp(future_str)
    assert is_valid is False
    assert "outside acceptable skew window" in err


def test_search_mapper():
    mock_payload = {
        "context": {
            "transaction_id": "test-tx-123",
            "bpp_id": "bpp-1",
            "bpp_uri": "https://bpp-1.com/ondc",
        },
        "message": {
            "catalog": {
                "bpp/providers": [
                    {
                        "id": "provider-1",
                        "descriptor": {
                            "name": "Provider One"
                        },
                        "items": [
                            {
                                "id": "item-1",
                                "location_id": "L1",
                                "parent_item_id": "V1",
                                "fulfillment_id": "F1",
                                "tags": [],
                                "descriptor": {
                                    "name": "Item One",
                                    "short_desc": "Short description of item one",
                                    "images": ["https://img.com/1.png"]
                                },
                                "price": {
                                    "value": "99.50",
                                    "currency": "INR"
                                }
                            }
                        ]
                    }
                ]
            }
        }
    }
    
    products = SearchMapper.map_on_search_to_products(mock_payload)
    assert len(products) == 1
    
    product = products[0]
    assert product.id == "item-1"
    assert product.name == "Item One"
    assert product.description == "Short description of item one"
    assert product.price == 99.50
    assert product.currency == "INR"
    assert product.images == ["https://img.com/1.png"]
    assert product.provider_id == "provider-1"
    assert product.provider_name == "Provider One"
    assert product.bpp_id == "bpp-1"
    assert product.bpp_uri == "https://bpp-1.com/ondc"
    assert product.transaction_id == "test-tx-123"
    assert product.location_id == "L1"
    assert product.parent_item_id == "V1"
    assert product.fulfillment_id == "F1"
    assert product.tags == []
