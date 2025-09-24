namespace WorkflowApp.Activities
{
    using System.Collections.Generic;
    using System.Threading.Tasks;
    using Dapr.Workflow;
    using WorkflowApp.Models;
    using Microsoft.Extensions.Logging;

    public class ReserveInventoryActivity : WorkflowActivity<InventoryRequest, InventoryResult>
    {
        public static Dictionary<string, int> Inventory = new Dictionary<string, int>
        {
            { "Car", 50 } // Initializing with 50
        };

        readonly ILogger logger;

        public ReserveInventoryActivity(ILoggerFactory loggerFactory)
        {
            this.logger = loggerFactory.CreateLogger<ReserveInventoryActivity>();
        }

        public override Task<InventoryResult> RunAsync(WorkflowActivityContext context, InventoryRequest req)
        {
            this.logger.LogInformation(
                "Reserving inventory for order {requestId} of {quantity} {item}",
                req.RequestId,
                req.Quantity,
                req.ItemName);

            // Simulate inventory check
            if (Inventory.TryGetValue(req.ItemName, out int available) && available >= req.Quantity)
            {
                this.logger.LogInformation("Inventory check successful for {quantity} {item}", req.Quantity, req.ItemName);
                return Task.FromResult(new InventoryResult(
                    Success: true,
                    Item: new InventoryItem(req.ItemName, available)
                ));
            }

            this.logger.LogInformation("Inventory check failed for {quantity} {item}", req.Quantity, req.ItemName);
            return Task.FromResult(new InventoryResult(Success: false));
        }
    }
}

