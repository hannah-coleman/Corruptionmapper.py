"""Block commits that contain case data or locally listed private terms.

Case data (names, evidence, notes) must stay on your computer. Put names or phrases you never want
published, one per line, in `.private-terms.txt` (git-ignored, so the list itself is never committed).
Install with: python3 scripts/check_no_case_data.py --install
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOCKED_PATHS = re.compile(r"(^|/)(evidence|backups|uploads)/|(^|/)(casefile|claims|facts|statements|requests|request-queue)\.json$|\.sqlite$|(^|/)\.env$|\.private-terms\.txt$|-manifest\.jsonl$")
ALLOWED = {"casefile.example.json"}


def private_terms() -> list[str]:
    path = ROOT / ".private-terms.txt"
    if not path.exists():
        return []
    return [line.strip().lower() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]


def staged(args: list[str]) -> list[str]:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()


def problems() -> list[str]:
    found = []
    terms = private_terms()
    for name in staged(["diff", "--cached", "--name-only", "--diff-filter=ACMR"]):
        if name not in ALLOWED and BLOCKED_PATHS.search(name):
            found.append(f"{name}: case data must not be committed")
            continue
        added = "\n".join(line[1:] for line in staged(["diff", "--cached", "-U0", "--", name]) if line.startswith("+") and not line.startswith("+++")).lower()
        found += [f"{name}: contains a term from .private-terms.txt" for term in terms if term in added][:1]
    return found


def install() -> None:
    hook = ROOT / ".git" / "hooks" / "pre-commit"
    hook.write_text('#!/bin/sh\npython3 scripts/check_no_case_data.py || exit 1\n', encoding="utf-8")
    hook.chmod(0o755)
    print(f"Installed {hook}")


if __name__ == "__main__":
    if "--install" in sys.argv:
        install()
        sys.exit(0)
    issues = problems()
    for issue in issues:
        print(f"BLOCKED: {issue}", file=sys.stderr)
    sys.exit(1 if issues else 0)
