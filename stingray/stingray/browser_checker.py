"""Перевірка розширень браузерів на підозрілі та шкідливі."""

import json
import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class BrowserExtension:
    name: str
    ext_id: str
    version: str
    browser: str
    path: str
    description: str = ""
    is_suspicious: bool = False
    reason: str = ""


@dataclass
class BrowserReport:
    extensions: list[BrowserExtension] = field(default_factory=list)
    suspicious_count: int = 0
    browsers_checked: list[str] = field(default_factory=list)


SUSPICIOUS_PERMISSIONS = [
    "webRequestBlocking",
    "nativeMessaging",
    "clipboardRead",
    "debugger",
    "proxy",
]

KNOWN_MALICIOUS_IDS = {
    "aaaabbbbccccddddeeeeffffgggghhh": "Відомий стілер паролів",
    "fakeidextensionmalware1234567": "Криптомайнер у розширенні",
}


class BrowserExtensionChecker:
    """Перевірка розширень Chrome, Edge, Firefox."""

    CHROME_PATHS_WIN = [
        r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Extensions",
        r"%LOCALAPPDATA%\Google\Chrome\User Data\Profile 1\Extensions",
    ]
    EDGE_PATHS_WIN = [
        r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Extensions",
    ]
    FIREFOX_PATHS_WIN = [
        r"%APPDATA%\Mozilla\Firefox\Profiles",
    ]

    CHROME_PATHS_LINUX = [
        os.path.expanduser("~/.config/google-chrome/Default/Extensions"),
        os.path.expanduser("~/.config/chromium/Default/Extensions"),
    ]

    def __init__(self):
        self._is_windows = platform.system() == "Windows"

    def check_all(self) -> BrowserReport:
        report = BrowserReport()
        report.extensions.extend(self._check_chrome())
        if self._is_windows:
            report.extensions.extend(self._check_edge())
        report.browsers_checked = self._get_checked_browsers()
        report.suspicious_count = sum(
            1 for e in report.extensions if e.is_suspicious
        )
        return report

    def _get_checked_browsers(self) -> list[str]:
        browsers = ["Google Chrome"]
        if self._is_windows:
            browsers.append("Microsoft Edge")
        return browsers

    def _get_extension_dirs(self, base_paths: list[str]) -> list[Path]:
        dirs = []
        for p in base_paths:
            expanded = os.path.expandvars(p)
            path = Path(expanded)
            if path.is_dir():
                dirs.append(path)
        return dirs

    def _parse_extension(self, ext_dir: Path, browser: str) -> Optional[BrowserExtension]:
        versions = sorted(ext_dir.iterdir()) if ext_dir.is_dir() else []
        for ver_dir in reversed(versions):
            manifest_path = ver_dir / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                ext = BrowserExtension(
                    name=manifest.get("name", ext_dir.name),
                    ext_id=ext_dir.name,
                    version=manifest.get("version", "?"),
                    browser=browser,
                    path=str(ext_dir),
                    description=manifest.get("description", ""),
                )

                if ext.ext_id in KNOWN_MALICIOUS_IDS:
                    ext.is_suspicious = True
                    ext.reason = KNOWN_MALICIOUS_IDS[ext.ext_id]
                    return ext

                permissions = manifest.get("permissions", [])
                dangerous = [p for p in permissions if p in SUSPICIOUS_PERMISSIONS]
                if len(dangerous) >= 2:
                    ext.is_suspicious = True
                    ext.reason = f"Підозрілі дозволи: {', '.join(dangerous)}"

                return ext
            except (json.JSONDecodeError, OSError):
                continue
        return None

    def _check_chrome(self) -> list[BrowserExtension]:
        paths = self.CHROME_PATHS_WIN if self._is_windows else self.CHROME_PATHS_LINUX
        ext_dirs = self._get_extension_dirs(paths)
        extensions = []
        for base in ext_dirs:
            for ext_dir in base.iterdir():
                if ext_dir.is_dir():
                    ext = self._parse_extension(ext_dir, "Chrome")
                    if ext:
                        extensions.append(ext)
        return extensions

    def _check_edge(self) -> list[BrowserExtension]:
        ext_dirs = self._get_extension_dirs(self.EDGE_PATHS_WIN)
        extensions = []
        for base in ext_dirs:
            for ext_dir in base.iterdir():
                if ext_dir.is_dir():
                    ext = self._parse_extension(ext_dir, "Edge")
                    if ext:
                        extensions.append(ext)
        return extensions
