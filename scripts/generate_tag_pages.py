#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-frontmatter>=1.0",
# ]
# ///
"""Generate a Hugo page for every tag used in content/pages.

In Logseq a tag *is* a page: it can carry prose, and everything referencing it
shows up underneath as linked references. This script gives every tag that
behaviour on the Hugo side.

Resolution rule (mirrored by layouts/partials/post_tags.html):

  - If a real Logseq page with the tag's title already exists in content/pages,
    nothing is generated — the tag pill links to that page, prose and all.
  - Otherwise a stub is written to content/tags/, which single.html renders as
    an empty page plus its "Linked references" list.

content/tags/ is owned entirely by this script: stubs that are no longer needed
(tag fell out of use, or a real Logseq page now covers it) are deleted. That is
also why the stubs do not live in content/pages — sync-exports.sh mirrors the
Logseq export into that directory with `rsync --delete`.

Tag pages sit outside `mainSections`, so they stay off the front page, the
archive and the RSS feed without needing a `hidden` flag.

Run via the sync step:
    ./sync-exports.sh            # calls this automatically
    uv run scripts/generate_tag_pages.py [--check]
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

import frontmatter

REPO_ROOT = Path(__file__).resolve().parent.parent
PAGES_DIR = REPO_ROOT / "content" / "pages"
TAGS_DIR = REPO_ROOT / "content" / "tags"

# Logseq occasionally exports a malformed tag list as a single blob, e.g.
#   - #{"virkkaus" "fi"}
# Anything that is not a plain word/phrase is dropped rather than turned into a
# page with an unusable URL.
VALID_TAG = re.compile(r"^[\w][\w &'’/+.-]*$", re.UNICODE)

STUB_TEMPLATE = """---
title: "{title}"
searchHidden: true
generated: true
---
"""


def slugify(value: str) -> str:
    """Approximate Hugo's urlize, enough to keep generated filenames stable."""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[\s_-]+", "-", value).strip("-")


def collect_tags(pages_dir: Path) -> dict[str, str]:
    """Map slug -> display title for every usable tag in the exported pages.

    Tags differing only in case (LLMDEV / llmdev) collapse onto one slug, so
    they would otherwise fight over the same URL. First spelling seen wins.
    """
    tags: dict[str, str] = {}
    for path in sorted(pages_dir.glob("*.md")):
        post = frontmatter.load(path)
        for tag in post.get("tags") or []:
            if not isinstance(tag, str):
                continue
            tag = tag.strip()
            if not tag or not VALID_TAG.match(tag):
                continue
            slug = slugify(tag)
            if slug:
                tags.setdefault(slug, tag)
    return tags


def existing_page_slugs(pages_dir: Path) -> set[str]:
    """Slugs of real Logseq pages, by title — these need no stub."""
    slugs = set()
    for path in sorted(pages_dir.glob("*.md")):
        post = frontmatter.load(path)
        title = post.get("title") or path.stem
        slugs.add(slugify(str(title)))
    return slugs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report what would change and exit non-zero if anything would, "
        "without writing",
    )
    args = parser.parse_args()

    if not PAGES_DIR.is_dir():
        print(f"error: {PAGES_DIR} not found", file=sys.stderr)
        return 1

    tags = collect_tags(PAGES_DIR)
    covered = existing_page_slugs(PAGES_DIR)

    wanted = {slug: title for slug, title in tags.items() if slug not in covered}
    skipped = sorted(slug for slug in tags if slug in covered)

    TAGS_DIR.mkdir(parents=True, exist_ok=True)
    # `_index.md` is the hand-written section page for /tags/, not a stub.
    current = {
        p.stem: p for p in TAGS_DIR.glob("*.md") if not p.name.startswith("_")
    }

    created, updated, removed = [], [], []

    for slug, title in sorted(wanted.items()):
        target = TAGS_DIR / f"{slug}.md"
        content = STUB_TEMPLATE.format(title=title.replace('"', '\\"'))
        if not target.exists():
            created.append(slug)
        elif target.read_text(encoding="utf-8") != content:
            updated.append(slug)
        else:
            continue
        if not args.check:
            target.write_text(content, encoding="utf-8")

    for slug, path in sorted(current.items()):
        if slug in wanted:
            continue
        removed.append(slug)
        if not args.check:
            path.unlink()

    print(
        f"tag pages: {len(wanted)} generated, {len(skipped)} backed by a Logseq page"
    )
    for label, items in (("created", created), ("updated", updated), ("removed", removed)):
        if items:
            print(f"  {label}: {', '.join(items)}")
    if skipped:
        print(f"  linked to content/pages: {', '.join(skipped)}")

    if args.check and (created or updated or removed):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
