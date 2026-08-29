from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True, extra="ignore")

    subscriber_id: str = "ride.fromnear.com"
    subscriber_uri: str = "https://ride.fromnear.com"
    domain: str = "ONDC:TRV10"
    role: str = "BAP"
    country: str = "IND"
    city: str = "*"
    core_version: str = "2.0.0"
    gateway_url: str = "https://preprod.gateway.ondc.org"
    registry_url: str = "https://preprod.registry.ondc.org"
    unique_key_id: str = ""
    signing_private_key: str = ""
    signing_public_key: str = ""


settings = Settings(
    subscriber_id=__import__("os").getenv("ONDC_SUBSCRIBER_ID", "ride.fromnear.com"),
    subscriber_uri=__import__("os").getenv("ONDC_SUBSCRIBER_URI", "https://ride.fromnear.com"),
    domain=__import__("os").getenv("ONDC_DOMAIN", "ONDC:TRV10"),
    role=__import__("os").getenv("ONDC_TYPE", "BAP"),
    country=__import__("os").getenv("ONDC_COUNTRY", "IND"),
    city=__import__("os").getenv("ONDC_CITY", "*"),
    core_version=__import__("os").getenv("ONDC_CORE_VERSION", "2.0.0"),
    gateway_url=__import__("os").getenv("ONDC_GATEWAY_URL", "https://preprod.gateway.ondc.org"),
    registry_url=__import__("os").getenv("ONDC_REGISTRY_URL", "https://preprod.registry.ondc.org"),
    unique_key_id=__import__("os").getenv("ONDC_UNIQUE_KEY_ID", ""),
    signing_private_key=__import__("os").getenv("ONDC_SIGNING_PRIVATE_KEY", ""),
    signing_public_key=__import__("os").getenv("ONDC_SIGNING_PUBLIC_KEY", ""),
)
