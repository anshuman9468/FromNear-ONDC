from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime


class AddressBase(BaseModel):
    name: str
    phone: str
    house: str
    street: str
    city: str
    state: str
    pincode: str


class AddressCreate(AddressBase):
    pass


class AddressSchema(AddressBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class OrderItemSchema(BaseModel):
    id: int
    item_id: str
    item_name: str
    quantity: int
    price: float

    class Config:
        from_attributes = True


class OrderSchema(BaseModel):
    id: int
    user_id: int
    transaction_id: str
    message_id: str
    provider_id: Optional[str] = None
    provider_name: Optional[str] = None
    order_id: Optional[str] = None
    state: str
    amount: float
    currency: str
    raw_response: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemSchema] = []

    class Config:
        from_attributes = True


class SelectRequestSchema(BaseModel):
    transaction_id: str
    bpp_id: str
    bpp_uri: str
    provider_id: str
    provider_name: str
    items: List[dict]  # format: [{"id": "item_id", "name": "name", "price": 10.0, "quantity": 1}]


class InitRequestSchema(BaseModel):
    transaction_id: str
    billing_address: AddressBase
    shipping_address: AddressBase


class ConfirmRequestSchema(BaseModel):
    transaction_id: str


class CancelRequestSchema(BaseModel):
    transaction_id: str
    cancellation_reason_id: Optional[str] = "001"


class SupportRequestSchema(BaseModel):
    transaction_id: str
