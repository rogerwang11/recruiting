"""Thin client for the X API v2 recent-search endpoint."""

from __future__ import annotations

import time
from dataclasses import dataclass

import requests

SEARCH_URL = "https://api.x.com/2/tweets/search/recent"

TWEET_FIELDS = "created_at,author_id,public_metrics,entities"
USER_FIELDS = "username,name,public_metrics"


class XAPIError(Exception):
    """A non-retryable error from the X API."""


@dataclass
class Page:
    posts: list[dict]
    next_token: str | None
    billed_reads: int


class XClient:
    def __init__(self, bearer_token: str, timeout: int = 30) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {bearer_token}",
                "User-Agent": "xhire/0.1",
            }
        )
        self.timeout = timeout

    def search(
        self,
        query: str,
        max_results: int = 100,
        since_id: str | None = None,
        next_token: str | None = None,
    ) -> Page:
        params: dict[str, str | int] = {
            "query": query,
            "max_results": max_results,
            "tweet.fields": TWEET_FIELDS,
            "expansions": "author_id",
            "user.fields": USER_FIELDS,
        }
        # since_id and next_token are mutually exclusive: paginating within a
        # result set must not re-anchor to the cursor.
        if next_token:
            params["next_token"] = next_token
        elif since_id:
            params["since_id"] = since_id

        payload = self._get(params)

        raw_posts = payload.get("data", [])
        users = {
            u["id"]: u for u in payload.get("includes", {}).get("users", [])
        }
        meta = payload.get("meta", {})

        posts = [self._shape(p, users.get(p.get("author_id"))) for p in raw_posts]
        return Page(
            posts=posts,
            next_token=meta.get("next_token"),
            # Bill against what came back, which is what X charges for.
            billed_reads=len(raw_posts),
        )

    def _get(self, params: dict, attempt: int = 0) -> dict:
        response = self.session.get(SEARCH_URL, params=params, timeout=self.timeout)

        if response.status_code == 429:
            if attempt >= 3:
                raise XAPIError("rate limited by X after 3 retries")
            wait = self._retry_after(response, attempt)
            time.sleep(wait)
            return self._get(params, attempt + 1)

        if response.status_code == 401:
            raise XAPIError(
                "401 from X: bearer token is missing, wrong, or lacks read access."
            )
        if response.status_code == 403:
            raise XAPIError(
                f"403 from X: {response.text[:300]}\n"
                "Usually means the project has no active credits, or the app is "
                "not attached to a project in the developer console."
            )
        if response.status_code >= 500:
            if attempt >= 3:
                raise XAPIError(f"X returned {response.status_code} after 3 retries")
            time.sleep(2**attempt)
            return self._get(params, attempt + 1)
        if not response.ok:
            raise XAPIError(f"{response.status_code} from X: {response.text[:300]}")

        return response.json()

    @staticmethod
    def _retry_after(response: requests.Response, attempt: int) -> float:
        """Prefer X's own reset header; fall back to exponential backoff."""
        reset = response.headers.get("x-rate-limit-reset")
        if reset and reset.isdigit():
            wait = int(reset) - time.time()
            if 0 < wait <= 900:
                return wait + 1
        return float(2 ** (attempt + 1))

    @staticmethod
    def _shape(post: dict, user: dict | None) -> dict:
        handle = user["username"] if user else "unknown"
        followers = 0
        if user:
            followers = user.get("public_metrics", {}).get("followers_count", 0)
        return {
            "id": post["id"],
            "author_id": post.get("author_id", ""),
            "author_handle": handle,
            "author_name": user.get("name", "") if user else "",
            "followers": followers,
            "text": post.get("text", ""),
            "created_at": post.get("created_at", ""),
            "url": f"https://x.com/{handle}/status/{post['id']}",
        }
