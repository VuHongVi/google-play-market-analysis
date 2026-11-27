"""Google Play market analysis: where should a small studio build its next app or game?

Cleans the 2018 Google Play scrape, then scores every category (and every game genre) on
demand vs competition. Every number in README.md comes from results/metrics.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
RESULTS = ROOT / "results"

HIT = 1_000_000        # "hit" = at least 1M installs (lower bound of the install bucket)
MIN_APPS = 50          # categories / genres smaller than this are too thin to score
TOP_SHARE = 0.10       # concentration = share of installs held by the top 10% of apps
TOP_N = 10             # whole-store concentration only
MIN_GENRE_APPS = 30    # game genres are smaller; same idea
# Google Play game genres. Many games are filed under FAMILY instead of GAME, so a game is
# any app in GAME, or a FAMILY app whose primary genre is one of these. Educational, Music and
# Sports are left out: in FAMILY/SPORTS they are mostly non-game apps.
GAME_GENRES = ["Action", "Adventure", "Arcade", "Board", "Card", "Casino", "Casual", "Puzzle",
               "Racing", "Role Playing", "Simulation", "Strategy", "Trivia", "Word"]


# ---------------------------------------------------------------- cleaning
def _size_mb(s: str) -> float:
    if not isinstance(s, str) or s == "Varies with device":
        return np.nan
    if s.endswith("M"):
        return float(s[:-1])
    if s.endswith("k"):
        return float(s[:-1]) / 1024
    return np.nan


def load_apps(path: Path | None = None) -> tuple[pd.DataFrame, dict]:
    raw = pd.read_csv(path or RAW / "googleplaystore.csv")
    log = {"raw_rows": int(len(raw))}

    # one scraped row has every field shifted one column left (Category = "1.9")
    bad = raw["Category"].str.fullmatch(r"[A-Z_]+").fillna(False) == False  # noqa: E712
    log["malformed_rows_dropped"] = int(bad.sum())
    df = raw[~bad].copy()

    df["reviews"] = pd.to_numeric(df["Reviews"], errors="raise").astype("int64")
    df["installs"] = df["Installs"].str.replace(r"[+,]", "", regex=True).astype("int64")
    df["price"] = df["Price"].str.replace("$", "", regex=False).astype(float)
    df["size_mb"] = df["Size"].map(_size_mb)
    df["last_updated"] = pd.to_datetime(df["Last Updated"], format="%B %d, %Y")
    df["is_paid"] = df["Type"].eq("Paid")
    df["primary_genre"] = df["Genres"].str.split(";").str[0]

    # the scrape lists the same app several times (once per chart it appeared in);
    # keep the most recent observation = the row with the most reviews
    before = len(df)
    df = df.sort_values("reviews", ascending=False).drop_duplicates("App", keep="first")
    log["duplicate_rows_dropped"] = int(before - len(df))
    log["apps"] = int(len(df))
    log["missing_rating_share"] = float(df["Rating"].isna().mean())
    log["snapshot_date"] = str(df["last_updated"].max().date())
    log["size_varies_share"] = float(df["size_mb"].isna().mean())
    df = df.rename(columns={"App": "app", "Category": "category", "Rating": "rating",
                            "Content Rating": "content_rating"})
    cols = ["app", "category", "primary_genre", "rating", "reviews", "installs", "price",
            "is_paid", "size_mb", "last_updated", "content_rating"]
    return df[cols].reset_index(drop=True), log


# ---------------------------------------------------------------- market scoring
def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    d = 1 + z**2 / n
    c = (p + z**2 / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / d
    return (c - h, c + h)


def games_of(df: pd.DataFrame) -> pd.DataFrame:
    family_games = df.category.eq("FAMILY") & df.primary_genre.isin(GAME_GENRES)
    return df[df.category.eq("GAME") | family_games]


def score_segments(df: pd.DataFrame, by: str, min_apps: int = MIN_APPS) -> pd.DataFrame:
    """Demand vs competition for each segment (category or genre)."""
    rows = []
    for seg, g in df.groupby(by):
        if len(g) < min_apps:
            continue
        total = g["installs"].sum()
        # top 10% (not top 10) so small segments are not "concentrated" just by being small
        top = g["installs"].nlargest(max(1, int(np.ceil(TOP_SHARE * len(g))))).sum()
        hits = int((g["installs"] >= HIT).sum())
        lo, hi = wilson(hits, len(g))
        rows.append({
            by: seg,
            "apps": len(g),
            "hit_rate": hits / len(g),
            "hit_rate_low": lo,
            "hit_rate_high": hi,
            "median_installs": float(g["installs"].median()),
            "top_decile_share": top / total if total else np.nan,
            "median_rating": float(g["rating"].median()),
            "paid_share": float(g["is_paid"].mean()),
        })
    s = pd.DataFrame(rows)
    # opportunity: a hit is likely (demand) and the market isn't owned by a few apps (competition)
    s["opportunity"] = s["hit_rate"].rank(pct=True) + (1 - s["top_decile_share"]).rank(pct=True)
    return s.sort_values("opportunity", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------- drivers
def drivers(df: pd.DataFrame) -> dict:
    out = {}
    rated = df.dropna(subset=["rating"])
    rho = stats.spearmanr(rated["rating"], rated["installs"])
    out["rating_installs_spearman"] = float(rho.statistic)
    # hit rate by rating band (apps with 100+ reviews so the rating is stable)
    stable = rated[rated["reviews"] >= 100]
    bands = pd.cut(stable["rating"], [0, 3.5, 4.0, 4.3, 4.6, 5.0],
                   labels=["<=3.5", "3.6-4.0", "4.1-4.3", "4.4-4.6", "4.7-5.0"])
    out["hit_rate_by_rating_band"] = {
        str(b): {"apps": int(len(g)), "hit_rate": float((g["installs"] >= HIT).mean())}
        for b, g in stable.groupby(bands, observed=True)
    }

    free, paid = df[~df.is_paid], df[df.is_paid]
    mw = stats.mannwhitneyu(free["installs"], paid["installs"])
    out["free_vs_paid"] = {
        "free_apps": int(len(free)), "paid_apps": int(len(paid)),
        "free_hit_rate": float((free["installs"] >= HIT).mean()),
        "paid_hit_rate": float((paid["installs"] >= HIT).mean()),
        "free_median_installs": float(free["installs"].median()),
        "paid_median_installs": float(paid["installs"].median()),
        "mannwhitney_p": float(mw.pvalue),
        "free_median_rating": float(free["rating"].median()),
        "paid_median_rating": float(paid["rating"].median()),
        "paid_median_price": float(paid["price"].median()),
        "paid_share_under_5usd": float((paid["price"] < 5).mean()),
    }

    snap = df["last_updated"].max()
    age = (snap - df["last_updated"]).dt.days
    buckets = pd.cut(age, [-1, 30, 180, 365, 10_000], labels=["<=30d", "31-180d", "181-365d", ">1y"])
    out["hit_rate_by_update_age"] = {
        str(b): {"apps": int(len(g)), "hit_rate": float((g["installs"] >= HIT).mean())}
        for b, g in df.groupby(buckets, observed=True)
    }
    sized = df.dropna(subset=["size_mb"])
    out["size_installs_spearman"] = float(stats.spearmanr(sized["size_mb"], sized["installs"]).statistic)
    return out


def sentiment(apps: pd.DataFrame, path: Path | None = None) -> dict:
    r = pd.read_csv(path or RAW / "googleplaystore_user_reviews.csv").dropna(subset=["Sentiment"])
    per_app = r.groupby("App").agg(reviews=("Sentiment", "size"),
                                   neg_share=("Sentiment", lambda s: (s == "Negative").mean()))
    per_app = per_app[per_app["reviews"] >= 20].join(apps.set_index("app")[["category", "rating"]], how="inner")
    rho = stats.spearmanr(per_app["neg_share"], per_app["rating"], nan_policy="omit")
    by_cat = (per_app.groupby("category").agg(apps=("neg_share", "size"), neg_share=("neg_share", "median"))
              .query("apps >= 15").sort_values("neg_share", ascending=False))
    return {
        "labelled_reviews": int(len(r)),
        "apps_with_20plus_reviews": int(len(per_app)),
        "neg_share_vs_rating_spearman": float(rho.statistic),
        "median_neg_share_by_category": {k: {"apps": int(v.apps), "neg_share": float(v.neg_share)}
                                         for k, v in by_cat.iterrows()},
    }


# ---------------------------------------------------------------- run
def analyse() -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df, log = load_apps()
    cats = score_segments(df, "category")
    games = games_of(df)
    genres = score_segments(games[games.primary_genre.isin(GAME_GENRES)], "primary_genre", MIN_GENRE_APPS)
    overall_hit = float((df.installs >= HIT).mean())
    metrics = {
        "cleaning": log,
        "overall": {
            "hit_rate": overall_hit,
            "median_installs": float(df.installs.median()),
            "top10_share_all": float(df.installs.nlargest(TOP_N).sum() / df.installs.sum()),
            "game_apps": int(len(games)),
            "games_filed_under_family": int(games.category.eq("FAMILY").sum()),
            "game_hit_rate": float((games.installs >= HIT).mean()),
            "game_paid_share": float(games.is_paid.mean()),
        },
        "categories": cats.round(4).to_dict(orient="records"),
        "game_genres": genres.round(4).to_dict(orient="records"),
        "drivers": drivers(df),
        "sentiment": sentiment(df),
        "params": {"hit_threshold": HIT, "min_apps": MIN_APPS, "min_genre_apps": MIN_GENRE_APPS,
                   "top_n": TOP_N, "top_share": TOP_SHARE, "game_genres": GAME_GENRES},
    }
    return metrics, df, cats, genres


def _round(o, nd=6):
    if isinstance(o, dict):
        return {k: _round(v, nd) for k, v in o.items()}
    if isinstance(o, list):
        return [_round(v, nd) for v in o]
    if isinstance(o, (float, np.floating)):
        return round(float(o), nd)
    if isinstance(o, np.integer):
        return int(o)
    return o


def write_metrics(m: dict) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    p = RESULTS / "metrics.json"
    p.write_text(json.dumps(_round(m), indent=2) + "\n", encoding="utf-8")
    return p
