package com.example.workflow;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class WorkflowController {

  @PostMapping("/workflow/start")
  public ResponseEntity<String> startWorkflow(@RequestBody OrderPayload order) {
    WorkflowConsoleApp.executeWorkflow(order);
    return ResponseEntity.ok("Workflow started successfully.");
  }
}
