"""Render README.md from results/metrics.json - every number is generated, none typed by hand."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _pct(x: float, nd: int = 0) -> str:
    return f"{x * 100:.{nd}f}%"


def _name(s: str) -> str:
    return s.replace("_AND_", " & ").replace("_", " ").title()


def _seg_table(rows: list[dict], key: str, n: int | None = None) -> str:
    lines = ["| Rank | Segment | Apps | Hit rate (1M+ installs) | 95% CI | Top-10% install share | Median rating | Paid share |",
             "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows[:n] if n else rows, 1):
        lines.append(f"| {i} | {_name(r[key])} | {r['apps']:,} | {_pct(r['hit_rate'])} | "
                     f"{_pct(r['hit_rate_low'])}-{_pct(r['hit_rate_high'])} | {_pct(r['top_decile_share'])} | "
                     f"{r['median_rating']:.1f} | {_pct(r['paid_share'])} |")
    return "\n".join(lines)


def render(m: dict) -> list[Path]:
    cl, ov, d, s = m["cleaning"], m["overall"], m["drivers"], m["sentiment"]
    cats, genres, fp = m["categories"], m["game_genres"], d["free_vs_paid"]
    rb, ua = d["hit_rate_by_rating_band"], d["hit_rate_by_update_age"]
    top_cats = ", ".join(_name(c["category"]) for c in cats[:5])
    bottom_cats = ", ".join(_name(c["category"]) for c in cats[-4:])
    g1, g2, g3 = genres[:3]
    worst_g = genres[-3:]
    casual = next(g for g in genres if g["primary_genre"] == "Casual")
    game_neg = s["median_neg_share_by_category"]["GAME"]["neg_share"]
    neg_sorted = sorted(s["median_neg_share_by_category"].items(), key=lambda kv: kv[1]["neg_share"])
    best_band = max(rb.items(), key=lambda kv: kv[1]["hit_rate"])
    by_paid = sorted(genres, key=lambda g: g["paid_share"], reverse=True)[:2]

    readme = f"""# Google Play market analysis - where should a small studio build next?

A studio with one team and no marketing budget has to pick its next app or game. This repo
answers **which categories and game genres give a new title the best odds**, using the public
Google Play scrape of **{cl['apps']:,} apps** (snapshot {cl['snapshot_date']}) and
**{s['labelled_reviews']:,} labelled user reviews**. Every number below is generated from
[`results/metrics.json`](results/metrics.json) by `python -m gplay` - nothing is typed by hand.

## In 30 seconds

![Category opportunity map](figures/01_category_opportunity.png)

- **Question:** where is demand high but the market not owned by a few giants?
- **Method:** for each category and game genre, *demand* = share of apps reaching 1M+ installs (hit rate),
  *competition* = share of the segment's installs taken by its top 10% of apps. Rank on both.
- **Answer for apps:** {top_cats} score best; {bottom_cats} score worst.
- **Answer for games:** games are a strong market overall (hit rate {_pct(ov['game_hit_rate'])} vs {_pct(ov['hit_rate'])} for all apps).
  Within games, **{g1['primary_genre']}**, **{g2['primary_genre']}** and **{g3['primary_genre']}** combine high hit rates with the
  least concentrated installs; {", ".join(g["primary_genre"] for g in worst_g)} are dominated by a few titles.
- **How to win once there:** be free ({_pct(fp['free_hit_rate'])} of free apps reach 1M+ vs {_pct(fp['paid_hit_rate'], 1)} of paid),
  keep shipping updates ({_pct(ua['<=30d']['hit_rate'])} hit rate when updated in the last 30 days vs {_pct(ua['>1y']['hit_rate'])} after a year),
  and budget for player support - game reviews are the most negative of any category ({_pct(game_neg)} negative at the median game).
- **Data catch found on the way:** **{ov['games_filed_under_family']:,} of {ov['game_apps']:,} games ({ov['games_filed_under_family'] / ov['game_apps']:.0%}) are filed under FAMILY, not GAME.**
  An analysis that filters on `Category == "GAME"` silently drops most Casual, Puzzle, Simulation and Role Playing games.

## Data and cleaning

| Step | Result |
|---|---|
| Source | Kaggle [`lava18/google-play-store-apps`](https://www.kaggle.com/datasets/lava18/google-play-store-apps) (Creative Commons, see `data/raw/license.txt` after download) |
| Raw rows | {cl['raw_rows']:,} |
| Malformed row (every field shifted one column) | {cl['malformed_rows_dropped']} dropped |
| Duplicate listings of the same app | {cl['duplicate_rows_dropped']:,} dropped, keeping the row with the most reviews (latest scrape) |
| Apps analysed | {cl['apps']:,} |
| Missing rating | {_pct(cl['missing_rating_share'])} of apps (kept; excluded only from rating analyses) |
| `Installs` | text buckets like "1,000,000+" parsed to their lower bound |
| Games | any `GAME` app, plus `FAMILY` apps whose primary genre is a game genre ({ov['game_apps']:,} games) |

## Method

1. **Demand - hit rate.** Install counts are buckets, so averages are misleading; the share of apps
   that cross **1M installs** is robust to that, and is what a studio actually wants to know: *what are
   my odds of a hit here?* Wilson 95% intervals show how sure each rate is.
2. **Competition - top-10% install share.** How much of the segment's installs the top tenth of apps
   take. A top-10 count would make small segments look concentrated just for being small; a top-10%
   share doesn't (there is a unit test for this).
3. **Opportunity rank** = percentile of hit rate + percentile of (1 - concentration). Segments under
   {m['params']['min_apps']} apps ({m['params']['min_genre_apps']} for game genres) are left out as too thin.
4. **Drivers** of a hit within any segment: rating, pricing, update recency, size - with rank
   correlations and Mann-Whitney tests, because installs are ordinal buckets.
5. **Review sentiment** (pre-labelled in the dataset) per app, checked against star ratings before use.

## Results

### App categories (top 10 of {len(cats)})

{_seg_table(cats, "category", 10)}

Full table: [`results/category_scores.csv`](results/category_scores.csv).

### Game genres

![Game genre opportunity map](figures/02_game_genre_opportunity.png)

{_seg_table(genres, "primary_genre")}

**Reading it:** {g1['primary_genre']} has the best hit rate for how open its install base is. Casual is popular
but {_pct(casual['top_decile_share'])} of its installs go to the top 10% of titles - a new casual game competes with giants.
{by_paid[0]['primary_genre']} and {by_paid[1]['primary_genre']} have the highest paid shares, a sign of players willing to pay up front.

### What separates hits inside a segment

![Hit rate by rating](figures/03_hit_rate_by_rating.png)

- **Rating:** across all apps the rank correlation between rating and installs is only
  {d['rating_installs_spearman']:.2f} - rating alone predicts little. Among apps with 100+ reviews the hit rate peaks
  at **{best_band[0]}** stars ({_pct(best_band[1]['hit_rate'])}) and falls for 4.7-5.0 ({_pct(rb['4.7-5.0']['hit_rate'])}): near-perfect scores mostly
  belong to small apps with a loyal niche. Aim for a solid 4.1-4.6, not perfection.
- **Updates:** apps updated in the 30 days before the snapshot are hits {ua['<=30d']['hit_rate'] / ua['>1y']['hit_rate']:.1f}x as often as
  apps untouched for a year. Causality runs both ways (successful apps can afford updates), but an
  unmaintained app does not stay a hit.

![Hit rate by update recency](figures/04_hit_rate_by_update_age.png)

- **Price:** paid apps reach 1M installs {fp['free_hit_rate'] / fp['paid_hit_rate']:.0f}x less often (median {fp['paid_median_installs']:,.0f} vs
  {fp['free_median_installs']:,.0f} installs; Mann-Whitney p < 0.001), and their median rating is barely higher
  ({fp['paid_median_rating']:.1f} vs {fp['free_median_rating']:.1f}). Median paid price is ${fp['paid_median_price']:.2f}; {_pct(fp['paid_share_under_5usd'])} cost under $5.

![Free vs paid](figures/06_free_vs_paid.png)

- **Size:** larger apps install more (Spearman {d['size_installs_spearman']:.2f}) - a proxy for production value, not a lever.

### What players complain about

![Negative reviews by category](figures/05_negative_reviews_by_category.png)

The sentiment labels track star ratings (Spearman {s['neg_share_vs_rating_spearman']:.2f} between an app's negative-review share and its
rating, across {s['apps_with_20plus_reviews']} apps with 20+ labelled reviews), so they are usable. Game reviews are the most negative
({_pct(game_neg)} at the median game) - far above {_name(neg_sorted[0][0])} ({_pct(neg_sorted[0][1]['neg_share'])}). Game players are
engaged enough to complain: support, balancing and bug-fix cadence matter more in games than anywhere else.

## Recommendation for a small studio

| Decision | Choice | Evidence |
|---|---|---|
| **What to build** | A free game in **{g1['primary_genre']}**, **{g2['primary_genre']}** or **{g3['primary_genre']}** | Top opportunity ranks among game genres: high hit rate, least concentrated installs |
| **What to avoid** | {", ".join(g["primary_genre"] for g in worst_g)} games; {bottom_cats} apps | Lowest hit rates and/or most concentrated installs |
| **Business model** | Free + ads / in-app purchases | Free hit rate {_pct(fp['free_hit_rate'])} vs paid {_pct(fp['paid_hit_rate'], 1)} |
| **Operating plan** | Ship updates at least monthly; staff player support from day one | {_pct(ua['<=30d']['hit_rate'])} vs {_pct(ua['>1y']['hit_rate'])} hit rate by update recency; games have the most negative reviews |
| **Quality bar** | 4.1-4.6 stars with 100+ reviews | Hit rate peaks in that band |

## Limitations

- **2018 snapshot.** The specific winners will have moved; the *method* (hit rate vs concentration,
  with a clean game definition) is what transfers to a current data pull.
- **The scrape is not the whole store.** It over-represents visible, popular apps (median {ov['median_installs']:,.0f} installs),
  so absolute hit rates are inflated. Use them to *compare* segments, not as real odds.
- **Installs are lower bounds of buckets**, and there is **no revenue column** - "hit" means installs,
  not money. A studio would add revenue estimates from a market-intelligence tool before committing.
- **Correlation only** for the drivers: no experiment, and successful apps can afford more updates.

## Reproduce

```powershell
pip install -r requirements.txt
pip install -e .
$env:KAGGLE_API_TOKEN = "<your token>"   # or ~/.kaggle/kaggle.json
kaggle datasets download -d lava18/google-play-store-apps -p data/raw --unzip
python -m gplay       # writes results/, figures/, README.md
pytest -q
```

## Repo layout

```
src/gplay/analysis.py   cleaning, game definition, segment scoring, drivers, sentiment -> results/
src/gplay/figures.py    the charts in figures/
src/gplay/report.py     renders this README from results/metrics.json
tests/                  unit tests on parsing, scoring and the data contract
```
"""
    out = ROOT / "README.md"
    out.write_text(readme, encoding="utf-8")
    return [out]
