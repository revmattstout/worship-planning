# Lectionary Archive Search

Builds a local, searchable SQLite database from the Discipleship Ministries
lectionary content library
(https://www.umcdiscipleship.org/content-library/lectionary), so you can
search past worship-planning content by topic, scripture reference, series,
date, or content type, instead of paging through the site's non-searchable
archive.

## Important: this needs a machine with normal internet access

The scraper (`scraper.py`) makes real HTTP requests to umcdiscipleship.org.
It won't work in a network-sandboxed environment. Run it from your own
computer.

It is polite by default: it identifies itself with a descriptive User-Agent,
checks `robots.txt` before fetching, rate-limits requests (1 request/second
by default), and caches every fetched page to disk so re-runs don't
re-download unchanged content.

## Setup

```
cd lectionary_archive
pip install -r requirements.txt
```

## Build the database

```
python scraper.py
```

This crawls the year-by-year archive (2016 through the current year),
finds every lectionary week, and for each one fetches the main "Planning
Worship" notes plus every linked sub-page (Preaching Notes, Liturgical
Resources, Hymn Suggestions, Music Notes, Offertory Prayer, Youth Lessons,
Children's Message, Small Groups, Graphics -- not every week has all of
these). A full initial crawl covers on the order of a thousand pages, so at
the default 1 request/second it will take a while; let it run in the
background. It's resumable -- if it's interrupted, just run it again and
it'll pick up where it left off (already-fetched pages are cached and
already-processed weeks are skipped unless you pass `--refresh`).

Useful flags:

```
python scraper.py --start-year 2023           # only crawl recent years
python scraper.py --delay 2.0                 # slower / more polite
python scraper.py --refresh                   # re-fetch everything, ignore cache
```

The database is written to `data/lectionary.db`.

## A real double-clickable app (macOS)

`mac_app/` has AppleScript sources for two tiny real macOS apps: one starts
the search server and opens it in your browser, the other stops it. Unlike
`Launch Lectionary Search.command`, these behave like normal apps -- no
Terminal window, and you can drag them anywhere on the Dock (including the
apps side, left of the divider).

These have to be compiled on your own Mac (there's no way to build a macOS
app bundle from anywhere else). One-time setup:

1. Confirm the path in both `.applescript` files matches where you actually
   cloned this repo -- they assume
   `/Users/mattstout/Documents/GitHub/worship-planning/lectionary_archive`.
   Edit the `appDir` line in each file if yours is different.
2. Compile them:

   ```
   cd ~/Documents/GitHub/worship-planning/lectionary_archive/mac_app
   osacompile -o "Lectionary Search.app" "Lectionary Search.applescript"
   osacompile -o "Stop Lectionary Search.app" "Stop Lectionary Search.applescript"
   ```
3. Drag both `.app` files (in Finder, from the `mac_app` folder) onto your
   Dock, or into `/Applications`, wherever is convenient.

Double-click **Lectionary Search** to start the server and open the search
page. Double-click **Stop Lectionary Search** when you're done (it shows a
quick notification either way). Output/errors from the server go to
`webapp.log` in this folder if you ever need to check on it.

## Keeping it up to date automatically (macOS)

`update_and_publish.sh` runs the full weekly refresh in one shot: crawl for
new lectionary weeks (`scraper.py`, safe to re-run any time -- it only
fetches weeks it hasn't seen before), rebuild the static export
(`export_static.py`), and -- if anything actually changed --
`git commit` and `git push` `docs/data.json` so the GitHub Pages site
updates itself too. If nothing changed, it does nothing (no empty commits).

`com.umcdiscipleship.lectionary-scraper.plist` is a `launchd` job (macOS's
built-in scheduler) that runs this script every Sunday at 6:00 AM.

**One-time setup:**

1. Confirm your Python path. Run `which python3` in Terminal -- if it
   doesn't print `/usr/bin/python3`, edit `update_and_publish.sh` and change
   the `python3` calls to the full path `which python3` printed (launchd
   jobs use a minimal PATH that may not match your Terminal's).
2. Confirm `git push` works without being prompted for a password when you
   run it by hand in Terminal (i.e. you've already got a credential helper
   or an unlocked SSH key set up). A scheduled job can't type a password for
   you -- if it's not already passwordless, run `git push` manually once and
   follow whatever prompts your Mac gives you to save the credential, then
   confirm a second `git push` doesn't ask again.
3. Double-check the file paths in the `.plist` and in `update_and_publish.sh`
   match where you actually cloned this repo (they assume
   `/Users/mattstout/Documents/GitHub/worship-planning/lectionary_archive`).
4. Copy the job into place and load it:

   ```
   cp com.umcdiscipleship.lectionary-scraper.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.umcdiscipleship.lectionary-scraper.plist
   ```

That's it -- it'll now run automatically every Sunday morning, even if
Terminal isn't open (as long as your Mac is on), and your GitHub Pages site
will reflect newly-published lectionary content within a few minutes after.
Check `update.log` in this folder afterward to confirm it ran (and to see
`PUSH FAILED` if step 2 above wasn't actually passwordless).

**Useful commands:**

```
# run it right now instead of waiting for Sunday
launchctl start com.umcdiscipleship.lectionary-scraper

# stop the schedule
launchctl unload ~/Library/LaunchAgents/com.umcdiscipleship.lectionary-scraper.plist

# turn it back on
launchctl load ~/Library/LaunchAgents/com.umcdiscipleship.lectionary-scraper.plist
```

## Search

Command line:

```
python search.py "forgiveness"
python search.py "grief" --type childrens_message
python search.py --scripture "John 3"
python search.py --series "Renewed in Mercy"
python search.py "baptism" --after 2023-01-01 --before 2024-12-31
```

Or a small local web UI:

```
python webapp.py
```

then open http://localhost:8000 -- type a topic, optionally narrow by
content type (Preaching Notes, Hymn Suggestions, etc.), and it shows
matching entries with a highlighted snippet and a link back to the original
page on umcdiscipleship.org.

## How it's structured

- `weeks` -- one row per lectionary Sunday/occasion: date, liturgical name
  (e.g. "Second Sunday in Lent, Year A"), series name, theme title, teaser,
  liturgical colors.
- `scripture_refs` -- the Hebrew Bible/Psalm/Epistle/Gospel readings for each
  week, linked back to the Vanderbilt Revised Common Lectionary site.
- `pages` -- the actual content: one row per sub-page per week (planning
  notes, preaching notes, hymn suggestions, etc.), with both HTML and
  plain-text body content.
- `search_index` -- a SQLite FTS5 full-text index over all of the above, used
  by `search.py` and `webapp.py`.

Re-running `scraper.py` later will pick up newly published weeks without
re-fetching everything else.

## Publishing a public, browser-only version (GitHub Pages)

GitHub Pages only serves static files -- no Python, no live SQLite queries --
so `docs/index.html` is a from-scratch client-side version: it fetches
`docs/data.json` (a flat export of everything in `search_index`) once when
the page loads, then does searching, filtering, snippet highlighting, and
pagination entirely in JavaScript in the visitor's browser. Same look, same
core features (topic search, page-type filter, 50-per-page results with
Previous/Next) as `webapp.py`, just no server required.

**Heads up:** this makes the archive's content -- the actual scraped text,
not just links to it -- visible to anyone with the URL, even though the
GitHub repo itself is private. GitHub Pages doesn't inherit a repo's privacy
on the free plan. Only do this if you're fine with that.

**Generate the data file** (run this on your Mac, after `scraper.py` has
built `data/lectionary.db`):

```
cd lectionary_archive
python3 export_static.py
```

This writes `docs/data.json`. Re-run it any time you want the published
site to reflect newly-scraped content, then commit and push both
`docs/data.json` and any changes.

**Turn on GitHub Pages** (one-time, in the browser):

1. On GitHub, go to your repo -> **Settings** -> **Pages**.
2. Under "Build and deployment", set **Source** to "Deploy from a branch".
3. Set **Branch** to `claude/lectionary-searchable-database-vzdgnx` (or
   whichever branch you're using) and the folder to **/docs**.
4. Save. GitHub will give you a URL like
   `https://<your-username>.github.io/worship-planning/` -- it can take a
   minute or two to go live the first time, and re-deploys automatically a
   minute or so after every push that touches `docs/`.

To update the published site later: re-run `export_static.py`, then
`git add docs/data.json && git commit -m "update archive" && git push`.
