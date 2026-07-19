from pydantic import BaseModel
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
