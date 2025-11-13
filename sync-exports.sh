#!/bin/bash

# Sync exported pages from logseq-to-markdown and update tag descriptions
# Usage: ./sync-exports.sh [path-to-logseq-to-markdown-export]
#
# Default expects logseq-to-markdown to be a sibling directory:
#   ~/git/logseq-to-markdown/my-export
#   ~/git/adhocism/

EXPORT_DIR="${1:-$HOME/git/logseq-to-markdown/my-export}"
TAG_DESC_DIR="./content/tag-descriptions"
PAGES_DIR="$EXPORT_DIR/pages"

if [ ! -d "$PAGES_DIR" ]; then
    echo "Error: Export directory not found: $PAGES_DIR"
    echo "Usage: ./sync-exports.sh [path-to-logseq-to-markdown-export]"
    exit 1
fi

echo "Syncing from: $EXPORT_DIR"
echo "Tag descriptions: $TAG_DESC_DIR"

# Ensure tag-descriptions directory exists
mkdir -p "$TAG_DESC_DIR"

# List of pages that should become tag descriptions
# These are pages where the title matches a tag name
TAG_PAGES=("meta" "en" "fi" "id" "digital-garden")

synced=0
for tag in "${TAG_PAGES[@]}"; do
    # Find the markdown file (handles "digital garden" vs "digital-garden")
    # Convert slug to filename: digital-garden -> "digital garden"
    search_term=$(echo "$tag" | tr '-' ' ')
    filename=$(ls "$PAGES_DIR" | grep -i "^${search_term}\\.md$" | head -1 || true)

    if [ -z "$filename" ]; then
        echo "  ○ $tag - No matching exported page found"
        continue
    fi

    source_file="$PAGES_DIR/$filename"
    slug=$(echo "$tag" | tr '_' '-')
    target_file="$TAG_DESC_DIR/$slug.md"

    # Extract content (everything after frontmatter)
    # Using sed to skip the first --- and second --- (frontmatter markers)
    content=$(sed '1,/^---$/d; /^---$/d' "$source_file")

    # Create new file with hidden frontmatter
    cat > "$target_file" << EOF
---
title: $tag
hidden: true
---
$content
EOF

    echo "  ✓ $filename → $slug.md"
    ((synced++))
done

echo ""
echo "Sync complete: $synced tag descriptions updated"
