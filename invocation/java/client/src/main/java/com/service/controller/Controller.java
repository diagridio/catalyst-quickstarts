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
import javax.annotation.PostConstruct;

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

  // Invoke another service
  @PostMapping(path = "/order", consumes = MediaType.ALL_VALUE)
  public Mono<ResponseEntity> request(@RequestBody(required = true) Order order) {
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
        JSONObject jsonObject = new JSONObject(response.body());
        logger.info("Invoke Successful. Response received: " + jsonObject.getInt("orderId"));
        return ResponseEntity.ok("SUCCESS");
      } catch (Exception e) {
        logger.error("Error occurred while invoking App ID. " + e);
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
