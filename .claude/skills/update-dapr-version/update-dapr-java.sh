#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    echo "Usage: $0 <version> [start-path]"
    echo "  Updates all Dapr SDK dependency versions in pom.xml files."
    echo "  Handles both inline <version> tags and <dapr.version> properties."
    echo "  Known artifacts: dapr-sdk, dapr-sdk-springboot, dapr-spring-boot-starter,"
    echo "                   dapr-spring-boot-starter-test"
    echo "  <version>    must be a valid semver (e.g. 1.18.0, 2.0.0-rc1)"
    echo "  [start-path] directory to search for pom.xml files (default: script directory)"
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

while IFS= read -r -d '' pom; do
    # Check if this file contains any Dapr dependencies (io.dapr or io.dapr.spring)
    if grep -q '<groupId>io\.dapr' "$pom"; then
        echo "Updating $pom"

        # Use awk to:
        # 1. Update <dapr.version> properties
        # 2. Update inline <version> tags inside Dapr dependency blocks
        awk -v ver="$VERSION" '
        BEGIN { in_dep = 0; is_dapr = 0 }
        /<dependency>/ { in_dep = 1; is_dapr = 0 }
        in_dep && /<groupId>io\.dapr/ { is_dapr = 1 }
        in_dep && is_dapr && /<version>/ && !/\$\{/ {
            sub(/<version>[^<]*<\/version>/, "<version>" ver "</version>")
        }
        /<\/dependency>/ { in_dep = 0; is_dapr = 0 }
        /<dapr\.version>/ {
            sub(/<dapr\.version>[^<]*<\/dapr\.version>/, "<dapr.version>" ver "</dapr.version>")
        }
        { print }
        ' "$pom" > "${pom}.tmp" && mv "${pom}.tmp" "$pom"

        # Show the updated Dapr-related lines
        grep -E '(<dapr\.version>|<groupId>io\.dapr)' "$pom" | while IFS= read -r line; do
            echo "  $line"
        done
        found=1
    fi
done < <(find "$SEARCH_DIR" -name 'pom.xml' -print0)

if [[ "$found" -eq 0 ]]; then
    echo "No pom.xml files with Dapr dependencies found."
    exit 1
fi

echo "Done. All Dapr packages updated to $VERSION."
