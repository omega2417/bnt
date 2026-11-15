"""Перевірка цілісності системних файлів та самого набору Stingray."""

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class IntegrityResult:
    file_path: str
    expected_hash: str
    actual_hash: str
    is_valid: bool


@dataclass
class IntegrityReport:
    total_files: int = 0
    valid_files: int = 0
    invalid_files: int = 0
    missing_files: int = 0
    results: list[IntegrityResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class IntegrityChecker:
    """Перевірка цілісності файлів за збереженими хешами."""

    def __init__(self, algorithm: str = "sha256"):
        self.algorithm = algorithm

    def compute_hash(self, file_path: str | Path) -> str:
        h = hashlib.new(self.algorithm)
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def create_manifest(self, directory: str | Path,
                        output_path: str | Path,
                        extensions: Optional[set[str]] = None) -> int:
        directory = Path(directory)
        output_path = Path(output_path)
        manifest = {}

        for root, _dirs, files in os.walk(directory):
            for fname in files:
                fpath = Path(root) / fname
                if extensions and fpath.suffix.lower() not in extensions:
                    continue
                rel = str(fpath.relative_to(directory))
                manifest[rel] = self.compute_hash(fpath)

        output_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return len(manifest)

    def verify_manifest(self, directory: str | Path,
                        manifest_path: str | Path) -> IntegrityReport:
        directory = Path(directory)
        manifest_path = Path(manifest_path)
        report = IntegrityReport()

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        for rel_path, expected_hash in manifest.items():
            report.total_files += 1
            full_path = directory / rel_path

            if not full_path.exists():
                report.missing_files += 1
                report.results.append(IntegrityResult(
                    file_path=rel_path,
                    expected_hash=expected_hash,
                    actual_hash="MISSING",
                    is_valid=False,
                ))
                continue

            try:
                actual = self.compute_hash(full_path)
                is_valid = actual == expected_hash
                report.results.append(IntegrityResult(
                    file_path=rel_path,
                    expected_hash=expected_hash,
                    actual_hash=actual,
                    is_valid=is_valid,
                ))
                if is_valid:
                    report.valid_files += 1
                else:
                    report.invalid_files += 1
            except Exception as e:
                report.errors.append(f"{rel_path}: {e}")

        return report

    def verify_self(self, stingray_root: str | Path) -> IntegrityReport:
        """Перевірка цілісності самого набору Stingray."""
        stingray_root = Path(stingray_root)
        manifest_path = stingray_root / "integrity_manifest.json"
        if not manifest_path.exists():
            report = IntegrityReport()
            report.errors.append("Маніфест цілісності не знайдено")
            return report
        return self.verify_manifest(stingray_root, manifest_path)
