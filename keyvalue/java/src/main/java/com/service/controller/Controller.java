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
import javax.annotation.PostConstruct;


@RestController
public class Controller {
    private static final Logger logger = LoggerFactory.getLogger(Controller.class);
    private DaprClient client;

    private static final String KVSTORE_NAME = System.getenv().getOrDefault("KVSTORE_NAME", "kvstore");

    @PostConstruct
    public void init() {
        client = new DaprClientBuilder().build();
    }

    // Save state
    @PostMapping(path = "/kv/orders", consumes = MediaType.ALL_VALUE)
    public Mono<ResponseEntity> saveKV(@RequestBody(required = true) Order order) {
        return Mono.fromSupplier(() -> {
            try {
                Void response = client.saveState(KVSTORE_NAME, "" + order.getOrderId(), order).block();
                logger.info("Save KV Successful.  Order saved: " + order.getOrderId());
                return ResponseEntity.ok("SUCCESS");
            } catch (Exception e) {
                logger.error("Error occurred while saving order: " + order.getOrderId());
                throw new RuntimeException(e);
            }
        });
    }

    // Retrieve state
    @GetMapping(path = "/kv/orders/{orderId}", consumes = MediaType.ALL_VALUE)
    public Mono<ResponseEntity> getKV(@PathVariable String orderId) {
        return Mono.fromSupplier(() -> {
            Order responseOrder = null;
            try {
                State<Order> response = client.getState(KVSTORE_NAME, "" + orderId, Order.class).block();
                responseOrder = response.getValue();
                logger.info("Get KV Successful. Order retrieved: " + responseOrder);
                return ResponseEntity.ok(responseOrder);
            } catch (Exception e) {
                logger.error("Error occurred while retrieving order: " + responseOrder);
                throw new RuntimeException(e);
            }
        });
    }

    // Delete state
    @DeleteMapping(path = "/kv/orders/{orderId}", consumes = MediaType.ALL_VALUE)
    public Mono<ResponseEntity> deleteKV(@PathVariable String orderId) {
        return Mono.fromSupplier(() -> {

            try {
                Void response = client.deleteState(KVSTORE_NAME, "" + orderId).block();
                logger.info("Delete KV Successful. Order deleted: " + orderId);
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