import hashlib
import os
import secrets
import json
import base64
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any, Union, Optional
from app.core.settings import settings


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a unique salt."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        100000
    )
    # Store both salt and key in hex format
    return f"{salt.hex()}:{key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against its hashed value."""
    try:
        salt_hex, key_hex = hashed_password.split(":")
        salt = bytes.fromhex(salt_hex)
        key = bytes.fromhex(key_hex)
        
        new_key = hashlib.pbkdf2_hmac(
            'sha256',
            plain_password.encode('utf-8'),
            salt,
            100000
        )
        return secrets.compare_digest(key, new_key)
    except Exception:
        return False


def create_access_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None,
    secret_key: str = settings.SECRET_KEY
) -> str:
    """Create a signed JWT-like access token using HMAC-SHA256."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
    payload = {
        "sub": str(subject),
        "exp": int(expire.timestamp())
    }
    
    header = {"alg": "HS256", "typ": "JWT"}
    
    def b64_encode(d: dict) -> str:
        s = json.dumps(d, separators=(',', ':'))
        return base64.urlsafe_b64encode(s.encode('utf-8')).decode('utf-8').rstrip('=')
        
    header_b64 = b64_encode(header)
    payload_b64 = b64_encode(payload)
    
    signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
    signature = hmac.new(
        secret_key.encode('utf-8'),
        signing_input,
        hashlib.sha256
    ).digest()
    
    signature_b64 = base64.urlsafe_b64encode(signature).decode('utf-8').rstrip('=')
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def decode_access_token(
    token: str,
    secret_key: str = settings.SECRET_KEY
) -> Optional[dict]:
    """Decode and verify a JWT-like access token."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
            
        header_b64, payload_b64, signature_b64 = parts
        
        signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
        expected_signature = hmac.new(
            secret_key.encode('utf-8'),
            signing_input,
            hashlib.sha256
        ).digest()
        
        def b64_decode(s: str) -> dict:
            padding = len(s) % 4
            if padding:
                s += "=" * (4 - padding)
            decoded_bytes = base64.urlsafe_b64decode(s.encode('utf-8'))
            return json.loads(decoded_bytes.decode('utf-8'))
            
        expected_sig_b64 = base64.urlsafe_b64encode(expected_signature).decode('utf-8').rstrip('=')
        if not secrets.compare_digest(expected_sig_b64, signature_b64):
            return None
            
        payload = b64_decode(payload_b64)
        
        exp = payload.get("exp")
        if not exp:
            return None
            
        if datetime.now(timezone.utc).timestamp() > exp:
            return None
            
        return payload
    except Exception:
        return None
