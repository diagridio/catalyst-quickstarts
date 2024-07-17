package io.dapr.quickstarts.workflows;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import io.dapr.workflows.runtime.WorkflowRuntime;
import io.dapr.workflows.runtime.WorkflowRuntimeBuilder;

import io.dapr.quickstarts.workflows.activities.*;

@Configuration
public class WorkflowConfig {

  @Bean
  public WorkflowRuntime workflowRuntime() {
    WorkflowRuntimeBuilder builder = new WorkflowRuntimeBuilder().registerWorkflow(OrderProcessingWorkflow.class);
    builder.registerActivity(NotifyActivity.class);
    builder.registerActivity(ProcessPaymentActivity.class);
    builder.registerActivity(ReserveInventoryActivity.class);
    builder.registerActivity(UpdateInventoryActivity.class);

    WorkflowRuntime runtime = builder.build();
    runtime.start(false);
    return runtime;
  }
}
