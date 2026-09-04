"""Command line entry point: poll, report, status, estimate."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import COST_PER_READ_USD
from .budget import BudgetExceeded, BudgetGuard
from .classify import classify
from .client import XAPIError, XClient
from .config import ConfigError, DEFAULT_DB, bearer_token, load_config
from .report import render
from .store import (
    connect,
    current_month,
    get_cursor,
    month_reads,
    month_spend,
    save_posts,
    set_cursor,
    top_posts,
    utcnow,
)

DEFAULT_REPORT = Path(__file__).resolve().parent.parent / "reports" / "leads.html"


def cmd_poll(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    client = XClient(bearer_token())

    with connect(args.db) as conn:
        guard = BudgetGuard(
            conn, config.monthly_usd, config.per_run_usd, config.max_results
        )
        print(
            f"Month to date: ${guard.month_spend:.2f} of ${config.monthly_usd:.2f}. "
            f"This run is capped at ${config.per_run_usd:.2f}."
        )

        total_new = 0
        for query in config.queries:
            try:
                total_new += _run_query(conn, client, guard, query, config)
            except BudgetExceeded as exc:
                print(f"\nStopped: {exc}")
                break
            except XAPIError as exc:
                print(f"\n[{query.name}] X API error: {exc}", file=sys.stderr)
                continue

        print(
            f"\nDone. {total_new} new posts stored. "
            f"This run: {guard.run_reads} reads, ${guard.run_spend:.2f}."
        )
        print(f"Month to date: ${guard.month_spend:.2f} of ${config.monthly_usd:.2f}.")
    return 0


def _run_query(conn, client, guard, query, config) -> int:
    print(f"\n[{query.name}]")
    since_id = get_cursor(conn, query.name)
    if since_id:
        print(f"  resuming after post {since_id}")

    next_token = None
    new_count = 0
    highest_id = since_id

    for page_num in range(config.max_pages):
        guard.check()

        page = client.search(
            query=query.query,
            max_results=config.max_results,
            since_id=since_id if page_num == 0 else None,
            next_token=next_token,
        )
        cost = guard.settle(query.name, page.billed_reads)
        print(f"  page {page_num + 1}: {page.billed_reads} posts, ${cost:.3f}")

        if not page.posts:
            break

        scored = []
        for post in page.posts:
            score, verdict, reasons = classify(post["text"])
            scored.append(
                {**post, "query_name": query.name, "score": score,
                 "verdict": verdict, "reasons": reasons, "fetched_at": utcnow()}
            )
            # Post ids are monotonic, so max() by numeric value is the newest.
            if highest_id is None or int(post["id"]) > int(highest_id):
                highest_id = post["id"]

        new_count += save_posts(conn, scored)
        hits = sum(1 for s in scored if s["verdict"] == "likely_hiring")
        print(f"    {hits} likely hiring, {len(scored) - hits} filtered out")

        next_token = page.next_token
        if not next_token:
            break

    if highest_id and highest_id != since_id:
        set_cursor(conn, query.name, highest_id)
    conn.commit()
    return new_count


def cmd_report(args: argparse.Namespace) -> int:
    with connect(args.db) as conn:
        rows = top_posts(conn, limit=args.limit, min_score=args.min_score)
        path = render(conn, rows, args.out)
    print(f"Wrote {len(rows)} posts to {path}")
    print(f"Open it with:  open {path}   (macOS)  /  xdg-open {path}  (Linux)")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    with connect(args.db) as conn:
        spent = month_spend(conn)
        reads = month_reads(conn)
        total = conn.execute("SELECT COUNT(*) AS n FROM posts").fetchone()["n"]
        hits = conn.execute(
            "SELECT COUNT(*) AS n FROM posts WHERE verdict = 'likely_hiring'"
        ).fetchone()["n"]

    pct = (spent / config.monthly_usd * 100) if config.monthly_usd else 0
    print(f"Month {current_month()}")
    print(f"  spent    ${spent:.2f} of ${config.monthly_usd:.2f} ({pct:.0f}%)")
    print(f"  reads    {reads:,}")
    print(f"  stored   {total:,} posts, {hits:,} likely hiring")
    print(f"  queries  {len(config.queries)} configured")
    return 0


def cmd_estimate(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    per_poll = len(config.queries) * config.max_pages * config.max_results
    worst = per_poll * COST_PER_READ_USD
    print(f"Queries: {len(config.queries)}, max {config.max_pages} pages of "
          f"{config.max_results} posts each.")
    print(f"\nWorst case per poll (every page full): {per_poll} reads = ${worst:.2f}")
    for label, per_day in (("hourly", 24), ("every 6h", 4), ("daily", 1)):
        month = worst * per_day * 30
        print(f"  {label:9} -> up to ${month:,.2f}/month")
    print("\nReal cost is far lower: you are billed per post returned, and a tight")
    print("query rarely fills a page. The monthly cap is the number that binds.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="xhire", description="Find X posts from brands hiring UGC creators."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite path")
    parser.add_argument("--config", type=Path, default=None, help="config.toml path")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("poll", help="fetch new posts (costs money)").set_defaults(
        func=cmd_poll
    )

    rep = sub.add_parser("report", help="build the HTML page of leads")
    rep.add_argument("--out", type=Path, default=DEFAULT_REPORT)
    rep.add_argument("--limit", type=int, default=100)
    rep.add_argument("--min-score", type=int, default=2)
    rep.set_defaults(func=cmd_report)

    sub.add_parser("status", help="show spend and stored counts").set_defaults(
        func=cmd_status
    )
    sub.add_parser("estimate", help="cost projection, makes no API calls").set_defaults(
        func=cmd_estimate
    )

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
