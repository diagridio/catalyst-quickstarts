namespace WorkflowApp.Activities
{
    using System.Threading.Tasks;
    using Dapr.Workflow;
    using Microsoft.Extensions.Logging;
    using WorkflowApp.Models;
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
                "Processing payment: {requestId} for {quantity} {item}",
                req.RequestId,
                req.Quantity,
                req.ItemName);

            // Simulate payment processing delay
            await Task.Delay(TimeSpan.FromSeconds(2));

            this.logger.LogInformation(
                "Payment for request ID '{requestId}' processed successfully",
                req.RequestId);

            return new { success = true };
        }
    }
}

