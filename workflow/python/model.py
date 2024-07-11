from dataclasses import dataclass
from typing import Optional
from pydantic import BaseModel, Field

class OrderPayload(BaseModel):
    item_name: str = Field(..., alias="Name")
    quantity: int = Field(..., alias="Quantity")

    class Config:
        allow_population_by_field_name = True

@dataclass
class InventoryItem:
    item_name: str
    quantity: int

@dataclass
class InventoryRequest:
    request_id: str
    item_name: str
    quantity: int

@dataclass
class InventoryResult:
    success: bool
    inventory_item: Optional[InventoryItem] = None

@dataclass
class PaymentRequest:
    request_id: str
    item_being_purchased: str
    quantity: int

@dataclass
class OrderResult:
    processed: bool

@dataclass
class Notification:
    message: str

