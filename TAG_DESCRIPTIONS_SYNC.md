# Tag Descriptions Sync Workflow

This document explains how to update tag descriptions after exporting from LogSeq.

## Overview

Tag descriptions are stored in `/content/tag-descriptions/` and automatically added to tag pages. When you export new content from LogSeq, the `sync-exports.sh` script synchronizes tag descriptions from the export.

## Workflow

### Step 1: Export from LogSeq

In the `logseq-to-markdown` repository, run the export:

```bash
cd ~/git/logseq-to-markdown
node index.mjs hw-logseq -o ./my-export -a -v
```

This exports all pages to `./my-export/pages/`.

### Step 2: Sync Tag Descriptions

In the `adhocism` repository, run the sync script:

```bash
cd ~/git/adhocism
./sync-exports.sh
```

The script will:
- Read pages from `~/git/logseq-to-markdown/my-export/pages/`
- Extract content for known tag pages (meta, en, fi, id, digital-garden)
- Create/update files in `./content/tag-descriptions/`
- Add `hidden: true` frontmatter to prevent them from appearing in page listings

Example output:
```
Syncing from: /home/user/git/logseq-to-markdown/my-export
Tag descriptions: ./content/tag-descriptions
  ✓ meta.md → meta.md
  ✓ en.md → en.md
  ✓ fi.md → fi.md
  ✓ id.md → id.md
  ✓ digital garden.md → digital-garden.md

Sync complete: 5 tag descriptions updated
```

### Step 3: Rebuild Hugo

Rebuild the site to generate updated tag pages with the new descriptions:

```bash
hugo
```

Or for a clean rebuild:

```bash
hugo --cleanDestinationDir
```

## What Gets Synced

The script syncs the following tag descriptions:
- `meta` - organization of the digital garden
- `en` - pages with English content
- `fi` - pages with Finnish content
- `id` - pages with Indonesian content
- `digital-garden` - the digital garden itself

These correspond to the files in `content/tag-descriptions/`:
- `meta.md`
- `en.md`
- `fi.md`
- `id.md`
- `digital-garden.md`

## Modifying Tag Descriptions

To add or modify tag descriptions:

1. **Edit in LogSeq**: Update the tag description page in your LogSeq graph
2. **Export**: Run the export from logseq-to-markdown
3. **Sync**: Run `./sync-exports.sh` in adhocism
4. **Rebuild**: Run `hugo` to generate the updated site

The script will automatically:
- Extract the content from the exported file
- Set the correct frontmatter with `hidden: true`
- Update the corresponding tag-descriptions file

## Custom Export Path

If your logseq-to-markdown export is in a different location, pass the path as an argument:

```bash
./sync-exports.sh /path/to/logseq-to-markdown/my-export
```

The default path is `$HOME/git/logseq-to-markdown/my-export`.

## Adding New Tag Descriptions

To add a new tag description:

1. Edit `sync-exports.sh` and add the tag name to the `TAG_PAGES` array
2. Create the corresponding page in LogSeq with that as the title
3. Run the sync workflow as described above

For example, to add a tag description for a "français" tag:

```bash
# In sync-exports.sh, change:
TAG_PAGES=("meta" "en" "fi" "id" "digital-garden")
# To:
TAG_PAGES=("meta" "en" "fi" "id" "digital-garden" "francais")
```

Then run the sync workflow.
