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

  // Service to be invoked
  @PostMapping(path = "/invoke/neworders", consumes = MediaType.APPLICATION_JSON_VALUE)
  public ResponseEntity<Order> reply(@RequestBody Order order) {
    logger.info("Request received: " + order.getOrderId());
    return ResponseEntity.ok(order);
  }
}

@Getter
@Setter
@ToString
class Order {
  private int orderId;
}
