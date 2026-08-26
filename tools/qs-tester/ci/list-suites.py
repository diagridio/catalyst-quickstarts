"""Read the suite manifest for CI and for the lint dryrun.

Four modes:

    --paths              space-separated suite paths, ready to paste after
                         `robot --dryrun`, run from tools/qs-tester
    --matrix agent       JSON array for a GitHub Actions matrix
    --validate           print problems and exit 1, or confirm and exit 0
    --row <suite-path>   KEY=value lines describing one registered suite, for
                         shell scripts that must branch on its family; exits 1
                         if the suite is not in the manifest

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
    mode.add_argument("--row", metavar="SUITE_PATH")
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
        # `leg` is `suites.leg_id(row)` — the fragment that actually feeds
        # `ci/project-name.sh` (via `agents-<leg>`) — kept distinct from `name`,
        # which stays the artifact and failure-summary key. A row's explicit
        # `leg` override exists to keep the ephemeral project name under the
        # 55-character ceiling; if the workflow rebuilt the leg from `name`
        # instead of reading this field, the override would pass
        # `--validate` and then still overflow at `diagrid project create`.
        matrix = [
            {
                "suite": row["suite"],
                "name": row["name"],
                "leg": suites.leg_id(row),
                "language": row["language"],
                "runtime": row["runtime"],
                "secrets": list(row["secrets"]),
            }
            for row in rows
        ]
        # Compact separators: this lands in $GITHUB_OUTPUT, which is line-based.
        print(json.dumps(matrix, separators=(",", ":")))
        return 0

    if args.row:
        # A leading "../../" is how robot receives a suite path, so accept it
        # here too rather than making callers strip it.
        suite = args.row.removeprefix("../../")
        row = suites.row_for_suite(suite)
        if row is None:
            print(
                f"::error::{suite} is not registered in variables/suites.py. "
                "Add its row there first: the manifest is what CI, the dryrun and "
                "doc-sync all read.",
                file=sys.stderr,
            )
            return 1
        # KEY=value lines rather than JSON: the only consumer is a shell script,
        # and the values come from the manifest, never from user input.
        print(f"FAMILY={row['family']}")
        if row["family"] == "canonical":
            print(f"API={row['api']}")
            print(f"LANGUAGES={' '.join(row['languages'])}")
        else:
            print(f"NAME={row['name']}")
            # The leg actually used for the ephemeral project name (via
            # `agents-<leg>`), not necessarily `name` -- see `suites.leg_id`.
            # A caller that rebuilds `agents-<name>` by hand instead of reading
            # this ignores a row's explicit `leg` override.
            print(f"LEG={suites.leg_id(row)}")
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
