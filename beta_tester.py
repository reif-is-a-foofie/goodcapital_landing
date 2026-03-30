#!/usr/bin/env python3
"""
Hourly beta tester runner.

Runs a compact suite of audits/browser regressions, writes a diagnostics report,
and appends durable tasks into the immutable ledger when high-signal checks fail.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DIAG = ROOT / "diagnostics"
REPORT = DIAG / "beta-tester-latest.json"
TXT = DIAG / "beta-tester-latest.txt"
LEDGER = ROOT / "task_ledger.py"
MISSION = ROOT / "AGENT_MISSION.md"
PROFILE = ROOT / "agents" / "beta_tester_profile.md"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


@dataclass
class Check:
    name: str
    cmd: list[str]
    task_title: str


CHECKS = [
    Check(
        name="search_quality",
        cmd=["python3", "audit_search_quality.py"],
        task_title="Beta tester: repair search quality regressions so exact refs, source titles, and chapter-intent queries remain reliable",
    ),
    Check(
        name="search_browser",
        cmd=["node", "test-search-quality.js"],
        task_title="Beta tester: fix browser search regressions when live query ranking or source opening stops matching expected behavior",
    ),
    Check(
        name="mobile_channel",
        cmd=["node", "test-library-mobile-channel.js"],
        task_title="Beta tester: fix mobile reference-panel scrolling and touch interaction so word-click results remain usable on phones",
    ),
    Check(
        name="commentary_links",
        cmd=["node", "test-library-commentary-links.js"],
        task_title="Beta tester: repair commentary reference navigation so inline references open the linked chapter or source instead of dead-ending",
    ),
    Check(
        name="corpus_integrity",
        cmd=["python3", "lds_pipeline/audit_corpus_integrity.py", "--strict"],
        task_title="Beta tester: resolve scripture/source corpus integrity failures flagged by the strict audit before they ship as silent regressions",
    ),
]


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
        "stdout": proc.stdout[-8000:],
        "stderr": proc.stderr[-8000:],
    }


def ensure_task(title: str, source: str) -> None:
    subprocess.run(
        ["python3", str(LEDGER), "ensure", title, "--source", source, "--priority", "high"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def note_failure(task_title: str, source: str, output: dict) -> None:
    ensured = subprocess.run(
        ["python3", str(LEDGER), "ensure", task_title, "--source", source, "--priority", "high"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    task_id = ""
    try:
        payload = json.loads(ensured.stdout or "{}")
        task_id = payload.get("task_id", "")
    except Exception:
        pass
    if not task_id:
        return
    note = f"{source} failed with exit {output['code']}. stderr: {(output['stderr'] or '').strip()[:400]} stdout: {(output['stdout'] or '').strip()[:400]}"
    subprocess.run(
        ["python3", str(LEDGER), "note", task_id, "--agent", "BetaTester", "--note", note],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> int:
    DIAG.mkdir(parents=True, exist_ok=True)
    report = {
        "ts": now_iso(),
        "agent": "BetaTester",
        "mission_path": str(MISSION.relative_to(ROOT)),
        "profile_path": str(PROFILE.relative_to(ROOT)),
        "mission": read_text(MISSION),
        "profile": read_text(PROFILE),
        "checks": [],
    }
    lines = [f"Beta tester run: {report['ts']}"]
    if report["mission_path"]:
        lines.append(f"Mission: {report['mission_path']}")
    if report["profile_path"]:
        lines.append(f"Profile: {report['profile_path']}")
    failures = 0

    for check in CHECKS:
        result = run(check.cmd)
        result["name"] = check.name
        ok = result["code"] == 0
        result["ok"] = ok
        report["checks"].append(result)
        lines.append(f"- {check.name}: {'ok' if ok else 'FAIL'}")
        if not ok:
            failures += 1
            note_failure(check.task_title, check.name, result)
            lines.append(f"  task: {check.task_title}")
            if result["stderr"].strip():
                lines.append(f"  stderr: {result['stderr'].strip()[:300]}")
            elif result["stdout"].strip():
                lines.append(f"  stdout: {result['stdout'].strip()[:300]}")

    report["failures"] = failures
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "agent": "BetaTester",
        "failures": failures,
        "report": str(REPORT.relative_to(ROOT)),
    }, indent=2))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
