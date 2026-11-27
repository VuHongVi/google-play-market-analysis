"""Turn Power BI Desktop page screenshots into README figures and a PDF of the whole report.

    powerbi-report-author preview powerbi/<Name>.Report --host desktop --screenshot <dir> --all-pages
    python powerbi/tools/export_pages.py <dir>

Crops each capture to the 16:9 report canvas (drops the Desktop chrome and the Filters pane),
writes figures/powerbi_NN_<slug>.png for every page in report order and
reports/<Name>_PowerBI_report.pdf.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
CANVAS = (0, 62, 2632, 1542)  # report canvas inside a 3034 x 1604 Desktop capture


def main(src: Path) -> None:
    report = next((ROOT / "powerbi").glob("*.Report"))
    name = report.name.removesuffix(".Report")
    pages_dir = report / "definition" / "pages"
    order = json.loads((pages_dir / "pages.json").read_text(encoding="utf-8"))["pageOrder"]
    names = [json.loads((pages_dir / p / "page.json").read_text(encoding="utf-8"))["displayName"] for p in order]
    (ROOT / "figures").mkdir(exist_ok=True)
    (ROOT / "reports").mkdir(exist_ok=True)
    pages = []
    for i, display in enumerate(names, 1):
        im = Image.open(src / f"{display}.png").convert("RGB")
        assert im.size == (3034, 1604), f"{display}: unexpected capture size {im.size}"
        page = im.crop(CANVAS)
        pages.append(page)
        slug = re.sub(r"[^a-z0-9]+", "_", display.lower()).strip("_")
        fig = page.resize((1600, round(1600 * page.height / page.width)), Image.LANCZOS)
        fig.save(ROOT / "figures" / f"powerbi_{i:02d}_{slug}.png", optimize=True)
    out = ROOT / "reports" / f"{name}_PowerBI_report.pdf"
    pages[0].save(out, save_all=True, append_images=pages[1:], resolution=150.0)
    print(f"{len(pages)} pages -> {out.relative_to(ROOT)} and figures/powerbi_*.png")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
