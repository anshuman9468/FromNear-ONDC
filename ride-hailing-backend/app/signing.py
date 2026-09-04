"""ONDC HTTP Signature construction for the registered Ed25519 key pair."""
import base64
import hashlib
import json
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .config import settings


def canonical_json(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def authorization_header(body: bytes, ttl_seconds: int = 300) -> str:
    if not settings.unique_key_id or not settings.signing_private_key:
        raise RuntimeError("ONDC signing configuration is incomplete")
    key_bytes = base64.b64decode(settings.signing_private_key)
    # ONDC's utility can supply a 32-byte seed or a 64-byte libsodium keypair.
    signing_key = Ed25519PrivateKey.from_private_bytes(key_bytes[:32])
    created = int(time.time())
    expires = created + ttl_seconds
    digest = base64.b64encode(hashlib.blake2b(body, digest_size=64).digest()).decode()
    signing_string = f"(created): {created}\n(expires): {expires}\ndigest: BLAKE-512={digest}".encode()
    signature = base64.b64encode(signing_key.sign(signing_string)).decode()
    return (
        f'Signature keyId="{settings.subscriber_id}|{settings.unique_key_id}|ed25519",'
        f'algorithm="ed25519",created="{created}",expires="{expires}",'
        f'headers="(created) (expires) digest",signature="{signature}"'
    )
