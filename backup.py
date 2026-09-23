from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


MANIFEST_NAME = "signal-ledger-backup-manifest.json"


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def create_backup(source_dir: Path | str, destination_dir: Path | str) -> dict:
    source = Path(source_dir)
    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).isoformat()
    archive = destination / f"signal-ledger-backup-{created_at.replace(':', '').replace('+00:00', 'Z')}.zip"
    files = []
    with ZipFile(archive, "w", ZIP_DEFLATED) as zip_file:
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            relative_path = path.relative_to(source).as_posix()
            content = path.read_bytes()
            zip_file.writestr(relative_path, content)
            files.append({"path": relative_path, "size_bytes": len(content), "sha256": _sha256(content)})
        manifest = {"format": "signal-ledger-backup-v1", "created_at": created_at, "files": files}
        zip_file.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2, sort_keys=True))
    return {"archive": str(archive), "created_at": created_at, "files": len(files), "manifest_sha256": _sha256(json.dumps(manifest, sort_keys=True).encode("utf-8"))}


def verify_backup(archive_path: Path | str) -> dict:
    archive = Path(archive_path)
    if not archive.exists():
        return {"valid": False, "files": 0, "issues": ["Backup archive not found."]}
    try:
        with ZipFile(archive) as zip_file:
            manifest = json.loads(zip_file.read(MANIFEST_NAME))
            issues = []
            for entry in manifest.get("files", []):
                try:
                    content = zip_file.read(entry["path"])
                except KeyError:
                    issues.append(f"Missing archived file: {entry['path']}")
                    continue
                if len(content) != entry["size_bytes"] or _sha256(content) != entry["sha256"]:
                    issues.append(f"Integrity mismatch: {entry['path']}")
            return {"valid": not issues, "files": len(manifest.get("files", [])), "issues": issues, "archive": str(archive)}
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        return {"valid": False, "files": 0, "issues": [f"Backup could not be verified: {error}"], "archive": str(archive)}