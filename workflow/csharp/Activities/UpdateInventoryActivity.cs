namespace WorkflowApp.Activities
{
    using System.Threading.Tasks;
    using Dapr.Workflow;
    using WorkflowApp.Models;
    using Microsoft.Extensions.Logging;
    using System;
    using System.Collections.Generic;

    public class UpdateInventoryActivity : WorkflowActivity<InventoryRequest, object?>
    {
        readonly ILogger logger;

        public UpdateInventoryActivity(ILoggerFactory loggerFactory)
        {
            this.logger = loggerFactory.CreateLogger<UpdateInventoryActivity>();
        }

        public override async Task<object?> RunAsync(WorkflowActivityContext context, InventoryRequest req)
        {
            this.logger.LogInformation(
                "Checking Inventory for: Order# {requestId} for {quantity} {item}",
                req.RequestId,
                req.Quantity,
                req.ItemName);

            // Simulate slow processing
            await Task.Delay(TimeSpan.FromSeconds(5));

            // Simulate inventory update
            if (ReserveInventoryActivity.Inventory.TryGetValue(req.ItemName, out int available))
            {
                if (available >= req.Quantity)
                {
                    ReserveInventoryActivity.Inventory[req.ItemName] -= req.Quantity;
                    this.logger.LogInformation($"There are now: {ReserveInventoryActivity.Inventory[req.ItemName]} {req.ItemName} left in stock");
                    return null;
                }
            }

            this.logger.LogInformation($"Payment for request ID '{req.RequestId}' could not be processed. Insufficient inventory.");
            throw new InvalidOperationException();
        }
    }
}


