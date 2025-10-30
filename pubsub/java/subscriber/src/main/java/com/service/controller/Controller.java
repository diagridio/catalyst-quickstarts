package com.service.controller;

import com.service.model.Order;
import com.service.model.ServiceInfo;
import com.service.model.SuccessResponse;
import io.dapr.client.domain.CloudEvent;

import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;


@RestController
public class Controller {
    
    private static final Logger logger = LoggerFactory.getLogger(Controller.class);

    // Health check endpoint
    @GetMapping(path = "/")
    public ResponseEntity<ServiceInfo> healthCheck() {
        String healthMessage = "Health check passed. Everything is running smoothly!";
        logger.info("Health check result: {}", healthMessage);
        return ResponseEntity.ok(new ServiceInfo("healthy", healthMessage));
    }

    @PostMapping(path = "/neworder", consumes = MediaType.ALL_VALUE)
    public ResponseEntity<SuccessResponse> subscribe(@RequestBody(required = false) CloudEvent<Order> cloudEvent) {
      try {
        int orderId = cloudEvent.getData().orderId();
        logger.info("Order received: {}", orderId);
        return ResponseEntity.ok(new SuccessResponse(orderId, "Message received successfully"));
      } catch (Exception e) {
        logger.error("Error occurred while processing order: {}", e.getMessage());
        throw new RuntimeException(e);
      }

    }
}
