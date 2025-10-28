package io.dapr.quickstarts.workflows.models;

public class ServiceInfo {
  private String message;

  public ServiceInfo() {
  }

  public ServiceInfo(String message) {
    this.message = message;
  }

  public String getMessage() {
    return message;
  }

  public void setMessage(String message) {
    this.message = message;
  }
}
