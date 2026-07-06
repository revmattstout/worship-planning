#!/usr/bin/env python3
"""
Search the local lectionary archive database built by scraper.py.

Examples:
    python search.py "forgiveness"
    python search.py "grace" --type preaching_notes
    python search.py "children" --type childrens_message --after 2023-01-01
    python search.py --scripture "John 3"
    python search.py --season Advent --limit 10
"""
import argparse
import sqlite3

import db


def run_search(conn, query, page_type=None, scripture=None, after=None, before=None, series=None, limit=20):
    where = []
    params = []

    if query:
        where.append("search_index MATCH ?")
        params.append(query)
    if page_type:
        where.append("search_index.page_type = ?")
        params.append(page_type)
    if scripture:
        where.append("search_index.scripture LIKE ?")
        params.append(f"%{scripture}%")
    if series:
        where.append("search_index.series_name LIKE ?")
        params.append(f"%{series}%")
    if after:
        where.append("search_index.sunday_date >= ?")
        params.append(after)
    if before:
        where.append("search_index.sunday_date <= ?")
        params.append(before)

    where_clause = " AND ".join(where) if where else "1=1"
    order = "bm25(search_index)" if query else "sunday_date DESC"
    sql = f"""
        SELECT title, series_name, liturgical_name, page_type, sunday_date, scripture, url,
               snippet(search_index, 1, '[', ']', '...', 12) AS snip
        FROM search_index
        WHERE {where_clause}
        ORDER BY {order}
        LIMIT ?
    """
    params.append(limit)
    return conn.execute(sql, params).fetchall()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query", nargs="?", default=None, help="full-text search terms")
    parser.add_argument("--type", dest="page_type", help="filter by page type, e.g. preaching_notes, hymn_suggestions")
    parser.add_argument("--scripture", help="filter by scripture reference substring, e.g. 'John 3'")
    parser.add_argument("--series", help="filter by worship series name substring")
    parser.add_argument("--after", help="only entries on/after this date (YYYY-MM-DD)")
    parser.add_argument("--before", help="only entries on/before this date (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--db", default=str(db.DEFAULT_DB_PATH))
    args = parser.parse_args()

    if not any([args.query, args.page_type, args.scripture, args.series, args.after, args.before]):
        parser.error("provide a query or at least one filter")

    conn = sqlite3.connect(args.db)
    try:
        rows = run_search(conn, args.query, args.page_type, args.scripture, args.after, args.before, args.series, args.limit)
    except sqlite3.OperationalError as exc:
        print(f"query error: {exc}")
        return

    if not rows:
        print("No results.")
        return

    for title, series_name, liturgical_name, page_type, sunday_date, scripture, url, snip in rows:
        print(f"\n{sunday_date or '?':<12} {series_name or ''} — {liturgical_name or ''}")
        print(f"  [{page_type}] {title}")
        if scripture:
            print(f"  Scripture: {scripture}")
        if snip:
            print(f"  {snip}")
        print(f"  {url}")


if __name__ == "__main__":
    main()
