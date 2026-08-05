"""Read the suite manifest for CI and for the lint dryrun.

Three modes:

    --paths              space-separated suite paths, ready to paste after
                         `robot --dryrun`, run from tools/qs-tester
    --matrix agent       JSON array for a GitHub Actions matrix
    --validate           print problems and exit 1, or confirm and exit 0

Usage from the workflow:

    uv run robot --dryrun ... $(uv run python ci/list-suites.py --paths)
    echo "agents=$(uv run python ci/list-suites.py --matrix agent --nightly)" >> "$GITHUB_OUTPUT"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Same reason as check_readme_sync.py: pytest's pythonpath setting does not
# apply when this file runs as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "variables"))

import suites  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--paths", action="store_true")
    mode.add_argument("--matrix", choices=("agent",))
    mode.add_argument("--validate", action="store_true")
    parser.add_argument(
        "--nightly",
        action="store_true",
        help="with --matrix: only suites opted into the nightly run",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
    )
    args = parser.parse_args()

    if args.paths:
        print(" ".join(suites.suite_paths()))
        return 0

    if args.matrix:
        rows = suites.agent_suites(nightly_only=args.nightly)
        # One flat object per matrix leg. `secrets` is a list of names, not
        # values: the workflow declares the values in its env block, and the
        # suite fails loudly through `Require Env Var` if one is missing.
        matrix = [
            {
                "suite": row["suite"],
                "name": row["name"],
                "language": row["language"],
                "runtime": row["runtime"],
                "secrets": list(row["secrets"]),
            }
            for row in rows
        ]
        # Compact separators: this lands in $GITHUB_OUTPUT, which is line-based.
        print(json.dumps(matrix, separators=(",", ":")))
        return 0

    problems = suites.validate(args.repo_root)
    for problem in problems:
        print(f"::error::{problem}")
    if problems:
        print(f"\n{len(problems)} problem(s) in the suite manifest")
        return 1
    print(f"Suite manifest is valid ({len(suites.SUITES)} suite(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
