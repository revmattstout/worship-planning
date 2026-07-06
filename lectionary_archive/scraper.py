#!/usr/bin/env python3
"""
Crawls the Discipleship Ministries lectionary content library
(https://www.umcdiscipleship.org/content-library/lectionary) and populates
a local SQLite database (see db.py) with full-text-searchable content.

This must be run from a machine with normal internet access -- it makes
real HTTP requests to umcdiscipleship.org.

Usage:
    pip install -r requirements.txt
    python scraper.py                       # full crawl, 2016..current year
    python scraper.py --start-year 2023      # narrower range
    python scraper.py --refresh              # re-fetch everything, ignore cache/existing rows
    python scraper.py --delay 2.0            # be more polite (default 1s between live fetches)
"""
import argparse
import hashlib
import json
import re
import sys
import time
import urllib.robotparser
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import db

BASE_URL = "https://www.umcdiscipleship.org"
LISTING_PATH = "/content-library/lectionary"
USER_AGENT = (
    "worship-planning-archive-bot/1.0 "
    "(personal research tool building a local searchable index; "
    "respects robots.txt and rate-limits requests)"
)

CACHE_DIR = Path(__file__).parent / "data" / "html_cache"

PAGE_TYPE_MAP = {
    "planning worship": "planning_worship",
    "preaching notes": "preaching_notes",
    "liturgical resources": "liturgical_resources",
    "hymn suggestions": "hymn_suggestions",
    "music notes": "music_notes",
    "offertory prayer": "offertory_prayer",
    "youth lessons": "youth_lessons",
    "children's message": "childrens_message",
    "small groups": "small_groups",
    "graphics": "graphics",
}


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


class Fetcher:
    def __init__(self, delay=1.0):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.delay = delay
        self.robots = urllib.robotparser.RobotFileParser()
        try:
            self.robots.set_url(BASE_URL + "/robots.txt")
            self.robots.read()
        except Exception as exc:
            print(f"warning: could not read robots.txt ({exc}); proceeding cautiously", file=sys.stderr)
            self.robots = None

    def allowed(self, url):
        if self.robots is None:
            return True
        return self.robots.can_fetch(USER_AGENT, url)

    def get(self, url, use_cache=True):
        if not self.allowed(url):
            print(f"robots.txt disallows fetching {url}; skipping", file=sys.stderr)
            return None

        cache_path = None
        if use_cache:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_path = CACHE_DIR / (hashlib.sha1(url.encode()).hexdigest() + ".html")
            if cache_path.exists():
                return cache_path.read_text(encoding="utf-8")

        for attempt in range(4):
            try:
                resp = self.session.get(url, timeout=20)
                resp.raise_for_status()
                html = resp.text
                if cache_path is not None:
                    cache_path.write_text(html, encoding="utf-8")
                time.sleep(self.delay)
                return html
            except requests.RequestException as exc:
                wait = 2 ** attempt
                print(f"fetch failed ({exc}) for {url}, retrying in {wait}s", file=sys.stderr)
                time.sleep(wait)
        print(f"giving up on {url}", file=sys.stderr)
        return None


def parse_listing_page(html):
    """Returns a list of dicts: sunday_date, liturgical_name, series_name, series_url, week_url, week_title."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for item in soup.select(".lectionary-view .item"):
        date_el = item.select_one(".date-text")
        lit_el = item.select_one(".page-secondary-text")
        series_a = item.select_one(".series-title a")
        week_a = item.select_one(".week-title a")
        if not (date_el and week_a):
            continue
        try:
            sunday_date = datetime.strptime(date_el.get_text(strip=True), "%B %d, %Y").date().isoformat()
        except ValueError:
            sunday_date = None
        out.append({
            "sunday_date": sunday_date,
            "liturgical_name": lit_el.get_text(strip=True) if lit_el else None,
            "series_name": series_a.get_text(strip=True) if series_a else None,
            "series_url": urljoin(BASE_URL, series_a["href"]) if series_a else None,
            "week_url": urljoin(BASE_URL, week_a["href"]),
            "week_title": week_a.get_text(strip=True),
        })
    return out


def _extract_jsonld_dates(soup):
    for script in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(script.string)
        except (TypeError, ValueError):
            continue
        graph = data.get("@graph", [data])
        for node in graph:
            if node.get("@type") == "WebPage":
                return node.get("datePublished"), node.get("dateModified")
    return None, None


def parse_week_page(html, url):
    soup = BeautifulSoup(html, "html.parser")

    h1 = soup.select_one(".event-banner .details h1")
    series_h2 = soup.select_one(".event-banner .page-secondary-headline")
    lit_p = soup.select_one(".event-banner .page-secondary-text")
    teaser_p = soup.select_one(".event-banner .info p")

    breadcrumb_links = soup.select(".breadcrumbs .text a")
    series_name, series_url = None, None
    if len(breadcrumb_links) >= 3:
        series_name = breadcrumb_links[-1].get_text(strip=True)
        series_url = urljoin(BASE_URL, breadcrumb_links[-1]["href"])

    refs = []
    refs_container = soup.select_one(".misc-sidebar .refs")
    if refs_container:
        for a in refs_container.select("ul li a"):
            href = a.get("href", "")
            reading_type = None
            if "#pericope_" in href:
                reading_type = href.split("#pericope_", 1)[1].replace("_reading", "")
            refs.append({"reference": a.get_text(strip=True), "url": href, "reading_type": reading_type})

    colors_container = soup.select_one(".misc-sidebar .colors ul")
    colors = [li.get_text(strip=True) for li in colors_container.select("li")] if colors_container else []

    main_richtext = soup.select_one("article.event-detail .main .richtext")
    body_text = main_richtext.get_text(" ", strip=True) if main_richtext else ""
    body_html = str(main_richtext) if main_richtext else ""

    date_published, date_modified = _extract_jsonld_dates(soup)

    subpages = []
    for a in soup.select(".sidebar .section-nav .page-sub-nav a"):
        title = a.get_text(strip=True)
        href = urljoin(BASE_URL, a["href"])
        page_type = PAGE_TYPE_MAP.get(title.lower(), slugify(title))
        subpages.append({"title": title, "url": href, "page_type": page_type})

    return {
        "theme_title": h1.get_text(strip=True) if h1 else None,
        "series_name": series_name or (series_h2.get_text(strip=True) if series_h2 else None),
        "series_url": series_url,
        "liturgical_name": lit_p.get_text(strip=True) if lit_p else None,
        "teaser": teaser_p.get_text(strip=True) if teaser_p else None,
        "colors": ", ".join(colors),
        "scripture_refs": refs,
        "date_published": date_published,
        "date_modified": date_modified,
        "planning_worship_page": {
            "page_type": "planning_worship",
            "title": h1.get_text(strip=True) if h1 else "Planning Worship",
            "url": url,
            "body_html": body_html,
            "body_text": body_text,
        },
        "subpages": [sp for sp in subpages if sp["page_type"] != "planning_worship"],
    }


def parse_subpage(html, url, title, page_type):
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("article.event-detail .main")
    body_text = main.get_text(" ", strip=True) if main else ""
    body_html = str(main) if main else ""
    return {"page_type": page_type, "title": title, "url": url, "body_html": body_html, "body_text": body_text}


def upsert_week(conn, item):
    row = conn.execute("SELECT id FROM weeks WHERE url = ?", (item["week_url"],)).fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO weeks (url, series_name, series_url, liturgical_name, sunday_date, fetched_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (item["week_url"], item["series_name"], item["series_url"], item["liturgical_name"],
         item["sunday_date"], datetime.utcnow().isoformat()),
    )
    return cur.lastrowid


def store_week_detail(conn, week_id, detail):
    conn.execute(
        """
        UPDATE weeks SET theme_title = ?, series_name = COALESCE(?, series_name),
            series_url = COALESCE(?, series_url), liturgical_name = COALESCE(?, liturgical_name),
            teaser = ?, colors = ?, date_published = ?, date_modified = ?, fetched_at = ?
        WHERE id = ?
        """,
        (detail["theme_title"], detail["series_name"], detail["series_url"], detail["liturgical_name"],
         detail["teaser"], detail["colors"], detail["date_published"], detail["date_modified"],
         datetime.utcnow().isoformat(), week_id),
    )
    conn.execute("DELETE FROM scripture_refs WHERE week_id = ?", (week_id,))
    for ref in detail["scripture_refs"]:
        conn.execute(
            "INSERT INTO scripture_refs (week_id, reference, reading_type, url) VALUES (?, ?, ?, ?)",
            (week_id, ref["reference"], ref["reading_type"], ref["url"]),
        )


def store_page(conn, week_id, page):
    conn.execute(
        """
        INSERT INTO pages (week_id, page_type, title, url, body_html, body_text)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            title = excluded.title, body_html = excluded.body_html, body_text = excluded.body_text
        """,
        (week_id, page["page_type"], page["title"], page["url"], page["body_html"], page["body_text"]),
    )


def crawl(start_year, end_year, delay, refresh, db_path):
    conn = db.connect(db_path)
    fetcher = Fetcher(delay=delay)
    current_year = date.today().year

    all_items = []
    for year in range(start_year, end_year + 1):
        listing_url = BASE_URL + LISTING_PATH if year == current_year else f"{BASE_URL}{LISTING_PATH}/{year}"
        print(f"Fetching listing for {year}: {listing_url}")
        html = fetcher.get(listing_url, use_cache=False)
        if html is None:
            continue
        items = parse_listing_page(html)
        print(f"  found {len(items)} entries")
        all_items.extend(items)

    week_ids_to_process = []
    for item in all_items:
        week_id = upsert_week(conn, item)
        existing_pages = conn.execute("SELECT COUNT(*) FROM pages WHERE week_id = ?", (week_id,)).fetchone()[0]
        if refresh or existing_pages == 0:
            week_ids_to_process.append((week_id, item["week_url"]))
    conn.commit()

    print(f"{len(week_ids_to_process)} week(s) need detail fetching")
    for i, (week_id, url) in enumerate(week_ids_to_process, 1):
        print(f"[{i}/{len(week_ids_to_process)}] {url}")
        html = fetcher.get(url, use_cache=not refresh)
        if html is None:
            continue
        detail = parse_week_page(html, url)
        store_week_detail(conn, week_id, detail)
        store_page(conn, week_id, detail["planning_worship_page"])

        for sp in detail["subpages"]:
            sub_html = fetcher.get(sp["url"], use_cache=not refresh)
            if sub_html is None:
                continue
            sub_page = parse_subpage(sub_html, sp["url"], sp["title"], sp["page_type"])
            store_page(conn, week_id, sub_page)
        conn.commit()

    print("Rebuilding search index...")
    db.rebuild_search_index(conn)
    print("Done.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start-year", type=int, default=2016)
    parser.add_argument("--end-year", type=int, default=date.today().year)
    parser.add_argument("--delay", type=float, default=1.0, help="seconds to sleep between live HTTP requests")
    parser.add_argument("--refresh", action="store_true", help="re-fetch everything, ignoring cache and existing rows")
    parser.add_argument("--db", default=str(db.DEFAULT_DB_PATH))
    args = parser.parse_args()
    crawl(args.start_year, args.end_year, args.delay, args.refresh, args.db)


if __name__ == "__main__":
    main()
