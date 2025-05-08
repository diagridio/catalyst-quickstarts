package io.dapr.quickstarts.workflows;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import io.dapr.workflows.client.DaprWorkflowClient;
import io.dapr.workflows.runtime.WorkflowRuntimeBuilder;

import io.dapr.quickstarts.workflows.activities.*;

@Configuration
public class WorkflowConfig {

  @Bean
  public DaprWorkflowClient daprWorkflowClient() {
    return new DaprWorkflowClient();
  }

  @Bean
  public WorkflowRuntimeBuilder workflowRuntimeBuilder() {
    WorkflowRuntimeBuilder builder = new WorkflowRuntimeBuilder();
    builder.registerWorkflow(OrderProcessingWorkflow.class);
    builder.registerActivity(NotifyActivity.class);
    builder.registerActivity(ProcessPaymentActivity.class);
    builder.registerActivity(ReserveInventoryActivity.class);
    builder.registerActivity(UpdateInventoryActivity.class);
    return builder;
  }
}
