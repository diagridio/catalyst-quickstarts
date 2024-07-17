package io.dapr.quickstarts.workflows.activities;

import io.dapr.quickstarts.workflows.models.PaymentRequest;
import io.dapr.workflows.runtime.WorkflowActivity;
import io.dapr.workflows.runtime.WorkflowActivityContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class ProcessPaymentActivity implements WorkflowActivity {

  private static final Logger logger = LoggerFactory.getLogger(ProcessPaymentActivity.class);

  @Override
  public Object run(WorkflowActivityContext ctx) {
    PaymentRequest paymentRequest = ctx.getInput(PaymentRequest.class);
    logger.info("Processing payment: {} for {} {}", paymentRequest.getRequestId(), paymentRequest.getQuantity(), paymentRequest.getItemBeingPurchased());

    // Simulate payment processing delay
    try {
      Thread.sleep(2000);  // Sleep for 2 seconds
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      logger.error("Payment processing was interrupted", e);
      return false;
    }

    logger.info("Payment for request ID {} processed successfully", paymentRequest.getRequestId());
    return true;
  }
}

