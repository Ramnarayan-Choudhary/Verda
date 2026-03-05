"""
Elo Rating System — arXiv:2502.18864 (AI Co-Scientist tournament ranking).

Implements standard Elo with K-factor tuning for hypothesis pairwise debates.
Supports LLM-judged pairwise comparisons with multi-criteria evaluation.
"""

from __future__ import annotations

import random

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_ELO = 1500.0
K_FACTOR = 32


def expected_score(rating_a: float, rating_b: float) -> float:
    """Expected win probability for player A against player B."""
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def update_elo(
    winner_rating: float,
    loser_rating: float,
    k: int = K_FACTOR,
    is_tie: bool = False,
) -> tuple[float, float]:
    """Update Elo ratings after a match.

    Args:
        winner_rating: Current Elo of the winner (or player A if tie).
        loser_rating: Current Elo of the loser (or player B if tie).
        k: K-factor controlling rating volatility.
        is_tie: If True, both players get 0.5 score.

    Returns:
        Tuple of (new_winner_rating, new_loser_rating).
    """
    expected_a = expected_score(winner_rating, loser_rating)
    expected_b = 1.0 - expected_a

    if is_tie:
        score_a, score_b = 0.5, 0.5
    else:
        score_a, score_b = 1.0, 0.0

    new_a = winner_rating + k * (score_a - expected_a)
    new_b = loser_rating + k * (score_b - expected_b)

    return new_a, new_b


def select_tournament_pairs(
    hypothesis_ids: list[str],
    elo_ratings: dict[str, float],
    n_rounds: int = 3,
) -> list[tuple[str, str]]:
    """Select diverse pairings for tournament rounds.

    Uses proximity-based pairing: sort by Elo, pair adjacent hypotheses
    to get competitive matches, then shuffle for diversity.

    Args:
        hypothesis_ids: List of hypothesis IDs to pair.
        elo_ratings: Current Elo ratings per hypothesis.
        n_rounds: Number of tournament rounds.

    Returns:
        List of (id_a, id_b) tuples.
    """
    if len(hypothesis_ids) < 2:
        return []

    pairs: list[tuple[str, str]] = []

    for _ in range(n_rounds):
        # Sort by Elo for competitive pairing
        sorted_ids = sorted(hypothesis_ids, key=lambda h: elo_ratings.get(h, DEFAULT_ELO))

        # Pair adjacent (similar-strength matchups)
        round_pairs = []
        for i in range(0, len(sorted_ids) - 1, 2):
            round_pairs.append((sorted_ids[i], sorted_ids[i + 1]))

        # If odd count, pair the leftover with a random opponent
        if len(sorted_ids) % 2 == 1:
            last = sorted_ids[-1]
            opponent = random.choice(sorted_ids[:-1])
            round_pairs.append((last, opponent))

        # Shuffle round pairs for diversity
        random.shuffle(round_pairs)
        pairs.extend(round_pairs)

    # Deduplicate exact pairs (keep first occurrence)
    seen: set[tuple[str, str]] = set()
    unique_pairs = []
    for a, b in pairs:
        key = (min(a, b), max(a, b))
        if key not in seen:
            seen.add(key)
            unique_pairs.append((a, b))

    logger.info(
        "elo.pairs_selected",
        total_pairs=len(unique_pairs),
        n_hypotheses=len(hypothesis_ids),
        n_rounds=n_rounds,
    )
    return unique_pairs


def run_tournament_sync(
    hypothesis_ids: list[str],
    results: list[tuple[str, str, str]],  # (id_a, id_b, winner: 'a'|'b'|'tie')
    initial_ratings: dict[str, float] | None = None,
) -> dict[str, float]:
    """Process tournament results and return final Elo ratings.

    Args:
        hypothesis_ids: All hypothesis IDs in the tournament.
        results: List of (id_a, id_b, outcome) tuples.
        initial_ratings: Starting Elo ratings (defaults to 1500 for all).

    Returns:
        Dict mapping hypothesis_id → final Elo rating.
    """
    ratings = {h: DEFAULT_ELO for h in hypothesis_ids}
    if initial_ratings:
        ratings.update(initial_ratings)

    for id_a, id_b, outcome in results:
        if outcome == "a":
            ratings[id_a], ratings[id_b] = update_elo(ratings[id_a], ratings[id_b])
        elif outcome == "b":
            ratings[id_b], ratings[id_a] = update_elo(ratings[id_b], ratings[id_a])
        else:  # tie
            ratings[id_a], ratings[id_b] = update_elo(
                ratings[id_a], ratings[id_b], is_tie=True
            )

    return ratings
