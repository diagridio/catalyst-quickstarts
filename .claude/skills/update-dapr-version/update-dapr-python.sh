#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    echo "Usage: $0 <version> [start-path]"
    echo "  Updates dapr and dapr-ext-workflow versions in requirements.txt files."
    echo "  Does NOT update dapr-agents (which has its own independent version)."
    echo "  <version>    must be a valid semver (e.g. 1.18.0, 2.0.0-rc1)"
    echo "  [start-path] directory to search for requirements.txt files (default: script directory)"
    exit 1
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
    usage
fi

VERSION="$1"
SEARCH_DIR="${2:-$SCRIPT_DIR}"

if [[ ! -d "$SEARCH_DIR" ]]; then
    echo "Error: '$SEARCH_DIR' is not a valid directory."
    exit 1
fi

# Validate semver: X.Y.Z with optional pre-release suffix
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([-][a-zA-Z0-9.]+)?$ ]]; then
    echo "Error: '$VERSION' is not a valid version. Expected format: X.Y.Z or X.Y.Z-suffix"
    exit 1
fi

# Packages to update (dapr and dapr-ext-* but NOT dapr-agents)
# Matches: dapr==x.y.z, dapr>=x.y.z, dapr-ext-workflow==x.y.z, etc.
DAPR_PATTERN='^dapr(-ext-[a-zA-Z0-9_-]+)?(==|>=|<=|~=|!=)'

found=0

while IFS= read -r -d '' reqfile; do
    # Check if this file contains any Dapr package references (excluding dapr-agents)
    if grep -qE "$DAPR_PATTERN" "$reqfile"; then
        echo "Updating $reqfile"
        # Replace version for dapr== or dapr>=, etc. (but not dapr-agents)
        sed -i -E "s/^(dapr)(==|>=|<=|~=|!=)[^ ]*/\1\2${VERSION}/" "$reqfile"
        # Replace version for dapr-ext-* packages
        sed -i -E "s/^(dapr-ext-[a-zA-Z0-9_-]+)(==|>=|<=|~=|!=)[^ ]*/\1\2${VERSION}/" "$reqfile"
        # Show the updated lines
        grep -E "$DAPR_PATTERN" "$reqfile" | while IFS= read -r line; do
            echo "  $line"
        done
        found=1
    fi
done < <(find "$SEARCH_DIR" -name 'requirements.txt' -print0)

if [[ "$found" -eq 0 ]]; then
    echo "No requirements.txt files with Dapr package references found."
    exit 1
fi

echo "Done. All Dapr Python packages updated to $VERSION."
