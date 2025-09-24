package com.service.controller;

import lombok.Getter;
import lombok.Setter;
import lombok.ToString;
import org.json.JSONObject;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
public class Controller {
  private static final Logger logger = LoggerFactory.getLogger(Controller.class);

  // Helper methods for consistent responses
  private JSONObject createSuccessResponse(String message, int orderId) {
    JSONObject response = new JSONObject();
    response.put("message", message);
    response.put("orderId", orderId);
    return response;
  }

  @PostMapping(path = "/neworder", consumes = MediaType.APPLICATION_JSON_VALUE)
  public ResponseEntity<Object> neworder(@RequestBody Order order) {
    logger.info("Invocation received with data " + order.getOrderId());
    return ResponseEntity.ok(createSuccessResponse("Order received successfully", order.getOrderId()).toMap());
  }

    // Health check endpoint
  @GetMapping(path = "/")
  public ResponseEntity<Object> healthCheck() {
    String healthMessage = "Health check passed. Everything is running smoothly!";
    logger.info("Health check result: {}", healthMessage);
    JSONObject response = new JSONObject();
    response.put("status", "healthy");
    response.put("message", healthMessage);
    return ResponseEntity.ok(response.toMap());
  }
}

@Getter
@Setter
@ToString
class Order {
  private int orderId;
}
