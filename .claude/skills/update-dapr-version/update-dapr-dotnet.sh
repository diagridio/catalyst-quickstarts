#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    echo "Usage: $0 <version> [start-path]"
    echo "  Updates all Dapr SDK PackageReference versions in .csproj files."
    echo "  <version>    must be a valid semver (e.g. 1.18.0, 2.0.0-rc1)"
    echo "  [start-path] directory to search for .csproj files (default: script directory)"
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

found=0

while IFS= read -r -d '' csproj; do
    # Check if this file contains any Dapr package references
    if grep -q 'PackageReference Include="Dapr\.' "$csproj"; then
        echo "Updating $csproj"
        # Replace the Version attribute on Dapr.* PackageReference lines
        sed -i "s/\(<PackageReference Include=\"Dapr\.[^\"]*\" Version=\"\)[^\"]*/\1${VERSION}/" "$csproj"
        # Show the updated lines
        grep 'PackageReference Include="Dapr\.' "$csproj" | while IFS= read -r line; do
            echo "  $line"
        done
        found=1
    fi
done < <(find "$SEARCH_DIR" -name '*.csproj' -print0)

if [[ "$found" -eq 0 ]]; then
    echo "No .csproj files with Dapr package references found."
    exit 1
fi

echo "Done. All Dapr packages updated to $VERSION."
