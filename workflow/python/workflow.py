import hashlib
import logging
import os
import threading
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

# Seconds into THIS ACTIVITY's run at which the app should kill itself, or 0 when nothing is
# asked for. Recorded by main's /crash/run handler, then read and acted on here.
#
# A plain module-level value is enough. One armed kill takes the whole process down, so there
# is nothing to key by instance, and the fresh process after the restart starts at 0 again,
# which is what makes the replay safe: the resumed activity re-runs this from the start and
# must not arm a second kill when it does.
_self_kill_seconds = 0

def note_self_kill(delay_seconds: int):
    """Record how far into this activity the process should kill itself. Pass 0 to disarm.

    Recording only: no timer starts here. See _arm_self_kill for why the timer belongs in the
    activity rather than at the request.
    """
    global _self_kill_seconds
    _self_kill_seconds = delay_seconds

def _consume_self_kill() -> int:
    """Read the armed value and clear it in one step, so one request arms one execution.

    The clear is load-bearing. A call that attaches to an existing run records the field and
    then never reaches this activity, so a value left set would survive to the next run in the
    same process and kill an app that had never asked for it.
    """
    global _self_kill_seconds
    armed = _self_kill_seconds
    _self_kill_seconds = 0
    return armed

def _arm_self_kill(delay_seconds: int):
    """Kill this process `delay_seconds` from now, on a daemon thread.

    Armed HERE, at the point the slow activity actually starts, and not back at the request.
    The request handler cannot start this clock honestly: between the schedule call and this
    activity sit the dispatch round-trip and the whole fast activity, so a budget measured
    from the request has to cover work the reader cannot see or predict. Measured from here it
    runs against this activity's own sleep, which is the window the README tells them to aim
    at. That is also what makes the field safe to send on a re-issue: an attaching call never
    reaches this line.

    Deliberately the same os._exit(1) that /crash/kill uses. A gentler exit would make this a
    controlled shutdown wearing a crash's name, which is the one thing this demo must not do.

    daemon=True so the timer can never hold the process open: a Ctrl+C during the countdown
    should still end the app rather than wait for a kill nobody wants any more.
    """
    def _kill():
        time.sleep(delay_seconds)
        logger.warning(
            f'>>> crash: killing this process {delay_seconds}s into the run, as asked by kill_after_seconds'
        )
        os._exit(1)

    threading.Thread(target=_kill, daemon=True).start()

def commit_reservation_activity(ctx: WorkflowActivityContext, input: str):
    delay = int(os.environ.get('CRASH_DELAY_SECONDS', '10'))
    # Read AND clear in one step, so one recorded request arms exactly one execution.
    armed = _consume_self_kill()
    # Two messages, because the reader's next move differs. Un-armed, the window is theirs to
    # aim at and they have to crash the app themselves. Armed, the app does that for them at a
    # known point, so the instruction would be wrong and the ~delay would be read as the wait.
    if armed:
        logger.info(f'Committing reservation {input} over ~{delay}s, but this process kills '
                    f'itself {armed}s into the run, as asked by kill_after_seconds. '
                    f'It resumes on restart.')
        _arm_self_kill(armed)
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

