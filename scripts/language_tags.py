#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-frontmatter>=1.0",
# ]
# ///
"""Find published pages carrying no language tag, and add one.

Every page should say what language it is in — `en`, `fi` or `id`. Those tags
are real Logseq pages (content/pages/en.md and friends), so a reader can pull
up everything written in one language, and `My digital garden` can promise that
the site is mostly English without the claim being unverifiable.

The report reads content/pages, because that is what actually got published.
The *writes* go to the Logseq graph, because content/pages is mirrored with
`rsync --delete` on every `just import` — a tag added on the Hugo side would
survive until the next sync and no longer. So this edits the source `tags::`
property and leaves you to re-export:

    just language-tags        # report, then offer to fill (Enter = all as en)
    just import               # pull the new tags through to Hugo

Tags live wherever `public:: true` lives — that is the whole rule for finding
the right line, and it covers both shapes a page takes in the graph:

  - A standalone page (`pages/Foo.md`) usually keeps `public::` and `tags::` in
    the unindented pre-block at the top. Not always, though: `Running WordPress
    Locally with WP-CLI` keeps them on its first bullet instead, and a `tags::`
    added to the top of that file would be a second list nothing reads.
  - A page derived from a journal (`journals/2026_08_13.md`) is really one
    public *bullet* inside that journal. Hugo names the file after the date
    ("Aug 13th, 2026") and titles it from the block, so the title is checked
    against the block before anything is written.

Looking for the public block rather than a position in the file handles both,
and means a private sibling block can never be edited by accident.

Pages excluded from the report: `front_page`, and any page that exists to back
a tag (`en`, `fi`, `id`, `meta`) — a tag page is not prose and has no language.

Usage:
    just language-tags                 # report + interactive fill
    just language-tags --lang fi       # same, filling in Finnish
    just language-tag fi "Some page"   # one page, by title
    just language-tags-check           # report only, non-zero exit if any lack one

    uv run scripts/language_tags.py [--check] [--yes] [--lang fi] [--pages ...]

The graph directory is resolved the way logseq-to-markdown resolves it, from
~/.logseq/graphs/*.transit for $LOGSEQ_GRAPH; override with $LOGSEQ_GRAPH_DIR.
That .transit file is also what the *export* reads — it is a dump of Logseq's
database, not the markdown — so edits made here reach Hugo only once Logseq has
noticed them and rewritten its index. See warn_if_index_stale().
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote

import frontmatter

REPO_ROOT = Path(__file__).resolve().parent.parent
PAGES_DIR = REPO_ROOT / "content" / "pages"

LANGUAGES = ("en", "fi", "id")
DEFAULT_LANGUAGE = "en"

# Pages that are infrastructure rather than prose. Tag pages are found by
# title (see tag_backed_titles); front_page is Hugo's, with no Logseq tags.
ALWAYS_SKIP = {"front_page"}

# Same filter as generate_tag_pages.py: Logseq sometimes exports a whole tag
# list as one malformed value, e.g. `#{"virkkaus" "fi"}`.
VALID_TAG = re.compile(r"^[\w][\w &'’/+.-]*$", re.UNICODE)

# Logseq's default journal page title, e.g. "Aug 13th, 2026" -> 2026_08_13.
JOURNAL_TITLE = re.compile(r"^([A-Z][a-z]{2}) (\d{1,2})(?:st|nd|rd|th), (\d{4})$")
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# logseq-to-markdown strips these from filenames (fs/->filename), which is why
# `… computer – misc notes` is published as `… computer  misc notes`.
EXPORT_STRIPPED = re.compile(
    r"([✀-➿]|[-]|[\U0001F000-\U0001FFFF]|[‑-⛿])"
)

# A property line: `tags:: a, b` at top level, or indented under a journal block.
PROPERTY = re.compile(r"^(\s*)([\w][\w-]*):: ?(.*)$")
BLOCK = re.compile(r"^(\s*)- (.*)$")


# --- reading the published side ---------------------------------------------

def page_tags(post) -> list[str]:
    return [
        t.strip()
        for t in (post.get("tags") or [])
        if isinstance(t, str) and t.strip() and VALID_TAG.match(t.strip())
    ]


def tag_backed_titles(pages: dict[Path, frontmatter.Post]) -> set[str]:
    """Titles of pages that exist to carry a tag (en, fi, id, meta, …).

    Same rule generate_tag_pages.py uses to decide a tag needs no stub: some
    page's title *is* the tag. Such a page is a heading for other pages, so
    asking it what language it is in is a category error.
    """
    used = {t.lower() for post in pages.values() for t in page_tags(post)}
    return {
        str(post.get("title") or path.stem)
        for path, post in pages.items()
        if str(post.get("title") or path.stem).lower() in used
    }


def survey() -> tuple[list[tuple[Path, str]], int]:
    """Published pages with no language tag, as (path, title); plus a total."""
    pages = {path: frontmatter.load(path) for path in sorted(PAGES_DIR.glob("*.md"))}
    skip = tag_backed_titles(pages) | ALWAYS_SKIP

    missing, considered = [], 0
    for path, post in pages.items():
        title = str(post.get("title") or path.stem)
        if title in skip or path.stem in skip:
            continue
        considered += 1
        if not any(t.lower() in LANGUAGES for t in page_tags(post)):
            missing.append((path, title))
    return missing, considered


# --- locating the source in the Logseq graph --------------------------------

def graph_dir() -> tuple[Path, Path | None]:
    """The Logseq graph directory and its index, resolved as the exporter does.

    Returns (graph directory, .transit index) — the index is None only when
    LOGSEQ_GRAPH_DIR names a directory directly, as the tests and a bare
    checkout do.
    """
    graph = os.environ.get("LOGSEQ_GRAPH", "hw-logseq")
    graphs = Path.home() / ".logseq" / "graphs"
    transits = sorted(graphs.glob("*.transit")) if graphs.is_dir() else []

    if override := os.environ.get("LOGSEQ_GRAPH_DIR"):
        root = Path(override).expanduser()
    else:
        for transit in transits:
            # logseq_local_++home++u++git++hw-logseq.transit -> /home/u/git/hw-logseq
            path = transit.stem.replace("logseq_local_", "", 1).replace("++", "/")
            if Path(path).name == graph:
                return Path(path), transit
        sys.exit(
            f"error: no graph named {graph!r} under {graphs}\n"
            f"       set LOGSEQ_GRAPH_DIR to point at it directly"
        )

    for transit in transits:
        path = transit.stem.replace("logseq_local_", "", 1).replace("++", "/")
        if Path(path) == root:
            return root, transit
    return root, None


def warn_if_index_stale(transit: Path | None, edited: list[Path]) -> None:
    """Say so when Logseq's index predates the edits just made.

    logseq-to-markdown exports from `~/.logseq/graphs/*.transit`, a dump of
    Logseq's own database — never from the markdown. Editing a file on disk
    therefore does not reach Hugo until Logseq notices the change and rewrites
    that index, which it does while running. Without this check `just import`
    would quietly export the old tags and look like this script had failed.
    """
    if transit is None or not edited:
        return
    if transit.stat().st_mtime >= max(p.stat().st_mtime for p in edited):
        return
    print(
        f"\nnote: {transit.name} is older than these edits.\n"
        f"      Logseq exports from that index, not from the files — open the\n"
        f"      graph in Logseq so it picks the changes up before `just import`."
    )


def journal_file(root: Path, title: str) -> Path | None:
    if not (m := JOURNAL_TITLE.match(title)):
        return None
    month, day, year = m.group(1), int(m.group(2)), m.group(3)
    if month not in MONTHS:
        return None
    path = root / "journals" / f"{year}_{MONTHS.index(month) + 1:02d}_{day:02d}.md"
    return path if path.exists() else None


def page_file(root: Path, stem: str) -> Path | None:
    """The graph file whose page is published under `stem`.

    Hugo's filename comes from the Logseq page name with a range of symbols
    dropped, and Logseq percent-encodes characters it cannot put in a filename
    (`:` becomes `%3A`), so neither side matches the other verbatim.
    """
    direct = root / "pages" / f"{stem}.md"
    if direct.exists():
        return direct
    for candidate in sorted((root / "pages").glob("*.md")):
        if EXPORT_STRIPPED.sub("", unquote(candidate.stem)) == stem:
            return candidate
    return None


# --- writing the tag ---------------------------------------------------------

def property_regions(lines: list[str]):
    """Yield (start, end, indent, block_text) for every property block in a file.

    Two shapes carry properties. A standalone page opens with an unindented
    pre-block (`public:: true`, `tags:: …`) above any bullet. Every bullet may
    then carry its own, indented two spaces past the bullet. Both are yielded
    in document order; `block_text` is None for the pre-block.
    """
    end = 0
    while end < len(lines) and (m := PROPERTY.match(lines[end])) and not m.group(1):
        end += 1
    if end:
        yield 0, end, "", None

    for i, line in enumerate(lines):
        if not (m := BLOCK.match(line)):
            continue
        indent = m.group(1)
        end = i + 1
        while end < len(lines):
            p = PROPERTY.match(lines[end])
            if not p or not p.group(1).startswith(indent) or p.group(1) == indent:
                break
            end += 1
        yield i + 1, end, indent + "  ", m.group(2)


def is_public(lines: list[str], start: int, end: int) -> bool:
    """Does this property block mark its page or block public?

    Spelling varies in the graph — `public:: true` and `Public::  true` both
    occur — so the name is matched case-insensitively and the value stripped.
    """
    for i in range(start, end):
        if (m := PROPERTY.match(lines[i])) and m.group(2).lower() == "public":
            return m.group(3).strip().lower() == "true"
    return False


def add_language(lines: list[str], start: int, end: int,
                 indent: str, language: str) -> bool:
    """Add `language` to this block's `tags::`, or give it one. False if present."""
    for i in range(start, end):
        if (m := PROPERTY.match(lines[i])) and m.group(2).lower() == "tags":
            existing = [t.strip() for t in m.group(3).split(",") if t.strip()]
            if language in (t.lower() for t in existing):
                return False
            lines[i] = f"{indent}tags:: {', '.join(existing + [language])}"
            return True
    lines.insert(end, f"{indent}tags:: {language}")
    return True


def looks_like(text: str, title: str) -> bool:
    """Is `title` plausibly the title the exporter derived from `text`?

    Only a sanity check, not a reimplementation of `derive-title`: the exporter
    strips markup, drops trailing tags and cuts at 70 characters, so the title
    survives as a prefix of the block once links are reduced to their labels.
    """
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[\[\]*=`]", "", text)
    text = re.sub(r"\s+", " ", text).strip().casefold()
    return text.startswith(title.rstrip("…").strip().casefold())


def tag_source(path: Path, language: str, expect_title: str | None = None) -> bool | None:
    """Add the language tag where this page's other tags live.

    Tags belong to whatever Logseq treats as the page: the property block that
    carries `public:: true`. For a standalone page that is usually the pre-block
    at the top, but not always — `Running WordPress Locally with WP-CLI` keeps
    `public::` and `tags::` on its first bullet, and a second `tags::` in the
    pre-block would not be the list the exporter reads. Finding the public block
    instead of assuming a position handles both, and journals for free.

    Returns True if written, False if the tag was already there, None if no
    public block was found or it does not match `expect_title`.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    for start, end, indent, block_text in property_regions(lines):
        if not is_public(lines, start, end):
            continue
        if expect_title is not None and block_text is not None:
            if not looks_like(block_text, expect_title):
                return None
        if not add_language(lines, start, end, indent, language):
            return False
        path.write_text(
            "\n".join(lines) + ("\n" if text.endswith("\n") else ""),
            encoding="utf-8",
        )
        return True
    return None


def apply(root: Path, path: Path, title: str,
          language: str) -> tuple[str, Path | None]:
    """Add the tag at the source. Returns (status line, file written or None)."""
    # A journal-derived page is named for the date and titled from its first
    # public block, so the title is worth checking before writing. A standalone
    # page is named for itself and its title says nothing about which block.
    if journal := journal_file(root, path.stem):
        source, expect = journal, title
    elif page := page_file(root, path.stem):
        source, expect = page, None
    else:
        return f"! no source in the graph for {path.stem!r} — page or journal?", None

    where = source.relative_to(root)
    result = tag_source(source, language, expect)
    if result is None:
        return f"! {where}: no public block matching {title!r} — tag it in Logseq", None
    if result is False:
        return f"! {where} already carries {language}", None
    return f"{where}" + (f" ({title})" if expect else ""), source


# --- driver ------------------------------------------------------------------

def choose(missing: list[tuple[Path, str]], language: str) -> list[int]:
    """Ask what to tag. Enter takes everything, which is the usual answer."""
    prompt = (
        f"\ntag all {len(missing)} as #{language}? "
        f"[Enter=all / numbers e.g. 1 3 / n=cancel] "
    )
    try:
        answer = input(prompt).strip()
    except EOFError:
        return []
    if answer.lower() in {"n", "no", "q"}:
        return []
    if not answer:
        return list(range(len(missing)))

    picked = []
    for token in answer.replace(",", " ").split():
        if not token.isdigit() or not 1 <= int(token) <= len(missing):
            print(f"not a listed number: {token}", file=sys.stderr)
            return []
        picked.append(int(token) - 1)
    return picked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="report only, exit non-zero if any page lacks a "
                             "language tag; never prompts and never writes")
    parser.add_argument("--lang", default=DEFAULT_LANGUAGE, choices=LANGUAGES,
                        help=f"language to add (default: {DEFAULT_LANGUAGE})")
    parser.add_argument("--yes", action="store_true",
                        help="tag every listed page without asking")
    parser.add_argument("--pages", nargs="+", metavar="TITLE",
                        help="tag only these pages, by title; implies --yes")
    args = parser.parse_args()

    if not PAGES_DIR.is_dir():
        print(f"error: {PAGES_DIR} not found", file=sys.stderr)
        return 1

    missing, considered = survey()
    tagged = considered - len(missing)

    if not missing:
        print(f"language tags: all {considered} pages carry one")
        return 0

    print(f"language tags: {len(missing)} of {considered} pages have none "
          f"({tagged} tagged)\n")
    for n, (path, title) in enumerate(missing, 1):
        print(f"  {n:2}. {title}")
        if title != path.stem:
            print(f"      {path.stem}")

    if args.check:
        print(f"\nrun `just language-tags` to fill these in")
        return 1

    if args.pages:
        wanted = {p.lower() for p in args.pages}
        picked = [i for i, (_, t) in enumerate(missing) if t.lower() in wanted]
        if unknown := wanted - {missing[i][1].lower() for i in picked}:
            print(f"error: not listed above: {', '.join(sorted(unknown))}",
                  file=sys.stderr)
            return 1
    elif args.yes:
        picked = list(range(len(missing)))
    else:
        picked = choose(missing, args.lang)

    if not picked:
        print("nothing tagged")
        return 0

    root, transit = graph_dir()
    print(f"\nediting {root}")
    edited, failures = [], 0
    for i in picked:
        path, title = missing[i]
        status, written = apply(root, path, title, args.lang)
        failures += status.startswith("!")
        if written:
            edited.append(written)
        print(f"  {status}")

    print(f"\nadded #{args.lang} to {len(edited)} page(s)")
    if edited:
        print("run `just import` to pull the new tags through to Hugo")
        warn_if_index_stale(transit, edited)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
