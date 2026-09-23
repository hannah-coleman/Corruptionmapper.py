from __future__ import annotations

import os
import stat
from pathlib import Path


def _is_private(path: Path) -> bool:
    return stat.S_IMODE(path.stat().st_mode) & 0o077 == 0


def assess_evidence_permissions(path: Path | str) -> dict:
    root = Path(path)
    if not root.exists():
        return {"private": False, "checked": 0, "issues": ["Evidence directory does not exist."], "limitation": "Encryption at rest is not configured."}
    paths = [root, *root.rglob("*")]
    checked = [item for item in paths if item.exists()]
    exposed = [str(item) for item in checked if not _is_private(item)]
    return {
        "private": not exposed,
        "checked": len(checked),
        "issues": [f"Group or world access enabled: {item}" for item in exposed],
        "limitation": "Owner-only permissions reduce local exposure but are not encryption at rest. Use full-disk encryption and device access controls for sensitive material.",
    }


def harden_evidence_permissions(path: Path | str) -> dict:
    root = Path(path)
    if not root.exists():
        raise ValueError("Evidence directory does not exist.")
    for item in [root, *root.rglob("*")]:
        os.chmod(item, 0o700 if item.is_dir() else 0o600)
    return assess_evidence_permissions(root)