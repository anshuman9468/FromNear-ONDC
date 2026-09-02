from pydantic import BaseModel, Field
from typing import List, Optional


class ProductModel(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    price: float
    currency: str = "INR"
    images: List[str] = []
    provider_id: str
    provider_name: str
    bpp_id: str
    bpp_uri: str
    transaction_id: str
    location_id: str = ""
    parent_item_id: str = ""
    fulfillment_id: str = ""
    tags: List[dict] = Field(default_factory=list)
