package com.service.controller;

import io.dapr.client.domain.CloudEvent;

import lombok.Getter;
import lombok.Setter;
import lombok.ToString;
import org.json.JSONObject;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import reactor.core.publisher.Mono;

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

    @PostMapping(path = "/neworder", consumes = MediaType.ALL_VALUE)
    public Mono<ResponseEntity> subscribe(@RequestBody(required = false) CloudEvent<Order> cloudEvent) {
        return Mono.fromSupplier(() -> {
            try {
                int orderId = cloudEvent.getData().getOrderId();
                logger.info("Order received: " + orderId);
                return ResponseEntity.ok(createSuccessResponse("Message received successfully", orderId).toMap());
            } catch (Exception e) {
                logger.error("Error occurred while processing order: " + e.getMessage());
                throw new RuntimeException(e);
            }
        });
    }
}

@Getter
@Setter
@ToString
class Order {
    private int orderId;
}