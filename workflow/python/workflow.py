import hashlib
import logging
import os
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

# ── Crash-recovery demo ──────────────────────────────────────────────────────
# A second workflow, deliberately slow, that exists to be interrupted. The order
# workflow above cannot do this job: its only delay is the 2s payment, which is
# not a window a human can aim a second terminal at.

def confirmation_code(reference: str) -> str:
    """A confirmation code derived only from the booking reference.

    SHA-256 rather than the built-in hash(): hash() is salted per process, so the
    code would differ before and after the restart and the re-issued call could
    not show the reader the same answer.
    """
    digest = hashlib.sha256(reference.encode('utf-8')).hexdigest()
    return 'BK-' + digest[:8].upper()

# Seconds into the run at which POST /crash/run has armed the app to kill itself, or None
# when nothing is armed. Set by main.arm_self_kill and read only to compose the log line
# below, which has to name the wait the reader actually gets: with a self-kill armed the slow
# activity never reaches the end of its sleep, so announcing that sleep on its own puts a
# number in the log that nothing honours.
#
# A plain module-level value is enough. One armed kill takes the whole process down, so there
# is nothing to key by instance, and the fresh process after the restart starts at None
# again, which is right: nothing is armed on the replay.
_self_kill_seconds = None

def note_self_kill(delay_seconds: int):
    """Record that this process will kill itself, so the slow activity can say so.

    Called just after the schedule, and the activity below cannot normally log before that:
    the worker has to be handed the work item and run the fast activity first. If it ever did
    win the race the line would read as though nothing were armed, which is a stale message
    rather than a broken demo.
    """
    global _self_kill_seconds
    _self_kill_seconds = delay_seconds

def commit_reservation_activity(ctx: WorkflowActivityContext, input: str):
    delay = int(os.environ.get('CRASH_DELAY_SECONDS', '30'))
    # Two messages, because the reader's next move differs. Un-armed, the window is theirs to
    # aim at and they have to crash the app themselves. Armed, the app does that for them at a
    # known point, so the instruction would be wrong and the ~delay would be read as the wait.
    if _self_kill_seconds:
        logger.info(f'Committing reservation {input} over ~{delay}s, but this process kills '
                    f'itself {_self_kill_seconds}s into the run, as asked by kill_after_seconds. '
                    f'It resumes on restart.')
    else:
        logger.info(f'Committing reservation {input} over ~{delay}s. KILL THE APP NOW to test '
                    f'crash recovery (POST /crash/kill, or kill -9). It resumes on restart.')
    time.sleep(delay)
    code = confirmation_code(input)
    logger.info(f'Committed reservation {input}. Confirmation code: {code}')
    return f'Reservation {input} confirmed. Confirmation code: {code}'

def crash_recovery_workflow(ctx: DaprWorkflowContext, reference: str):
    demo_id = ctx.instance_id

    # The fast activity runs FIRST and on purpose. It completes in milliseconds, so
    # the engine has persisted its result before the slow one starts, and the crash
    # therefore lands between two known points. After the restart this notification
    # must NOT appear again: that absence is what proves the replay skipped it.
    yield ctx.call_activity(notify_activity, input=Notification(
        message=f'Reservation {demo_id} received for {reference}'))

    # The slow activity. Kill the app while this is running.
    confirmation = yield ctx.call_activity(commit_reservation_activity, input=reference)

    yield ctx.call_activity(notify_activity, input=Notification(
        message=f'Reservation {demo_id} has completed! {confirmation}'))

    return confirmation

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

