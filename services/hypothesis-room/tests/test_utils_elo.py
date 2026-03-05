from vreda_hypothesis.utils import elo


def test_expected_score_symmetry():
    assert elo.expected_score(1500, 1500) == 0.5
    assert elo.expected_score(1600, 1400) > 0.5


def test_update_elo_win_and_tie():
    winner, loser = elo.update_elo(1500, 1500)
    assert winner > 1500 and loser < 1500
    tie_a, tie_b = elo.update_elo(1500, 1500, is_tie=True)
    assert tie_a == tie_b


def test_select_tournament_pairs_even_count():
    ids = [f"hyp-{i}" for i in range(4)]
    ratings = {id_: 1500 + i * 10 for i, id_ in enumerate(ids)}
    pairs = elo.select_tournament_pairs(ids, ratings, n_rounds=2)
    assert pairs  # non-empty
    assert all(len(pair) == 2 for pair in pairs)
