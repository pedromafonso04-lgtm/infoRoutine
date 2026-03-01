import logging

logger = logging.getLogger(__name__)


class TokenBudget:
    def __init__(self, total_budget: int) -> None:
        self._total = total_budget
        self._used = 0

    @property
    def total(self) -> int:
        return self._total

    @property
    def used(self) -> int:
        return self._used

    @property
    def remaining(self) -> int:
        return max(0, self._total - self._used)

    def can_spend(self, estimated_tokens: int) -> bool:
        return self._used + estimated_tokens <= self._total

    def record_usage(self, tokens: int) -> None:
        self._used += tokens
        logger.info(
            "Token usage: %d / %d (%.1f%% used)",
            self._used,
            self._total,
            (self._used / self._total) * 100,
        )

    @property
    def is_exhausted(self) -> bool:
        return self._used >= self._total

    def stats(self) -> dict[str, int]:
        return {
            "total_budget": self._total,
            "tokens_used": self._used,
            "tokens_remaining": self.remaining,
        }
