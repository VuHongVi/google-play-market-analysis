"""Write the GooglePlay semantic model as TMDL from the CSVs in powerbi/data.

    python powerbi/tools/build_model.py

Column types come from the CSVs; measures are listed below. Lineage tags are deterministic
(uuid5 of the object path) so re-running gives a clean diff. Auto date/time is off.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tmdl import write_model  # noqa: E402

MODEL = "GooglePlay"
FORMATS = {
    "hit_rate": "0.0%", "hit_rate_low": "0.0%", "hit_rate_high": "0.0%", "top_decile_share": "0.0%",
    "paid_share": "0.0%", "neg_share": "0.0%", "median_rating": "0.0", "opportunity": "0.00",
    "median_installs": "#,0", "installs": "#,0", "reviews": "#,0", "apps": "#,0", "price": "$0.00",
    "rating": "0.0", "size_mb": "0.0",
}
SORT_BY = {"rating_band": "rating_band_order", "update_age": "update_age_order"}
HIDDEN = {"rating_band_order", "update_age_order"}

A = "fact_apps"
MEASURES = [
    ("Apps", f"COUNTROWS ( {A} )", "#,0", "Market", "Unique apps after cleaning."),
    ("Games", f"CALCULATE ( [Apps], {A}[is_game] = 1 )", "#,0", "Market", "GAME apps + FAMILY apps with a game genre."),
    ("Games Filed Under Family", f"CALCULATE ( [Apps], {A}[game_filed_under] = \"Filed under FAMILY\" )", "#,0", "Market", ""),
    ("Games Filed Under Family %", "DIVIDE ( [Games Filed Under Family], [Games] )", "0%", "Market", "Share of games a Category = GAME filter would miss."),
    ("Hit Rate", f"DIVIDE ( SUM ( {A}[is_hit] ), [Apps] )", "0.0%", "Hits", "Share of apps with 1M+ installs (lower bound of the bucket)."),
    ("Hit Rate Games", f"CALCULATE ( [Hit Rate], {A}[is_game] = 1 )", "0.0%", "Hits", ""),
    ("Free Hit Rate", f"CALCULATE ( [Hit Rate], {A}[pricing] = \"Free\" )", "0.0%", "Hits", ""),
    ("Paid Hit Rate", f"CALCULATE ( [Hit Rate], {A}[pricing] = \"Paid\" )", "0.0%", "Hits", ""),
    ("Median Rating", f"MEDIAN ( {A}[rating] )", "0.0", "Market", ""),
    ("Negative Review Share", "SUM ( fact_category_sentiment[neg_share] )", "0%", "Sentiment",
     "Median share of an app's labelled reviews that are negative."),
]

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    write_model(root, MODEL, FORMATS, SORT_BY, HIDDEN, MEASURES)
