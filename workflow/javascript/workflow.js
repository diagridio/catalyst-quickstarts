const inventory = { Car: 50 };

const notifyActivity = async (ctx, input) => {
  const message = input.message || "No message provided";
  console.log(`Notification: ${message}`);
};

const processPaymentActivity = async (ctx, input) => {
  const quantity = input.quantity;
  const itemName = input.itemName;
  console.log(`Processing payment for ${quantity} ${itemName}`);

  // Simulate payment processing delay
  await new Promise((resolve) => setTimeout(resolve, 2000));

  console.log(`Payment processed successfully`);
  return { success: true };
};

const reserveInventoryActivity = async (ctx, input) => {
  const quantity = input.quantity || 0;
  const itemName = input.itemName || "Unknown item";

  console.log(`Verifying inventory for ${quantity} ${itemName}`);

  const available = inventory[itemName] || 0;
  if (available >= quantity) {
    console.log(
      `${quantity} ${itemName}(s) reserved. ${available - quantity} left.`
    );
    return {
      success: true,
      item: { name: itemName, quantity: available },
    };
  }

  console.log(
    `Failed to reserve ${quantity} ${itemName}(s). Only ${available} available.`
  );
  return { success: false };
};

const updateInventoryActivity = async (ctx, input) => {
  const quantity = input.quantity || 0;
  const itemName = input.itemName || "Unknown item";

  console.log(`Updating inventory for ${quantity} ${itemName}`);

  const available = inventory[itemName] || 0;
  if (available >= quantity) {
    inventory[itemName] -= quantity;
    console.log(
      `Updated ${itemName} inventory to ${inventory[itemName]} remaining.`
    );
    return {
      success: true,
      item: { name: itemName, quantity: inventory[itemName] },
    };
  }

  console.log(
    `Not enough ${itemName} in inventory for the request: only ${available} remaining.`
  );
  return { success: false };
};

const orderProcessingWorkflow = async function* (ctx, order) {
  const orderId = ctx.getWorkflowInstanceId();

  console.log(`Order received: ${JSON.stringify(order)}`);

  // Notify the user that an order has come through
  const notificationMessage = `Received order ${orderId} for ${order.quantity} ${order.name}`;
  yield ctx.callActivity(notifyActivity, { message: notificationMessage });

  // Determine if there is enough of the item available for purchase by checking the inventory
  const inventoryResult = yield ctx.callActivity(reserveInventoryActivity, {
    requestId: orderId,
    itemName: order.name,
    quantity: order.quantity,
  });

  // If there is insufficient inventory, fail and let the user know
  if (!inventoryResult.success) {
    yield ctx.callActivity(notifyActivity, {
      message: `Insufficient inventory for ${order.name}`,
    });
    return {
      processed: false,
      message: "Order failed due to insufficient inventory",
    };
  }

  // There is enough inventory available so the user can purchase the item(s). Process their payment
  yield ctx.callActivity(processPaymentActivity, {
    requestId: orderId,
    itemName: order.name,
    quantity: order.quantity,
  });

  try {
    // Update the inventory
    yield ctx.callActivity(updateInventoryActivity, {
      requestId: orderId,
      itemName: order.name,
      quantity: order.quantity,
    });
  } catch (error) {
    console.error(`Error updating inventory: ${error}`);
    yield ctx.callActivity(notifyActivity, {
      message: `Order ${orderId} Failed! You are now getting a refund`,
    });
    return {
      processed: false,
      message: "Order failed during inventory update",
    };
  }

  // Let them know their payment was processed
  yield ctx.callActivity(notifyActivity, {
    message: `Order ${orderId} has completed!`,
  });
  return { processed: true, message: "Order has completed!" };
};

export {
  orderProcessingWorkflow,
  notifyActivity,
  reserveInventoryActivity,
  processPaymentActivity,
  updateInventoryActivity,
};
