"""Сканер: пошук шкідливого ПЗ за хешами та YARA-правилами."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .signatures import SignatureDB


@dataclass
class ScanResult:
    """Результат сканування одного файлу."""

    file_path: str
    threat_name: Optional[str] = None
    detection_method: str = ""
    is_malicious: bool = False


@dataclass
class ScanReport:
    """Зведений звіт сканування."""

    scanned_files: int = 0
    threats_found: int = 0
    results: list[ScanResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return self.threats_found == 0


class StingrayScanner:
    """Основний сканер Stingray."""

    SUSPICIOUS_EXTENSIONS = {
        ".exe", ".dll", ".scr", ".bat", ".cmd", ".ps1",
        ".vbs", ".js", ".wsf", ".hta", ".msi", ".com",
    }

    def __init__(self, signature_db: SignatureDB):
        self.db = signature_db
        self._yara_rules = None

    def _load_yara_rules(self):
        if self._yara_rules is not None:
            return
        try:
            import yara
        except ImportError:
            self._yara_rules = False
            return

        if self.db.yara_rules_path and self.db.yara_rules_path.is_dir():
            rule_files = {}
            for f in self.db.yara_rules_path.glob("*.yar"):
                rule_files[f.stem] = str(f)
            if rule_files:
                self._yara_rules = yara.compile(filepaths=rule_files)
                return
        self._yara_rules = False

    def scan_file(self, file_path: str | Path) -> ScanResult:
        file_path = Path(file_path)
        result = ScanResult(file_path=str(file_path))

        threat = self.db.check_hash(file_path)
        if threat:
            result.threat_name = threat
            result.detection_method = "hash"
            result.is_malicious = True
            return result

        self._load_yara_rules()
        if self._yara_rules and self._yara_rules is not False:
            try:
                matches = self._yara_rules.match(str(file_path))
                if matches:
                    result.threat_name = matches[0].rule
                    result.detection_method = "yara"
                    result.is_malicious = True
                    return result
            except Exception:
                pass

        return result

    def scan_directory(
        self,
        directory: str | Path,
        recursive: bool = True,
        extensions: Optional[set[str]] = None,
        callback=None,
    ) -> ScanReport:
        directory = Path(directory)
        report = ScanReport()
        exts = extensions or self.SUSPICIOUS_EXTENSIONS

        for root, _dirs, files in os.walk(directory):
            if not recursive and root != str(directory):
                break
            for fname in files:
                fpath = Path(root) / fname
                if exts and fpath.suffix.lower() not in exts:
                    continue
                try:
                    sr = self.scan_file(fpath)
                    report.scanned_files += 1
                    report.results.append(sr)
                    if sr.is_malicious:
                        report.threats_found += 1
                    if callback:
                        callback(sr)
                except Exception as e:
                    report.errors.append(f"{fpath}: {e}")

        return report
