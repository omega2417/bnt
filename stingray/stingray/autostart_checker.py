"""Перевірка автозапуску: реєстр, служби, заплановані завдання, драйвери."""

import platform
import subprocess
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AutostartEntry:
    name: str
    location: str
    command: str
    entry_type: str
    is_suspicious: bool = False
    reason: str = ""


@dataclass
class ServiceEntry:
    name: str
    display_name: str
    status: str
    start_type: str
    path: str
    is_suspicious: bool = False
    reason: str = ""


@dataclass
class AutostartReport:
    registry_entries: list[AutostartEntry] = field(default_factory=list)
    services: list[ServiceEntry] = field(default_factory=list)
    scheduled_tasks: list[AutostartEntry] = field(default_factory=list)
    suspicious_count: int = 0


SUSPICIOUS_PATHS = [
    "\\temp\\", "\\tmp\\", "\\appdata\\local\\temp\\",
    "\\public\\", "\\downloads\\",
]

SUSPICIOUS_KEYWORDS = [
    "powershell -enc", "powershell -e ", "cmd /c",
    "mshta", "wscript", "cscript", "regsvr32 /s /n /u",
    "rundll32", "certutil -urlcache",
]


class AutostartChecker:
    """Перевірка елементів автозапуску Windows."""

    REGISTRY_LOCATIONS = [
        r"HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
        r"HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce",
        r"HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
        r"HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce",
        r"HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run",
    ]

    def __init__(self):
        self._is_windows = platform.system() == "Windows"

    def check_all(self) -> AutostartReport:
        report = AutostartReport()
        if not self._is_windows:
            return report

        report.registry_entries = self._check_registry()
        report.services = self._check_services()
        report.scheduled_tasks = self._check_scheduled_tasks()

        report.suspicious_count = (
            sum(1 for e in report.registry_entries if e.is_suspicious)
            + sum(1 for s in report.services if s.is_suspicious)
            + sum(1 for t in report.scheduled_tasks if t.is_suspicious)
        )
        return report

    def _is_path_suspicious(self, path: str) -> Optional[str]:
        path_lower = path.lower()
        for sp in SUSPICIOUS_PATHS:
            if sp in path_lower:
                return f"Виконується з підозрілого шляху: {sp}"
        for kw in SUSPICIOUS_KEYWORDS:
            if kw.lower() in path_lower:
                return f"Підозрілий параметр: {kw}"
        return None

    def _check_registry(self) -> list[AutostartEntry]:
        entries = []
        for loc in self.REGISTRY_LOCATIONS:
            try:
                result = subprocess.run(
                    ["powershell", "-Command",
                     f"Get-ItemProperty '{loc}' -ErrorAction SilentlyContinue "
                     f"| Select-Object * -ExcludeProperty PS*"],
                    capture_output=True, text=True, timeout=15,
                )
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if ":" in line and not line.startswith("("):
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            name = parts[0].strip()
                            cmd = parts[1].strip()
                            entry = AutostartEntry(
                                name=name, location=loc,
                                command=cmd, entry_type="registry",
                            )
                            reason = self._is_path_suspicious(cmd)
                            if reason:
                                entry.is_suspicious = True
                                entry.reason = reason
                            entries.append(entry)
            except Exception:
                pass
        return entries

    def _check_services(self) -> list[ServiceEntry]:
        services = []
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-WmiObject Win32_Service | Select-Object Name,DisplayName,"
                 "State,StartMode,PathName | ConvertTo-Json"],
                capture_output=True, text=True, timeout=30,
            )
            import json
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                data = [data]
            for svc in data:
                path = svc.get("PathName", "")
                entry = ServiceEntry(
                    name=svc.get("Name", ""),
                    display_name=svc.get("DisplayName", ""),
                    status=svc.get("State", ""),
                    start_type=svc.get("StartMode", ""),
                    path=path,
                )
                reason = self._is_path_suspicious(path)
                if reason:
                    entry.is_suspicious = True
                    entry.reason = reason
                services.append(entry)
        except Exception:
            pass
        return services

    def _check_scheduled_tasks(self) -> list[AutostartEntry]:
        tasks = []
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-ScheduledTask | Where-Object {$_.State -ne 'Disabled'} "
                 "| Select-Object TaskName,TaskPath | ConvertTo-Json"],
                capture_output=True, text=True, timeout=30,
            )
            import json
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                data = [data]
            for task in data:
                entry = AutostartEntry(
                    name=task.get("TaskName", ""),
                    location=task.get("TaskPath", ""),
                    command="",
                    entry_type="scheduled_task",
                )
                tasks.append(entry)
        except Exception:
            pass
        return tasks
