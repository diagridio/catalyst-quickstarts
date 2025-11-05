package com.service.model;

public record SuccessResponse(int orderId, String message) implements StateResponse{
  @Override
  public String getMessage() {
    return this.message;
  }
}
