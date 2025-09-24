package com.service.controller;

import io.dapr.client.DaprClient;
import io.dapr.client.DaprClientBuilder;
import io.dapr.client.domain.CloudEvent;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
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
  private HttpClient httpClient;

  private static final String DAPR_HTTP_ENDPOINT = System.getenv().getOrDefault("DAPR_HTTP_ENDPOINT",
      "http://localhost");
  private static final String DAPR_API_TOKEN = System.getenv().getOrDefault("DAPR_API_TOKEN", "");
  private static final String INVOKE_APPID = System.getenv().getOrDefault("INVOKE_APPID", "server");

  @PostConstruct
  public void init() {
    client = new DaprClientBuilder().build();
    httpClient = HttpClient.newBuilder()
        .version(HttpClient.Version.HTTP_2)
        .connectTimeout(Duration.ofSeconds(10))
        .build();
  }

  // Helper methods for consistent responses
  private JSONObject createSuccessResponse(String message, int orderId, String targetApp) {
    JSONObject response = new JSONObject();
    response.put("message", message);
    response.put("orderId", orderId);
    response.put("targetApp", targetApp);
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

  // Invoke another service
  @PostMapping(path = "/order", consumes = MediaType.ALL_VALUE)
  public Mono<ResponseEntity> order(@RequestBody(required = true) Order order) {
    return Mono.fromSupplier(() -> {
      try {
        JSONObject obj = new JSONObject();
        obj.put("orderId", order.getOrderId());

        HttpRequest request = HttpRequest.newBuilder()
            .POST(HttpRequest.BodyPublishers.ofString(obj.toString()))
            .uri(URI.create(DAPR_HTTP_ENDPOINT + "/neworder"))
            .header("dapr-api-token", DAPR_API_TOKEN)
            .header("Content-Type", "application/json")
            .header("dapr-app-id", INVOKE_APPID)
            .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() == 200) {
          logger.info("Invoke Successful. Response received: " + order.getOrderId());
          return ResponseEntity.ok(createSuccessResponse("Invocation successful", order.getOrderId(), INVOKE_APPID).toMap());
        } else {
          logger.error("Invocation unsuccessful with status code: " + response.statusCode());
          return ResponseEntity.status(500).body(createErrorResponse("INVOCATION_ERROR", "Failed to invoke service").toMap());
        }
      } catch (Exception e) {
        logger.error("Error occurred while invoking App ID. " + e);
        return ResponseEntity.status(500).body(createErrorResponse("INVOCATION_ERROR", "Failed to invoke service").toMap());
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
