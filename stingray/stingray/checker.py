"""Перевірка стану системи: антивірус, оновлення, налаштування, автозапуск."""

import platform
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CheckStatus(Enum):
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    SKIPPED = "skipped"


@dataclass
class CheckResult:
    """Результат однієї перевірки."""

    name: str
    name_uk: str
    status: CheckStatus
    message: str
    details: Optional[str] = None


@dataclass
class SystemCheckReport:
    """Зведений звіт перевірки системи."""

    hostname: str = ""
    os_version: str = ""
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.WARNING)

    @property
    def ok_count(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.OK)


class SystemChecker:
    """Перевірка стану Windows-системи."""

    def __init__(self):
        self._is_windows = platform.system() == "Windows"

    def run_all_checks(self) -> SystemCheckReport:
        report = SystemCheckReport(
            hostname=platform.node(),
            os_version=platform.platform(),
        )

        report.checks.append(self.check_antivirus())
        report.checks.append(self.check_firewall())
        report.checks.append(self.check_uac())
        report.checks.append(self.check_rdp())
        report.checks.append(self.check_smb_v1())
        report.checks.append(self.check_autorun())
        report.checks.append(self.check_guest_account())

        return report

    def check_antivirus(self) -> CheckResult:
        if not self._is_windows:
            return CheckResult(
                name="antivirus",
                name_uk="Антивірус",
                status=CheckStatus.SKIPPED,
                message="Перевірка доступна лише на Windows",
            )
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-MpComputerStatus | Select-Object -Property "
                 "AntivirusEnabled,RealTimeProtectionEnabled"],
                capture_output=True, text=True, timeout=30,
            )
            output = result.stdout
            if "True" in output:
                return CheckResult(
                    name="antivirus",
                    name_uk="Антивірус",
                    status=CheckStatus.OK,
                    message="Windows Defender увімкнений",
                    details=output.strip(),
                )
            return CheckResult(
                name="antivirus",
                name_uk="Антивірус",
                status=CheckStatus.CRITICAL,
                message="Антивірус вимкнений!",
                details=output.strip(),
            )
        except Exception as e:
            return CheckResult(
                name="antivirus",
                name_uk="Антивірус",
                status=CheckStatus.WARNING,
                message=f"Не вдалося перевірити: {e}",
            )

    def check_firewall(self) -> CheckResult:
        if not self._is_windows:
            return CheckResult(
                name="firewall", name_uk="Фаєрвол",
                status=CheckStatus.SKIPPED,
                message="Перевірка доступна лише на Windows",
            )
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-NetFirewallProfile | Select-Object Name,Enabled"],
                capture_output=True, text=True, timeout=30,
            )
            if "False" in result.stdout:
                return CheckResult(
                    name="firewall", name_uk="Фаєрвол",
                    status=CheckStatus.CRITICAL,
                    message="Один або декілька профілів фаєрвола вимкнені!",
                    details=result.stdout.strip(),
                )
            return CheckResult(
                name="firewall", name_uk="Фаєрвол",
                status=CheckStatus.OK,
                message="Фаєрвол увімкнений",
            )
        except Exception as e:
            return CheckResult(
                name="firewall", name_uk="Фаєрвол",
                status=CheckStatus.WARNING, message=f"Не вдалося перевірити: {e}",
            )

    def check_uac(self) -> CheckResult:
        if not self._is_windows:
            return CheckResult(
                name="uac", name_uk="UAC",
                status=CheckStatus.SKIPPED,
                message="Перевірка доступна лише на Windows",
            )
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-ItemProperty "
                 "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System"
                 ").EnableLUA"],
                capture_output=True, text=True, timeout=15,
            )
            if result.stdout.strip() == "1":
                return CheckResult(
                    name="uac", name_uk="UAC",
                    status=CheckStatus.OK,
                    message="UAC увімкнений",
                )
            return CheckResult(
                name="uac", name_uk="UAC",
                status=CheckStatus.CRITICAL,
                message="UAC вимкнений — це небезпечно!",
            )
        except Exception as e:
            return CheckResult(
                name="uac", name_uk="UAC",
                status=CheckStatus.WARNING, message=f"Не вдалося перевірити: {e}",
            )

    def check_rdp(self) -> CheckResult:
        if not self._is_windows:
            return CheckResult(
                name="rdp", name_uk="Віддалений доступ (RDP)",
                status=CheckStatus.SKIPPED,
                message="Перевірка доступна лише на Windows",
            )
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-ItemProperty "
                 "'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server'"
                 ").fDenyTSConnections"],
                capture_output=True, text=True, timeout=15,
            )
            if result.stdout.strip() == "1":
                return CheckResult(
                    name="rdp", name_uk="Віддалений доступ (RDP)",
                    status=CheckStatus.OK,
                    message="RDP вимкнений",
                )
            return CheckResult(
                name="rdp", name_uk="Віддалений доступ (RDP)",
                status=CheckStatus.WARNING,
                message="RDP увімкнений — переконайтесь, що це потрібно",
            )
        except Exception as e:
            return CheckResult(
                name="rdp", name_uk="Віддалений доступ (RDP)",
                status=CheckStatus.WARNING, message=f"Не вдалося перевірити: {e}",
            )

    def check_smb_v1(self) -> CheckResult:
        if not self._is_windows:
            return CheckResult(
                name="smbv1", name_uk="SMBv1",
                status=CheckStatus.SKIPPED,
                message="Перевірка доступна лише на Windows",
            )
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-SmbServerConfiguration).EnableSMB1Protocol"],
                capture_output=True, text=True, timeout=15,
            )
            if "True" in result.stdout:
                return CheckResult(
                    name="smbv1", name_uk="SMBv1",
                    status=CheckStatus.CRITICAL,
                    message="SMBv1 увімкнений — це вразливість (WannaCry)!",
                )
            return CheckResult(
                name="smbv1", name_uk="SMBv1",
                status=CheckStatus.OK,
                message="SMBv1 вимкнений",
            )
        except Exception as e:
            return CheckResult(
                name="smbv1", name_uk="SMBv1",
                status=CheckStatus.WARNING, message=f"Не вдалося перевірити: {e}",
            )

    def check_autorun(self) -> CheckResult:
        if not self._is_windows:
            return CheckResult(
                name="autorun", name_uk="Автозапуск USB",
                status=CheckStatus.SKIPPED,
                message="Перевірка доступна лише на Windows",
            )
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-ItemProperty "
                 "'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\Explorer' "
                 "-ErrorAction SilentlyContinue).NoDriveTypeAutoRun"],
                capture_output=True, text=True, timeout=15,
            )
            val = result.stdout.strip()
            if val == "255":
                return CheckResult(
                    name="autorun", name_uk="Автозапуск USB",
                    status=CheckStatus.OK,
                    message="Автозапуск вимкнений для всіх дисків",
                )
            return CheckResult(
                name="autorun", name_uk="Автозапуск USB",
                status=CheckStatus.WARNING,
                message=f"Автозапуск не повністю вимкнений (значення: {val})",
            )
        except Exception as e:
            return CheckResult(
                name="autorun", name_uk="Автозапуск USB",
                status=CheckStatus.WARNING, message=f"Не вдалося перевірити: {e}",
            )

    def check_guest_account(self) -> CheckResult:
        if not self._is_windows:
            return CheckResult(
                name="guest", name_uk="Обліковий запис Guest",
                status=CheckStatus.SKIPPED,
                message="Перевірка доступна лише на Windows",
            )
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-LocalUser -Name Guest).Enabled"],
                capture_output=True, text=True, timeout=15,
            )
            if "True" in result.stdout:
                return CheckResult(
                    name="guest", name_uk="Обліковий запис Guest",
                    status=CheckStatus.WARNING,
                    message="Guest-обліковий запис увімкнений",
                )
            return CheckResult(
                name="guest", name_uk="Обліковий запис Guest",
                status=CheckStatus.OK,
                message="Guest-обліковий запис вимкнений",
            )
        except Exception as e:
            return CheckResult(
                name="guest", name_uk="Обліковий запис Guest",
                status=CheckStatus.WARNING, message=f"Не вдалося перевірити: {e}",
            )
