#!/usr/bin/env python3
"""
rebuild_after_correlate.py
==========================
Run this after correlate_embeddings.py finishes to:
  1. Rebuild all chapter graph JSON files from the new correlation cache
  2. Rebuild source_links.json (reverse index: source para → verses)
  3. Rebuild source_dashboard.json (stats)

Run from repo root:
    python3 lds_pipeline/rebuild_after_correlate.py [--books genesis exodus]
"""

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent


def run(cmd: list[str], label: str) -> bool:
    print(f"\n=== {label} ===")
    result = subprocess.run(cmd, cwd=REPO)
    if result.returncode == 0:
        print(f"  [OK] {label}")
        return True
    else:
        print(f"  [FAIL] {label} (exit {result.returncode})")
        return False


def main():
    parser = argparse.ArgumentParser(description="Rebuild graphs and indexes after correlate_embeddings run")
    parser.add_argument("--books", nargs="+", help="Only rebuild these book prefixes")
    args = parser.parse_args()

    # Check that correlations exist
    corr_dir = REPO / "lds_pipeline" / "cache" / "correlations"
    corr_count = sum(1 for _ in corr_dir.glob("*.json"))
    print(f"Correlation cache: {corr_count:,} files in {corr_dir}")

    if corr_count < 1000:
        print(f"WARNING: Only {corr_count} correlation files — correlate_embeddings may not have finished.")
        print("Run: python3 lds_pipeline/correlate_embeddings.py")
        sys.exit(1)

    # 1. Rebuild chapter graphs
    build_graph_cmd = ["python3", "lds_pipeline/build_graph.py"]
    if args.books:
        build_graph_cmd += ["--books"] + args.books
    ok = run(build_graph_cmd, "build_graph.py")
    if not ok:
        print("build_graph.py failed — aborting.")
        sys.exit(1)

    # 2. Rebuild source_links.json
    ok = run(["python3", "lds_pipeline/build_source_links.py"], "build_source_links.py")
    if not ok:
        print("build_source_links.py failed (non-fatal, continuing...)")

    # 3. Rebuild source dashboard
    dashboard_script = REPO / "lds_pipeline" / "build_source_dashboard.py"
    if dashboard_script.exists():
        run(["python3", "lds_pipeline/build_source_dashboard.py"], "build_source_dashboard.py")

    print("\nDone. The library graphs, source links, and dashboard are up to date.")
    print("Commit: git add library/chapters/ library/source_links.json library/source-dashboard.json")


if __name__ == "__main__":
    main()
