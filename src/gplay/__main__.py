"""python -m gplay : clean data, score the market, write results/metrics.json, figures and README."""
from .analysis import analyse, write_metrics
from .figures import build_all
from .report import render


def main() -> None:
    metrics, df, cats, genres = analyse()
    print("metrics ->", write_metrics(metrics))
    cats.to_csv("results/category_scores.csv", index=False)
    genres.to_csv("results/game_genre_scores.csv", index=False)
    for p in build_all(metrics, cats, genres):
        print("figure  ->", p)
    for p in render(metrics):
        print("report  ->", p)


if __name__ == "__main__":
    main()
