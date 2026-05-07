#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-frontmatter>=1.0",
#   "PyYAML>=6.0",
#   "weasyprint>=62",
# ]
# ///
"""Upload Hugo pages tagged 'DOI' to Zenodo.

Run via uv (deps are declared inline above):
    export ZENODO_SANDBOX_TOKEN=...    # or ZENODO_TOKEN for production
    uv run scripts/zenodo_export.py --sandbox --dry-run

Live run:
    uv run scripts/zenodo_export.py --sandbox

State (concept DOI, version DOI, content hash) is written to:
    data/zenodo-sandbox.yml   (--sandbox, gitignored)
    data/zenodo.yml           (production, committed)

Pages are identified by tag 'DOI' in their frontmatter. The script:
  - creates and publishes a new Zenodo deposition for tagged pages with no
    state entry yet,
  - skips pages whose body hash matches the last published version,
  - with --update, cuts a new Zenodo version for pages whose body changed.

The uploaded artifact is the page's rendered HTML from public/pages/<slug>/.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import frontmatter
import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tufte_transform import transform_tufte_notes  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
PAGES_DIR = REPO_ROOT / "content" / "pages"
PUBLIC_DIR = REPO_ROOT / "public"
DATA_DIR = REPO_ROOT / "data"
PRINT_CSS = REPO_ROOT / "scripts" / "print.css"

DOI_TAG = "DOI"
CREATORS = [{"name": "Wilenius, Heikki", "orcid": "0000-0003-4601-2392"}]
LICENSE = "cc-by-4.0"
UPLOAD_TYPE = "publication"
PUBLICATION_TYPE = "other"
ACCESS_RIGHT = "open"

API_PROD = "https://zenodo.org/api"
API_SANDBOX = "https://sandbox.zenodo.org/api"

# DOI prefixes used by Zenodo for minted records. Sandbox uses 10.5072,
# production uses 10.5281. Both forms are `<prefix>/zenodo.<recid>`.
DOI_PREFIX_PROD = "10.5281"
DOI_PREFIX_SANDBOX = "10.5072"


def api_base(sandbox: bool) -> str:
    return API_SANDBOX if sandbox else API_PROD


def doi_from_recid(recid: int | str, sandbox: bool) -> str:
    prefix = DOI_PREFIX_SANDBOX if sandbox else DOI_PREFIX_PROD
    return f"{prefix}/zenodo.{recid}"


def state_path(sandbox: bool) -> Path:
    return DATA_DIR / ("zenodo-sandbox.yml" if sandbox else "zenodo.yml")


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"pages": {}}
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("pages", {})
    return data


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        yaml.safe_dump(state, f, sort_keys=True, allow_unicode=True)


def slugify(name: str) -> str:
    """Approximate Hugo's default slugification for the public/ output path.

    Hugo keeps underscores; only whitespace becomes a hyphen.
    """
    s = name.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s


def hash_payload(post: frontmatter.Post, body: str) -> str:
    """Hash everything that should trigger a new Zenodo version: body + key metadata.

    Title/abstract/keyword changes are citable too, not just body changes.
    """
    abstract = post.get("abstract")
    payload = {
        "title": str(post.get("title") or ""),
        "abstract": str(abstract).strip() if abstract else "",
        "tags": sorted(t for t in (post.get("tags") or []) if t != DOI_TAG),
        "body": body.strip(),
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


_LINK_TAG_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
_ATTR_RE = re.compile(
    r'''(?P<name>\w+)\s*=\s*(?:"(?P<dq>[^"]*)"|'(?P<sq>[^']*)'|(?P<bare>[^\s>]+))''',
    re.IGNORECASE,
)


def _link_attrs(tag: str) -> dict[str, str]:
    return {
        m.group("name").lower(): m.group("dq") or m.group("sq") or m.group("bare") or ""
        for m in _ATTR_RE.finditer(tag)
    }


def inline_stylesheets(html: str, public_dir: Path) -> str:
    """Replace <link rel=stylesheet href=...> with inline <style> blocks.

    Quick-and-dirty: only handles same-origin paths under public/. External
    URLs and missing files are left untouched.
    """
    def repl(m: re.Match[str]) -> str:
        attrs = _link_attrs(m.group(0))
        rel = attrs.get("rel", "")
        if "stylesheet" not in rel.lower():
            return m.group(0)
        href = attrs.get("href", "").split("?")[0]
        if not href or href.startswith(("http://", "https://", "//")):
            return m.group(0)
        css_path = public_dir / href.lstrip("/")
        if not css_path.exists():
            return m.group(0)
        return f"<style>\n{css_path.read_text(encoding='utf-8')}\n</style>"
    return _LINK_TAG_RE.sub(repl, html)


def safe_filename(title: str, ext: str = "html") -> str:
    """Title as a filename, stripping only characters that break HTTP/filesystems."""
    cleaned = re.sub(r'[/\\:*?"<>|\x00-\x1f]+', "-", title).strip().strip(".")
    return f"{cleaned or 'page'}.{ext}"


def excerpt_from_body(body: str) -> str:
    """First non-empty chunk of the body, with leading markdown header markers stripped."""
    for chunk in re.split(r"\n\s*\n", body.strip()):
        chunk = chunk.strip()
        if not chunk:
            continue
        return re.sub(r"^#+\s*", "", chunk)
    return ""


def to_iso_date(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dt.date, dt.datetime)):
        return value.date().isoformat() if isinstance(value, dt.datetime) else value.isoformat()
    return str(value)


def find_tagged_pages() -> list[tuple[Path, frontmatter.Post]]:
    out = []
    for md in sorted(PAGES_DIR.glob("*.md")):
        post = frontmatter.load(md)
        tags = post.get("tags") or []
        if not isinstance(tags, list):
            continue
        if DOI_TAG not in tags:
            continue
        out.append((md, post))
    return out


def build_metadata(post: frontmatter.Post, body: str, fallback_title: str) -> dict:
    title = post.get("title") or fallback_title
    tags = [t for t in (post.get("tags") or []) if t != DOI_TAG]
    pub_date = to_iso_date(post.get("lastMod") or post.get("date")) or dt.date.today().isoformat()
    abstract = post.get("abstract")
    description = (str(abstract).strip() if abstract else "") or excerpt_from_body(body) or title
    return {
        "title": title,
        "upload_type": UPLOAD_TYPE,
        "publication_type": PUBLICATION_TYPE,
        "publication_date": pub_date,
        "description": description,
        "creators": CREATORS,
        "keywords": tags,
        "license": LICENSE,
        "access_right": ACCESS_RIGHT,
    }


def hugo_build() -> None:
    print("Running `hugo --gc --minify`...")
    subprocess.run(["hugo", "--gc", "--minify"], cwd=REPO_ROOT, check=True)


def html_path_for(page_md: Path) -> Path:
    return PUBLIC_DIR / "pages" / slugify(page_md.stem) / "index.html"


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def zen(method: str, url: str, token: str, **kw) -> dict:
    headers = kw.pop("headers", {})
    headers.update(auth_headers(token))
    r = requests.request(method, url, headers=headers, **kw)
    if not r.ok:
        sys.exit(f"Zenodo {method} {url} -> {r.status_code}: {r.text}")
    if r.status_code == 204 or not r.content:
        return {}
    return r.json()


def create_deposition(base: str, token: str, metadata: dict) -> dict:
    return zen("POST", f"{base}/deposit/depositions", token, json={"metadata": metadata})


def upload_bytes(bucket_url: str, data: bytes, filename: str, token: str) -> None:
    r = requests.put(f"{bucket_url}/{filename}", data=data, headers=auth_headers(token))
    if not r.ok:
        sys.exit(f"Upload failed for {filename}: {r.status_code} {r.text}")


def publish_deposition(base: str, token: str, dep_id: int) -> dict:
    return zen("POST", f"{base}/deposit/depositions/{dep_id}/actions/publish", token)


def new_version(base: str, token: str, dep_id: int) -> dict:
    """Cut a new draft version. Returns the new draft deposition."""
    resp = zen("POST", f"{base}/deposit/depositions/{dep_id}/actions/newversion", token)
    latest_draft_url = resp["links"]["latest_draft"]
    return zen("GET", latest_draft_url, token)


def replace_files(base: str, token: str, dep_id: int) -> None:
    files = zen("GET", f"{base}/deposit/depositions/{dep_id}/files", token)
    for f in files:
        zen("DELETE", f"{base}/deposit/depositions/{dep_id}/files/{f['id']}", token)


def update_metadata(base: str, token: str, dep_id: int, metadata: dict) -> dict:
    return zen("PUT", f"{base}/deposit/depositions/{dep_id}", token,
               json={"metadata": metadata})


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Upload Hugo pages tagged 'DOI' to Zenodo.")
    ap.add_argument("--sandbox", action="store_true",
                    help="Use sandbox.zenodo.org and ZENODO_SANDBOX_TOKEN.")
    ap.add_argument("--update", action="store_true",
                    help="Publish a new version for pages whose body hash changed.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Report planned actions without calling Zenodo or building Hugo.")
    ap.add_argument("--preview-pdf", metavar="STEM",
                    help="Render the PDF for one page (markdown filename stem, e.g. "
                         "'The three maxims of synthesised ethnography') to "
                         "/tmp/<slug>.pdf and exit. No Zenodo calls. Assumes "
                         "`hugo` has already produced public/.")
    ap.add_argument("--preview-html", metavar="STEM",
                    help="Write the upload-ready HTML for one page (transform "
                         "applied, stylesheets inlined) to /tmp/<slug>.html and "
                         "exit. No Zenodo calls. Useful for sanity-checking the "
                         "exact bytes that will be uploaded.")
    return ap.parse_args()


def render_pdf(html_str: str, base_url: Path) -> bytes:
    """Render HTML (with site CSS already inlined) to a print-styled PDF.

    Imported lazily so dry-runs and metadata-only flows don't pay the cost.

    print.css is injected as an inline <style> block (author-origin, last in
    the cascade) rather than passed via weasyprint's stylesheets= argument,
    which loads CSS as user-origin and loses to the site's author CSS at
    equal specificity.
    """
    from weasyprint import HTML

    if PRINT_CSS.exists():
        style_tag = f"<style>\n{PRINT_CSS.read_text(encoding='utf-8')}\n</style>"
        if "</head>" in html_str:
            html_str = html_str.replace("</head>", style_tag + "</head>", 1)
        else:
            html_str = style_tag + html_str

    pdf = HTML(string=html_str, base_url=str(base_url)).write_pdf()
    assert pdf is not None  # only None when target= is passed; we don't.
    return pdf


def render_uploaded_artifacts(html_path: Path) -> tuple[bytes, bytes]:
    """Return (html_bytes, pdf_bytes) for upload to a single Zenodo deposition."""
    if not html_path.exists():
        sys.exit(f"Rendered HTML not found: {html_path}. Did Hugo build correctly?")
    html_str = transform_tufte_notes(html_path.read_text(encoding="utf-8"))
    html_str = inline_stylesheets(html_str, PUBLIC_DIR)
    return html_str.encode("utf-8"), render_pdf(html_str, PUBLIC_DIR)


def preview_pdf(stem: str) -> None:
    md = PAGES_DIR / f"{stem}.md"
    if not md.exists():
        sys.exit(f"No markdown file at {md}")
    html_path = html_path_for(md)
    _, pdf_bytes = render_uploaded_artifacts(html_path)
    out = Path("/tmp") / f"{slugify(stem)}.pdf"
    out.write_bytes(pdf_bytes)
    print(f"Wrote {out} ({len(pdf_bytes):,} bytes)")


def preview_html(stem: str) -> None:
    md = PAGES_DIR / f"{stem}.md"
    if not md.exists():
        sys.exit(f"No markdown file at {md}")
    html_path = html_path_for(md)
    html_bytes, _ = render_uploaded_artifacts(html_path)
    out = Path("/tmp") / f"{slugify(stem)}.html"
    out.write_bytes(html_bytes)
    print(f"Wrote {out} ({len(html_bytes):,} bytes)")


def main() -> None:
    args = parse_args()
    if args.preview_pdf:
        preview_pdf(args.preview_pdf)
        return
    if args.preview_html:
        preview_html(args.preview_html)
        return
    base = api_base(args.sandbox)
    token_env = "ZENODO_SANDBOX_TOKEN" if args.sandbox else "ZENODO_TOKEN"
    token: str = os.environ.get(token_env, "")
    if not args.dry_run and not token:
        sys.exit(f"{token_env} is not set in the environment.")

    sp = state_path(args.sandbox)
    state = load_state(sp)
    pages_state = state["pages"]

    tagged = find_tagged_pages()
    if not tagged:
        print(f"No pages tagged with '{DOI_TAG}'. Nothing to do.")
        return

    plan = []
    for md, post in tagged:
        body = post.content
        h = hash_payload(post, body)
        existing = pages_state.get(md.stem)
        if existing is None:
            plan.append(("create", md, post, body, h))
        elif existing.get("content_hash") == h:
            plan.append(("skip", md, post, body, h))
        elif args.update:
            plan.append(("new_version", md, post, body, h))
        else:
            plan.append(("changed", md, post, body, h))

    for action, md, post, body, h in plan:
        label = f"  {md.name}"
        if action == "skip":
            print(f"[skip]    {label} (unchanged)")
            continue
        if action == "changed":
            print(f"[changed] {label} — body changed, re-run with --update to publish a new version")
            continue
        if args.dry_run:
            print(f"[dry-run] {action:<11} {label}")
            continue

        meta = build_metadata(post, body, fallback_title=md.stem)
        upload_name = safe_filename(meta["title"])
        pdf_upload_name = safe_filename(meta["title"], ext="pdf")
        html_path = html_path_for(md)

        if action == "create":
            print(f"[create]  {label}")
            dep = create_deposition(base, token, meta)
            concept_recid = dep.get("conceptrecid")
            version_recid = dep["id"]
            # Don't trust dep["metadata"]["prereserve_doi"]["doi"] — Zenodo's sandbox
            # API returns the PRODUCTION prefix (10.5281) there even on sandbox, while
            # the actually-minted DOI uses the sandbox prefix (10.5072). The recid is
            # correct, so construct the DOI ourselves.
            concept_doi = doi_from_recid(concept_recid, args.sandbox) if concept_recid else None
            version_doi = doi_from_recid(version_recid, args.sandbox)
            pages_state[md.stem] = {
                "title": meta["title"],
                "concept_recid": str(concept_recid) if concept_recid else None,
                "concept_doi": concept_doi,
                "latest_recid": version_recid,
                "latest_doi": version_doi,
                "content_hash": h,
            }
            save_state(sp, state)
            print(f"          Reserved: {version_doi} (concept: {concept_doi}); rebuilding to embed.")
            hugo_build()
            html_bytes, pdf_bytes = render_uploaded_artifacts(html_path)
            upload_bytes(dep["links"]["bucket"], html_bytes, upload_name, token)
            upload_bytes(dep["links"]["bucket"], pdf_bytes, pdf_upload_name, token)
            published = publish_deposition(base, token, version_recid)
            actual_doi = published.get("doi") or version_doi
            if actual_doi != version_doi:
                print(f"          WARN: minted DOI {actual_doi} differs from reserved {version_doi}")
                pages_state[md.stem]["latest_doi"] = actual_doi
            pages_state[md.stem]["published_at"] = (
                published.get("submitted") or published.get("created")
            )
            save_state(sp, state)
            print(f"          Published: {actual_doi}")
        elif action == "new_version":
            print(f"[update]  {label}")
            prev = pages_state[md.stem]
            draft = new_version(base, token, prev["latest_recid"])
            version_recid = draft["id"]
            # See note in the create branch: don't trust prereserve_doi.doi on sandbox.
            version_doi = doi_from_recid(version_recid, args.sandbox)
            pages_state[md.stem]["title"] = meta["title"]
            pages_state[md.stem]["latest_recid"] = version_recid
            pages_state[md.stem]["latest_doi"] = version_doi
            pages_state[md.stem]["content_hash"] = h
            save_state(sp, state)
            print(f"          Reserved: {version_doi} (concept: {prev.get('concept_doi')}); rebuilding to embed.")
            hugo_build()
            replace_files(base, token, version_recid)
            update_metadata(base, token, version_recid, meta)
            html_bytes, pdf_bytes = render_uploaded_artifacts(html_path)
            upload_bytes(draft["links"]["bucket"], html_bytes, upload_name, token)
            upload_bytes(draft["links"]["bucket"], pdf_bytes, pdf_upload_name, token)
            published = publish_deposition(base, token, version_recid)
            actual_doi = published.get("doi") or version_doi
            if actual_doi != version_doi:
                print(f"          WARN: minted DOI {actual_doi} differs from reserved {version_doi}")
                pages_state[md.stem]["latest_doi"] = actual_doi
            pages_state[md.stem]["published_at"] = (
                published.get("submitted") or published.get("created")
            )
            save_state(sp, state)
            print(f"          Published: {actual_doi}")

    print(f"\nState in {sp.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
