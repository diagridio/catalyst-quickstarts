using System.Threading.Tasks;
using Dapr.Workflow;
using WorkflowApp.Activities;
using WorkflowApp.Models;

namespace WorkflowApp.Workflows
{
    public class OrderProcessingWorkflow : Workflow<OrderPayload, OrderResult>
    {
        public override async Task<OrderResult> RunAsync(WorkflowContext context, OrderPayload order)
        {
            string orderId = context.InstanceId;

            // Notify the user that an order has come through
            await context.CallActivityAsync(
                nameof(NotifyActivity),
                new Notification($"Received order {orderId} for {order.Quantity} {order.Name}"));

            // Determine if there is enough of the item available for purchase by checking the inventory
            InventoryResult result = await context.CallActivityAsync<InventoryResult>(
                nameof(ReserveInventoryActivity),
                new InventoryRequest(orderId, order.Name, order.Quantity));

            // If there is insufficient inventory, fail and let the user know 
            if (!result.Success)
            {
                await context.CallActivityAsync(
                    nameof(NotifyActivity),
                    new Notification($"Insufficient inventory for {order.Name}"));

                context.SetCustomStatus("Stopped order process due to insufficient inventory");

                return new OrderResult(false, "Order failed due to insufficient inventory");
            }

            // There is enough inventory available so the user can purchase the item(s). Process their payment
            await context.CallActivityAsync(
                nameof(ProcessPaymentActivity),
                new PaymentRequest(orderId, order.Name, order.Quantity));

            try
            {
                // Update the inventory
                await context.CallActivityAsync(
                    nameof(UpdateInventoryActivity),
                    new InventoryRequest(orderId, order.Name, order.Quantity));
            }
            catch
            {
                await context.CallActivityAsync(
                    nameof(NotifyActivity),
                    new Notification($"Order {orderId} Failed! You are now getting a refund"));

                context.SetCustomStatus("Stopped order process due to error in inventory update");

                return new OrderResult(false, "Order failed during inventory update");
            }

            // Let them know their payment was processed
            await context.CallActivityAsync(
                nameof(NotifyActivity),
                new Notification($"Order {orderId} has completed!"));

            // End the workflow with a success result
            return new OrderResult(true, "Order has completed!");
        }
    }
}

