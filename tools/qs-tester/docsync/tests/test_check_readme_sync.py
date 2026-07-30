import pytest
from check_readme_sync import (
    extract_bash_blocks,
    extract_curl_calls,
    extract_json_blocks,
    normalise_run_command,
)

README = """\
# Quickstart: State Management (Python)

## 1. Prerequisites

- Python 3.12+

## 4. Install Dependencies

```bash
uv venv
source .venv/bin/activate
```

Install dependencies:

```bash
uv sync
```

## 5. Run the application with Catalyst Cloud

```bash
diagrid dev run -f state-quickstart.yaml --project state-quickstart --approve
```

## 6. Call the State API

### 6.1 Store state

**macOS/Linux (curl):**

```bash
curl -i -X POST http://localhost:5001/order -H "Content-Type: application/json" -d '{"orderId":1}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:5001/order"
```

The expected response is `201 Created` with this body:

```json
{"id":1,"message":"Order created successfully"}
```

## 7. Clean Up

```bash
diagrid project delete state-quickstart
```
"""


def test_extract_bash_blocks_returns_only_the_named_section():
    assert extract_bash_blocks(README, "4") == [
        "uv venv\nsource .venv/bin/activate",
        "uv sync",
    ]
    assert extract_bash_blocks(README, "5") == [
        "diagrid dev run -f state-quickstart.yaml --project state-quickstart --approve"
    ]


def test_extract_bash_blocks_ignores_powershell():
    blocks = extract_bash_blocks(README, "6")
    assert len(blocks) == 1
    assert blocks[0].startswith("curl -i -X POST")
    assert not any("Invoke-RestMethod" in b for b in blocks)


def test_extract_curl_calls_parses_method_url_and_payload():
    assert extract_curl_calls(README) == [
        {
            "method": "POST",
            "url": "http://localhost:5001/order",
            "payload": {"orderId": 1},
        }
    ]


def test_extract_json_blocks_returns_expected_bodies():
    assert extract_json_blocks(README, "6") == [
        {"id": 1, "message": "Order created successfully"}
    ]


def test_normalise_run_command_replaces_the_documented_project_name():
    documented = "diagrid dev run -f state-quickstart.yaml --project state-quickstart --approve"
    harness = "diagrid dev run -f state-quickstart.yaml --project {project} --approve"
    assert normalise_run_command(documented) == normalise_run_command(harness)


def test_normalise_run_command_keeps_other_differences_visible():
    a = "diagrid dev run -f state-quickstart.yaml --project {project} --approve"
    b = "diagrid dev run -f wrong-file.yaml --project {project} --approve"
    assert normalise_run_command(a) != normalise_run_command(b)
