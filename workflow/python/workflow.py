import logging
from dapr.ext.workflow import WorkflowActivityContext, DaprWorkflowContext
from model import InventoryItem, InventoryRequest, InventoryResult, PaymentRequest, Notification, OrderResult, OrderPayload
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mocked inventory in memory
inventory = {"Car": 50}

def notify_activity(ctx: WorkflowActivityContext, input: Notification):
    logger.info(input.message)

def process_payment_activity(ctx: WorkflowActivityContext, input: PaymentRequest):
    logger.info('Processing payment: '+f'{input.request_id}'+' for '
                +f'{input.quantity}' +' ' +f'{input.item_name}')
    # Simulate payment processing delay
    time.sleep(2)  
    logger.info(f'Payment for request ID {input.request_id} processed successfully')
    return {"success": True}

def reserve_inventory_activity(ctx: WorkflowActivityContext, input: InventoryRequest):
    logger.info(f'Verifying inventory for order {input.request_id}: {input.quantity} {input.item_name}')

    available = inventory.get(input.item_name, 0)
    if available >= input.quantity:
        logger.info(f'{input.quantity} {input.item_name}(s) reserved. {available - input.quantity} left.')
        return InventoryResult(success=True, item=InventoryItem(name=input.item_name, quantity=available))

    logger.info(f'Failed to reserve {input.quantity} {input.item_name}(s). Only {available} available.')
    return InventoryResult(success=False)

def update_inventory_activity(ctx: WorkflowActivityContext, input: InventoryRequest):
    logger.info(f'Updating inventory for order {input.request_id}: {input.quantity} {input.item_name}')

    available = inventory.get(input.item_name, 0)
    if available >= input.quantity:
        inventory[input.item_name] -= input.quantity
        logger.info(f'Updated {input.item_name} inventory to {inventory[input.item_name]} remaining.')
        return InventoryResult(success=True, item=InventoryItem(name=input.item_name, quantity=inventory[input.item_name]))

    logger.info(f'Not enough {input.item_name} in inventory for the request: only {available} remaining.')
    return InventoryResult(success=False)  

def order_processing_workflow(ctx: DaprWorkflowContext, order: dict):
    order_payload = OrderPayload.parse_obj(order)
    order_id = ctx.instance_id

    logger.info(f"Order received: {order_payload}")

    # Notify the user that an order has come through
    notification_message = f"Received order {order_id} for {order_payload.quantity} {order_payload.name}"
    yield ctx.call_activity(notify_activity, input=Notification(message=notification_message))

    # Determine if there is enough of the item available for purchase by checking the inventory
    result = yield ctx.call_activity(reserve_inventory_activity, input=InventoryRequest(request_id=order_id, item_name=order_payload.name, quantity=order_payload.quantity))

    # If there is insufficient inventory, fail and let the user know 
    if not result.success:
        yield ctx.call_activity(notify_activity, input=Notification(message=f"Insufficient inventory for {order_payload.name}"))
        return OrderResult(processed=False, message="Order failed due to insufficient inventory")

    # There is enough inventory available so the user can purchase the item(s). Process their payment
    yield ctx.call_activity(process_payment_activity, input=PaymentRequest(request_id=order_id, item_name=order_payload.name, quantity=order_payload.quantity))

    # Update the inventory
    try:
        yield ctx.call_activity(update_inventory_activity, input=InventoryRequest(request_id=order_id, item_name=order_payload.name, quantity=order_payload.quantity))
    except Exception as e:
        logger.error(f"Error updating inventory: {e}")
        yield ctx.call_activity(notify_activity, input=Notification(message=f"Order {order_id} Failed! You are now getting a refund"))
        return OrderResult(processed=False, message="Order failed during inventory update")

    # Let them know their payment was processed
    yield ctx.call_activity(notify_activity, input=Notification(message=f"Order {order_id} has completed!"))
    
    # End the workflow with a success result
    return OrderResult(processed=True, message="Order has completed!")

