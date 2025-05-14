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

    private static final String STATESTORE_NAME = System.getenv().getOrDefault("STATESTORE_NAME", "kvstore");

    @PostConstruct
    public void init() {
        client = new DaprClientBuilder().build();
    }

    // Health check endpoint
    @GetMapping(path = "/")
    public ResponseEntity<String> healthCheck() {
        String healthMessage = "Health check passed. Everything is running smoothly! 🚀";
        logger.info("Health check result: {}", healthMessage);
        return ResponseEntity.ok(healthMessage);
    }

    // Save state
    @PostMapping(path = "/order", consumes = MediaType.ALL_VALUE)
    public Mono<ResponseEntity> saveState(@RequestBody(required = true) Order order) {
        return Mono.fromSupplier(() -> {
            try {
                Void response = client.saveState(STATESTORE_NAME, "" + order.getOrderId(), order).block();
                logger.info("Save state item successful. Order saved: " + order.getOrderId());
                return ResponseEntity.ok("SUCCESS");
            } catch (Exception e) {
                logger.error("Error occurred while saving order: " + order.getOrderId());
                throw new RuntimeException(e);
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
                logger.info("Get state item successful. Order retrieved: " + responseOrder);
                return ResponseEntity.ok(responseOrder);
            } catch (Exception e) {
                logger.error("Error occurred while retrieving order: " + responseOrder);
                throw new RuntimeException(e);
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
                return ResponseEntity.ok("SUCCESS");
            } catch (Exception e) {
                logger.error("Error occurred while deleting order: " + orderId);
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