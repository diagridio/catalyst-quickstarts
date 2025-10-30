package com.service.controller;

import com.service.model.ErrorResponse;
import com.service.model.Order;
import com.service.model.PublishResponse;
import com.service.model.ServiceInfo;
import com.service.model.SuccessResponse;
import io.dapr.client.DaprClient;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@RestController
public class Controller {
    private static final Logger logger = LoggerFactory.getLogger(Controller.class);

    @Autowired
    private DaprClient client;

    private static final String PUBSUB_NAME = System.getenv().getOrDefault("PUBSUB_NAME", "pubsub");

    // Health check endpoint
    @GetMapping(path = "/")
    public ResponseEntity<ServiceInfo> healthCheck() {
        String healthMessage = "Health check passed. Everything is running smoothly!";
        logger.info("Health check result: {}", healthMessage);
        return ResponseEntity.ok(new ServiceInfo("healthy", healthMessage));
    }

    // Publish messages 
    @PostMapping(path = "/order", consumes = MediaType.ALL_VALUE)
    public ResponseEntity<PublishResponse> publish(@RequestBody(required = true) Order order) {
      try {
        client.publishEvent(PUBSUB_NAME, "orders", order).block();
        logger.info("Publish successful. Order published: {}", order.orderId());
        return ResponseEntity.status(201).body(new SuccessResponse(String.valueOf(order.orderId()), "Message published successfully", "orders"));
      } catch (Exception e) {
        logger.error("Error occurred while publishing order: {}", order.orderId());
        return ResponseEntity.status(500).body(new ErrorResponse("PUBLISH_ERROR", "Failed to publish message"));
      }
    }
}
