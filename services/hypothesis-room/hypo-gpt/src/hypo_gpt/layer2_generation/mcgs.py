from __future__ import annotations

from collections import Counter

from hypo_gpt.layer2_generation.idea_tree import get_frontier
from hypo_gpt.models import IdeaTree


class MCGSEngine:
    """Lightweight MCGS controls used by generation orchestration."""

    @staticmethod
    def strategy_distribution(tree: IdeaTree) -> dict[str, float]:
        frontier = get_frontier(tree)
        counter = Counter(node.hypothesis.strategy for node in frontier)
        total = sum(counter.values())
        if total == 0:
            return {}
        return {key: value / total for key, value in counter.items()}

    @staticmethod
    def blocked_strategies(tree: IdeaTree, threshold: float = 0.40) -> list[str]:
        distribution = MCGSEngine.strategy_distribution(tree)
        return [strategy for strategy, ratio in distribution.items() if ratio > threshold]
