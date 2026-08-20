#!/usr/bin/env python3
"""
Exports the SQLite search index to docs/data.json, a static JSON file that
docs/index.html can search entirely in the browser -- no server needed.
This is what makes GitHub Pages deployment possible.

Usage:
    python export_static.py                 # reads data/lectionary.db, writes ../docs/data.json
    python export_static.py --db path/to.db --out ../docs/data.json
"""
import argparse
import json
import sqlite3
from pathlib import Path

import db

DEFAULT_OUT = Path(__file__).parent.parent / "docs" / "data.json"


def export(conn, out_path):
    rows = conn.execute(
        """
        SELECT title, body_text, series_name, liturgical_name, scripture, page_type, sunday_date, url
        FROM search_index
        ORDER BY sunday_date DESC
        """
    ).fetchall()

    docs = []
    for i, (title, body, series, liturgical, scripture, page_type, sunday_date, url) in enumerate(rows):
        docs.append({
            "id": i,
            "title": title or "",
            "body": body or "",
            "series": series or "",
            "liturgical": liturgical or "",
            "scripture": scripture or "",
            "type": page_type or "",
            "date": sunday_date or "",
            "url": url or "",
        })

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(docs, f, separators=(",", ":"), ensure_ascii=False)

    print(f"Wrote {len(docs)} documents to {out_path} ({out_path.stat().st_size / 1024:.0f} KB)")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(db.DEFAULT_DB_PATH))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    export(conn, args.out)


if __name__ == "__main__":
    main()
