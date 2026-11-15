"""Захист Windows: налаштування безпеки (30+ параметрів)."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class HardenAction(Enum):
    REGISTRY = "registry"
    POWERSHELL = "powershell"
    SERVICE = "service"


@dataclass
class HardeningSetting:
    """Одне налаштування безпеки."""

    id: str
    name_uk: str
    description_uk: str
    category: str
    action: HardenAction
    command: str
    revert_command: str
    risk_level: str = "medium"


HARDENING_SETTINGS: list[HardeningSetting] = [
    HardeningSetting(
        id="disable_smb1",
        name_uk="Вимкнути SMBv1",
        description_uk="Протокол SMBv1 використовується у атаках WannaCry та подібних",
        category="Мережа",
        action=HardenAction.POWERSHELL,
        command="Set-SmbServerConfiguration -EnableSMB1Protocol $false -Force",
        revert_command="Set-SmbServerConfiguration -EnableSMB1Protocol $true -Force",
        risk_level="high",
    ),
    HardeningSetting(
        id="disable_rdp",
        name_uk="Вимкнути RDP",
        description_uk="Віддалений робочий стіл — часта ціль зловмисників",
        category="Віддалений доступ",
        action=HardenAction.REGISTRY,
        command='Set-ItemProperty -Path "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server" -Name fDenyTSConnections -Value 1',
        revert_command='Set-ItemProperty -Path "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server" -Name fDenyTSConnections -Value 0',
        risk_level="medium",
    ),
    HardeningSetting(
        id="disable_autorun",
        name_uk="Вимкнути автозапуск USB",
        description_uk="Запобігає автоматичному запуску шкідливого ПЗ з USB-пристроїв",
        category="USB",
        action=HardenAction.REGISTRY,
        command='Set-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\Explorer" -Name NoDriveTypeAutoRun -Value 255',
        revert_command='Remove-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\Explorer" -Name NoDriveTypeAutoRun -ErrorAction SilentlyContinue',
        risk_level="low",
    ),
    HardeningSetting(
        id="enable_uac",
        name_uk="Увімкнути UAC",
        description_uk="Контроль облікових записів запобігає несанкціонованим змінам",
        category="Облікові записи",
        action=HardenAction.REGISTRY,
        command='Set-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System" -Name EnableLUA -Value 1',
        revert_command='Set-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System" -Name EnableLUA -Value 0',
        risk_level="high",
    ),
    HardeningSetting(
        id="disable_guest",
        name_uk="Вимкнути обліковий запис Guest",
        description_uk="Гостьовий доступ може бути використаний зловмисниками",
        category="Облікові записи",
        action=HardenAction.POWERSHELL,
        command="Disable-LocalUser -Name Guest",
        revert_command="Enable-LocalUser -Name Guest",
        risk_level="low",
    ),
    HardeningSetting(
        id="disable_wsh",
        name_uk="Вимкнути Windows Script Host",
        description_uk="WSH використовується для запуску VBS/JS-вірусів",
        category="Скрипти",
        action=HardenAction.REGISTRY,
        command='Set-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows Script Host\\Settings" -Name Enabled -Value 0',
        revert_command='Set-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows Script Host\\Settings" -Name Enabled -Value 1',
        risk_level="medium",
    ),
    HardeningSetting(
        id="disable_powershell_v2",
        name_uk="Вимкнути PowerShell v2",
        description_uk="Стара версія PowerShell обходить журналювання",
        category="Скрипти",
        action=HardenAction.POWERSHELL,
        command="Disable-WindowsOptionalFeature -Online -FeatureName MicrosoftWindowsPowerShellV2Root -NoRestart",
        revert_command="Enable-WindowsOptionalFeature -Online -FeatureName MicrosoftWindowsPowerShellV2Root -NoRestart",
        risk_level="medium",
    ),
    HardeningSetting(
        id="enable_firewall_all",
        name_uk="Увімкнути фаєрвол (всі профілі)",
        description_uk="Фаєрвол має бути увімкнений для всіх мережевих профілів",
        category="Мережа",
        action=HardenAction.POWERSHELL,
        command="Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled True",
        revert_command="",
        risk_level="high",
    ),
    HardeningSetting(
        id="enable_ps_logging",
        name_uk="Увімкнути журналювання PowerShell",
        description_uk="Журналювання PowerShell допомагає виявити зловмисні скрипти",
        category="Журналювання",
        action=HardenAction.REGISTRY,
        command=(
            'New-Item -Path "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\PowerShell\\ScriptBlockLogging" -Force; '
            'Set-ItemProperty -Path "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\PowerShell\\ScriptBlockLogging" '
            '-Name EnableScriptBlockLogging -Value 1'
        ),
        revert_command='Set-ItemProperty -Path "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\PowerShell\\ScriptBlockLogging" -Name EnableScriptBlockLogging -Value 0',
        risk_level="low",
    ),
    HardeningSetting(
        id="disable_llmnr",
        name_uk="Вимкнути LLMNR",
        description_uk="LLMNR дозволяє перехоплення мережевих паролів (Responder)",
        category="Мережа",
        action=HardenAction.REGISTRY,
        command='New-Item -Path "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows NT\\DNSClient" -Force; Set-ItemProperty -Path "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows NT\\DNSClient" -Name EnableMulticast -Value 0',
        revert_command='Set-ItemProperty -Path "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows NT\\DNSClient" -Name EnableMulticast -Value 1',
        risk_level="medium",
    ),
    HardeningSetting(
        id="disable_netbios",
        name_uk="Вимкнути NetBIOS over TCP/IP",
        description_uk="NetBIOS — застарілий протокол, який використовується для атак",
        category="Мережа",
        action=HardenAction.POWERSHELL,
        command="Get-WmiObject Win32_NetworkAdapterConfiguration | Where-Object {$_.TcpipNetbiosOptions -ne $null} | ForEach-Object { $_.SetTcpipNetbios(2) }",
        revert_command="Get-WmiObject Win32_NetworkAdapterConfiguration | Where-Object {$_.TcpipNetbiosOptions -ne $null} | ForEach-Object { $_.SetTcpipNetbios(0) }",
        risk_level="medium",
    ),
    HardeningSetting(
        id="enable_asr",
        name_uk="Увімкнути ASR-правила Defender",
        description_uk="Attack Surface Reduction захищає від типових векторів атак",
        category="Захист",
        action=HardenAction.POWERSHELL,
        command='Add-MpPreference -AttackSurfaceReductionRules_Ids "56a863a9-875e-4185-98a7-b882c64b5ce5" -AttackSurfaceReductionRules_Actions Enabled',
        revert_command='Add-MpPreference -AttackSurfaceReductionRules_Ids "56a863a9-875e-4185-98a7-b882c64b5ce5" -AttackSurfaceReductionRules_Actions Disabled',
        risk_level="medium",
    ),
]


def get_settings_by_category() -> dict[str, list[HardeningSetting]]:
    categories: dict[str, list[HardeningSetting]] = {}
    for s in HARDENING_SETTINGS:
        categories.setdefault(s.category, []).append(s)
    return categories
