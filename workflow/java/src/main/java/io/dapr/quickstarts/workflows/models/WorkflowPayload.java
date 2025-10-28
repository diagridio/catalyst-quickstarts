package io.dapr.quickstarts.workflows.models;

public class WorkflowPayload {

  private String instanceId;
  private String errorMessage;

  public WorkflowPayload() {
  }

  public WorkflowPayload(String instanceId) {
    this.instanceId = instanceId;
  }

  public WorkflowPayload(String instanceId, String errorMessage) {
    this.instanceId = instanceId;
    this.errorMessage = errorMessage;
  }

  public String getInstanceId() {
    return instanceId;
  }

  public void setInstanceId(String instanceId) {
    this.instanceId = instanceId;
  }

  public String getErrorMessage() {
    return errorMessage;
  }

  public void setErrorMessage(String errorMessage) {
    this.errorMessage = errorMessage;
  }
}
