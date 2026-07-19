from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional


class OndcContext(BaseModel):
    domain: str
    country: str
    city: str
    action: str
    core_version: str = Field(alias="core_version", default="1.2.0")
    bap_id: str
    bap_uri: str
    bpp_id: Optional[str] = None
    bpp_uri: Optional[str] = None
    transaction_id: str
    message_id: str
    timestamp: str
    ttl: Optional[str] = "PT30S"

    class Config:
        populate_by_name = True


class OndcSearchIntent(BaseModel):
    item: Optional[Dict[str, Any]] = None
    provider: Optional[Dict[str, Any]] = None
    fulfillment: Optional[Dict[str, Any]] = None
    category: Optional[Dict[str, Any]] = None


class OndcSearchMessage(BaseModel):
    intent: OndcSearchIntent


class OndcSearchPayload(BaseModel):
    context: OndcContext
    message: OndcSearchMessage


class OndcOnSearchMessage(BaseModel):
    catalog: Optional[Dict[str, Any]] = None


class OndcOnSearchPayload(BaseModel):
    context: OndcContext
    message: OndcOnSearchMessage


# Response models
class OndcAck(BaseModel):
    status: str  # "ACK" or "NACK"


class OndcAckMessage(BaseModel):
    ack: OndcAck


class OndcError(BaseModel):
    type: str
    code: str
    message: str


class OndcAckResponse(BaseModel):
    message: OndcAckMessage
    error: Optional[OndcError] = None
