const inventory = { Car: 50 };

const notifyActivity = async (ctx, input) => {
  const message = input.message || 'No message provided';
  console.log(`Notification: ${message}`);
};

const processPaymentActivity = async (ctx, input) => {
  const quantity = input.Quantity || 0;
  const item = input.item_being_purchased || 'Unknown item';

  console.log(`Processing payment for ${quantity} ${item}`);

  // Simulate payment processing delay
  await new Promise(resolve => setTimeout(resolve, 2000));

  console.log(`Payment processed successfully`);
};

const reserveInventoryActivity = async (ctx, input) => {
  const quantity = input.Quantity || 0;
  const name = input.Name || 'Unknown item';

  console.log(`Verifying inventory for ${quantity} ${name}`);

  const available = inventory[name] || 0;
  if (available >= quantity) {
    console.log(`${quantity} ${name}(s) reserved. ${available - quantity} left.`);
    return { success: true, inventory_item: { Name: name, Quantity: available } };
  }

  console.log(`Failed to reserve ${quantity} ${name}(s). Only ${available} available.`);
  return { success: false };
};

const updateInventoryActivity = async (ctx, input) => {
  const quantity = input.Quantity || 0;
  const name = input.Name || 'Unknown item';

  console.log(`Updating inventory for ${quantity} ${name}`);

  const available = inventory[name] || 0;
  if (available >= quantity) {
    inventory[name] -= quantity;
    console.log(`Updated ${name} inventory to ${inventory[name]} remaining.`);
    return { success: true, inventory_item: { Name: name, Quantity: inventory[name] } };
  }

  console.log(`Not enough ${name} in inventory for the request: only ${available} remaining.`);
  return { success: false };
};

const orderProcessingWorkflow = async function*(ctx, order) {
  const orderId = ctx.instance_id;

  console.log(`Order received: ${JSON.stringify(order)}`);

  const notificationMessage = `Received order for ${order.Quantity} ${order.Name}!`;
  yield ctx.callActivity(notifyActivity, { message: notificationMessage });

  const inventoryResult = yield ctx.callActivity(reserveInventoryActivity, {
    Name: order.Name,
    Quantity: order.Quantity,
  });

  if (!inventoryResult.success) {
    yield ctx.callActivity(notifyActivity, { message: `Insufficient inventory for ${order.Name}!` });
    return { processed: false };
  }

  yield ctx.callActivity(processPaymentActivity, {
    item_being_purchased: order.Name,
    Quantity: order.Quantity,
  });

  try {
    yield ctx.callActivity(updateInventoryActivity, {
      Name: order.Name,
      Quantity: order.Quantity,
    });
  } catch (error) {
    console.error(`Error updating inventory: ${error}`);
    yield ctx.callActivity(notifyActivity, { message: `Order Failed!` });
    return { processed: false };
  }

  yield ctx.callActivity(notifyActivity, { message: `Order has completed!` });
  return { processed: true };
};

export {
  orderProcessingWorkflow,
  notifyActivity,
  reserveInventoryActivity,
  processPaymentActivity,
  updateInventoryActivity,
};
