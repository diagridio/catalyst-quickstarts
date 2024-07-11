import logging
from dapr.ext.workflow import WorkflowActivityContext, DaprWorkflowContext
from model import InventoryItem, InventoryRequest, InventoryResult, PaymentRequest, Notification, OrderResult, OrderPayload
import json
import time

logger = logging.getLogger(__name__)

# Mocked inventory in memory
inventory = {"Car": 50}

def notify_activity(ctx: WorkflowActivityContext, input: Notification):
    logger.info(f"Notification: {input.message}")

def process_payment_activity(ctx: WorkflowActivityContext, input: PaymentRequest):
    logger.info(f'Processing payment: {input.request_id} for {input.quantity} {input.item_being_purchased}')
    time.sleep(2)  # Simulate payment processing delay
    logger.info(f'Payment for request ID {input.request_id} processed successfully')

def reserve_inventory_activity(ctx: WorkflowActivityContext, input: InventoryRequest) -> InventoryResult:
    logger.info(f'Verifying inventory for order {input.request_id} of {input.quantity} {input.item_name}')
    available = inventory.get(input.item_name, 0)
    if available >= input.quantity:
        inventory[input.item_name] -= input.quantity
        logger.info(f'Reserved {input.quantity} {input.item_name}(s). {available - input.quantity} left.')
        return InventoryResult(success=True, inventory_item=InventoryItem(item_name=input.item_name, quantity=available))
    logger.info(f'Failed to reserve {input.quantity} {input.item_name}(s). Only {available} available.')
    return InventoryResult(success=False)

def update_inventory_activity(ctx: WorkflowActivityContext, input: PaymentRequest):
    logger.info(f'Updating inventory for order {input.request_id} of {input.quantity} {input.item_being_purchased}')
    available = inventory.get(input.item_being_purchased, 0)
    if available >= input.quantity:
        inventory[input.item_being_purchased] -= input.quantity
        logger.info(f'Updated {input.item_being_purchased} inventory to {inventory[input.item_being_purchased]} remaining.')
        return InventoryResult(success=True, inventory_item=InventoryItem(item_name=input.item_being_purchased, quantity=inventory[input.item_being_purchased]))
    raise ValueError(f'Not enough {input.item_being_purchased} in inventory for the request.')

def order_processing_workflow(ctx: DaprWorkflowContext):
    order_payload_str = ctx.get_input()
    order_payload = OrderPayload(**json.loads(order_payload_str))
    order_id = ctx.instance_id

    ctx.call_activity(notify_activity, Notification(message=f"Received order {order_id} for {order_payload.quantity} {order_payload.item_name}(s)"))

    result = ctx.call_activity(reserve_inventory_activity, InventoryRequest(request_id=order_id, item_name=order_payload.item_name, quantity=order_payload.quantity))
    if not result.success:
        ctx.call_activity(notify_activity, Notification(message=f"Insufficient inventory for {order_payload.item_name}!"))
        return OrderResult(processed=False)

    ctx.call_activity(process_payment_activity, PaymentRequest(request_id=order_id, item_being_purchased=order_payload.item_name, quantity=order_payload.quantity))

    try:
        ctx.call_activity(update_inventory_activity, PaymentRequest(request_id=order_id, item_being_purchased=order_payload.item_name, quantity=order_payload.quantity))
    except Exception:
        ctx.call_activity(notify_activity, Notification(message=f"Order {order_id} Failed!"))
        return OrderResult(processed=False)

    ctx.call_activity(notify_activity, Notification(message=f"Order {order_id} has completed!"))
    return OrderResult(processed=True)

