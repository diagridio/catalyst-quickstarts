/*
 * Dapr Workflow Quickstart - Java Implementation
 * 
 * This application demonstrates a simple order processing workflow using Dapr Workflows.
 * The workflow includes inventory checking, payment processing, and inventory updates.
 * 
 * Workflow Steps:
 * 1. Notify user of order receipt
 * 2. Reserve inventory for the order
 * 3. Process payment for the order
 * 4. Update inventory after successful payment
 * 5. Notify user of completion
 * 
 * For more information, visit: https://docs.diagrid.io/catalyst/quickstart/workflow
 */

package io.dapr.quickstarts.workflows;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;
import io.dapr.workflows.client.DaprWorkflowClient;
import io.dapr.workflows.client.WorkflowInstanceStatus;
import io.dapr.spring.workflows.config.EnableDaprWorkflows;
import java.time.Duration;
import java.util.concurrent.TimeoutException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;

import io.dapr.quickstarts.workflows.models.*;

/**
 * Main Spring Boot application class for the Dapr Workflow Quickstart.
 * This class provides REST endpoints to interact with the order processing workflow.
 */
@SpringBootApplication
@RestController
@EnableDaprWorkflows
public class WorkflowApp {

  private static final Logger logger = LoggerFactory.getLogger(WorkflowApp.class);

  // The wait budget for the blocking /crash/run. Kept comfortably above the slow activity's
  // default 30s so the first call is still blocked when you kill the app. Overridable through
  // CRASH_WAIT_SECONDS, which is how the e2e suite exercises the 202 branch without waiting
  // two minutes for it.
  @Value("${CRASH_WAIT_SECONDS:120}")
  private int crashWaitSeconds;

  @Autowired
  private DaprWorkflowClient workflowClient;

  private String instanceId;

  /**
   * Health check endpoint - verifies the service is running
   * GET /
   * Returns: { "message": "Health check passed. Everything is running smoothly!" }
   */
  @GetMapping("/")
  public ResponseEntity<ServiceInfo> info() {
    String healthMessage = "Health check passed. Everything is running smoothly!";
    logger.info("Health check result: {}", healthMessage);
    return ResponseEntity.ok(new ServiceInfo(healthMessage));
  }

  /**
   * Start new workflow - creates and schedules a new order processing workflow
   * POST /workflow/start
   * Body: { "name": "Car", "quantity": 2 }
   * Returns: { "instanceId": "uuid" }
   */
  @PostMapping("/workflow/start")
  public ResponseEntity<WorkflowPayload> startWorkflow(@RequestBody OrderPayload order) {
    logger.info("Received request to start workflow for item: {} with quantity: {}", order.getName(), order.getQuantity());

    try {
      instanceId = workflowClient.scheduleNewWorkflow(OrderProcessingWorkflow.class, order);
      logger.info("Workflow execution started successfully for item: {} {}", order.getQuantity(), order.getName());
      return ResponseEntity.ok(new WorkflowPayload(instanceId));
    } catch (Exception e) {
      logger.error("Error starting workflow for item: {} {}", order.getQuantity(), order.getName(), e);
      return ResponseEntity.internalServerError().body(new WorkflowPayload("N/A",
          "Failed to start workflow: " + e.getMessage()));
    }
  }

  /**
   * Get workflow status - retrieves the current state of a workflow instance
   * GET /workflow/status/{instanceId}
   * Returns: WorkflowInstanceStatus object or 204 if not found
   */
  @GetMapping("/workflow/status/{instanceId}")
  public ResponseEntity<WorkflowInstanceStatus> getWorkflowStatus(@PathVariable String instanceId) {
    try {
      // instanceExists, not a null check: getInstanceState hands back a non-null status
      // with empty fields when the instance is absent. See instanceExists below.
      WorkflowInstanceStatus status = workflowClient.getInstanceState(instanceId, true);
      if (instanceExists(status)) {
        logger.info("Retrieved workflow status for {}.", instanceId);
        return ResponseEntity.ok(status);
      } else {
        logger.info("Workflow with id {} does not exist", instanceId);
        return ResponseEntity.status(204).build();
      }
    } catch (Exception e) {
      logger.error("Error occurred while getting the status of the workflow: {}. Exception: {}", instanceId, e.getMessage());
      return ResponseEntity.status(500).build();
    }
  }

  /**
   * Terminate workflow - stops a running workflow instance
   * POST /workflow/terminate/{instanceId}
   * Returns: Updated WorkflowInstanceStatus object
   */
  @PostMapping("/workflow/terminate/{instanceId}")
  public ResponseEntity<WorkflowInstanceStatus> terminateWorkflow(@PathVariable String instanceId) {
    try {
      // Check current state first to provide accurate messaging. A missing instance is a
      // non-null status with empty fields, not a null, so test instanceExists.
      WorkflowInstanceStatus currentStatus = workflowClient.getInstanceState(instanceId, true);
      if (!instanceExists(currentStatus)) {
        logger.info("Workflow with id {} does not exist", instanceId);
        return ResponseEntity.status(204).build();
      }

      // If already in a terminal state, just return the current state
      var terminalStatuses = java.util.Set.of("COMPLETED", "FAILED", "TERMINATED");
      if (terminalStatuses.contains(currentStatus.getRuntimeStatus().toString())) {
        logger.info("Workflow with id {} is already in terminal state {}", instanceId, currentStatus.getRuntimeStatus());
        return ResponseEntity.ok(currentStatus);
      }

      // Terminate the workflow
      workflowClient.terminateWorkflow(instanceId, "dapr");
      logger.info("Terminated workflow with id {}.", instanceId);
      
      // Return the updated state
      WorkflowInstanceStatus updatedStatus = workflowClient.getInstanceState(instanceId, true);
      return ResponseEntity.ok(updatedStatus);
    } catch (Exception e) {
      logger.error("Error occurred while terminating the workflow: {}. Exception: {}", instanceId, e.getMessage());
      return ResponseEntity.status(500).build();
    }
  }

  /**
   * Crash-recovery demo: run the slow workflow under an instance ID the caller owns
   * POST /crash/run
   * Body: { "id": "trip-42", "reference": "ABC123", "kill_after_seconds": 8 }
   * Returns: 200 with the confirmation, or 202 with the ID if the wait budget elapses
   *
   * <p>Re-issuing this with the same ID attaches to the existing run rather than reserving a
   * second time. That is what the caller-owned ID buys, and it is the point of the demo.
   *
   * <p>{@code kill_after_seconds} is optional. Send it and the app crashes itself that many
   * seconds in, so the whole demo runs in two terminals with no window to aim at; leave it
   * out and nothing changes, and you crash the app yourself from a second terminal with
   * {@code POST /crash/kill}.
   */
  @PostMapping("/crash/run")
  public ResponseEntity<CrashRunResponse> crashRun(@RequestBody CrashRunRequest request) {
    String id = request.getId();
    if (id == null || id.isBlank()) {
      return ResponseEntity.badRequest().body(new CrashRunResponse(id, null, "id is required"));
    }

    try {
      if (!instanceExists(workflowClient.getInstanceState(id, false))) {
        logger.info("Starting crash-recovery workflow {} for reservation {}", id, request.getReference());
        workflowClient.scheduleNewWorkflow(CrashRecoveryWorkflow.class, request.getReference(), id);
        // Armed here and nowhere else: only on the branch that actually scheduled a run, and
        // only after the schedule call returned. On the attach branch below it would halt the
        // JVM every time the reader tried to read the answer.
        Integer killAfter = request.getKillAfterSeconds();
        if (killAfter != null && killAfter > 0) {
          armSelfKill(killAfter);
        }
      } else {
        logger.info("Attaching to existing crash-recovery workflow {}", id);
      }

      WorkflowInstanceStatus status = workflowClient.waitForInstanceCompletion(
          id, Duration.ofSeconds(crashWaitSeconds), true);

      // The wait returns on ANY terminal state, so a failed or terminated instance would
      // otherwise be reported as a 200 carrying a null result.
      if (!"COMPLETED".equals(status.getRuntimeStatus().toString())) {
        logger.error("Crash-recovery workflow {} ended as {}", id, status.getRuntimeStatus());
        return ResponseEntity.status(500).body(new CrashRunResponse(id, null,
            "workflow " + id + " ended as " + status.getRuntimeStatus()));
      }

      return ResponseEntity.ok(new CrashRunResponse(id, status.readOutputAs(String.class), null));
    } catch (TimeoutException e) {
      // Not a failure: the run is still going. Re-issue the same request with the same ID to
      // attach and collect the result.
      return ResponseEntity.accepted().body(new CrashRunResponse(id, null,
          "still running as " + id + ", re-issue POST /crash/run with the same id to attach"));
    } catch (Exception e) {
      logger.error("Error running the crash-recovery workflow {}. Exception: {}", id, e.getMessage());
      return ResponseEntity.status(500).body(new CrashRunResponse(id, null, e.getMessage()));
    }
  }

  /**
   * Whether getInstanceState actually found an instance.
   *
   * <p>A null check is not enough, and this is the same trap the C# quickstart fell into.
   * getInstanceState returns null only when the layer below it does, and that layer,
   * DurableTaskGrpcClient.getInstanceMetadata, unconditionally wraps the gRPC response in a
   * new OrchestrationMetadata. A missing instance therefore comes back as a non-null status
   * whose fields are simply empty, so `getInstanceState(id, false) == null` is always false:
   * the schedule branch would be dead and every call would report an attach to a run nobody
   * had created.
   *
   * <p>OrchestrationMetadata answers this with isInstanceFound(), but Dapr's
   * WorkflowInstanceStatus does not expose it. This is that method's exact condition,
   * expressed with the two getters the interface does expose.
   */
  private static boolean instanceExists(WorkflowInstanceStatus status) {
    if (status == null) {
      return false;
    }
    return !isNullOrEmpty(status.getName()) || !isNullOrEmpty(status.getInstanceId());
  }

  private static boolean isNullOrEmpty(String value) {
    return value == null || value.isEmpty();
  }

  /**
   * Simulate a crash: halt the JVM abruptly, like SIGKILL. Demo only.
   * POST /crash/kill
   * Returns: nothing. The process is gone before a response can be written, so the caller sees a
   * connection reset.
   */
  /**
   * Halt the JVM {@code delaySeconds} from now, on a daemon thread.
   *
   * <p>What lets the demo run in two terminals instead of three. {@code /crash/run} blocks for
   * the length of the slow activity, so the shell that starts a run cannot also stop the app,
   * and the kill has always needed a terminal of its own. Arming it here removes that terminal
   * AND the race: the crash lands at a known point inside the window rather than wherever the
   * reader's reflexes put it.
   *
   * <p>Deliberately the same {@code halt(137)} that {@code /crash/kill} uses, for the reason
   * given there: halt skips the shutdown hooks, so this is an abrupt crash rather than a
   * controlled one wearing a crash's name.
   *
   * <p>A daemon thread so the timer can never hold the JVM open if the reader Ctrl+Cs during
   * the countdown.
   */
  private void armSelfKill(int delaySeconds) {
    Thread timer = new Thread(() -> {
      try {
        Thread.sleep(delaySeconds * 1000L);
      } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
        return;
      }
      logger.warn(">>> crash: halting the JVM {}s into the run, as asked by kill_after_seconds",
          delaySeconds);
      Runtime.getRuntime().halt(137);
    }, "crash-self-kill");
    timer.setDaemon(true);
    timer.start();
  }

  @PostMapping("/crash/kill")
  public void crashKill() {
    logger.warn(">>> /crash/kill: halting the JVM to simulate a worker crash");
    // halt, not System.exit: halt skips the JVM shutdown hooks, so this is an abrupt crash rather
    // than a controlled one. System.exit would also run the container's stop sequence on this very
    // request thread, which is not what a crashed worker does.
    Runtime.getRuntime().halt(137);
  }

  public static void main(String[] args) {
    SpringApplication.run(WorkflowApp.class, args);
  }
}
