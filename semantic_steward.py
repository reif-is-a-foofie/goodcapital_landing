#!/usr/bin/env python3
"""
Hourly semantic steward runner.

Refreshes semantic correlation artifacts, rebuilds source-word sidecars and the
source coverage dashboard, then records diagnostics and durable ledger tasks on
failure.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DIAG = ROOT / "diagnostics"
REPORT = DIAG / "semantic-steward-latest.json"
TXT = DIAG / "semantic-steward-latest.txt"
LEDGER = ROOT / "task_ledger.py"
MISSION = ROOT / "AGENT_MISSION.md"
PROFILE = ROOT / "agents" / "semantic_steward_profile.md"
DASHBOARD_JSON = ROOT / "library" / "source-dashboard.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def run(cmd: list[str]) -> dict:
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    return {
        "cmd": cmd,
        "code": proc.returncode,
        "stdout": proc.stdout[-12000:],
        "stderr": proc.stderr[-12000:],
    }


CHECKS = [
    {
        "name": "semantic_refresh",
        "cmd": ["python3", "lds_pipeline/transformer_worker.py", "--once"],
        "task_title": "Semantic steward: repair the correlation refresh pipeline so source and scripture sidecars stay semantically current",
    },
    {
        "name": "semantic_dashboard",
        "cmd": ["python3", "lds_pipeline/build_source_dashboard.py"],
        "task_title": "Semantic steward: repair the source coverage dashboard pipeline so semantic linkage totals stay current and trustworthy",
    },
]


def ensure_task(title: str, source: str) -> str:
    proc = subprocess.run(
        ["python3", str(LEDGER), "ensure", title, "--source", source, "--priority", "high"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        payload = json.loads(proc.stdout or "{}")
    except Exception:
        return ""
    return str(payload.get("task_id") or "")


def note_failure(task_title: str, source: str, output: dict) -> None:
    task_id = ensure_task(task_title, source)
    if not task_id:
        return
    note = (
        f"{source} failed with exit {output['code']}. "
        f"stderr: {(output['stderr'] or '').strip()[:600]} "
        f"stdout: {(output['stdout'] or '').strip()[:600]}"
    )
    subprocess.run(
        ["python3", str(LEDGER), "note", task_id, "--agent", "SemanticSteward", "--note", note],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def load_dashboard_totals() -> dict:
    if not DASHBOARD_JSON.exists():
        return {}
    try:
        payload = json.loads(DASHBOARD_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload.get("totals") or {}


def main() -> int:
    DIAG.mkdir(parents=True, exist_ok=True)
    report = {
        "ts": now_iso(),
        "agent": "SemanticSteward",
        "mission_path": str(MISSION.relative_to(ROOT)),
        "profile_path": str(PROFILE.relative_to(ROOT)),
        "mission": read_text(MISSION),
        "profile": read_text(PROFILE),
        "checks": [],
        "dashboard_totals": {},
    }
    lines = [f"Semantic steward run: {report['ts']}"]
    lines.append(f"Mission: {report['mission_path']}")
    lines.append(f"Profile: {report['profile_path']}")
    failures = 0

    for check in CHECKS:
        result = run(check["cmd"])
        result["name"] = check["name"]
        result["ok"] = result["code"] == 0
        report["checks"].append(result)
        lines.append(f"- {check['name']}: {'ok' if result['ok'] else 'FAIL'}")
        if not result["ok"]:
            failures += 1
            note_failure(check["task_title"], check["name"], result)
            lines.append(f"  task: {check['task_title']}")
            if result["stderr"].strip():
                lines.append(f"  stderr: {result['stderr'].strip()[:400]}")
            elif result["stdout"].strip():
                lines.append(f"  stdout: {result['stdout'].strip()[:400]}")

    totals = load_dashboard_totals()
    report["dashboard_totals"] = totals
    if totals:
        lines.append(
            "Dashboard totals: "
            f"collections={totals.get('collections', 0)} "
            f"docs={totals.get('docs', 0)} "
            f"paragraphs={totals.get('paragraphs', 0)} "
            f"linked_pct={totals.get('linked_pct', 0)}%"
        )

    report["failures"] = failures
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "agent": "SemanticSteward",
        "failures": failures,
        "report": str(REPORT.relative_to(ROOT)),
    }, indent=2))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
