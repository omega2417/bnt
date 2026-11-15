"""Перевірка мережевих з'єднань: виявлення зв'язку з відомими C2-серверами."""

import socket
from dataclasses import dataclass, field
from typing import Optional

KNOWN_C2_DOMAINS = [
    "cobaltstrike.example.com",
    "evil-c2.example.net",
    "malware-panel.example.org",
    "apt28-infrastructure.example.com",
    "sandworm-c2.example.net",
    "gamaredon-server.example.org",
    "armageddon-c2.example.com",
    "uat-0056.example.net",
]

KNOWN_C2_IPS = [
    "198.51.100.1",
    "198.51.100.2",
    "203.0.113.50",
    "203.0.113.100",
]


@dataclass
class ConnectionInfo:
    local_addr: str
    local_port: int
    remote_addr: str
    remote_port: int
    status: str
    pid: Optional[int] = None
    process_name: Optional[str] = None
    is_suspicious: bool = False
    reason: str = ""


@dataclass
class NetworkReport:
    total_connections: int = 0
    suspicious_connections: int = 0
    connections: list[ConnectionInfo] = field(default_factory=list)


class NetworkChecker:
    """Перевірка активних мережевих з'єднань."""

    def __init__(self, c2_domains: Optional[list[str]] = None,
                 c2_ips: Optional[list[str]] = None):
        self.c2_domains = set(c2_domains or KNOWN_C2_DOMAINS)
        self.c2_ips = set(c2_ips or KNOWN_C2_IPS)
        self._resolved_ips: dict[str, str] = {}

    def _resolve_domain(self, domain: str) -> Optional[str]:
        if domain in self._resolved_ips:
            return self._resolved_ips[domain]
        try:
            ip = socket.gethostbyname(domain)
            self._resolved_ips[domain] = ip
            return ip
        except socket.gaierror:
            return None

    def check_connections(self) -> NetworkReport:
        report = NetworkReport()
        try:
            import psutil
        except ImportError:
            return report

        for conn in psutil.net_connections(kind="inet"):
            if not conn.raddr:
                continue
            remote_ip = conn.raddr.ip
            remote_port = conn.raddr.port

            ci = ConnectionInfo(
                local_addr=conn.laddr.ip if conn.laddr else "",
                local_port=conn.laddr.port if conn.laddr else 0,
                remote_addr=remote_ip,
                remote_port=remote_port,
                status=conn.status,
                pid=conn.pid,
            )

            if conn.pid:
                try:
                    proc = psutil.Process(conn.pid)
                    ci.process_name = proc.name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            if remote_ip in self.c2_ips:
                ci.is_suspicious = True
                ci.reason = f"IP {remote_ip} у списку відомих C2-серверів"

            if remote_port in (4444, 5555, 8443, 9999, 1337, 31337):
                ci.is_suspicious = True
                ci.reason = f"Порт {remote_port} часто використовується зловмисниками"

            report.connections.append(ci)
            report.total_connections += 1
            if ci.is_suspicious:
                report.suspicious_connections += 1

        return report

    def check_dns_cache(self) -> list[str]:
        """Перевірка DNS-кешу на відомі C2-домени (Windows)."""
        import platform
        import subprocess
        found = []
        if platform.system() != "Windows":
            return found
        try:
            result = subprocess.run(
                ["powershell", "-Command", "Get-DnsClientCache | Select-Object Entry"],
                capture_output=True, text=True, timeout=30,
            )
            for line in result.stdout.splitlines():
                entry = line.strip()
                for domain in self.c2_domains:
                    if domain.lower() in entry.lower():
                        found.append(entry)
        except Exception:
            pass
        return found
