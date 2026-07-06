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
