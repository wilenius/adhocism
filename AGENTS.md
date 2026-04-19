# Agent notes

This is a Hugo site whose content comes from a Logseq graph via the
`logseq-to-markdown` tool. GitHub Actions builds and deploys on push to `main`.

## Publishing flow

Use `just` — the `justfile` in this repo is the single entry point.

```
just            # list targets
just import     # export Logseq graph + sync into content/pages and static/logseq-assets
just build      # local Hugo build (validation; production deploy runs in CI on push)
just preview    # local Hugo dev server
just publish    # import + build + commit content changes + push
```

`just publish` is the full flow. It only stages `content/pages` and
`static/logseq-assets`, so unrelated working-tree changes are left alone.

## Configuration

The justfile reads two env vars with sensible defaults:

- `LOGSEQ_TO_MD_DIR` — path to the `logseq-to-markdown` checkout
  (default: `$HOME/git/logseq-to-markdown`)
- `LOGSEQ_GRAPH` — name of the Logseq graph to export
  (default: `hw-logseq`)

The export runs with `-o ./my-export -d -v -t`. The `./my-export` output
directory is not arbitrary: it is configured in Logseq to render only public
pages and blocks. Do not change it.

## Requirements

`just`, `hugo` (extended), `node`, plus a local clone of `logseq-to-markdown`
with its dependencies installed (`npm install` in that repo).
