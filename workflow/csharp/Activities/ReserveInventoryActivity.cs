namespace WorkflowConsoleApp.Activities
{
    using System.Collections.Generic;
    using System.Threading.Tasks;
    using Dapr.Workflow;
    using WorkflowConsoleApp.Models;
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
                "Reserving inventory for order {requestId} of {amount} {item}",
                req.RequestId,
                req.Quantity,
                req.ItemName);

            // Simulate inventory check
            if (Inventory.TryGetValue(req.ItemName, out int available) && available >= req.Quantity)
            {
                this.logger.LogInformation("Inventory check successful for {amount} {item}", req.Quantity, req.ItemName);
                return Task.FromResult(new InventoryResult(true));
            }

            this.logger.LogInformation("Inventory check failed for {amount} {item}", req.Quantity, req.ItemName);
            return Task.FromResult(new InventoryResult(false));
        }
    }
}

