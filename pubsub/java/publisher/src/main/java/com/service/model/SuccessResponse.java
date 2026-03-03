package com.service.model;

public record SuccessResponse(String id, String message, String topic) implements PublishResponse {
  @Override
  public String getMessage() {
    return this.message;
  }
}
