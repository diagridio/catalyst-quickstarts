//! Release Manager: a two-turn Goose conversation run as a durable Dapr
//! Workflow, via Catalyst.
//!
//! Each turn is one Dapr activity that drives a real, unmodified `goose acp`
//! process over the Agent Client Protocol. In turn 1 Goose writes the release
//! notes with its own file tools. Turn 2 runs in a fresh Goose process that
//! reloads the same Goose session, so it still knows which file it wrote.
//! Catalyst records each turn as it completes, so killing this process mid-run
//! and restarting it resumes from the last completed turn instead of starting
//! over (and re-paying for the model calls). See src/bin/crash_test.rs for a
//! demonstration.
//!
//! Run with Catalyst:
//!   diagrid dev run -f dev-goose.yaml --approve

use std::time::{Duration, SystemTime, UNIX_EPOCH};

use anyhow::bail;
use dapr::workflow::{FetchOptions, RuntimeStatus, ScheduleOptions};
use diagrid_goose::{GooseWorkflowOutput, WORKFLOW_NAME};
use goose_release_manager::goose::{self, Goose};

/// One user message per turn, all in the same Goose session. Turn 2 asks for
/// "the release notes" without naming the file: Goose has to remember turn 1.
const TASKS: [&str; 2] = [
    "Write release notes for version 2.4.0 to RELEASE_NOTES.md: it adds dark mode \
     and fixes the login timeout bug.",
    "Add a \"Known issues\" section to the release notes saying CSV export is slow \
     for very large files, then reply with the file's full contents.",
];

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // diagrid_goose logs a warning when it resumes an interrupted turn.
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("warn")).init();

    let goose = Goose::from_env()?;
    println!("Goose:     {}", goose.describe());

    // A local `dapr run` sidecar or a Catalyst project, whichever the
    // environment names. Unlike the Dapr SDK's own WorkflowClient::new(), this
    // adds the TLS and API token Catalyst requires.
    let mut client = diagrid_goose::workflow_client().await?;
    // diagrid_goose's workflow, and the activity that runs one Goose turn.
    diagrid_goose::register(client.registry_mut());
    let worker = client.start_worker().await?;

    let run_id = format!(
        "release-notes-{}",
        SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs()
    );
    let workspace = goose::workspace(&run_id)?;
    println!("Workspace: {}", workspace.display());

    let tasks = TASKS.iter().map(|task| task.to_string()).collect();
    client
        .schedule_workflow(
            WORKFLOW_NAME,
            ScheduleOptions::new()
                .with_instance_id(&run_id)
                .try_with_input(goose.workflow_input(workspace, tasks))?,
        )
        .await?;
    println!(
        "Started workflow {run_id}: {} Goose turns, one durable activity each.\n",
        TASKS.len()
    );

    let done = client
        .wait_for_workflow_completion_with_options(
            &run_id,
            FetchOptions::new().with_fetch_payloads(true),
            Some(Duration::from_secs(600)),
        )
        .await?;
    worker.shutdown().await?;
    if done.runtime_status != RuntimeStatus::Completed {
        bail!(
            "workflow {run_id} ended {}: {}",
            done.runtime_status,
            done.failure_details.map(|f| f.message).unwrap_or_default()
        );
    }
    let output: GooseWorkflowOutput =
        serde_json::from_str(done.serialized_output.as_deref().unwrap_or_default())?;

    println!("{}", "=".repeat(60));
    for (i, (task, turn)) in TASKS.iter().zip(&output.turns).enumerate() {
        println!(
            "Turn {}\n  you:   {task}\n  goose: {}\n",
            i + 1,
            hanging_indent(turn.response_text.trim())
        );
    }
    println!("Status:  {}", done.runtime_status);
    println!(
        "Turns:   {}, all in Goose session {}",
        output.turns.len(),
        output.session_id
    );
    println!("{}", "=".repeat(60));
    println!(
        "Print the whole conversation with: goose session export --session-id {}",
        output.session_id
    );
    Ok(())
}

/// Indent every line after the first, so a multi-line reply lines up under the
/// `goose: ` label.
fn hanging_indent(text: &str) -> String {
    text.lines().collect::<Vec<_>>().join("\n         ")
}
