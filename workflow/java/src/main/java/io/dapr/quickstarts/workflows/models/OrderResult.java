package io.dapr.quickstarts.workflows.models;

public class OrderResult {
  private boolean processed;
  private String message;

  public OrderResult() {}

  public OrderResult(boolean processed, String message) {
    this.processed = processed;
    this.message = message;
  }

  public boolean isProcessed() {
    return processed;
  }

  public void setProcessed(boolean processed) {
    this.processed = processed;
  }

  public String getMessage() {
    return message;
  }

  public void setMessage(String message) {
    this.message = message;
  }

  @Override
  public String toString() {
    return "OrderResult [processed=" + processed + ", message=" + message + "]";
  }
}
