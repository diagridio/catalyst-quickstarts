package io.dapr.quickstarts.workflows;

import io.dapr.quickstarts.workflows.activities.CommitReservationActivity;
import io.dapr.quickstarts.workflows.activities.NotifyActivity;
import io.dapr.quickstarts.workflows.models.Notification;
import io.dapr.workflows.Workflow;
import io.dapr.workflows.WorkflowStub;
import org.springframework.stereotype.Component;

/**
 * Crash-recovery demo: a workflow built to be interrupted.
 *
 * <p>{@link OrderProcessingWorkflow} cannot do this job. Its only delay is the 2s payment, and two
 * seconds is not a window a human can aim a second terminal at. This workflow runs one instant
 * activity and then one that takes about 30 seconds, so a kill lands between two known points.
 *
 * <p>The activity ORDER is the whole design. The fast notification completes first, so Catalyst has
 * persisted its result before the slow activity starts. After a restart that notification is
 * replayed from the recorded result rather than re-executed, and its absence from the log is what
 * proves durable execution did something. Reverse the two and the crash lands before anything has
 * completed, the run restarts from nothing, and the demo proves nothing at all.
 *
 * <p>No registration is needed: {@code @EnableDaprWorkflows} on {@link WorkflowApp} discovers every
 * {@code Workflow} and {@code WorkflowActivity} bean by type.
 */
@Component
public class CrashRecoveryWorkflow implements Workflow {

  @Override
  public WorkflowStub create() {
    return ctx -> {
      String demoId = ctx.getInstanceId();
      String reference = ctx.getInput(String.class);

      // Fast, and first. See the class comment: this is not an arbitrary ordering.
      Notification received = new Notification();
      received.setMessage("Reservation " + demoId + " received for " + reference);
      ctx.callActivity(NotifyActivity.class.getCanonicalName(), received).await();

      // Slow. Kill the app while this is running.
      String confirmation = ctx
          .callActivity(CommitReservationActivity.class.getCanonicalName(), reference, String.class)
          .await();

      // A fresh object rather than a setter on the one above. Reusing and mutating an input
      // across an await is the pattern a reader should not copy out of a workflow.
      Notification completed = new Notification();
      completed.setMessage("Reservation " + demoId + " has completed! " + confirmation);
      ctx.callActivity(NotifyActivity.class.getCanonicalName(), completed).await();

      ctx.complete(confirmation);
    };
  }
}
