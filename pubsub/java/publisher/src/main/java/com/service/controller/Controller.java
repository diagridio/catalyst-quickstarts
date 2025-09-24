package com.service.controller;

import io.dapr.client.DaprClient;
import io.dapr.client.DaprClientBuilder;
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
import jakarta.annotation.PostConstruct;

@RestController
public class Controller {
    private static final Logger logger = LoggerFactory.getLogger(Controller.class);
    private DaprClient client;

    private static final String PUBSUB_NAME = System.getenv().getOrDefault("PUBSUB_NAME", "pubsub");

    @PostConstruct
    public void init() {
        client = new DaprClientBuilder().build();
    }

    // Helper methods for consistent responses
    private JSONObject createSuccessResponse(String id, String message, String topic) {
        JSONObject response = new JSONObject();
        response.put("id", id);
        response.put("message", message);
        response.put("topic", topic);
        return response;
    }

    private JSONObject createErrorResponse(String code, String message) {
        JSONObject response = new JSONObject();
        JSONObject error = new JSONObject();
        error.put("code", code);
        error.put("message", message);
        response.put("error", error);
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

    // Publish messages 
    @PostMapping(path = "/order", consumes = MediaType.ALL_VALUE)
    public Mono<ResponseEntity> publish(@RequestBody(required = true) Order order) {
        return Mono.fromSupplier(() -> {
            // Publish an event/message using Dapr PubSub
            try {
                client.publishEvent(PUBSUB_NAME, "orders", order).block();
                logger.info("Publish successful. Order published: " + order.getOrderId());
                return ResponseEntity.status(201).body(createSuccessResponse("" + order.getOrderId(), "Message published successfully", "orders").toMap());
            } catch (Exception e) {
                logger.error("Error occurred while publishing order: " + order.getOrderId());
                return ResponseEntity.status(500).body(createErrorResponse("PUBLISH_ERROR", "Failed to publish message").toMap());
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