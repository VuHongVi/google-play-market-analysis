import numpy as np
import pandas as pd
import pytest

from gplay import analysis as a


def test_size_parsing():
    assert a._size_mb("19M") == 19.0
    assert a._size_mb("512k") == pytest.approx(0.5)
    assert np.isnan(a._size_mb("Varies with device"))


def test_wilson_interval_contains_rate_and_is_bounded():
    lo, hi = a.wilson(30, 100)
    assert 0 <= lo < 0.30 < hi <= 1
    assert a.wilson(0, 10)[0] == pytest.approx(0, abs=1e-12)


def _apps(n, installs, cat="X", genre="Action"):
    return pd.DataFrame({"app": [f"{cat}{i}" for i in range(n)], "category": cat, "primary_genre": genre,
                         "installs": installs, "rating": 4.2, "is_paid": False})


def test_concentration_is_size_neutral():
    # two segments with identical shape but different size get the same top-decile share
    small = _apps(50, [10] * 45 + [1000] * 5, "S")
    big = _apps(500, [10] * 450 + [1000] * 50, "B")
    s = a.score_segments(pd.concat([small, big]), "category")
    assert s.set_index("category").loc["S", "top_decile_share"] == pytest.approx(
        s.set_index("category").loc["B", "top_decile_share"])


def test_opportunity_prefers_high_hit_low_concentration():
    good = _apps(60, [a.HIT] * 40 + [a.HIT // 10] * 20, "GOOD")
    bad = _apps(60, [100] * 54 + [10 * a.HIT] * 6, "BAD")
    s = a.score_segments(pd.concat([good, bad]), "category")
    assert s.iloc[0]["category"] == "GOOD"


def test_games_include_family_game_genres():
    df = pd.DataFrame({"category": ["GAME", "FAMILY", "FAMILY", "TOOLS"],
                       "primary_genre": ["Action", "Puzzle", "Education", "Puzzle"]})
    assert len(a.games_of(df)) == 2


def test_real_data_contract():
    if not (a.RAW / "googleplaystore.csv").exists():
        pytest.skip("raw data not downloaded")
    df, log = a.load_apps()
    assert df["app"].is_unique
    assert log["malformed_rows_dropped"] == 1
    assert (df["installs"] >= 0).all() and df["rating"].dropna().between(1, 5).all()
