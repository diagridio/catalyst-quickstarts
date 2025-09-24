from dataclasses import dataclass
from typing import Optional
from pydantic import BaseModel

class OrderPayload(BaseModel):
    Name: str
    Quantity: int

    class Config:
        populate_by_name = True
        from_attributes = True

@dataclass
class InventoryItem:
    Name: str
    Quantity: int

    def __str__(self):
        return f"InventoryItem(item_name={self.Name}, quantity={self.Quantity})"

@dataclass
class InventoryRequest:
    request_id: str
    item_name: str
    quantity: int

    def __str__(self):
        return f"InventoryRequest(request_id={self.request_id}, item_name={self.item_name}, quantity={self.quantity})"

@dataclass
class InventoryResult:
    success: bool
    item: Optional[InventoryItem] = None

    def __str__(self):
        return f"InventoryResult(success={self.success}, item={self.item})"

@dataclass
class PaymentRequest:
    request_id: str
    item_name: str
    quantity: int
  
    def __str__(self):
        return f"PaymentRequest(request_id={self.request_id}, item_name={self.item_name}, quantity={self.quantity})"

@dataclass
class OrderResult:
    processed: bool
    message: str = ""

    def __str__(self):
        return f"OrderResult(processed={self.processed}, message='{self.message}')"

@dataclass
class Notification:
    message: str

    def __str__(self):
        return f"Notification(message={self.message})"

