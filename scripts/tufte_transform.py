"""Server-side port of static/js/tufte.js for the Zenodo export pipeline.

WeasyPrint doesn't execute JavaScript, and Zenodo's HTML preview can't
fetch site assets like /js/tufte.js (the path is absolute to the live
site). This module mirrors the DOM transforms tufte.js performs at
runtime so the uploaded HTML and the rendered PDF both show real
sidenotes/margin notes instead of raw [note: ...] text and bottom
footnotes.

WARNING — DUPLICATED IMPLEMENTATION. If you change the note markup
conventions (the [note: ...] syntax, footnote handling, class names,
or the sidenote/marginnote span structure), update BOTH
static/js/tufte.js AND this module. They must stay in sync. The
long-term fix is to do the transform once at Hugo build time via a
render hook and drop the JS entirely.
"""

from __future__ import annotations

import re

# Hugo --minify strips quotes from attribute values where HTML5 allows
# (single-token values with no whitespace or special chars). The
# transform's regexes all assume quoted attributes, so re-quote the
# attributes we depend on before matching. Limit to id/href/class so
# we don't touch unrelated attribute values that happen to match the
# unquoted-value character class.
_UNQUOTED_ATTR_RE = re.compile(
    r'\b(id|href|class)=([^\s"\'>=<`]+)',
    re.IGNORECASE,
)


def _normalize_attrs(html: str) -> str:
    return _UNQUOTED_ATTR_RE.sub(r'\1="\2"', html)


# Hugo emits: <sup id="fnref:N"><a href="#fn:N" class="footnote-ref">N</a></sup>
_FNREF_RE = re.compile(
    r'<sup\b[^>]*>\s*<a\b[^>]*href=["\']#fn:([^"\']+)["\'][^>]*>[^<]*</a>\s*</sup>',
    re.IGNORECASE,
)

# <li id="fn:N">...</li> — the footnote body, used as the sidenote content.
_FN_LI_RE = re.compile(
    r'<li\s+id=["\']fn:([^"\']+)["\'][^>]*>(.*?)</li>',
    re.DOTALL | re.IGNORECASE,
)

# Backref link Hugo appends to each footnote item, with its leading nbsp.
_BACKREF_RE = re.compile(
    r'(?:&#160;|&nbsp;|\s)*<a\b[^>]*class=["\'][^"\']*\bfootnote-backref\b[^"\']*["\'][^>]*>.*?</a>',
    re.IGNORECASE | re.DOTALL,
)

# The whole footnotes section at the bottom of .post-content.
_FOOTNOTES_SECTION_RE = re.compile(
    r'<(section|div)\b[^>]*\bclass=["\'][^"\']*\bfootnotes\b[^"\']*["\'][^>]*>.*?</\1>',
    re.IGNORECASE | re.DOTALL,
)

# Single-paragraph wrapper that Hugo emits around footnote bodies.
_PARA_WRAP_RE = re.compile(
    r'^\s*<p\b[^>]*>(.*?)</p>\s*$',
    re.DOTALL | re.IGNORECASE,
)


def _unwrap_paragraph(html: str) -> str:
    """Strip a sole `<p>...</p>` wrapper from a fragment.

    Hugo emits each footnote body as `<p>...</p>`. Injecting that into a
    `<span class="sidenote">` that sits inside another `<p>` is invalid
    HTML — html5lib (and WeasyPrint's parser) auto-close the outer `<p>`
    when they see the inner one, which tears the surrounding paragraph
    apart in the PDF. tufte.js doesn't hit this because it runs after
    parsing, but a server-side string transform must respect parsing.
    """
    m = _PARA_WRAP_RE.match(html)
    if m:
        return m.group(1).strip()
    return html.strip()

# Anchor for scoping the transform to the article body so we don't
# rewrite [note: ...] strings that appear in <meta name="description">
# or other head-side attributes.
_POST_CONTENT_OPEN = re.compile(
    r'<div\b[^>]*\bclass=["\'][^"\']*\bpost-content\b[^"\']*["\'][^>]*>',
    re.IGNORECASE,
)


def _transform_footnotes(html: str) -> str:
    fn_content: dict[str, str] = {}
    for m in _FN_LI_RE.finditer(html):
        fid = m.group(1)
        body = _BACKREF_RE.sub("", m.group(2))
        body = _unwrap_paragraph(body)
        fn_content[fid] = body

    if not fn_content:
        return html

    def replace_sup(match: re.Match[str]) -> str:
        fid = match.group(1)
        body = fn_content.get(fid)
        if body is None:
            return match.group(0)
        sn_id = f"sn-{fid}"
        return (
            f'<label for="{sn_id}" class="margin-toggle sidenote-number"></label>'
            f'<input type="checkbox" id="{sn_id}" class="margin-toggle"/>'
            f'<span class="sidenote">{body}</span>'
        )

    html = _FNREF_RE.sub(replace_sup, html)
    html = _FOOTNOTES_SECTION_RE.sub("", html)
    return html


def _find_margin_notes(s: str) -> list[tuple[int, int, str]]:
    """Mirror of findMarginNotesInHtml in tufte.js: bracket counting that
    skips over HTML tag content so attributes like href="..." can't
    throw off the depth count."""
    results: list[tuple[int, int, str]] = []
    i = 0
    n = len(s)
    while i < n:
        marker = s.find("[note:", i)
        if marker == -1:
            break
        depth = 1
        j = marker + 6
        while j < n and depth > 0:
            ch = s[j]
            if ch == "<":
                tag_end = s.find(">", j)
                if tag_end != -1:
                    j = tag_end + 1
                    continue
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
            j += 1
        if depth == 0:
            results.append((marker, j, s[marker + 6 : j - 1].strip()))
            i = j
        else:
            i = marker + 6
    return results


def _transform_margin_notes(html: str) -> str:
    notes = _find_margin_notes(html)
    if not notes:
        return html

    parts: list[str] = []
    last = 0
    for idx, (start, end, content) in enumerate(notes, start=1):
        if start > last:
            parts.append(html[last:start])
        nid = f"mn-{idx}"
        parts.append(
            f'<label for="{nid}" class="margin-toggle">&#8853;</label>'
            f'<input type="checkbox" id="{nid}" class="margin-toggle"/>'
            f'<span class="marginnote">{content}</span>'
        )
        last = end
    parts.append(html[last:])
    return "".join(parts)


def transform_tufte_notes(html: str) -> str:
    """Apply the tufte.js DOM transforms server-side.

    Scoped to the suffix that begins at the first `<div class="post-content">`
    so we don't touch [note: ...] strings that bled into <meta> tags in <head>.
    """
    html = _normalize_attrs(html)
    m = _POST_CONTENT_OPEN.search(html)
    if not m:
        return html
    head = html[: m.start()]
    body = html[m.start() :]
    body = _transform_footnotes(body)
    body = _transform_margin_notes(body)
    return head + body
