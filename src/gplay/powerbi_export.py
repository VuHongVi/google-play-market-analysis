"""python -m gplay.powerbi_export : write the CSV tables the Power BI model imports.

Uses the same cleaned data and scores as results/, so the report and the README agree.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .analysis import GAME_GENRES, HIT, analyse

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "powerbi" / "data"
RATING_BANDS = [(0, 3.5, "<=3.5"), (3.5, 4.0, "3.6-4.0"), (4.0, 4.3, "4.1-4.3"), (4.3, 4.6, "4.4-4.6"), (4.6, 5.0, "4.7-5.0")]
AGE_BUCKETS = [(-1, 30, "<=30 days"), (30, 180, "31-180 days"), (180, 365, "181-365 days"), (365, 10_000, "Over 1 year")]


def label(s: str) -> str:
    return s.replace("_AND_", " & ").replace("_", " ").title()


def _bucket(x, buckets):
    for i, (lo, hi, name) in enumerate(buckets, 1):
        if lo < x <= hi:
            return name, i
    return None, None


def apps(df: pd.DataFrame) -> pd.DataFrame:
    is_game = df.category.eq("GAME") | (df.category.eq("FAMILY") & df.primary_genre.isin(GAME_GENRES))
    snap = df.last_updated.max()
    age = (snap - df.last_updated).dt.days
    stable = df.reviews >= 100
    band = [(_bucket(r, RATING_BANDS) if s and pd.notna(r) else (None, None)) for r, s in zip(df.rating, stable)]
    upd = [_bucket(a, AGE_BUCKETS) for a in age]
    return pd.DataFrame({
        "app": df.app, "category": df.category, "category_label": df.category.map(label),
        "primary_genre": df.primary_genre, "is_game": is_game.astype(int),
        "app_type": is_game.map({True: "Game", False: "Other app"}),
        "game_filed_under": df.category.where(is_game, None).map({"GAME": "Filed under GAME", "FAMILY": "Filed under FAMILY"}),
        "rating": df.rating, "reviews": df.reviews, "installs": df.installs,
        "is_hit": (df.installs >= HIT).astype(int), "price": df.price, "is_paid": df.is_paid.astype(int),
        "pricing": df.is_paid.map({True: "Paid", False: "Free"}), "size_mb": df.size_mb,
        "rating_band": [b[0] for b in band], "rating_band_order": [b[1] for b in band],
        "update_age": [u[0] for u in upd], "update_age_order": [u[1] for u in upd],
        "last_updated": df.last_updated.dt.date,
    })


def segment_table(seg: pd.DataFrame, key: str, flag: str, flagged) -> pd.DataFrame:
    s = seg.copy()
    s.insert(0, "opportunity_rank", range(1, len(s) + 1))
    if key == "category":
        s.insert(2, "category_label", s["category"].map(label))
    s[flag] = s[key].isin(flagged).astype(int)
    return s


def sentiment(m: dict) -> pd.DataFrame:
    rows = [{"category": k, "category_label": label(k), "apps": v["apps"], "neg_share": v["neg_share"],
             "is_game": int(k == "GAME")} for k, v in m["sentiment"]["median_neg_share_by_category"].items()]
    return pd.DataFrame(rows)


def kpis(m: dict) -> pd.DataFrame:
    vals = {
        "raw_rows": m["cleaning"]["raw_rows"], "duplicate_rows_dropped": m["cleaning"]["duplicate_rows_dropped"],
        "labelled_reviews": m["sentiment"]["labelled_reviews"],
        "sentiment_rating_spearman": m["sentiment"]["neg_share_vs_rating_spearman"],
        "rating_installs_spearman": m["drivers"]["rating_installs_spearman"],
    }
    return pd.DataFrame({"metric": list(vals), "value": list(vals.values())})


def reconciliation(m: dict) -> str:
    """DAX query comparing model measures with results/metrics.json (run against the open model)."""
    d, ov, fp = m["drivers"], m["overall"], m["drivers"]["free_vs_paid"]
    rb, ua = d["hit_rate_by_rating_band"], d["hit_rate_by_update_age"]
    cats = {c["category"]: c for c in m["categories"]}
    genres = {g["primary_genre"]: g for g in m["game_genres"]}
    q = chr(34)
    checks = [
        ("[Apps]", m["cleaning"]["apps"], 0),
        ("[Games]", ov["game_apps"], 0),
        ("[Games Filed Under Family]", ov["games_filed_under_family"], 0),
        ("[Hit Rate]", ov["hit_rate"], 1e-6),
        ("[Hit Rate Games]", ov["game_hit_rate"], 1e-6),
        ("[Free Hit Rate]", fp["free_hit_rate"], 1e-6),
        ("[Paid Hit Rate]", fp["paid_hit_rate"], 1e-6),
    ]
    for i, (band, v) in enumerate(rb.items(), 1):
        checks.append((f"CALCULATE ( [Hit Rate], fact_apps[rating_band_order] = {i} )", v["hit_rate"], 1e-6))
    for i, (age, v) in enumerate(ua.items(), 1):
        checks.append((f"CALCULATE ( [Hit Rate], fact_apps[update_age_order] = {i} )", v["hit_rate"], 1e-6))
    for k in ("EDUCATION", "GAME", "BUSINESS"):
        checks.append((f"CALCULATE ( [Hit Rate], fact_apps[category] = {q}{k}{q} )", cats[k]["hit_rate"], 1e-4))
    for k in ("Racing", "Casual", "Trivia"):
        checks.append((f"CALCULATE ( SUM ( fact_genre_scores[top_decile_share] ), fact_genre_scores[primary_genre] = {q}{k}{q} )", genres[k]["top_decile_share"], 1e-4))
    checks.append((f"CALCULATE ( [Negative Review Share], fact_category_sentiment[category] = {q}GAME{q} )",
                   m["sentiment"]["median_neg_share_by_category"]["GAME"]["neg_share"], 1e-6))
    rows = ",\n".join(
        f'ROW ( "check_id", {i}, "measure", "{e.replace(q, chr(39))}", "expected", {float(v)!r}, "actual", {e}, "tol", {tol:.12f} )'
        for i, (e, v, tol) in enumerate(checks, 1))
    return ("// Generated by python -m gplay.powerbi_export from results/metrics.json.\n"
            "// Run against the open GooglePlay model; every row must say PASS.\n"
            f"EVALUATE\nVAR t = UNION (\n{rows}\n)\n"
            'RETURN ADDCOLUMNS ( t, "result", IF ( ABS ( [actual] - [expected] ) <= [tol], "PASS", "FAIL" ) )\n'
            "ORDER BY [check_id]\n")


def main() -> None:
    m, df, cats, genres = analyse()
    OUT.mkdir(parents=True, exist_ok=True)
    tables = {
        "fact_apps": apps(df),
        "fact_category_scores": segment_table(cats, "category", "is_highlight", ["GAME"]),
        "fact_genre_scores": segment_table(genres, "primary_genre", "is_recommended", list(genres.primary_genre[:3])),
        "fact_category_sentiment": sentiment(m),
        "kpi_metrics": kpis(m),
    }
    for name, t in tables.items():
        t.to_csv(OUT / f"{name}.csv", index=False, float_format="%.10g", encoding="utf-8")
        print(f"{name:24s} {len(t):>6,} rows")
    dax = ROOT / "powerbi" / "tools" / "reconciliation_query.dax"
    dax.write_text(reconciliation(m), encoding="utf-8")
    print("reconciliation ->", dax.relative_to(ROOT))


if __name__ == "__main__":
    main()
