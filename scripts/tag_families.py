#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-frontmatter>=1.0",
#   "ruamel.yaml>=0.18",
# ]
# ///
"""Maintain the tag -> family mapping in data/tag_families.yml.

A tag pill's colour comes from its family, not from the tag itself. That is a
deliberate limit: colour can only carry a handful of distinctions before it
stops being readable, so it groups tags rather than naming them. The mapping is
a plain data file — there is no inference here, and none is wanted. This script
only reports what is unfiled and writes what you tell it to.

Hugo reads data/tag_families.yml directly (site.Data.tag_families); the
inversion to tag -> family happens in layouts/partials/tag_family.html.

A tag belongs to exactly one family, because it gets exactly one colour. Words
that straddle two fields (`evaluation`, `frontier`) are settled by the company
they keep — the families of the other tags they appear alongside — which
`--why` reports and you decide. A tag filed twice is an error, not a coin flip.

Usage:
    just tag-families                  # families + anything unassigned
    just tag-why frontier              # evidence for where an ambiguous tag goes
    just tag-family ai LLMops          # file one or more tags under a family
    just tag-families-check            # non-zero exit if anything is unassigned

    uv run scripts/tag_families.py [--check]
    uv run scripts/tag_families.py --why TAG
    uv run scripts/tag_families.py --assign FAMILY TAG [TAG ...]
    uv run scripts/tag_families.py --prune

Comments and key order in the YAML survive edits (round-trip loader), so the
file stays hand-editable — which is usually the faster way to move several tags
at once.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import frontmatter
from ruamel.yaml import YAML

REPO_ROOT = Path(__file__).resolve().parent.parent
PAGES_DIR = REPO_ROOT / "content" / "pages"
FAMILIES_FILE = REPO_ROOT / "data" / "tag_families.yml"
TAGS_CSS = REPO_ROOT / "assets" / "css" / "extended" / "30-tags.css"

# Same filter as generate_tag_pages.py and post_tags.html: Logseq sometimes
# exports a whole tag list as one malformed value, e.g. `#{"virkkaus" "fi"}`.
VALID_TAG = re.compile(r"^[\w][\w &'’/+.-]*$", re.UNICODE)

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)


def used_tags(pages_dir: Path) -> dict[str, str]:
    """Map lowercased tag -> display spelling, across content/pages."""
    tags: dict[str, str] = {}
    for path in sorted(pages_dir.glob("*.md")):
        for tag in frontmatter.load(path).get("tags") or []:
            if not isinstance(tag, str):
                continue
            tag = tag.strip()
            if tag and VALID_TAG.match(tag):
                tags.setdefault(tag.lower(), tag)
    return tags


def load_families():
    if not FAMILIES_FILE.exists():
        sys.exit(f"error: {FAMILIES_FILE} not found")
    data = yaml.load(FAMILIES_FILE.read_text(encoding="utf-8")) or {}
    if "families" not in data:
        sys.exit(f"error: {FAMILIES_FILE} has no top-level 'families' key")
    return data


def assigned_map(data) -> tuple[dict[str, str], dict[str, list[str]]]:
    """tag (lowercased) -> family, plus any tag filed under more than one.

    One tag gets one family because it gets one colour: a pill split between two
    colours reads as a third colour belonging to neither, which is exactly the
    overload the family scheme exists to avoid. So a tag filed twice is an error
    to resolve, not something to silently pick a winner for — `--why` shows the
    evidence for choosing.
    """
    out: dict[str, str] = {}
    dupes: dict[str, list[str]] = {}
    for family, spec in (data["families"] or {}).items():
        for tag in (spec or {}).get("tags") or []:
            key = str(tag).strip().lower()
            if key in out:
                dupes.setdefault(key, [out[key]]).append(family)
                continue
            out[key] = family
    return out, dupes


def report_dupes(dupes: dict[str, list[str]]) -> None:
    for tag, families in sorted(dupes.items()):
        print(
            f"error: '{tag}' is filed under {' and '.join(sorted(families))} — "
            f"a tag gets exactly one family.\n"
            f"       `just tag-why {tag}` shows which one the content supports.",
            file=sys.stderr,
        )


def styled_families() -> set[str]:
    """Family names that actually have a colour rule in the CSS."""
    if not TAGS_CSS.exists():
        return set()
    return set(re.findall(r"\.tag-family-([\w-]+)", TAGS_CSS.read_text(encoding="utf-8")))


def why(data, tag: str, pages_dir: Path) -> int:
    """Show the company a tag keeps, to settle which family it belongs in.

    Words like `evaluation` or `frontier` belong to two fields in the abstract —
    but on a given page a tag travels with particular other tags, and those have
    families already. That co-occurrence is the evidence, and it is the thing to
    decide on: `frontier` alongside anthropology/economy is the historical sense,
    not frontier models.

    Deliberately advisory. It counts and prints; it never assigns. If the tag
    pulls hard in two directions across different pages, that is the signal it is
    really two tags, and no colour can paper over it.
    """
    assigned, _ = assigned_map(data)
    key = tag.strip().lower()
    hits, tally = [], {}

    for path in sorted(pages_dir.glob("*.md")):
        post = frontmatter.load(path)
        page_tags = [
            t.strip()
            for t in post.get("tags") or []
            if isinstance(t, str) and t.strip()
        ]
        if key not in {t.lower() for t in page_tags}:
            continue
        others = [t for t in page_tags if t.lower() != key]
        hits.append((str(post.get("title") or path.stem), others))
        for other in others:
            fam = assigned.get(other.lower())
            if fam:
                tally[fam] = tally.get(fam, 0) + 1

    if not hits:
        print(f"  '{tag}' is not used by any page in content/pages.")
        return 1

    current = assigned.get(key)
    print(f"\n  {tag} — filed under: {current or 'nothing yet'}")
    for title, others in hits:
        print(f"\n    {title}")
        for other in sorted(others, key=str.lower):
            fam = assigned.get(other.lower()) or "unassigned"
            print(f"        {other:28} {fam}")

    if tally:
        print("\n  Company kept, by family:")
        for fam, n in sorted(tally.items(), key=lambda kv: (-kv[1], kv[0])):
            mark = "  <- currently filed here" if fam == current else ""
            print(f"      {fam:14} {n}{mark}")
        best = max(tally.items(), key=lambda kv: (kv[1], kv[0]))[0]
        if current and best != current and tally[best] > tally.get(current, 0):
            print(
                f"\n  The content leans '{best}', not '{current}'. Your call —"
                f"\n  `just tag-family {best} {tag}` moves it."
            )
    else:
        print("\n  Its co-tags have no families yet — file those first.")
    return 0


def report(data, tags: dict[str, str]) -> int:
    assigned, dupes = assigned_map(data)
    report_dupes(dupes)
    styled = styled_families()

    for family, spec in (data["families"] or {}).items():
        listed = [str(t) for t in (spec or {}).get("tags") or []]
        in_use = [t for t in listed if t.lower() in tags]
        stale = [t for t in listed if t.lower() not in tags]
        label = (spec or {}).get("label", family)
        note = "" if family in styled or not styled else "   [no CSS rule!]"
        print(f"\n  {label} ({family}) — {len(in_use)} in use{note}")
        for t in sorted(in_use, key=str.lower):
            print(f"      {t}")
        for t in sorted(stale, key=str.lower):
            print(f"      {t}  (unused — `--prune` drops it)")

    unassigned = sorted(
        (tags[k] for k in tags if k not in assigned), key=str.lower
    )
    if unassigned:
        print(f"\n  UNASSIGNED — {len(unassigned)} tag(s), rendering neutral:")
        for t in unassigned:
            print(f"      {t}")
        print("\n  File them with:  just tag-family FAMILY TAG [TAG ...]")
    else:
        print(f"\n  All {len(tags)} tags in use are assigned.")
    return 1 if (unassigned or dupes) else 0


def assign(data, family: str, new_tags: list[str], tags: dict[str, str]) -> int:
    families = data["families"]
    if family not in families:
        known = ", ".join(families)
        sys.exit(
            f"error: no family '{family}'. Known families: {known}\n"
            f"Add a new one to {FAMILIES_FILE.name} by hand — it also needs a "
            f".tag-family-{family} rule in {TAGS_CSS.name}."
        )

    assigned, dupes = assigned_map(data)
    if dupes:
        report_dupes(dupes)
        sys.exit("refusing to write while a tag is filed twice — resolve that first")

    spec = families[family]
    if spec.get("tags") is None:
        spec["tags"] = []
    bucket = spec["tags"]

    for tag in new_tags:
        tag = tag.strip()
        if not tag:
            continue
        key = tag.lower()
        if key in assigned:
            if assigned[key] == family:
                print(f"  already there: {tag}")
            else:
                # Move it: drop from the old family, then add below.
                old = families[assigned[key]]["tags"]
                for i, existing in enumerate(old):
                    if str(existing).lower() == key:
                        del old[i]
                        break
                print(f"  moved: {tag}  ({assigned[key]} -> {family})")
                bucket.append(tags.get(key, tag))
            continue
        if key not in tags:
            print(f"  added: {tag}  (not currently used by any page)")
        else:
            print(f"  added: {tag}")
        bucket.append(tags.get(key, tag))

    bucket.sort(key=str.lower)
    write(data)
    return 0


def prune(data, tags: dict[str, str]) -> int:
    removed = []
    for family, spec in (data["families"] or {}).items():
        bucket = (spec or {}).get("tags") or []
        for i in range(len(bucket) - 1, -1, -1):
            if str(bucket[i]).lower() not in tags:
                removed.append(f"{bucket[i]} (from {family})")
                del bucket[i]
    if removed:
        for r in sorted(removed, key=str.lower):
            print(f"  removed: {r}")
        write(data)
    else:
        print("  nothing to prune — every listed tag is still in use.")
    return 0


def normalise(text: str) -> str:
    """Put blank lines back where they belong.

    ruamel round-trips the header comment fine, but it attaches blank lines to
    whichever list item happened to precede them — so sorting or deleting a tag
    drags the separators into the middle of a `tags:` list. Rather than fight
    that, drop every blank line inside the families block and re-insert exactly
    one before each family key. Output is then identical for identical data,
    which keeps the diffs honest.
    """
    # A bare key at top level (`families:`) or family level (`  scholarship:`);
    # `    tags:` is deeper, and `label: x` has a value, so neither matches.
    # The `[^#]` guard matters: a comment ending in a colon ("# Maintain with:")
    # otherwise looks exactly like a bare key.
    key = re.compile(r"^(?: {2})?[^#\s][^:]*:\s*$")

    out: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if key.match(line) and out:
            at = len(out)
            # A comment above a *family* documents it, so the blank goes above
            # the comment too. The file header is not attached to `families:`
            # that way, so a top-level key just takes the blank directly.
            if line.startswith(" "):
                while at > 0 and out[at - 1].lstrip().startswith("#"):
                    at -= 1
            if at > 0:
                out.insert(at, "")
        out.append(line)
    return "\n".join(out) + "\n"


def write(data) -> None:
    from io import StringIO

    buf = StringIO()
    yaml.dump(data, buf)
    FAMILIES_FILE.write_text(normalise(buf.getvalue()), encoding="utf-8")
    print(f"\nwrote {FAMILIES_FILE.relative_to(REPO_ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if any tag in use has no family",
    )
    parser.add_argument(
        "--assign",
        nargs="+",
        metavar=("FAMILY", "TAG"),
        help="file TAG(s) under FAMILY, moving them out of any current family",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="drop listed tags that no page uses any more",
    )
    parser.add_argument(
        "--why",
        metavar="TAG",
        help="show which families TAG's co-tags belong to, to settle where it "
        "goes; reports only, never assigns",
    )
    args = parser.parse_args()

    if not PAGES_DIR.is_dir():
        sys.exit(f"error: {PAGES_DIR} not found")

    data = load_families()
    tags = used_tags(PAGES_DIR)

    if args.why:
        return why(data, args.why, PAGES_DIR)
    if args.assign:
        if len(args.assign) < 2:
            sys.exit("error: --assign needs a family and at least one tag")
        return assign(data, args.assign[0], args.assign[1:], tags)
    if args.prune:
        return prune(data, tags)

    status = report(data, tags)
    return status if args.check else 0


if __name__ == "__main__":
    sys.exit(main())
