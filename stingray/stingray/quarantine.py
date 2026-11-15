"""Карантин: ізоляція підозрілих файлів з можливістю повернення."""

import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class QuarantineEntry:
    original_path: str
    quarantine_name: str
    threat_name: str
    timestamp: str
    sha256: str


class QuarantineManager:
    """Керування карантином файлів."""

    MANIFEST_NAME = "manifest.json"

    def __init__(self, quarantine_dir: str | Path):
        self.quarantine_dir = Path(quarantine_dir)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self.quarantine_dir / self.MANIFEST_NAME
        self._entries: list[QuarantineEntry] = []
        self._load_manifest()

    def _load_manifest(self):
        if self._manifest_path.exists():
            data = json.loads(self._manifest_path.read_text(encoding="utf-8"))
            self._entries = [QuarantineEntry(**e) for e in data]

    def _save_manifest(self):
        data = [e.__dict__ for e in self._entries]
        self._manifest_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def quarantine_file(
        self, file_path: str | Path, threat_name: str
    ) -> QuarantineEntry:
        from .signatures import compute_file_hash

        file_path = Path(file_path)
        sha256 = compute_file_hash(file_path, "sha256")
        ts = datetime.now(timezone.utc).isoformat()
        q_name = f"{ts.replace(':', '-')}_{file_path.name}.quarantined"

        dest = self.quarantine_dir / q_name
        shutil.move(str(file_path), str(dest))

        entry = QuarantineEntry(
            original_path=str(file_path),
            quarantine_name=q_name,
            threat_name=threat_name,
            timestamp=ts,
            sha256=sha256,
        )
        self._entries.append(entry)
        self._save_manifest()
        return entry

    def restore_file(self, index: int) -> Optional[str]:
        if index < 0 or index >= len(self._entries):
            return None

        entry = self._entries[index]
        src = self.quarantine_dir / entry.quarantine_name
        if not src.exists():
            return None

        dest = Path(entry.original_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))

        self._entries.pop(index)
        self._save_manifest()
        return str(dest)

    def list_entries(self) -> list[QuarantineEntry]:
        return list(self._entries)

    def delete_entry(self, index: int) -> bool:
        if index < 0 or index >= len(self._entries):
            return False
        entry = self._entries[index]
        q_file = self.quarantine_dir / entry.quarantine_name
        if q_file.exists():
            q_file.unlink()
        self._entries.pop(index)
        self._save_manifest()
        return True
