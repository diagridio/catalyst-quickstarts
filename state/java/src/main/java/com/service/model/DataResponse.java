package com.service.model;

public record DataResponse(Object data) implements StateResponse {
  @Override
  public String getMessage() {
    return "";
  }
}
