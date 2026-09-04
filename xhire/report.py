"""Render stored posts as a standalone HTML page."""

from __future__ import annotations

import html
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

VERDICT_LABELS = {
    "likely_hiring": ("Likely hiring", "hit"),
    "maybe_hiring": ("Maybe", "warm"),
    "unclear": ("Unclear", "cold"),
    "creator_selling": ("Creator self-promo", "cold"),
    "off_topic": ("Off topic", "cold"),
}

STYLE = """
:root {
  --bg: #fbfaf8; --panel: #fff; --ink: #1a1a19; --muted: #6b6a67;
  --line: #e5e3df; --hit: #1f7a4d; --hit-bg: #e8f5ee;
  --warm: #8a6412; --warm-bg: #fdf4e0; --cold: #6b6a67; --cold-bg: #f0efec;
}
:root:not([data-theme="light"]) { }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #16161a; --panel: #1e1e23; --ink: #eceaea; --muted: #9d9a97;
    --line: #32323a; --hit: #58c78d; --hit-bg: #16301f;
    --warm: #d8ab4a; --warm-bg: #2e2513; --cold: #9d9a97; --cold-bg: #26262c;
  }
}
:root[data-theme="dark"] {
  --bg: #16161a; --panel: #1e1e23; --ink: #eceaea; --muted: #9d9a97;
  --line: #32323a; --hit: #58c78d; --hit-bg: #16301f;
  --warm: #d8ab4a; --warm-bg: #2e2513; --cold: #9d9a97; --cold-bg: #26262c;
}
body {
  background: var(--bg); color: var(--ink); margin: 0;
  font: 15px/1.55 ui-sans-serif, -apple-system, "Segoe UI", system-ui, sans-serif;
}
.wrap { max-width: 820px; margin: 0 auto; padding: 40px 20px 80px; }
h1 { font-size: 22px; margin: 0 0 4px; letter-spacing: -0.01em; }
.sub { color: var(--muted); font-size: 13px; margin: 0 0 28px; }
.stats { display: flex; gap: 28px; flex-wrap: wrap; padding: 16px 0 24px;
         border-top: 1px solid var(--line); border-bottom: 1px solid var(--line);
         margin-bottom: 28px; }
.stat b { display: block; font-size: 20px; font-weight: 600; }
.stat span { color: var(--muted); font-size: 12px; text-transform: uppercase;
             letter-spacing: 0.05em; }
.post { background: var(--panel); border: 1px solid var(--line);
        border-radius: 10px; padding: 16px 18px; margin-bottom: 12px; }
.head { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap;
        margin-bottom: 8px; }
.handle { font-weight: 600; text-decoration: none; color: var(--ink); }
.handle:hover { text-decoration: underline; }
.meta { color: var(--muted); font-size: 12px; }
.tag { margin-left: auto; font-size: 11px; font-weight: 600; padding: 2px 8px;
       border-radius: 20px; text-transform: uppercase; letter-spacing: 0.04em; }
.tag.hit { color: var(--hit); background: var(--hit-bg); }
.tag.warm { color: var(--warm); background: var(--warm-bg); }
.tag.cold { color: var(--cold); background: var(--cold-bg); }
.text { white-space: pre-wrap; word-wrap: break-word; margin: 0 0 10px; }
.why { color: var(--muted); font-size: 12px; font-family: ui-monospace, monospace;
       border-top: 1px dashed var(--line); padding-top: 8px; }
.empty { color: var(--muted); text-align: center; padding: 60px 0; }
"""


def render(conn: sqlite3.Connection, rows: list[sqlite3.Row], out_path: Path) -> Path:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    likely = sum(1 for r in rows if r["verdict"] == "likely_hiring")

    cards = "\n".join(_card(r) for r in rows) or (
        '<p class="empty">No posts scored above the threshold yet. '
        "Run <code>python -m xhire poll</code>.</p>"
    )

    doc = f"""<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>UGC hiring leads</title>
<style>{STYLE}</style></head>
<body><div class="wrap">
<h1>UGC hiring leads</h1>
<p class="sub">Generated {generated}</p>
<div class="stats">
  <div class="stat"><b>{len(rows)}</b><span>shown</span></div>
  <div class="stat"><b>{likely}</b><span>likely hiring</span></div>
  <div class="stat"><b>{_total_posts(conn)}</b><span>stored</span></div>
  <div class="stat"><b>${_month_spend(conn):.2f}</b><span>spent this month</span></div>
</div>
{cards}
</div></body></html>"""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc, encoding="utf-8")
    return out_path


def _card(row: sqlite3.Row) -> str:
    label, css = VERDICT_LABELS.get(row["verdict"], ("Unknown", "cold"))
    followers = f"{row['followers']:,} followers" if row["followers"] else ""
    posted = (row["created_at"] or "")[:16].replace("T", " ")
    return f"""<article class="post">
  <div class="head">
    <a class="handle" href="{html.escape(row['url'])}">@{html.escape(row['author_handle'])}</a>
    <span class="meta">{html.escape(followers)}</span>
    <span class="meta">{html.escape(posted)}</span>
    <span class="tag {css}">{label} &middot; {row['score']}</span>
  </div>
  <p class="text">{html.escape(row['text'])}</p>
  <div class="why">{html.escape(row['reasons'])}</div>
</article>"""


def _total_posts(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) AS n FROM posts").fetchone()["n"])


def _month_spend(conn: sqlite3.Connection) -> float:
    from .store import month_spend

    return month_spend(conn)
