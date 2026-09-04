import httpx

from .config import settings
from .signing import authorization_header, canonical_json


async def dispatch(payload: dict) -> dict:
    action = payload["context"]["action"]
    if action == "search":
        url = settings.gateway_search_url
    else:
        bpp_uri = payload["context"].get("bpp_uri")
        if not bpp_uri:
            raise ValueError(f"{action} requires bpp_uri")
        url = f"{bpp_uri.rstrip('/')}/{action}"
    body = canonical_json(payload)
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, content=body, headers={
            "Content-Type": "application/json",
            "Authorization": authorization_header(body),
        })
    response.raise_for_status()
    return response.json() if response.content else {"message": {"ack": {"status": "ACK"}}}
