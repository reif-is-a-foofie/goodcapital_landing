#!/usr/bin/env python3
"""
Audit the source corpus for completeness and obvious range gaps.

Outputs:
  diagnostics/source-completeness-report.txt
  diagnostics/source-completeness-report.json

This is a read-only audit. It does not rebuild any corpus files.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent
TOC_PATH = REPO / "library" / "source_toc.json"
SOURCE_ROOT = REPO / "library" / "sources"
OUT_DIR = REPO / "diagnostics"
TEXT_OUT = OUT_DIR / "source-completeness-report.txt"
JSON_OUT = OUT_DIR / "source-completeness-report.json"


def year_span_from_text(text: str) -> tuple[int | None, int | None]:
    years = [int(y) for y in re.findall(r"(18\d{2}|19\d{2}|20\d{2})", text)]
    if not years:
        return (None, None)
    return (min(years), max(years))


def collection_stats(items: list[dict]) -> dict:
    html = sum(1 for it in items if str(it.get("href", "")).endswith(".html"))
    words = sum(1 for it in items if str(it.get("href", "")).endswith("_words.json"))
    return {"count": len(items), "html": html, "words": words}


def source_dir_stats() -> dict[str, dict]:
    stats = {}
    for d in sorted(SOURCE_ROOT.iterdir()):
        if not d.is_dir():
            continue
        html = len(list(d.glob("*.html")))
        words = len(list(d.glob("*_words.json")))
        stats[d.name] = {"html": html, "words": words}
    return stats


def summarize_collection(coll: dict, disk_stats: dict[str, dict]) -> dict:
    items = coll.get("items", [])
    ids = [it.get("id", "") for it in items]
    min_year = None
    max_year = None
    if coll["id"] == "general_conference":
        years = []
        for item_id in ids:
            m = re.search(r"general_conference_(\d{4})_(\d{2})", item_id)
            if m:
                years.append(int(m.group(1)))
        if years:
            min_year = min(years)
            max_year = max(years)
    elif coll["id"] in {"times_and_seasons", "millennial_star", "joseph_smith_papers"}:
        years = []
        for it in items:
            text = " ".join(
                str(part) for part in (it.get("id", ""), it.get("label", ""), it.get("meta", ""), it.get("href", ""))
            )
            lo, hi = year_span_from_text(text)
            if lo is not None:
                years.append(lo)
            if hi is not None:
                years.append(hi)
        if years:
            min_year = min(years)
            max_year = max(years)
    return {
        "id": coll["id"],
        "label": coll.get("label", coll["id"]),
        **collection_stats(items),
        "source_dir": disk_stats.get(coll["id"], {}),
        "year_range": [min_year, max_year],
    }


def main() -> None:
    toc = json.loads(TOC_PATH.read_text())
    disk_stats = source_dir_stats()
    collections = [summarize_collection(coll, disk_stats) for coll in toc]

    recommendations = []
    gc = next((c for c in collections if c["id"] == "general_conference"), None)
    if gc and gc["year_range"][0] is not None and gc["year_range"][0] > 1851:
        recommendations.append(
            "General Conference starts at {} in the repo; add pre-{} conference reports to cover the historical gap.".format(
                gc["year_range"][0], gc["year_range"][0]
            )
        )

    if any(c["id"] == "times_and_seasons" for c in collections):
        t = next(c for c in collections if c["id"] == "times_and_seasons")
        recommendations.append(
            "Times and Seasons is present as a 26-issue subset spanning {}-{}; add the remaining run if the goal is publication completeness.".format(
                t["year_range"][0], t["year_range"][1]
            )
        )
    if any(c["id"] == "millennial_star" for c in collections):
        m = next(c for c in collections if c["id"] == "millennial_star")
        recommendations.append(
            "Millennial Star is present as a 162-issue subset spanning {}-{}; expand beyond the current tranche if a fuller magazine archive is desired.".format(
                m["year_range"][0], m["year_range"][1]
            )
        )
    if any(c["id"] == "joseph_smith_papers" for c in collections):
        jsp = next(c for c in collections if c["id"] == "joseph_smith_papers")
        recommendations.append(
            "Joseph Smith Papers is only 9 documents here; treat it as a seed corpus, not a complete archive."
        )

    report = {
        "collections": collections,
        "recommendations": recommendations,
        "disk_stats": disk_stats,
    }

    OUT_DIR.mkdir(exist_ok=True)
    JSON_OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    lines = []
    lines.append("Source Completeness Audit")
    lines.append("")
    for coll in collections:
        yr = coll["year_range"]
        yr_txt = f"{yr[0]}-{yr[1]}" if yr[0] and yr[1] else "n/a"
        src = coll.get("source_dir", {})
        lines.append(
            f"- {coll['label']}: {coll['count']} items, {coll['html']} html, {coll['words']} words, years {yr_txt}, disk {src.get('html', 0)} html/{src.get('words', 0)} words"
        )
    lines.append("")
    lines.append("Recommendations")
    for rec in recommendations:
        lines.append(f"- {rec}")

    TEXT_OUT.write_text("\n".join(lines) + "\n")
    print(TEXT_OUT)
    print(JSON_OUT)


if __name__ == "__main__":
    main()
