package com.service.model;

public record ErrorResponse(String code, String message ) implements StateResponse {
  @Override
  public String getMessage() {
    return this.message;
  }
}