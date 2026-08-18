from app.history.grader import grade_pick


def test_1x2_hit_and_miss():
    assert grade_pick("1X2", "1", "Arsenal", "Chelsea", 2, 0) == "hit"
    assert grade_pick("1X2", "1", "Arsenal", "Chelsea", 0, 2) == "miss"
    assert grade_pick("1X2", "X", "Arsenal", "Chelsea", 1, 1) == "hit"


def test_double_chance():
    assert grade_pick("Double Chance", "1X", "Arsenal", "Chelsea", 1, 1) == "hit"
    assert grade_pick("Double Chance", "1X", "Arsenal", "Chelsea", 0, 1) == "miss"
    assert grade_pick("Double Chance", "X2", "Arsenal", "Chelsea", 0, 0) == "hit"


def test_btts():
    assert grade_pick("BTTS", "Yes", "Arsenal", "Chelsea", 1, 1) == "hit"
    assert grade_pick("BTTS", "Yes", "Arsenal", "Chelsea", 1, 0) == "miss"
    assert grade_pick("BTTS", "No", "Arsenal", "Chelsea", 0, 0) == "hit"


def test_draw_no_bet_hit_miss_and_push():
    assert grade_pick("Draw No Bet", "Arsenal Draw No Bet", "Arsenal", "Chelsea", 2, 1) == "hit"
    assert grade_pick("Draw No Bet", "Arsenal Draw No Bet", "Arsenal", "Chelsea", 0, 1) == "miss"
    assert grade_pick("Draw No Bet", "Arsenal Draw No Bet", "Arsenal", "Chelsea", 1, 1) == "push"


def test_total_goals_over_under_and_push():
    assert grade_pick("Total Goals", "Over 2.5 Match Goals", "Arsenal", "Chelsea", 2, 1) == "hit"
    assert grade_pick("Total Goals", "Over 2.5 Match Goals", "Arsenal", "Chelsea", 1, 0) == "miss"
    assert grade_pick("Total Goals", "Under 2.5 Match Goals", "Arsenal", "Chelsea", 1, 0) == "hit"
    assert grade_pick("Total Goals", "Over 3", "Arsenal", "Chelsea", 2, 1) == "push"


def test_correct_score_named_team_home_or_away():
    # Named team is home: score order is that team's goals first.
    assert grade_pick("Correct Score", "Arsenal 2-0", "Arsenal", "Chelsea", 2, 0) == "hit"
    assert grade_pick("Correct Score", "Arsenal 2-0", "Arsenal", "Chelsea", 0, 2) == "miss"
    # Named team is away: score order still that team's goals first, so it
    # maps onto (away, home) not (home, away).
    assert grade_pick("Correct Score", "Chelsea 2-0", "Arsenal", "Chelsea", 0, 2) == "hit"


def test_ungradeable_market_returns_unknown():
    assert grade_pick("Goal Scorer - Anytime", "Talisca To Score Anytime", "Fenerbahce", "Lyon", 1, 0) == "unknown"
    assert grade_pick("1X2", "garbage", "Arsenal", "Chelsea", 1, 0) == "unknown"
