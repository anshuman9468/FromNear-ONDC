from dataclasses import dataclass
from typing import Optional

from app.core.settings import settings


@dataclass(frozen=True)
class AccommodationBuyerProfile:
    subscriber_id: str
    subscriber_uri: str
    unique_key_id: str
    signing_private_key: str
    signing_public_key: Optional[str]
    encryption_private_key: Optional[str]
    encryption_public_key: Optional[str]
    domain: str
    country: str
    city: str
    version: str
    gateway_url: str


def get_accommodation_buyer_profile() -> AccommodationBuyerProfile:
    return AccommodationBuyerProfile(
        subscriber_id=settings.ACCOMMODATION_ONDC_SUBSCRIBER_ID,
        subscriber_uri=settings.ACCOMMODATION_ONDC_SUBSCRIBER_URI,
        unique_key_id=settings.ACCOMMODATION_ONDC_UNIQUE_KEY_ID or settings.ONDC_UNIQUE_KEY_ID,
        signing_private_key=settings.ACCOMMODATION_ONDC_SIGNING_PRIVATE_KEY
        or settings.ONDC_SIGNING_PRIVATE_KEY,
        signing_public_key=settings.ACCOMMODATION_ONDC_SIGNING_PUBLIC_KEY
        or settings.ONDC_SIGNING_PUBLIC_KEY,
        encryption_private_key=settings.ACCOMMODATION_ONDC_ENC_PRIVATE_KEY
        or settings.ONDC_ENC_PRIVATE_KEY,
        encryption_public_key=settings.ACCOMMODATION_ONDC_ENC_PUBLIC_KEY
        or settings.ONDC_ENC_PUBLIC_KEY,
        domain=settings.ACCOMMODATION_ONDC_DOMAIN,
        country=settings.ONDC_COUNTRY,
        city=settings.ACCOMMODATION_ONDC_CITY or settings.ONDC_CITY,
        version=settings.ACCOMMODATION_ONDC_VERSION,
        gateway_url=settings.ONDC_GATEWAY_URL,
    )


def get_public_key() -> Optional[str]:
    return settings.ACCOMMODATION_ONDC_SIGNING_PUBLIC_KEY or settings.ONDC_SIGNING_PUBLIC_KEY
