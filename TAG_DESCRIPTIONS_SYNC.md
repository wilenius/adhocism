# Tag Descriptions Sync Workflow

This document explains how to sync your LogSeq export to your Hugo site.

## Overview

The `sync-exports.sh` script handles the complete synchronization from LogSeq export to your Hugo site:

1. **Copies pages** - All exported markdown files from LogSeq go to `/content/pages/`
2. **Copies assets** - All images and other assets go to `/static/logseq-assets/`
3. **Syncs tag descriptions** - Extracts content from tag pages and creates/updates `/content/tag-descriptions/` files with `hidden: true` frontmatter

This ensures your site stays up-to-date with your latest LogSeq content.

## Workflow

### Step 1: Export from LogSeq

In the `logseq-to-markdown` repository, run the export:

```bash
cd ~/git/logseq-to-markdown
node index.mjs hw-logseq -o ./my-export -a -v
```

This exports all pages to `./my-export/pages/`.

### Step 2: Sync Export to Site

In the `adhocism` repository, run the sync script:

```bash
cd ~/git/adhocism
./sync-exports.sh
```

The script will:
- Copy all pages from `~/git/logseq-to-markdown/my-export/pages/` to `./content/pages/`
- Copy all assets from `~/git/logseq-to-markdown/my-export/assets/` to `./static/logseq-assets/`
- Extract content for known tag pages (meta, en, fi, id, digital-garden)
- Create/update files in `./content/tag-descriptions/` with `hidden: true` frontmatter

Example output:
```
Syncing from: /home/user/git/logseq-to-markdown/my-export

Copying pages to ./content/pages/
  [pages copied...]

Copying assets to ./static/logseq-assets/
  [assets copied...]

Syncing tag descriptions to ./content/tag-descriptions...
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

### Pages
All markdown files from the export are copied to `content/pages/`. This includes:
- Your regular content pages (Jan 30th, 2024, Pandoc lua filters, etc.)
- Tag description pages (meta, en, fi, id, digital-garden)

### Assets
All images and other assets from the export are copied to `static/logseq-assets/` and can be referenced in your markdown files.

### Tag Descriptions
The script automatically extracts tag description content and creates hidden pages:
- `meta` - organization of the digital garden
- `en` - pages with English content
- `fi` - pages with Finnish content
- `id` - pages with Indonesian content
- `digital-garden` - the digital garden itself

These become files in `content/tag-descriptions/`:
- `meta.md`
- `en.md`
- `fi.md`
- `id.md`
- `digital-garden.md`

These files have `hidden: true` in their frontmatter so they don't appear in page listings, but their content is displayed on the corresponding tag pages.

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
