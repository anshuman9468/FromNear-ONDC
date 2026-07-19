# ONDC Pramaan Certification Setup Guide

This guide contains the manual infrastructure configuration, credentials, cryptographic keys, and settings required to run the FromNear ONDC Buyer Network Participant (BAP) in the staging registry and successfully complete Pramaan certification.

---

## 1. Network & Callback Tunnel Configuration

ONDC is an asynchronous callback-based protocol. The ONDC Gateway and seller apps (BPPs) require a publicly accessible URL to send callback payloads (`/on_search`, `/on_select`, `/on_init`, etc.) to your BAP application.

### Setting up a Public URL (e.g., via ngrok)
1. Expose the FastAPI backend container port (`8000` by default):
   ```bash
   ngrok http 8000
   ```
2. Note your forwarding URL (e.g., `https://your-tunnel-subdomain.ngrok-free.app`).
3. Set your **BAP URI** to:
   `https://your-tunnel-subdomain.ngrok-free.app/api/v1/ondc`

---

## 2. Cryptographic Key Generation

ONDC requires Ed25519 keypairs for signing requests/responses and X25519 keypairs for payload encryption/decryption.

You can generate these using OpenSSL or Python utilities.

### Using Python to Generate ONDC-Compliant Keys
Create a scratch script in `backend/app/scratch_keygen.py` or run the following python command to generate base64-encoded keys:

```python
import base64
from nacl.public import PrivateKey as X25519PrivateKey
from nacl.signing import SigningKey as Ed25519SigningKey

# Generate Signing Keys (Ed25519)
signing_key = Ed25519SigningKey.generate()
signing_private = base64.b64encode(signing_key.encode()).decode('utf-8')
signing_public = base64.b64encode(signing_key.verify_key.encode()).decode('utf-8')

# Generate Encryption Keys (X25519)
enc_key = X25519PrivateKey.generate()
enc_private = base64.b64encode(enc_key.encode()).decode('utf-8')
enc_public = base64.b64encode(enc_key.public_key.encode()).decode('utf-8')

print(f"ONDC_SIGNING_PRIVATE_KEY={signing_private}")
print(f"ONDC_SIGNING_PUBLIC_KEY={signing_public}")
print(f"ONDC_ENC_PRIVATE_KEY={enc_private}")
print(f"ONDC_ENC_PUBLIC_KEY={enc_public}")
```

---

## 3. Environment Variables Configuration

Create a `.env` file in the `backend/` directory and populate it with your staging and registry credentials:

```ini
# --- ONDC BAP STAGING IDENTIFIERS ---
ONDC_SUBSCRIBER_ID=fromnear-buyer-staging.com
ONDC_SUBSCRIBER_URI=https://your-tunnel-subdomain.ngrok-free.app/api/v1/ondc
ONDC_UNIQUE_KEY_ID=fromnear-bap-key-id-1

# --- CRYPTOGRAPHIC KEYS (Generated in Step 2) ---
ONDC_SIGNING_PRIVATE_KEY=your_base64_signing_private_key
ONDC_SIGNING_PUBLIC_KEY=your_base64_signing_public_key
ONDC_ENC_PRIVATE_KEY=your_base64_encryption_private_key
ONDC_ENC_PUBLIC_KEY=your_base64_encryption_public_key

# --- NETWORK GATEWAYS & REGISTRY ---
# Staging Gateway URL for Retail
ONDC_GATEWAY_URL=https://staging.gateway.ondc.org

# Staging Registry URL for Looking up public keys of BPPs/Gateways
ONDC_REGISTRY_URL=https://staging.registry.ondc.org/lookup

# Enable signature verification for live staging (Disable ONLY during local testing)
ONDC_VERIFY_SIGNATURES=True
```

---

## 4. ONDC Staging Registry Registration

Before you can receive calls or query BPPs, you must register your BAP on the ONDC Staging Portal:

1. **Access Staging Registry Portal**: Go to the ONDC Staging Registry portal.
2. **Submit BAP Details**:
   - **Subscriber ID**: Use your configured `ONDC_SUBSCRIBER_ID`.
   - **Subscriber URL (BAP URI)**: Use `https://your-tunnel-subdomain.ngrok-free.app/api/v1/ondc`.
   - **Unique Key ID**: Use `fromnear-bap-key-id-1`.
   - **Signing Public Key**: Provide the value of `ONDC_SIGNING_PUBLIC_KEY`.
   - **Encryption Public Key**: Provide the value of `ONDC_ENC_PUBLIC_KEY`.
3. **Download ONDC Public Key**: Note down the ONDC Registry Public Key for verifying incoming signatures from the ONDC gateway.

---

## 5. Deployment and Verification

1. **Run the Database and FastAPI Backend**:
   ```bash
   docker compose up --build -d
   ```
2. **Verify Swagger Docs**:
   Access `http://localhost:8000/docs` to verify endpoints are up.
3. **Run End-to-End Test Suite**:
   ```bash
   PYTHONPATH=. .venv/bin/pytest
   ```

---

## 6. Pramaan Testing Guidelines

Once your BAP is registered and accessible via your Ngrok public URL:
1. Trigger a Search request by making a `POST` to `/api/v1/search` with the query parameters required by the Pramaan test suite.
2. Monitor log statements and verification steps to ensure signed callback headers are successfully processed.
3. Follow the sequence: `search` -> `select` -> `init` -> `confirm` -> `status` -> `track` -> `cancel` -> `support`.
