#!/usr/bin/env python3
"""
Generate a simple source coverage dashboard for the library.

Outputs:
  - library/source-dashboard.json
  - library/source-dashboard.html
"""

from __future__ import annotations

import json
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
LIBRARY = REPO / "library"
SOURCE_TOC = LIBRARY / "source_toc.json"
DASHBOARD_JSON = LIBRARY / "source-dashboard.json"
DASHBOARD_HTML = LIBRARY / "source-dashboard.html"


def load_words_payload(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def count_source_words(payload) -> tuple[int, int]:
    if not isinstance(payload, dict) or "v" not in payload:
        return 0, 0
    rows = payload.get("v", {})
    annotated = 0
    matched = 0
    for entry in rows.values():
        if not isinstance(entry, dict) or not entry:
            continue
        annotated += 1
        if any(isinstance(word, dict) and word.get("m") for word in entry.values()):
            matched += 1
    return annotated, matched


def pct(part: int, whole: int) -> float:
    return round((part / whole) * 100, 1) if whole else 0.0


def build_data() -> dict:
    collections = json.loads(SOURCE_TOC.read_text(encoding="utf-8"))
    rows = []
    totals = {
        "collections": 0,
        "docs": 0,
        "docs_with_words": 0,
        "paragraphs": 0,
        "annotated_paragraphs": 0,
        "matched_paragraphs": 0,
    }

    for collection in collections:
        coll_docs = 0
        coll_docs_with_words = 0
        coll_paragraphs = 0
        coll_annotated = 0
        coll_matched = 0

        raw_items = collection.get("items", [])
        flat_items = []
        for it in raw_items:
            if it.get("type") == "group":
                flat_items.extend(it.get("items", []))
            else:
                flat_items.append(it)
        for item in flat_items:
            coll_docs += 1
            coll_paragraphs += int(item.get("paragraphs") or 0)
            html_path = LIBRARY / item["href"]
            words_path = html_path.with_name(f"{html_path.stem}_words.json")
            payload = load_words_payload(words_path)
            annotated, matched = count_source_words(payload)
            if payload is not None:
                coll_docs_with_words += 1
            coll_annotated += annotated
            coll_matched += matched

        row = {
            "id": collection["id"],
            "label": collection["label"],
            "docs": coll_docs,
            "docs_with_words": coll_docs_with_words,
            "paragraphs": coll_paragraphs,
            "annotated_paragraphs": coll_annotated,
            "matched_paragraphs": coll_matched,
            "doc_coverage_pct": pct(coll_docs_with_words, coll_docs),
            "annotated_pct": pct(coll_annotated, coll_paragraphs),
            "linked_pct": pct(coll_matched, coll_paragraphs),
            "recursive": coll_docs_with_words == coll_docs and coll_matched > 0,
        }
        rows.append(row)
        totals["collections"] += 1
        totals["docs"] += coll_docs
        totals["docs_with_words"] += coll_docs_with_words
        totals["paragraphs"] += coll_paragraphs
        totals["annotated_paragraphs"] += coll_annotated
        totals["matched_paragraphs"] += coll_matched

    rows.sort(key=lambda row: (row["linked_pct"], row["doc_coverage_pct"], row["paragraphs"]))
    totals["doc_coverage_pct"] = pct(totals["docs_with_words"], totals["docs"])
    totals["annotated_pct"] = pct(totals["annotated_paragraphs"], totals["paragraphs"])
    totals["linked_pct"] = pct(totals["matched_paragraphs"], totals["paragraphs"])
    return {"totals": totals, "collections": rows}


def render_html(report: dict) -> str:
    rows = []
    for row in report["collections"]:
        status = "Recursive" if row["recursive"] else ("Partial" if row["docs_with_words"] else "Browse only")
        rows.append(
            "<tr>"
            f"<td>{row['label']}</td>"
            f"<td>{row['docs']}</td>"
            f"<td>{row['paragraphs']:,}</td>"
            f"<td>{row['docs_with_words']}</td>"
            f"<td>{row['annotated_paragraphs']:,}</td>"
            f"<td>{row['matched_paragraphs']:,}</td>"
            f"<td>{row['doc_coverage_pct']}%</td>"
            f"<td>{row['linked_pct']}%</td>"
            f"<td>{status}</td>"
            "</tr>"
        )
    total = report["totals"]
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Source Coverage Dashboard</title>
  <style>
    :root {{
      --bg: #f7f3eb;
      --card: #fffdf9;
      --line: rgba(0,0,0,0.08);
      --text: #2f2a24;
      --muted: #7a6d5c;
      --accent: #9c7a4d;
    }}
    body {{
      margin: 0;
      padding: 32px;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 Inter, system-ui, sans-serif;
    }}
    h1 {{
      margin: 0 0 8px;
      font: 700 40px/1.05 "EB Garamond", Georgia, serif;
      color: #2b241d;
    }}
    p {{
      margin: 0 0 18px;
      color: var(--muted);
    }}
    .totals {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 12px;
      margin: 0 0 22px;
    }}
    .metric {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px 16px;
    }}
    .metric-label {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: .08em;
      color: var(--muted);
      margin-bottom: 6px;
    }}
    .metric-value {{
      font-size: 28px;
      font-weight: 700;
      color: var(--accent);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 16px;
      overflow: hidden;
    }}
    th, td {{
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: .08em;
      color: var(--muted);
      background: rgba(156,122,77,0.06);
    }}
    tr:last-child td {{ border-bottom: none; }}
    @media (max-width: 900px) {{
      body {{ padding: 16px; }}
      table {{ display: block; overflow-x: auto; }}
    }}
  </style>
</head>
<body>
  <h1>Source Coverage Dashboard</h1>
  <p>How much of each source shelf is actually in the semantic graph, not just browseable.</p>
  <div class="totals">
    <div class="metric"><div class="metric-label">Collections</div><div class="metric-value">{total['collections']}</div></div>
    <div class="metric"><div class="metric-label">Documents</div><div class="metric-value">{total['docs']}</div></div>
    <div class="metric"><div class="metric-label">Paragraphs</div><div class="metric-value">{total['paragraphs']:,}</div></div>
    <div class="metric"><div class="metric-label">Doc Coverage</div><div class="metric-value">{total['doc_coverage_pct']}%</div></div>
    <div class="metric"><div class="metric-label">Annotated</div><div class="metric-value">{total['annotated_pct']}%</div></div>
    <div class="metric"><div class="metric-label">Semantically Linked</div><div class="metric-value">{total['linked_pct']}%</div></div>
  </div>
  <table>
    <thead>
      <tr>
        <th>Collection</th>
        <th>Docs</th>
        <th>Paragraphs</th>
        <th>Docs With Words</th>
        <th>Annotated Paragraphs</th>
        <th>Linked Paragraphs</th>
        <th>Doc Coverage</th>
        <th>Linked %</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</body>
</html>
"""


def main() -> int:
    report = build_data()
    DASHBOARD_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    DASHBOARD_HTML.write_text(render_html(report), encoding="utf-8")
    print(json.dumps(report["totals"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
