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
                +f'{input.Quantity}' +' ' +f'{input.item_being_purchased}')
    # Simulate payment processing delay
    time.sleep(2)  
    logger.info(f'Payment for request ID {input.request_id} processed successfully')

def reserve_inventory_activity(ctx: WorkflowActivityContext, input: InventoryRequest) -> InventoryResult:
    logger.info(f'Verifying inventory for order {input.request_id}: {input.Quantity} {input.Name}')

    available = inventory.get(input.Name, 0)
    if available >= input.Quantity:
        logger.info(f'{input.Quantity} {input.Name}(s) reserved. {available - input.Quantity} left.')
        return InventoryResult(success=True, inventory_item=InventoryItem(Name=input.Name, Quantity=available))

    logger.info(f'Failed to reserve {input.Quantity} {input.Name}(s). Only {available} available.')
    return InventoryResult(success=False)

def update_inventory_activity(ctx: WorkflowActivityContext, input: InventoryRequest) -> InventoryResult:
    logger.info(f'Updating inventory for order {input.request_id}: {input.Quantity} {input.Name}')

    available = inventory.get(input.Name, 0)
    if available >= input.Quantity:
        inventory[input.Name] -= input.Quantity
        logger.info(f'Updated {input.Name} inventory to {inventory[input.Name]} remaining.')
        return InventoryResult(success=True, inventory_item=InventoryItem(Name=input.Name, Quantity=inventory[input.Name]))

    logger.info(f'Not enough {input.Name} in inventory for the request: only {available} remaining.')
    return InventoryResult(success=False)  

def order_processing_workflow(ctx: DaprWorkflowContext, order: dict):
    try:
        order_payload = OrderPayload.parse_obj(order)
    except Exception as e:
        raise TypeError(f"Failed to convert order to OrderPayload: {e}")

    print(f'Order received: {order_payload}')
    print(f'Type of order: {type(order_payload)}')
    order_id = ctx.instance_id

    # Ensure order is an instance of OrderPayload
    if not isinstance(order_payload, OrderPayload):
        raise TypeError(f"Expected order to be an instance of OrderPayload, but got {type(order_payload)}")

    # Notify the user that an order has come through
    notification_message = f"Received order for {order_payload.Quantity} {order_payload.Name}!"
    print(f'Notification message: {notification_message}')

    yield ctx.call_activity(notify_activity, input=Notification(message=notification_message))
    logger.debug("Notification activity called.")

    # Determine if there is enough of the item available for purchase by checking the inventory
    result = yield ctx.call_activity(reserve_inventory_activity, input=InventoryRequest(request_id= order_id, Name=order_payload.Name, Quantity=order_payload.Quantity))

    # If there is insufficient inventory, fail and let the user know 
    if not result.success:
        yield ctx.call_activity(notify_activity, input=Notification(message=f"Insufficient inventory for {order_payload.Name}!"))
        logger.debug("Inventory check failed. Exiting workflow.")
        return OrderResult(processed=False)
    
    logger.debug("Inventory reserved successfully.")


    # There is enough inventory available so the user can purchase the item(s). Process their payment
    yield ctx.call_activity(process_payment_activity, input=PaymentRequest(request_id=order_id, item_being_purchased=order_payload.Name, Quantity=order_payload.Quantity))
    logger.debug("Payment processed.")


    # Update the inventory
    try:
        yield ctx.call_activity(update_inventory_activity, input=InventoryRequest(request_id=order_id, Name=order_payload.Name, Quantity=order_payload.Quantity))
        logger.debug("Inventory updated.")
    except Exception as e:
        logger.error(f"Error updating inventory: {e}")
        yield ctx.call_activity(notify_activity, input=Notification(message=f"Order Failed!"))
        return OrderResult(processed=False)


    # Let them know their payment was processed
    yield ctx.call_activity(notify_activity, input=Notification(message=f"Order has completed!"))
    logger.debug("Order processing completed successfully.")
    

    # End the workflow with a success result
    return OrderResult(processed=True)

