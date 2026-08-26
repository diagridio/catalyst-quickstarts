from dataclasses import dataclass
from typing import Optional
from pydantic import BaseModel

class OrderPayload(BaseModel):
    name: str
    quantity: int

    class Config:
        populate_by_name = True
        from_attributes = True

@dataclass
class InventoryItem:
    name: str
    quantity: int

    def __str__(self):
        return f"InventoryItem(item_name={self.name}, quantity={self.quantity})"

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

class CrashRunRequest(BaseModel):
    """Request body of POST /crash/run: the instance id the caller owns, and the reference
    the confirmation code is derived from.

    `id` is Optional here so that the handler can reject a missing one the same way the C#
    and Java quickstarts do, with a 400 carrying the shared {id, result, message} body. A
    required pydantic field would instead produce FastAPI's own 422 in a different shape,
    which is the kind of gratuitous divergence these three quickstarts exist to avoid.
    """

    id: Optional[str] = None
    reference: str = "ABC123"

