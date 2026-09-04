"""The cap must hold even though a request's cost is unknown until it returns."""

import pytest

from xhire.budget import BudgetExceeded, BudgetGuard
from xhire.store import connect, month_spend


@pytest.fixture
def conn(tmp_path):
    with connect(tmp_path / "test.db") as c:
        yield c


def test_check_passes_when_budget_is_free(conn):
    guard = BudgetGuard(conn, monthly_usd=10.0, per_run_usd=5.0, max_results=100)
    guard.check()  # 100 * $0.005 = $0.50, well inside both caps


def test_per_run_cap_blocks_before_the_request_goes_out(conn):
    # $1.00 run cap, worst case $0.50/request -> the third request is refused.
    guard = BudgetGuard(conn, monthly_usd=100.0, per_run_usd=1.0, max_results=100)
    guard.check()
    guard.settle("q", 100)
    guard.check()
    guard.settle("q", 100)
    with pytest.raises(BudgetExceeded, match="per-run cap"):
        guard.check()


def test_monthly_cap_blocks_across_runs(conn):
    spent = BudgetGuard(conn, monthly_usd=1.0, per_run_usd=100.0, max_results=100)
    spent.settle("q", 100)
    spent.settle("q", 100)

    # A fresh run: run spend resets, month spend does not.
    fresh = BudgetGuard(conn, monthly_usd=1.0, per_run_usd=100.0, max_results=100)
    assert fresh.run_spend == 0.0
    with pytest.raises(BudgetExceeded, match="monthly cap"):
        fresh.check()


def test_cap_reserves_worst_case_not_actual(conn):
    # Only 1 post came back ($0.005), but the guard must still assume the next
    # request could return a full page ($0.50), or the cap could be breached by
    # a request already in flight. $0.005 + $0.50 > $0.50 cap, so this refuses
    # even though actual spend is a hundredth of the budget.
    guard = BudgetGuard(conn, monthly_usd=0.50, per_run_usd=100.0, max_results=100)
    guard.settle("q", 1)
    assert guard.month_spend == pytest.approx(0.005)
    with pytest.raises(BudgetExceeded, match="monthly cap"):
        guard.check()


def test_settle_records_actual_cost(conn):
    guard = BudgetGuard(conn, monthly_usd=10.0, per_run_usd=5.0, max_results=100)
    cost = guard.settle("ugc-direct-ask", 37)
    assert cost == pytest.approx(0.185)
    assert month_spend(conn) == pytest.approx(0.185)
    assert guard.run_reads == 37
