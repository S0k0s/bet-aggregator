from app.odds.adapter import _sport_key_for


def test_maps_known_competitions_despite_naming_differences():
    assert _sport_key_for("UEFA Champions League") == "soccer_uefa_champs_league"
    assert _sport_key_for("INTERNATIONAL - CHAMPIONS LEAGUE PLAYOFF ROUND") == "soccer_uefa_champs_league"
    assert _sport_key_for("Spanish La Liga") == "soccer_spain_la_liga"
    assert _sport_key_for("England: Premier League") == "soccer_epl"


def test_greece_super_league_requires_both_keywords():
    assert _sport_key_for("Greece Super League") == "soccer_greece_super_league"
    assert _sport_key_for("Greece") is None
    assert _sport_key_for("Greece Cup") is None


def test_serie_a_disambiguates_italy_from_brazil():
    assert _sport_key_for("Italy: Serie A") == "soccer_italy_serie_a"
    assert _sport_key_for("Brazil: Serie A") is None
    assert _sport_key_for("Brazil Serie A") is None


def test_unmapped_or_missing_competition_returns_none():
    assert _sport_key_for("Mexico: Liga MX") is None
    assert _sport_key_for(None) is None
    assert _sport_key_for("") is None
