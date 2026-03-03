package com.service.model;

public record ErrorResponse(String code, String message ) implements PublishResponse {
  @Override
  public String getMessage() {
    return this.message;
  }
}
