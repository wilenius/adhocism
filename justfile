# Adhocism: Logseq → Hugo publishing flow.
#
# Override paths with env vars if your checkout lives elsewhere:
#   LOGSEQ_TO_MD_DIR  path to the logseq-to-markdown repo
#   LOGSEQ_GRAPH      name of the Logseq graph to export
#
# The export uses `-o ./my-export` on purpose: that directory is
# configured in Logseq to render only public pages and blocks.

logseq_dir := env_var_or_default("LOGSEQ_TO_MD_DIR", env_var("HOME") + "/git/logseq-to-markdown")
graph      := env_var_or_default("LOGSEQ_GRAPH", "hw-logseq")

default:
    @just --list

# Export the Logseq graph to Markdown (public-only via ./my-export)
export:
    cd {{logseq_dir}} && node index.mjs {{graph}} -o ./my-export -d -v -t

# Copy exported pages and assets into this Hugo site
sync:
    ./sync-exports.sh {{logseq_dir}}/my-export

# Pull fresh content from Logseq (export + sync)
import: export sync

# Build the Hugo site locally. Production deploy runs via GitHub Actions on push.
build:
    hugo --gc --minify

# Local preview server
preview:
    hugo server

# Full flow: import, validate build, commit content changes, push.
publish: import build
    git add content/pages static/logseq-assets
    @if git diff --cached --quiet; then \
        echo "no content changes — nothing to commit"; \
    else \
        git commit -m "publish: sync logseq export ($(date -I))"; \
        git push; \
    fi
