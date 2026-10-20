//! How this quickstart runs Goose: which binary, which model, and where it works.
//!
//! Uses OpenAI's gpt-4o-mini by default (needs OPENAI_API_KEY). Set
//! GOOSE_PROVIDER and GOOSE_MODEL to run on any other provider Goose supports,
//! with that provider's own key in the environment.

use std::path::PathBuf;
use std::process::Command;

use anyhow::{bail, Context};
use diagrid_goose::GooseWorkflowInput;

const DEFAULT_PROVIDER: &str = "openai";
const DEFAULT_MODEL: &str = "gpt-4o-mini";

/// The Goose CLI this process found, and the model it will run on.
pub struct Goose {
    program: String,
    version: String,
    provider: String,
    model: String,
}

impl Goose {
    /// Find the Goose CLI and settle the model. Fails here, before anything is
    /// scheduled, if Goose is missing or the default provider has no key.
    pub fn from_env() -> anyhow::Result<Self> {
        let program = env_or("GOOSE_BIN", "goose");
        let version = Command::new(&program)
            .arg("--version")
            .output()
            .with_context(|| {
                format!(
                    "can't run `{program}`: install the Goose CLI (see README.md) \
                     or set GOOSE_BIN to its path"
                )
            })?
            .stdout;
        let provider = env_or("GOOSE_PROVIDER", DEFAULT_PROVIDER);
        let model = env_or("GOOSE_MODEL", DEFAULT_MODEL);
        if provider == DEFAULT_PROVIDER && env_or("OPENAI_API_KEY", "").is_empty() {
            bail!(
                "OPENAI_API_KEY is not set. Export it (see README.md), or set \
                 GOOSE_PROVIDER and GOOSE_MODEL to use another provider Goose supports."
            );
        }
        Ok(Self {
            program,
            version: String::from_utf8_lossy(&version).trim().to_string(),
            provider,
            model,
        })
    }

    /// One line for the startup log, e.g. `goose 1.54.0 on openai/gpt-4o-mini`.
    pub fn describe(&self) -> String {
        format!("goose {} on {}/{}", self.version, self.provider, self.model)
    }

    /// The durable input for one run: one message per turn, all in one Goose
    /// session, with Goose working in `cwd`.
    pub fn workflow_input(&self, cwd: PathBuf, tasks: Vec<String>) -> GooseWorkflowInput {
        GooseWorkflowInput {
            program: self.program.clone(),
            args: vec!["acp".to_string()],
            // Provider and model only, never the API key. The workflow input is
            // recorded in Catalyst, where anyone with access to the project can
            // read it, so Goose inherits the key from this process's
            // environment instead.
            env: vec![
                ("GOOSE_PROVIDER".to_string(), self.provider.clone()),
                ("GOOSE_MODEL".to_string(), self.model.clone()),
                // Take the key from the environment, never from a system
                // keyring: nobody is at the keyboard to unlock one.
                ("GOOSE_DISABLE_KEYRING".to_string(), "1".to_string()),
            ],
            cwd,
            tasks,
        }
    }
}

/// A fresh directory for one run. Goose approves its own tool calls (nobody is
/// there to ask), so it gets a scratch directory rather than this repository.
pub fn workspace(run_id: &str) -> std::io::Result<PathBuf> {
    // The crash demo takes the run ID from a request, so keep it to one path
    // segment: no separators, no `..`.
    let name: String = run_id
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || c == '-' || c == '_' {
                c
            } else {
                '_'
            }
        })
        .collect();
    let dir = std::env::temp_dir().join("goose-quickstart").join(name);
    std::fs::create_dir_all(&dir)?;
    Ok(dir)
}

/// `name`'s value, or `default` when it is unset or empty.
fn env_or(name: &str, default: &str) -> String {
    std::env::var(name)
        .ok()
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| default.to_string())
}
