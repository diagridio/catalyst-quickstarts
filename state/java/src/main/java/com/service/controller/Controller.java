package com.service.controller;

import io.dapr.client.DaprClient;
import io.dapr.client.DaprClientBuilder;

import java.net.URI;
import java.time.Duration;

import io.dapr.client.domain.State;
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

    private static final String STATESTORE_NAME = System.getenv().getOrDefault("STATESTORE_NAME", "statestore");

    @PostConstruct
    public void init() {
        client = new DaprClientBuilder().build();
    }

    // Helper methods for consistent responses
    private JSONObject createSuccessResponse(String id, String message) {
        JSONObject response = new JSONObject();
        response.put("id", id);
        response.put("message", message);
        return response;
    }

    private JSONObject createDataResponse(Object data) {
        JSONObject response = new JSONObject();
        response.put("data", data);
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

    // Save state
    @PostMapping(path = "/order", consumes = MediaType.ALL_VALUE)
    public Mono<ResponseEntity> saveState(@RequestBody(required = true) Order order) {
        return Mono.fromSupplier(() -> {
            try {
                Void response = client.saveState(STATESTORE_NAME, "" + order.getOrderId(), order).block();
                logger.info("Save state item successful. Order saved: " + order.getOrderId());
                return ResponseEntity.status(201).body(createSuccessResponse("" + order.getOrderId(), "Order created successfully").toMap());
            } catch (Exception e) {
                logger.error("Error occurred while saving order: " + order.getOrderId());
                return ResponseEntity.status(500).body(createErrorResponse("INTERNAL_ERROR", "An internal server error occurred").toMap());
            }
        });
    }

    // Retrieve state
    @GetMapping(path = "/order/{orderId}", consumes = MediaType.ALL_VALUE)
    public Mono<ResponseEntity> getState(@PathVariable String orderId) {
        return Mono.fromSupplier(() -> {
            Order responseOrder = null;
            try {
                State<Order> response = client.getState(STATESTORE_NAME, "" + orderId, Order.class).block();
                responseOrder = response.getValue();
                if (responseOrder != null) {
                    logger.info("Get state item successful. Order retrieved: " + responseOrder);
                    return ResponseEntity.ok(createDataResponse(responseOrder).toMap());
                } else {
                    logger.info("State item with key does not exist: " + orderId);
                    return ResponseEntity.status(404).body(createErrorResponse("ORDER_NOT_FOUND", "Order with id '" + orderId + "' not found").toMap());
                }
            } catch (Exception e) {
                logger.error("Error occurred while retrieving order: " + responseOrder);
                return ResponseEntity.status(500).body(createErrorResponse("INTERNAL_ERROR", "An internal server error occurred").toMap());
            }
        });
    }

    // Delete state
    @DeleteMapping(path = "/order/{orderId}", consumes = MediaType.ALL_VALUE)
    public Mono<ResponseEntity> deleteState(@PathVariable String orderId) {
        return Mono.fromSupplier(() -> {
            try {
                Void response = client.deleteState(STATESTORE_NAME, "" + orderId).block();
                logger.info("Delete state item successful. Order deleted: " + orderId);
                return ResponseEntity.noContent().build();
            } catch (Exception e) {
                logger.error("Error occurred while deleting order: " + orderId);
                return ResponseEntity.status(500).body(createErrorResponse("INTERNAL_ERROR", "An internal server error occurred").toMap());
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