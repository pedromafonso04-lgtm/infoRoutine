from src.ai.token_budget import TokenBudget


def test_initial_state():
    budget = TokenBudget(1_000_000)
    assert budget.total == 1_000_000
    assert budget.used == 0
    assert budget.remaining == 1_000_000
    assert not budget.is_exhausted


def test_record_usage():
    budget = TokenBudget(10_000)
    budget.record_usage(3_000)
    assert budget.used == 3_000
    assert budget.remaining == 7_000


def test_can_spend_within_budget():
    budget = TokenBudget(10_000)
    assert budget.can_spend(5_000)
    assert budget.can_spend(10_000)
    assert not budget.can_spend(10_001)


def test_can_spend_after_usage():
    budget = TokenBudget(10_000)
    budget.record_usage(8_000)
    assert budget.can_spend(2_000)
    assert not budget.can_spend(2_001)


def test_exhaustion():
    budget = TokenBudget(5_000)
    assert not budget.is_exhausted
    budget.record_usage(5_000)
    assert budget.is_exhausted
    assert budget.remaining == 0


def test_over_usage_clamps_remaining():
    budget = TokenBudget(5_000)
    budget.record_usage(7_000)
    assert budget.remaining == 0
    assert budget.is_exhausted


def test_stats():
    budget = TokenBudget(100_000)
    budget.record_usage(25_000)
    stats = budget.stats()
    assert stats["total_budget"] == 100_000
    assert stats["tokens_used"] == 25_000
    assert stats["tokens_remaining"] == 75_000


def test_multiple_record_usage():
    budget = TokenBudget(50_000)
    budget.record_usage(10_000)
    budget.record_usage(15_000)
    budget.record_usage(5_000)
    assert budget.used == 30_000
    assert budget.remaining == 20_000
