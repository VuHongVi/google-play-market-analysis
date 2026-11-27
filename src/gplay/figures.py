"""Static README figures. Palette: validated default categorical slots 1-2 (blue, orange)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "figures"
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "font.size": 11, "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "legend.frameon": False,
})


def _save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    p = FIG / name
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p


def _pretty(s: str) -> str:
    return s.replace("_AND_", " & ").replace("_", " ").title()


def opportunity_map(seg: pd.DataFrame, key: str, title: str, name: str, highlight: str | None = None,
                    n_label: int = 6, offsets: dict | None = None) -> Path:
    offsets = offsets or {}
    fig, ax = plt.subplots(figsize=(9, 6))
    x, y = seg["top_decile_share"] * 100, seg["hit_rate"] * 100
    ax.scatter(x, y, s=seg["apps"].clip(upper=900) / 3 + 30, color=BLUE, alpha=0.75,
               edgecolor=SURFACE, linewidth=2, zorder=3)
    mx, my = x.median(), y.median()
    ax.axvline(mx, color=INK2, linewidth=0.8, linestyle="--")
    ax.axhline(my, color=INK2, linewidth=0.8, linestyle="--")
    labelled = set(seg.head(n_label)[key]) | set(seg.tail(3)[key])
    if highlight:
        labelled.add(highlight)
    for _, r in seg.iterrows():
        if r[key] not in labelled:
            continue
        hi = r[key] == highlight
        if hi:
            ax.scatter(r.top_decile_share * 100, r.hit_rate * 100, s=r.apps / 3 + 30, color=ORANGE,
                       edgecolor=SURFACE, linewidth=2, zorder=4)
        ax.annotate(_pretty(r[key]), (r.top_decile_share * 100, r.hit_rate * 100), xytext=offsets.get(r[key], (6, 4)),
                    textcoords="offset points", fontsize=9, color=INK,
                    fontweight="bold" if hi else "normal")
    ax.set_xlabel("Competition: share of installs taken by the top 10% of apps (%)")
    ax.set_ylabel("Demand: share of apps with 1M+ installs (%)")
    ax.set_title(title)
    ax.set_ylim(0, max(100, y.max() + 8))
    ax.text(0, -0.13, "Dot size = number of apps. Dashed lines = medians. Top-left = more hits in a less concentrated market.",
            transform=ax.transAxes, fontsize=9, color=INK2)
    return _save(fig, name)


def bar(labels, values, title, xlabel, name, ylabel="Share of apps with 1M+ installs (%)", highlight=None,
        counts=None) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    colors = [ORANGE if l == highlight else BLUE for l in labels]
    bars = ax.bar(labels, [v * 100 for v in values], color=colors, width=0.6, zorder=3)
    for i, (b, v) in enumerate(zip(bars, values)):
        txt = f"{v:.0%}" + (f"\nn={counts[i]:,}" if counts is not None else "")
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.5, txt, ha="center", va="bottom",
                fontsize=9, color=INK)
    ax.set_ylim(0, max(v * 100 for v in values) * 1.3)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(axis="x", visible=False)
    ax.set_title(title)
    return _save(fig, name)


def sentiment_bars(sent: dict) -> Path:
    d = pd.DataFrame(sent["median_neg_share_by_category"]).T.sort_values("neg_share")
    fig, ax = plt.subplots(figsize=(8, 6.5))
    colors = [ORANGE if c == "GAME" else BLUE for c in d.index]
    ax.barh([_pretty(c) for c in d.index], d["neg_share"] * 100, color=colors, height=0.65, zorder=3)
    for i, v in enumerate(d["neg_share"]):
        ax.text(v * 100 + 0.5, i, f"{v:.0%}", va="center", fontsize=9, color=INK)
    ax.set_xlabel("Median share of an app's reviews that are negative (%)")
    ax.grid(axis="y", visible=False)
    ax.set_title("Game players complain the most")
    ax.text(0, -0.14, "Apps with 20+ labelled reviews; categories with 15+ such apps.",
            transform=ax.transAxes, fontsize=9, color=INK2)
    return _save(fig, "05_negative_reviews_by_category.png")


def build_all(m: dict, cats: pd.DataFrame, genres: pd.DataFrame) -> list[Path]:
    d = m["drivers"]
    rb, ua, fp = d["hit_rate_by_rating_band"], d["hit_rate_by_update_age"], d["free_vs_paid"]
    return [
        opportunity_map(cats, "category", "App categories: demand vs competition", "01_category_opportunity.png",
                        highlight="GAME",
                        offsets={"WEATHER": (-58, 6), "SHOPPING": (6, -12)}),
        opportunity_map(genres, "primary_genre", "Game genres: demand vs competition", "02_game_genre_opportunity.png",
                        n_label=20, offsets={"Strategy": (-62, 6), "Casual": (6, -12)}),
        bar(list(rb), [v["hit_rate"] for v in rb.values()], "Ratings pay off up to ~4.6 - then fall back",
            "Store rating (apps with 100+ reviews)", "03_hit_rate_by_rating.png",
            counts=[v["apps"] for v in rb.values()]),
        bar(list(ua), [v["hit_rate"] for v in ua.values()], "Hits keep shipping updates",
            "Days since last update (snapshot date)", "04_hit_rate_by_update_age.png",
            counts=[v["apps"] for v in ua.values()]),
        bar(["Free", "Paid"], [fp["free_hit_rate"], fp["paid_hit_rate"]], "Paid apps almost never reach 1M installs",
            "Pricing model", "06_free_vs_paid.png", counts=[fp["free_apps"], fp["paid_apps"]]),
        sentiment_bars(m["sentiment"]),
    ]
