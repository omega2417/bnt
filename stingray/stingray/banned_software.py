"""Виявлення програмного забезпечення, забороненого в Україні."""

import os
import platform
from dataclasses import dataclass, field


@dataclass
class BannedSoftwareEntry:
    name: str
    vendor: str
    reason: str
    legal_reference: str
    detection_paths: list[str] = field(default_factory=list)
    detection_processes: list[str] = field(default_factory=list)
    found: bool = False
    found_at: str = ""


BANNED_SOFTWARE_LIST: list[BannedSoftwareEntry] = [
    BannedSoftwareEntry(
        name="Kaspersky Antivirus",
        vendor="Kaspersky Lab (РФ)",
        reason="Програмне забезпечення російського походження",
        legal_reference="Указ Президента України №549/2017, рішення РНБО",
        detection_paths=[
            r"C:\Program Files\Kaspersky Lab",
            r"C:\Program Files (x86)\Kaspersky Lab",
        ],
        detection_processes=["avp.exe", "avpui.exe", "klnagent.exe"],
    ),
    BannedSoftwareEntry(
        name="Dr.Web",
        vendor="Doctor Web (РФ)",
        reason="Програмне забезпечення російського походження",
        legal_reference="Указ Президента України №549/2017",
        detection_paths=[
            r"C:\Program Files\DrWeb",
            r"C:\Program Files (x86)\DrWeb",
        ],
        detection_processes=["dwservice.exe", "dwengine.exe", "spideragent.exe"],
    ),
    BannedSoftwareEntry(
        name="1С:Підприємство",
        vendor="1С (РФ)",
        reason="Програмне забезпечення російського походження",
        legal_reference="Указ Президента України №549/2017",
        detection_paths=[
            r"C:\Program Files\1cv8",
            r"C:\Program Files (x86)\1cv8",
            r"C:\Program Files\1cv82",
        ],
        detection_processes=["1cv8.exe", "1cv8s.exe", "ragent.exe"],
    ),
    BannedSoftwareEntry(
        name="Яндекс.Браузер",
        vendor="Yandex (РФ)",
        reason="Програмне забезпечення російського походження",
        legal_reference="Указ Президента України №549/2017",
        detection_paths=[
            r"C:\Users\*\AppData\Local\Yandex\YandexBrowser",
        ],
        detection_processes=["browser.exe"],
    ),
    BannedSoftwareEntry(
        name="Mail.ru Agent",
        vendor="VK / Mail.ru Group (РФ)",
        reason="Програмне забезпечення російського походження",
        legal_reference="Указ Президента України №549/2017",
        detection_paths=[
            r"C:\Program Files\Mail.Ru",
            r"C:\Program Files (x86)\Mail.Ru",
        ],
        detection_processes=["magent.exe"],
    ),
    BannedSoftwareEntry(
        name="Punto Switcher",
        vendor="Yandex (РФ)",
        reason="Програмне забезпечення російського походження, може працювати як кейлогер",
        legal_reference="Указ Президента України №549/2017",
        detection_paths=[
            r"C:\Program Files\Yandex\Punto Switcher",
        ],
        detection_processes=["punto.exe"],
    ),
]


class BannedSoftwareChecker:
    """Виявлення забороненого в Україні програмного забезпечення."""

    def __init__(self, software_list: list[BannedSoftwareEntry] | None = None):
        self.software_list = software_list or [
            BannedSoftwareEntry(**{
                k: (list(v) if isinstance(v, list) else v)
                for k, v in s.__dict__.items()
            })
            for s in BANNED_SOFTWARE_LIST
        ]
        self._is_windows = platform.system() == "Windows"

    def check_all(self) -> list[BannedSoftwareEntry]:
        if not self._is_windows:
            return self.software_list

        for entry in self.software_list:
            for path_pattern in entry.detection_paths:
                if "*" in path_pattern:
                    import glob
                    matches = glob.glob(path_pattern)
                    if matches:
                        entry.found = True
                        entry.found_at = matches[0]
                        break
                elif os.path.exists(path_pattern):
                    entry.found = True
                    entry.found_at = path_pattern
                    break

            if not entry.found and entry.detection_processes:
                try:
                    import psutil
                    running = {p.info["name"].lower()
                               for p in psutil.process_iter(["name"])
                               if p.info["name"]}
                    for proc_name in entry.detection_processes:
                        if proc_name.lower() in running:
                            entry.found = True
                            entry.found_at = f"Процес: {proc_name}"
                            break
                except Exception:
                    pass

        return self.software_list

    def get_found(self) -> list[BannedSoftwareEntry]:
        return [e for e in self.software_list if e.found]

    def get_summary(self) -> str:
        found = self.get_found()
        if not found:
            return "Забороненого ПЗ не виявлено."
        lines = [f"Виявлено {len(found)} заборонених програм:"]
        for e in found:
            lines.append(f"  - {e.name} ({e.vendor}): {e.found_at}")
            lines.append(f"    Підстава: {e.legal_reference}")
        return "\n".join(lines)
