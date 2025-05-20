package io.dapr.quickstarts.workflows;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import io.dapr.workflows.runtime.WorkflowRuntime;
import io.dapr.workflows.runtime.WorkflowRuntimeBuilder;

import io.dapr.quickstarts.workflows.activities.*;

// @Configuration
public class WorkflowConfig {
  // Configuration is handled by Spring's component scanning
  // Workflows and activities are automatically registered as they are annotated
  // with @Service and @Component
}
