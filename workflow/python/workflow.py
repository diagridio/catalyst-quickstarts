import logging
from dapr.ext.workflow import WorkflowActivityContext, DaprWorkflowContext
from model import InventoryItem, InventoryRequest, InventoryResult, PaymentRequest, Notification, OrderResult, OrderPayload
import time

logging.basicConfig(level=logging.INFO)

# Mocked inventory in memory
inventory = {"Car": 50}

def notify_activity(ctx: WorkflowActivityContext, input: Notification):
    logger = logging.getLogger('NotifyActivity')
    logger.info(input.message)

def process_payment_activity(ctx: WorkflowActivityContext, input: PaymentRequest):
    logger = logging.getLogger('ProcessPaymentActivity')
    logger.info('Processing payment: '+f'{input.request_id}'+' for '
                +f'{input.Quantity}' +' ' +f'{input.item_being_purchased}')
    # Simulate payment processing delay
    time.sleep(2)  
    logger.info(f'Payment for request ID {input.request_id} processed successfully')

def reserve_inventory_activity(ctx: WorkflowActivityContext, input: InventoryRequest) -> InventoryResult:
    logger = logging.getLogger('ReserveInventoryActivity')
    logger.info(f'Verifying inventory for order {input.request_id}: {input.Quantity} {input.Name}')

    available = inventory.get(input.Name, 0)
    if available >= input.Quantity:
        inventory[input.Name] -= input.Quantity
        logger.info(f'Reserved {input.Quantity} {input.Name}(s). {available - input.Quantity} left.')
        return InventoryResult(success=True, inventory_item=InventoryItem(Name=input.Name, Quantity=available))

    logger.info(f'Failed to reserve {input.Quantity} {input.Name}(s). Only {available} available.')
    return InventoryResult(success=False)

def update_inventory_activity(ctx: WorkflowActivityContext, input: InventoryRequest):
    logger = logging.getLogger('UpdateInventoryActivity')
    logger.info(f'Updating inventory for order {input.request_id}: {input.Quantity} {input.Name}')

    available = inventory.get(input.Name, 0)
    if available >= input.Quantity:
        inventory[input.Name] -= input.Quantity
        logger.info(f'Updated {input.Name} inventory to {inventory[input.Name]} remaining.')
        return InventoryResult(success=True, inventory_item=InventoryItem(Name=input.Name, Quantity=inventory[input.Name]))

    raise ValueError(f'Not enough {input.Name} in inventory for the request.')

def order_processing_workflow(ctx: DaprWorkflowContext, order: OrderPayload):
    print(f'{order}')

    logger = logging.getLogger('OrderProcessingWorkflow')
    order_id = ctx.instance_id

    # Notify the user that an order has come through
    yield ctx.call_activity(notify_activity, input=Notification(message=f"Received order for {order.Quantity} {order.Name}!"))
    logger.debug("Notification activity called.")

    # Determine if there is enough of the item available for purchase by checking the inventory
    result = yield ctx.call_activity(reserve_inventory_activity, input=InventoryRequest(request_id= order_id, Name=order.Name, Quantity=order.Quantity))

    # If there is insufficient inventory, fail and let the user know 
    if not result.success:
        yield ctx.call_activity(notify_activity, input=Notification(message=f"Insufficient inventory for {order.Name}!"))
        logger.debug("Inventory check failed. Exiting workflow.")
        return OrderResult(processed=False)
    
    logger.debug("Inventory reserved successfully.")


    # There is enough inventory available so the user can purchase the item(s). Process their payment
    yield ctx.call_activity(process_payment_activity, input=PaymentRequest(request_id=order_id, item_being_purchased=order.Name, Quantity=order.Quantity))
    logger.debug("Payment processed.")


    # Update the inventory
    try:
        yield ctx.call_activity(update_inventory_activity, input=InventoryRequest(request_id=order_id, Name=order.Name, Quantity=order.Quantity))
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
