---
name: Update Dapr Version
description: Updates Dapr SDK dependency versions in .NET, Python, and/or Java projects. Use this skill when the user mentions updating, bumping, or upgrading dapr versions, e.g. "update the .NET projects to dapr 1.17.0", "bump the dapr version in Java to 1.17.0-rc1", "upgrade all dapr dependencies to 1.17.0".
---

## Overview

This skill upgrades Dapr SDK dependencies across the quickstart projects in this repo.
Each supported language has a dedicated bash script.

## Scripts

| Language   | Script                                          |
|------------|-------------------------------------------------|
| .NET/C#    | [update-dapr-dotnet](./update-dapr-dotnet.sh)   |
| Java       | [update-dapr-java](./update-dapr-java.sh)       |
| Python     | [update-dapr-python](./update-dapr-python.sh)   |

### Usage

```bash
bash <script> <version> <start-path>
```

- `version` — the target semver version (e.g. `1.17.0`, `2.0.0-rc1`).
- `start-path` — the root of the repository to search from.

### Example

```bash
bash .claude/skills/update-dapr-version/update-dapr-dotnet.sh 1.17.0 /workspaces/catalyst-quickstarts
```

## Behavior

- If the user specifies a language, run only that language's script.
- If no language is specified, run **all three** scripts.
- After running, show the user the list of files that were updated.
