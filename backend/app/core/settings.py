from typing import Any, Dict, Optional
from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )

    PROJECT_NAME: str = "ONDC Buyer Certification"
    API_V1_STR: str = "/api/v1"

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "ondc_buyer"
    POSTGRES_PORT: int = 5432
    DATABASE_URI: Optional[str] = None
    ASYNC_DATABASE_URI: Optional[str] = None

    @field_validator("DATABASE_URI", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], values: Any) -> Any:
        if isinstance(v, str):
            return v
        data = values.data if hasattr(values, "data") else values
        if not isinstance(data, dict):
            return v
        server = data.get("POSTGRES_SERVER")
        user = data.get("POSTGRES_USER")
        password = data.get("POSTGRES_PASSWORD")
        db = data.get("POSTGRES_DB")
        port = data.get("POSTGRES_PORT")
        return f"postgresql://{user}:{password}@{server}:{port}/{db}"

    @field_validator("ASYNC_DATABASE_URI", mode="before")
    @classmethod
    def assemble_async_db_connection(cls, v: Optional[str], values: Any) -> Any:
        if isinstance(v, str):
            return v
        data = values.data if hasattr(values, "data") else values
        if not isinstance(data, dict):
            return v
        server = data.get("POSTGRES_SERVER")
        user = data.get("POSTGRES_USER")
        password = data.get("POSTGRES_PASSWORD")
        db = data.get("POSTGRES_DB")
        port = data.get("POSTGRES_PORT")
        return f"postgresql+asyncpg://{user}:{password}@{server}:{port}/{db}"

    # Security
    SECRET_KEY: str = "supersecretkeychangeinproduction"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days

    # ONDC Protocol Configuration
    ONDC_SUBSCRIBER_ID: str = "bap.fromnear.com"
    ONDC_SUBSCRIBER_URI: str = "https://bap.fromnear.com/api/v1/ondc"
    ONDC_GATEWAY_URL: str = "https://staging.gateway.ondc.org"
    ONDC_REGISTRY_URL: str = "https://staging.registry.ondc.org"
    ONDC_UNIQUE_KEY_ID: str = "bap-unique-key-id"
    ONDC_TYPE: str = "BAP"  # BAP (Buyer Application Platform) or BPP (Provider)
    ONDC_DOMAIN: str = "nic2004:52110"  # Retail domain
    ONDC_COUNTRY: str = "IND"
    ONDC_CITY: str = "std:080"  # e.g., Bengaluru
    ONDC_VERSION: str = "1.2.0"  # ONDC API version

    # ONDC Cryptographic Keys (Base64-encoded string, in hex or standard format)
    # Note: ONDC uses Ed25519 signing keys and X25519 encryption keys.
    # We provide default keys for local tests, which will be generated or loaded in code.
    ONDC_SIGNING_PRIVATE_KEY: str = "MC4CAQAwBQYDK2VwBCIEINT3ZlYyE8tLgU7w1+J9wLzC2e+Y019V8B0V05YkR7m5"
    ONDC_SIGNING_PUBLIC_KEY: str = "MCowBQYDK2VwAyEAWIQTxIJjgQ+BHrEIwnEioCMxtXBLswKuUayrWP5e0xk="
    ONDC_ENC_PRIVATE_KEY: str = "MC4CAQAwBQYDK2VwBCIEINT3ZlYyE8tLgU7w1+J9wLzC2e+Y019V8B0V05YkR7m5"
    ONDC_ENC_PUBLIC_KEY: str = "MCowBQYDK2VwAyEAWIQTxIJjgQ+BHrEIwnEioCMxtXBLswKuUayrWP5e0xk="

    ONDC_VERIFY_SIGNATURES: bool = True



settings = Settings()
