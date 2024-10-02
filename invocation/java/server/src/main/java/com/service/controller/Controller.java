package com.service.controller;

import lombok.Getter;
import lombok.Setter;
import lombok.ToString;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
public class Controller {
  private static final Logger logger = LoggerFactory.getLogger(Controller.class);

  @PostMapping(path = "/neworder", consumes = MediaType.APPLICATION_JSON_VALUE)
  public ResponseEntity<Order> neworder(@RequestBody Order order) {
    logger.info("Invocation received with data " + order.getOrderId());
    return ResponseEntity.ok(order);
  }

    // Health check endpoint
  @GetMapping(path = "/")
  public ResponseEntity<String> healthCheck() {
    String healthMessage = "Health check passed. Everything is running smoothly! 🚀";
    logger.info("Health check result: {}", healthMessage);
    return ResponseEntity.ok(healthMessage);
  }
}

@Getter
@Setter
@ToString
class Order {
  private int orderId;
}
