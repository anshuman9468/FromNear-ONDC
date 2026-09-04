import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Only TRV10 Buyer NP settings belong in this isolated service."""

    model_config = SettingsConfigDict(case_sensitive=True, extra="ignore")

    subscriber_id: str = os.getenv("ONDC_SUBSCRIBER_ID", "ride.fromnear.com")
    subscriber_uri: str = os.getenv("ONDC_SUBSCRIBER_URI", "https://ride.fromnear.com")
    domain: str = "ONDC:TRV10"
    country: str = os.getenv("ONDC_COUNTRY", "IND")
    default_city: str = os.getenv("ONDC_CITY", "std:080")
    version: str = os.getenv("ONDC_VERSION", "2.0.1")
    gateway_search_url: str = os.getenv("ONDC_GATEWAY_SEARCH_URL", "https://preprod.gateway.ondc.org/search")
    static_terms_url: str = os.getenv("ONDC_STATIC_TERMS_URL", "https://ride.fromnear.com/static-terms.txt")
    finder_fee_percentage: str = os.getenv("ONDC_FINDER_FEE_PERCENTAGE", "1")
    unique_key_id: str = os.getenv("ONDC_UNIQUE_KEY_ID", "")
    signing_private_key: str = os.getenv("ONDC_SIGNING_PRIVATE_KEY", "")
    signing_public_key: str = os.getenv("ONDC_SIGNING_PUBLIC_KEY", "")


settings = Settings()
