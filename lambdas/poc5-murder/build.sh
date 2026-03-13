#!/bin/bash
# Build Murder Lambda package with dependencies
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
PACKAGE_DIR="$DIR/package"

rm -rf "$PACKAGE_DIR"
mkdir -p "$PACKAGE_DIR"

pip install -r "$DIR/requirements.txt" -t "$PACKAGE_DIR" --quiet
cp "$DIR/handler.py" "$PACKAGE_DIR/"

echo "Murder Lambda package built at $PACKAGE_DIR"
