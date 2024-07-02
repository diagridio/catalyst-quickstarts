namespace WorkflowConsoleApp.Activities
{
    using System.Threading.Tasks;
    using Dapr.Workflow;
    using Microsoft.Extensions.Logging;
    using WorkflowConsoleApp.Models;
    using System;

    public class ProcessPaymentActivity : WorkflowActivity<PaymentRequest, object?>
    {
        readonly ILogger logger;

        public ProcessPaymentActivity(ILoggerFactory loggerFactory)
        {
            this.logger = loggerFactory.CreateLogger<ProcessPaymentActivity>();
        }

        public override async Task<object?> RunAsync(WorkflowActivityContext context, PaymentRequest req)
        {
            this.logger.LogInformation(
                "Processing payment: {requestId} for {amount} {item}",
                req.RequestId,
                req.Amount,
                req.ItemBeingPurchased);

            // Simulate slow processing
            await Task.Delay(TimeSpan.FromSeconds(7));

            this.logger.LogInformation(
                "Payment for request ID '{requestId}' processed successfully",
                req.RequestId);

            return Task.FromResult<object?>(null);
        }
    }
}

