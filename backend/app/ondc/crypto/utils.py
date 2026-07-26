import base64
import hashlib
import hmac
import time
import logging
from typing import Dict, Tuple, Optional
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from app.core.settings import settings

logger = logging.getLogger(__name__)


def calculate_blake2b_digest(body: bytes) -> str:
    """Calculate BLAKE2b (digest_size=64) hash of the request body, base64 encoded."""
    h = hashlib.blake2b(digest_size=64)
    h.update(body)
    encoded = base64.b64encode(h.digest()).decode("utf-8")
    return f"BLAKE-512={encoded}"


def load_private_key(key_str: str) -> ed25519.Ed25519PrivateKey:
    """Robustly load an Ed25519 private key from Base64, PEM, DER, or hex."""
    # 1. Try Base64 raw bytes
    try:
        raw_bytes = base64.b64decode(key_str)
        if len(raw_bytes) == 32:
            return ed25519.Ed25519PrivateKey.from_private_bytes(raw_bytes)
        elif len(raw_bytes) == 64:
            # Libsodium often provides 64 bytes (private key + public key)
            # cryptography library expects just the 32-byte seed
            return ed25519.Ed25519PrivateKey.from_private_bytes(raw_bytes[:32])
    except Exception:
        pass
    
    # 2. Try PEM format
    try:
        if "PRIVATE KEY" in key_str:
            return serialization.load_pem_private_key(key_str.encode("utf-8"), password=None)
    except Exception:
        pass
        
    # 3. Try DER format
    try:
        raw_bytes = base64.b64decode(key_str)
        return serialization.load_der_private_key(raw_bytes, password=None)
    except Exception:
        pass
        
    # 4. Try Hex
    try:
        raw_bytes = bytes.fromhex(key_str)
        if len(raw_bytes) == 32:
            return ed25519.Ed25519PrivateKey.from_private_bytes(raw_bytes)
        elif len(raw_bytes) == 64:
            return ed25519.Ed25519PrivateKey.from_private_bytes(raw_bytes[:32])
    except Exception:
        pass
        
    raise ValueError("Failed to load Ed25519 private key using available formats")


def load_public_key(key_str: str) -> ed25519.Ed25519PublicKey:
    """Robustly load an Ed25519 public key from Base64, PEM, DER, or hex."""
    # 1. Try Base64 raw bytes
    try:
        raw_bytes = base64.b64decode(key_str)
        if len(raw_bytes) == 32:
            return ed25519.Ed25519PublicKey.from_public_bytes(raw_bytes)
    except Exception:
        pass
        
    # 2. Try PEM format
    try:
        if "PUBLIC KEY" in key_str:
            return serialization.load_pem_public_key(key_str.encode("utf-8"))
    except Exception:
        pass
        
    # 3. Try DER format
    try:
        raw_bytes = base64.b64decode(key_str)
        return serialization.load_der_public_key(raw_bytes)
    except Exception:
        pass
        
    # 4. Try Hex
    try:
        raw_bytes = bytes.fromhex(key_str)
        if len(raw_bytes) == 32:
            return ed25519.Ed25519PublicKey.from_public_bytes(raw_bytes)
    except Exception:
        pass
        
    raise ValueError("Failed to load Ed25519 public key using available formats")


def generate_signing_string(created: int, expires: int, digest: str) -> bytes:
    """Generate the signing string for ONDC authorization header."""
    signing_string = f"(created): {created}\n(expires): {expires}\ndigest: {digest}"
    return signing_string.encode("utf-8")


def generate_auth_header(
    body: bytes,
    subscriber_id: Optional[str] = None,
    unique_key_id: Optional[str] = None,
    private_key_str: Optional[str] = None,
    ttl: int = 300,
) -> str:
    """Generate a valid ONDC Authorization header for a request body."""
    if subscriber_id is None:
        subscriber_id = settings.ONDC_SUBSCRIBER_ID
    if unique_key_id is None:
        unique_key_id = settings.ONDC_UNIQUE_KEY_ID
    if private_key_str is None:
        private_key_str = settings.ONDC_SIGNING_PRIVATE_KEY
        
    created = int(time.time())
    expires = created + ttl
    digest = calculate_blake2b_digest(body)
    
    signing_string = generate_signing_string(created, expires, digest)
    
    private_key = load_private_key(private_key_str)
    signature_bytes = private_key.sign(signing_string)
    signature = base64.b64encode(signature_bytes).decode("utf-8")
    
    auth_header = (
        f'Signature keyId="{subscriber_id}|{unique_key_id}|ed25519",'
        f'algorithm="ed25519",'
        f'created="{created}",'
        f'expires="{expires}",'
        f'headers="(created) (expires) digest",'
        f'signature="{signature}"'
    )
    return auth_header


def parse_auth_header(header: str) -> Dict[str, str]:
    """Parse the comma-separated authorization header key-value pairs."""
    if not header.startswith("Signature "):
        raise ValueError("Invalid auth header prefix")
        
    pairs = header[10:].split(",")
    parsed = {}
    for pair in pairs:
        if "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        parsed[k.strip()] = v.strip().strip('"')
    return parsed


def verify_auth_header(
    header: str,
    body: bytes,
    public_key_str: str,
    time_skew_allowance: int = 300,
) -> bool:
    """Verify an ONDC Authorization header against a request body and sender public key."""
    try:
        parsed = parse_auth_header(header)
        
        signature = parsed.get("signature")
        created = int(parsed.get("created", 0))
        expires = int(parsed.get("expires", 0))
        algorithm = parsed.get("algorithm")
        
        if not signature or not created or not expires:
            logger.warning("Missing required fields in signature header")
            return False
            
        if algorithm != "ed25519":
            logger.warning(f"Unsupported signature algorithm: {algorithm}")
            return False
            
        # Check timestamps
        now = int(time.time())
        if now > expires + time_skew_allowance:
            logger.warning(f"Signature expired. Expired: {expires}, Now: {now}")
            return False
            
        if created > now + time_skew_allowance:
            logger.warning(f"Signature created in the future. Created: {created}, Now: {now}")
            return False
            
        # Verify body digest
        digest = calculate_blake2b_digest(body)
        
        # Verify signature
        signing_string = generate_signing_string(created, expires, digest)
        
        public_key = load_public_key(public_key_str)
        signature_bytes = base64.b64decode(signature)
        
        public_key.verify(signature_bytes, signing_string)
        return True
    except Exception as e:
        logger.error(f"Signature verification failed: {str(e)}", exc_info=True)
        return False
