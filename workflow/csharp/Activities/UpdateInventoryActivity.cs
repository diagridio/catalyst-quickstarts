namespace WorkflowApp.Activities
{
    using System.Threading.Tasks;
    using Dapr.Workflow;
    using WorkflowApp.Models;
    using Microsoft.Extensions.Logging;
    using System;
    using System.Collections.Generic;

    public class UpdateInventoryActivity : WorkflowActivity<PaymentRequest, object?>
    {
        readonly ILogger logger;

        public UpdateInventoryActivity(ILoggerFactory loggerFactory)
        {
            this.logger = loggerFactory.CreateLogger<UpdateInventoryActivity>();
        }

        public override async Task<object?> RunAsync(WorkflowActivityContext context, PaymentRequest req)
        {
            this.logger.LogInformation(
                "Checking Inventory for: Order# {requestId} for {amount} {item}",
                req.RequestId,
                req.Amount,
                req.ItemBeingPurchased);

            // Simulate slow processing
            await Task.Delay(TimeSpan.FromSeconds(5));

            // Simulate inventory update
            if (ReserveInventoryActivity.Inventory.TryGetValue(req.ItemBeingPurchased, out int available))
            {
                if (available >= req.Amount)
                {
                    ReserveInventoryActivity.Inventory[req.ItemBeingPurchased] -= req.Amount;
                    this.logger.LogInformation($"There are now: {ReserveInventoryActivity.Inventory[req.ItemBeingPurchased]} {req.ItemBeingPurchased} left in stock");
                    return Task.FromResult<object?>(null);
                }
            }

            this.logger.LogInformation($"Payment for request ID '{req.RequestId}' could not be processed. Insufficient inventory.");
            throw new InvalidOperationException();
        }
    }
}


