"""Client-side spend cap.

X bills per post returned, so the cost of a request is not known until it comes
back. The guard therefore reserves the worst case (a full page) before letting a
request go out, and settles up with the real count afterwards. That means the cap
can never be breached by a request already in flight.
"""

from __future__ import annotations

import sqlite3

from . import COST_PER_READ_USD
from .store import month_spend, record_usage


class BudgetExceeded(Exception):
    """Raised when the next request could push spend past a configured cap."""


class BudgetGuard:
    def __init__(
        self,
        conn: sqlite3.Connection,
        monthly_usd: float,
        per_run_usd: float,
        max_results: int,
    ) -> None:
        self.conn = conn
        self.monthly_usd = monthly_usd
        self.per_run_usd = per_run_usd
        self.worst_case_request = max_results * COST_PER_READ_USD
        self.run_spend = 0.0
        self.run_reads = 0

    @property
    def month_spend(self) -> float:
        return month_spend(self.conn)

    def check(self) -> None:
        """Raise if a full-page response would breach either cap."""
        projected_run = self.run_spend + self.worst_case_request
        if projected_run > self.per_run_usd:
            raise BudgetExceeded(
                f"per-run cap ${self.per_run_usd:.2f} would be exceeded "
                f"(spent ${self.run_spend:.2f} this run, next request could "
                f"cost up to ${self.worst_case_request:.2f})"
            )

        projected_month = self.month_spend + self.worst_case_request
        if projected_month > self.monthly_usd:
            raise BudgetExceeded(
                f"monthly cap ${self.monthly_usd:.2f} would be exceeded "
                f"(spent ${self.month_spend:.2f} this month, next request could "
                f"cost up to ${self.worst_case_request:.2f})"
            )

    def settle(self, query_name: str, posts_read: int) -> float:
        """Record what a completed request actually cost."""
        cost = posts_read * COST_PER_READ_USD
        record_usage(self.conn, query_name, posts_read, cost)
        self.run_spend += cost
        self.run_reads += posts_read
        return cost
