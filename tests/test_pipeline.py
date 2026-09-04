"""End-to-end wiring: a stubbed API response should reach the HTML report."""

import pytest

from xhire.classify import classify
from xhire.client import XClient
from xhire.report import render
from xhire.store import connect, get_cursor, save_posts, set_cursor, top_posts, utcnow

API_RESPONSE = {
    "data": [
        {
            "id": "1800000000000000002",
            "author_id": "u1",
            "text": "We're hiring UGC creators for a paid campaign. $300/video, DM to apply.",
            "created_at": "2026-09-04T10:00:00.000Z",
        },
        {
            "id": "1800000000000000001",
            "author_id": "u2",
            "text": "I'm a UGC creator, DM for my rates!",
            "created_at": "2026-09-04T09:00:00.000Z",
        },
    ],
    "includes": {
        "users": [
            {"id": "u1", "username": "brandco", "name": "Brand Co",
             "public_metrics": {"followers_count": 12000}},
            {"id": "u2", "username": "creator", "name": "A Creator",
             "public_metrics": {"followers_count": 800}},
        ]
    },
    "meta": {"next_token": "abc123"},
}


class StubResponse:
    status_code = 200
    ok = True
    headers: dict = {}

    def json(self):
        return API_RESPONSE


@pytest.fixture
def client(monkeypatch):
    c = XClient("fake-token")
    monkeypatch.setattr(c.session, "get", lambda *a, **kw: StubResponse())
    return c


def test_search_shapes_posts_and_counts_billed_reads(client):
    page = client.search("ugc", max_results=100)

    assert page.billed_reads == 2
    assert page.next_token == "abc123"
    assert page.posts[0]["author_handle"] == "brandco"
    assert page.posts[0]["followers"] == 12000
    assert page.posts[0]["url"] == "https://x.com/brandco/status/1800000000000000002"


def test_since_id_and_next_token_are_mutually_exclusive(client, monkeypatch):
    captured = {}

    def capture(url, params=None, timeout=None):
        captured.update(params)
        return StubResponse()

    monkeypatch.setattr(client.session, "get", capture)
    client.search("ugc", since_id="123", next_token="tok")

    assert captured["next_token"] == "tok"
    assert "since_id" not in captured


def test_full_pipeline_to_html(client, tmp_path):
    page = client.search("ugc", max_results=100)

    with connect(tmp_path / "t.db") as conn:
        scored = []
        for post in page.posts:
            score, verdict, reasons = classify(post["text"])
            scored.append({**post, "query_name": "q", "score": score,
                           "verdict": verdict, "reasons": reasons,
                           "fetched_at": utcnow()})
        assert save_posts(conn, scored) == 2

        # Re-saving the same posts must not duplicate them.
        assert save_posts(conn, scored) == 0

        rows = top_posts(conn, min_score=2)
        assert len(rows) == 1, "the creator self-promo should be filtered out"
        assert rows[0]["author_handle"] == "brandco"

        out = render(conn, rows, tmp_path / "leads.html")

    html = out.read_text()
    assert "brandco" in html
    assert "Likely hiring" in html
    assert "I&#x27;m a UGC creator" not in html


def test_cursor_roundtrip(tmp_path):
    with connect(tmp_path / "t.db") as conn:
        assert get_cursor(conn, "q") is None
        set_cursor(conn, "q", "1800000000000000002")
        assert get_cursor(conn, "q") == "1800000000000000002"
        set_cursor(conn, "q", "1800000000000000009")
        assert get_cursor(conn, "q") == "1800000000000000009"


def test_html_escapes_post_text(tmp_path):
    with connect(tmp_path / "t.db") as conn:
        save_posts(conn, [{
            "id": "1", "author_id": "u", "author_handle": "x", "author_name": "X",
            "followers": 0, "text": "<script>alert(1)</script> hiring UGC creators",
            "created_at": "2026-09-04T10:00:00.000Z", "url": "https://x.com/x/status/1",
            "query_name": "q", "score": 9, "verdict": "likely_hiring",
            "reasons": "test", "fetched_at": utcnow(),
        }])
        out = render(conn, top_posts(conn), tmp_path / "l.html")

    assert "<script>alert(1)</script>" not in out.read_text()
