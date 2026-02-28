#!/bin/bash

# Sync exported pages from logseq-to-markdown to Hugo content
# Usage: ./sync-exports.sh [path-to-logseq-to-markdown-export]
#
# Default expects logseq-to-markdown to be a sibling directory:
#   ~/git/logseq-to-markdown/my-export
#   ~/git/adhocism/
#
# This script:
# 1. Copies all pages from export to content/pages/
# 2. Copies all assets from export to static/logseq-assets/

EXPORT_DIR="${1:-$HOME/git/logseq-to-markdown/my-export}"
PAGES_DIR="$EXPORT_DIR/pages"
ASSETS_DIR="$EXPORT_DIR/assets"
CONTENT_PAGES_DIR="./content/pages"
STATIC_ASSETS_DIR="./static/logseq-assets"

if [ ! -d "$PAGES_DIR" ]; then
    echo "Error: Export directory not found: $PAGES_DIR"
    echo "Usage: ./sync-exports.sh [path-to-logseq-to-markdown-export]"
    exit 1
fi

echo "Syncing from: $EXPORT_DIR"
echo ""

# Copy pages
echo "Copying pages to $CONTENT_PAGES_DIR..."
mkdir -p "$CONTENT_PAGES_DIR"
cp -v "$PAGES_DIR"/*.md "$CONTENT_PAGES_DIR/" 2>&1 | sed 's/^/  /'
echo ""

# Copy assets if they exist
if [ -d "$ASSETS_DIR" ]; then
    echo "Copying assets to $STATIC_ASSETS_DIR..."
    mkdir -p "$STATIC_ASSETS_DIR"
    cp -rv "$ASSETS_DIR"/* "$STATIC_ASSETS_DIR/" 2>&1 | sed 's/^/  /'
    echo ""
fi

echo "Sync complete."
