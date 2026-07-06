#!/usr/bin/env python3
"""
A tiny local search UI for the lectionary archive database, stdlib only.

Usage:
    python webapp.py            # serves on http://localhost:8000
    python webapp.py --port 9000 --db data/lectionary.db
"""
import argparse
import html
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import db
from search import run_search

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Lectionary Archive Search</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; color: #222; }}
  form {{ display: flex; gap: 0.5rem; margin-bottom: 1.5rem; }}
  input[type=text] {{ flex: 1; padding: 0.5rem; font-size: 1rem; }}
  select {{ padding: 0.5rem; }}
  button {{ padding: 0.5rem 1rem; }}
  .result {{ border-bottom: 1px solid #ddd; padding: 1rem 0; }}
  .result h3 {{ margin: 0 0 0.25rem 0; }}
  .meta {{ color: #666; font-size: 0.9rem; }}
  .snippet {{ margin: 0.5rem 0; }}
  mark {{ background: #ffe58a; }}
  .count {{ color: #666; margin-bottom: 1rem; }}
</style>
</head>
<body>
<h1>Lectionary Archive Search</h1>
<form method="get" action="/">
  <input type="text" name="q" placeholder="Search topic, e.g. forgiveness, baptism, grief..." value="{query}">
  <select name="type">
    <option value="">All page types</option>
    {type_options}
  </select>
  <button type="submit">Search</button>
</form>
{results}
</body>
</html>
"""

PAGE_TYPES = [
    "planning_worship", "preaching_notes", "liturgical_resources", "hymn_suggestions",
    "music_notes", "offertory_prayer", "youth_lessons", "childrens_message",
    "small_groups", "graphics",
]


def render_results(conn, query, page_type):
    if not query and not page_type:
        return ""
    try:
        rows = run_search(conn, query or None, page_type=page_type or None, limit=50)
    except sqlite3.OperationalError as exc:
        return f"<p>Query error: {html.escape(str(exc))}</p>"

    if not rows:
        return "<p class='count'>No results.</p>"

    parts = [f"<p class='count'>{len(rows)} result(s)</p>"]
    for title, series_name, liturgical_name, ptype, sunday_date, scripture, url, snip in rows:
        snip_html = snip.replace("[", "<mark>").replace("]", "</mark>") if snip else ""
        parts.append(f"""
        <div class="result">
          <h3><a href="{html.escape(url)}" target="_blank">{html.escape(title or '')}</a></h3>
          <div class="meta">{html.escape(sunday_date or '')} &middot; {html.escape(series_name or '')} &mdash;
            {html.escape(liturgical_name or '')} &middot; <em>{html.escape(ptype)}</em></div>
          {"<div class='meta'>Scripture: " + html.escape(scripture) + "</div>" if scripture else ""}
          <div class="snippet">{snip_html}</div>
        </div>
        """)
    return "\n".join(parts)


class Handler(BaseHTTPRequestHandler):
    db_path = str(db.DEFAULT_DB_PATH)

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        query = params.get("q", [""])[0]
        page_type = params.get("type", [""])[0]

        if not Path(self.db_path).exists():
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            msg = (
                f"<p>No database found at <code>{html.escape(self.db_path)}</code>.</p>"
                "<p>Run <code>python scraper.py</code> first to build it, then reload this page.</p>"
            )
            self.wfile.write(PAGE_TEMPLATE.format(query="", type_options="", results=msg).encode("utf-8"))
            return

        conn = sqlite3.connect(self.db_path)
        try:
            results_html = render_results(conn, query, page_type)
        finally:
            conn.close()

        type_options = "\n".join(
            f'<option value="{t}"{" selected" if t == page_type else ""}>{t}</option>' for t in PAGE_TYPES
        )
        body = PAGE_TEMPLATE.format(query=html.escape(query), type_options=type_options, results=results_html)

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", default=str(db.DEFAULT_DB_PATH))
    args = parser.parse_args()

    Handler.db_path = args.db
    server = ThreadingHTTPServer(("localhost", args.port), Handler)
    print(f"Serving on http://localhost:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
