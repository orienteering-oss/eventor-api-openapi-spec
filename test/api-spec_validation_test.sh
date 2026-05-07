#!/bin/sh
# Validates openapi.yml using Redocly CLI.
# Requires Node.js. Run from the repository root:
#   sh test/api-spec_validation_test.sh

set -e

SPEC_FILE="openapi.yml"

if [ ! -f "$SPEC_FILE" ]; then
  echo "Error: $SPEC_FILE not found. Run this script from the repository root." >&2
  exit 1
fi

echo "Validating $SPEC_FILE ..."
npx --yes @redocly/cli@latest lint "$SPEC_FILE"
echo "Validation passed."
