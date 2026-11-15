"""Менеджер сигнатур: завантаження хешів та YARA-правил."""

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class SignatureDB:
    """База сигнатур шкідливого ПЗ."""

    md5_hashes: dict[str, str] = field(default_factory=dict)
    sha256_hashes: dict[str, str] = field(default_factory=dict)
    yara_rules_path: Optional[Path] = None
    total_signatures: int = 0

    @classmethod
    def load(cls, db_path: str | Path) -> "SignatureDB":
        db_path = Path(db_path)
        db = cls()

        hashes_file = db_path / "hashes.json"
        if hashes_file.exists():
            data = json.loads(hashes_file.read_text(encoding="utf-8"))
            db.md5_hashes = data.get("md5", {})
            db.sha256_hashes = data.get("sha256", {})

        yara_dir = db_path / "yara_rules"
        if yara_dir.is_dir():
            db.yara_rules_path = yara_dir

        db.total_signatures = len(db.md5_hashes) + len(db.sha256_hashes)
        return db

    def check_hash(self, file_path: str | Path) -> Optional[str]:
        file_path = Path(file_path)
        if not file_path.exists():
            return None

        md5 = hashlib.md5()
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5.update(chunk)
                sha256.update(chunk)

        md5_hex = md5.hexdigest()
        sha256_hex = sha256.hexdigest()

        if md5_hex in self.md5_hashes:
            return self.md5_hashes[md5_hex]
        if sha256_hex in self.sha256_hashes:
            return self.sha256_hashes[sha256_hex]
        return None


def compute_file_hash(file_path: str | Path, algorithm: str = "sha256") -> str:
    h = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
