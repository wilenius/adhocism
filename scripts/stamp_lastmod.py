#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# ///
"""Set each page's `lastMod:` to the day its published body last changed.

The exporter takes `lastMod:` from Logseq's own `updated-at`, which lives only
in Logseq's database: a graph re-index resets it for every page at once, and a
`lastMod::` property that pins it has to be kept up to date by hand. This
repo's git history is a record that survives both. A page's body is everything
below its front matter, so tags, dates and exporter quirks never count as an
edit; edits to private blocks never reach the export in the first place.

For each file in content/pages, find the earliest commit, on either side of
any publish merge, in which the page had its current body: that is when the
body took its current form. A page whose body matches
no commit, because it is new, renamed or edited in this import, gets today's
date. A page unchanged since the export pipeline arrived here (2025-11-13) keeps an
earlier date when one is known: the committed one, then the exporter's.

Runs from sync-exports.sh after the rsync, which rewrites the front matter on
every import. `--check` reports pages whose `lastMod:` would change, without
writing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

PAGES_DIR = Path("content/pages")
LASTMOD_RE = re.compile(r"^lastMod:.*$", re.MULTILINE | re.IGNORECASE)
DATE_RE = re.compile(r"^date:.*$", re.MULTILINE)


def split_front_matter(text: str) -> tuple[str, str]:
    """(front matter including its fences, body). No front matter → ("", text)."""
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---\n", 4)
    if end == -1:
        return "", text
    return text[: end + 5], text[end + 5 :]


def normalise(body: str) -> str:
    return "\n".join(line.rstrip() for line in body.strip().splitlines())


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True
    ).stdout


class History:
    """Every state of each page in content/pages, from both sides of every
    publish merge. Pages are published from more than one machine, so a page
    often first appears on a side branch and reaches main days later in a
    merge; walking main's first-parent line alone would date it by the merge.
    Per-file `git log` is no good either: history simplification hides commits
    that a merge later undid, and --follow misses some outright."""

    def __init__(self) -> None:
        # name -> [(date, blob)], one entry per commit that changed the page,
        # merges diffed against their first parent so a merge that brings a
        # side branch's version in counts too.
        self.states: dict[str, list[tuple[str, str]]] = {}
        out = git(
            "log", "--full-history", "--diff-merges=first-parent", "--raw",
            "--no-abbrev", "-z", "--format=%x01%cs", "HEAD", "--", f"{PAGES_DIR}/",
        )
        for chunk in out.split("\x01")[1:]:
            fields = chunk.split("\0")
            date = fields[0].strip()
            # --raw -z: ":<modes> <old> <new> <status>" then the path(s)
            i = 1
            while i < len(fields):
                f = fields[i].strip()
                if not f.startswith(":"):
                    i += 1
                    continue
                meta = f.split()
                status, new_blob = meta[4], meta[3]
                paths = 2 if status[0] in "RC" else 1
                path = fields[i + paths]
                if status[0] != "D":
                    self.states.setdefault(Path(path).name, []).append((date, new_blob))
                i += 1 + paths
        self._bodies: dict[str, str] = {}

    def body(self, blob: str) -> str:
        if blob not in self._bodies:
            self._bodies[blob] = normalise(split_front_matter(git("cat-file", "blob", blob))[1])
        return self._bodies[blob]

    @property
    def start(self) -> str:
        """The day the Logseq export pipeline arrived in this repo (the first
        commit of sync-exports.sh). Pages synced that day may have been edited
        in Logseq any time before it; git knows nothing earlier."""
        added = git("log", "--diff-filter=A", "--format=%cs", "HEAD", "--", "sync-exports.sh")
        return added.split()[-1]

    def body_since(self, name: str, current_body: str) -> str | None:
        """Date of the earliest commit, on any branch, in which the page had
        its current body. None when the current body was never committed."""
        current = normalise(current_body)
        matching = [d for d, blob in self.states.get(name, []) if self.body(blob) == current]
        return min(matching) if matching else None


def committed_lastmod(path: Path) -> str | None:
    try:
        return current_lastmod(split_front_matter(git("show", f"HEAD:{path}"))[0])
    except subprocess.CalledProcessError:
        return None


ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def current_lastmod(front: str) -> str | None:
    m = LASTMOD_RE.search(front)
    iso = ISO_RE.search(m.group(0)) if m else None
    return iso.group(0) if iso else None


def stamp(front: str, date: str) -> str:
    """Front matter with exactly one `lastMod: date` line, placed where the
    first one was, or after `date:`. Any further `lastmod:` key — the old
    exporter's unparseable `lastmod: #{...}` — is dropped."""
    lines = front.split("\n")
    at = next((i for i, l in enumerate(lines) if LASTMOD_RE.match(l)), None)
    if at is None:
        at = next((i + 1 for i, l in enumerate(lines) if DATE_RE.match(l)), 1)
    kept = [l for i, l in enumerate(lines) if not LASTMOD_RE.match(l) or i == at]
    if at < len(lines) and LASTMOD_RE.match(lines[at]):
        kept[kept.index(lines[at])] = f"lastMod: {date}"
    else:
        kept.insert(at, f"lastMod: {date}")
    return "\n".join(kept)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report only")
    args = parser.parse_args()

    today = dt.date.today().isoformat()
    hist = History()
    start = hist.start
    changed = 0
    for path in sorted(PAGES_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        front, body = split_front_matter(text)
        if not front:
            continue
        since = hist.body_since(path.name, body)
        if since is None:
            date = today
        elif since <= start:
            # Unchanged since before this repo's history begins, so git only
            # says "no later than". Keep an earlier date if one is known:
            # first the one already committed, which a graph re-index cannot
            # touch, then the exporter's (a hand-pinned lastMod:: property).
            known = [d for d in (committed_lastmod(path), current_lastmod(front)) if d]
            date = min([since, *known])
        else:
            date = since
        new_front = stamp(front, date)
        if new_front == front:
            continue
        changed += 1
        old_value = current_lastmod(front) or "—"
        print(f"{old_value:>12} -> {date}  {path.name}")
        if not args.check:
            path.write_text(new_front + body, encoding="utf-8")

    print(f"{changed} page(s) {'would change' if args.check else 'updated'}.")
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    sys.exit(main())
