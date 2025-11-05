package com.service.controller;

import com.service.model.DataResponse;
import com.service.model.ErrorResponse;
import com.service.model.Order;
import com.service.model.ServiceInfo;
import com.service.model.StateResponse;
import com.service.model.SuccessResponse;
import io.dapr.client.DaprClient;

import io.dapr.client.domain.State;
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

    private static final String STATESTORE_NAME = System.getenv().getOrDefault("STATESTORE_NAME", "kvstore");

    // Health check endpoint
    @GetMapping(path = "/")
    public ResponseEntity<ServiceInfo> healthCheck() {
        String healthMessage = "Health check passed. Everything is running smoothly!";
        logger.info("Health check result: {}", healthMessage);
        return ResponseEntity.ok(new ServiceInfo("healthy", healthMessage));
    }

    // Save state
    @PostMapping(path = "/order", consumes = MediaType.ALL_VALUE)
    public ResponseEntity<StateResponse> saveState(@RequestBody(required = true) Order order) {
        try {
          Void response = client.saveState(STATESTORE_NAME, "" + order.orderId(), order).block();
          logger.info("Save state item successful. Order saved: " + order.orderId());
          return ResponseEntity.status(201).body(new SuccessResponse(order.orderId(), "Order created successfully"));
        } catch (Exception e) {
          logger.error("Error occurred while saving order: " + order.orderId());
          return ResponseEntity.status(500).body(new ErrorResponse("INTERNAL_ERROR", "An internal server error occurred"));
        }
    }

    // Retrieve state
    @GetMapping(path = "/order/{orderId}", consumes = MediaType.ALL_VALUE)
    public ResponseEntity<StateResponse> getState(@PathVariable String orderId) {

            Order responseOrder = null;
            try {
                State<Order> response = client.getState(STATESTORE_NAME, String.valueOf(orderId), Order.class).block();
                responseOrder = response.getValue();
                if (responseOrder != null) {
                    logger.info("Get state item successful. Order retrieved: " + responseOrder);
                    return ResponseEntity.ok(new DataResponse(responseOrder));
                } else {
                    logger.info("State item with key does not exist: " + orderId);
                    return ResponseEntity.status(404).body(new ErrorResponse("ORDER_NOT_FOUND", "Order with id '" + orderId + "' not found"));
                }
            } catch (Exception e) {
                logger.error("Error occurred while retrieving order: " + responseOrder);
                return ResponseEntity.status(500).body(new ErrorResponse("INTERNAL_ERROR", "An internal server error occurred"));
            }

    }

    // Delete state
    @DeleteMapping(path = "/order/{orderId}", consumes = MediaType.ALL_VALUE)
    public ResponseEntity<StateResponse> deleteState(@PathVariable String orderId) {

            try {
                Void response = client.deleteState(STATESTORE_NAME, String.valueOf(orderId)).block();
                logger.info("Delete state item successful. Order deleted: " + orderId);
                return ResponseEntity.noContent().build();
            } catch (Exception e) {
                logger.error("Error occurred while deleting order: " + orderId);
                return ResponseEntity.status(500).body(new ErrorResponse("INTERNAL_ERROR", "An internal server error occurred"));
            }

    }
}

