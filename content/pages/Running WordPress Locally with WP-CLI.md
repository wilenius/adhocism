---
title: "Running WordPress Locally with WP-CLI"
tags: 
categories: 
date: 2026-05-07
lastMod: 2026-05-07
---
Running WordPress Locally with WP-CLI

+ Quick reference for setting up a local WordPress instance and importing a database dump using WP-CLI.

+ ## Create a Site in Local

	+ Click **+** → name your site → "Preferred" setup → set credentials → Create Site

	+ Local provisions WordPress automatically

+ ## Import a Database Dump

	+ Right-click the site → **Open Site Shell**

	+ **Reset the database first** (fresh installs already have tables):

		+ ```
		  wp db reset --yes
		  ```

	+ Then import:

		+ ```
		  wp db import /path/to/your-dump.sql
		  ```

	+ Drag the `.sql` file into the terminal to paste its full path instead of typing it

+ ## Fix URLs After Import

	+ The dump contains the production domain; you need to search-replace it:

		+ ```
		  wp search-replace 'https://old-domain.com' 'http://yoursite.local' --all-tables
		  ```

	+ `--all-tables` catches serialised data in custom tables

	+ Then force the core options:

		+ ```
		  wp option update siteurl 'http://yoursite.local'
		  wp option update home 'http://yoursite.local'
		  ```

	+ Verify:

		+ ```
		  wp option get siteurl
		  wp option get home
		  ```

+ ## Still Redirecting to Production?

	+ The browser caches 301 redirects — the database is probably fine

	+ **Test in a private/incognito window** first

	+ If it works there, clear browser cache for that domain

+ ## Common Gotchas

	+ `Table already exists` error → you forgot `wp db reset --yes` first

	+ `DISALLOW_FILE_EDIT already defined` warning → harmless, ignore it

	+ Large dumps fail in Adminer or phpMyAdmin→ use WP-CLI instead

