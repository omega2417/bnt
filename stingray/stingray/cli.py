"""CLI-інтерфейс Stingray."""

import argparse
import sys
from pathlib import Path

from . import __version__
from .checker import SystemChecker
from .quarantine import QuarantineManager
from .report import generate_report
from .scanner import ScanReport, StingrayScanner
from .signatures import SignatureDB


def main():
    parser = argparse.ArgumentParser(
        prog="stingray",
        description="Stingray — офлайн-набір для перевірки та захисту ПК",
    )
    parser.add_argument("--version", action="version", version=f"Stingray {__version__}")

    sub = parser.add_subparsers(dest="command")

    # scan
    sp_scan = sub.add_parser("scan", help="Сканування на шкідливе ПЗ")
    sp_scan.add_argument("path", help="Директорія для сканування")
    sp_scan.add_argument("--signatures", "-s", default="demo_signatures",
                         help="Шлях до бази сигнатур")
    sp_scan.add_argument("--all-files", action="store_true",
                         help="Сканувати всі файли, не лише виконувані")

    # check
    sub.add_parser("check", help="Перевірка стану системи")

    # report
    sp_report = sub.add_parser("report", help="Повна перевірка з HTML-звітом")
    sp_report.add_argument("--scan-path", default=".",
                           help="Директорія для сканування")
    sp_report.add_argument("--signatures", "-s", default="demo_signatures",
                           help="Шлях до бази сигнатур")
    sp_report.add_argument("--output", "-o", default="stingray_report.html",
                           help="Шлях до HTML-звіту")

    # quarantine
    sp_q = sub.add_parser("quarantine", help="Керування карантином")
    sp_q.add_argument("action", choices=["list", "restore", "delete"])
    sp_q.add_argument("--index", type=int, help="Індекс елемента")
    sp_q.add_argument("--dir", default=".stingray_quarantine",
                       help="Директорія карантину")

    args = parser.parse_args()

    if args.command == "scan":
        db = SignatureDB.load(args.signatures)
        scanner = StingrayScanner(db)
        exts = None if args.all_files else None
        print(f"[Stingray] Сканування: {args.path}")
        print(f"[Stingray] Сигнатур: {db.total_signatures}")

        def on_scan(result):
            if result.is_malicious:
                print(f"  ⚠ ЗАГРОЗА: {result.file_path} → {result.threat_name}")

        report = scanner.scan_directory(args.path, extensions=exts, callback=on_scan)
        print(f"\n[Stingray] Готово: {report.scanned_files} файлів, "
              f"{report.threats_found} загроз")

    elif args.command == "check":
        checker = SystemChecker()
        report = checker.run_all_checks()
        print(f"[Stingray] Перевірка системи: {report.hostname}")
        print(f"[Stingray] ОС: {report.os_version}\n")
        for c in report.checks:
            icon = {"ok": "✓", "warning": "⚠", "critical": "✗", "skipped": "○"}
            print(f"  {icon.get(c.status.value, '?')} {c.name_uk}: {c.message}")
        print(f"\n  Критичних: {report.critical_count}, "
              f"Попереджень: {report.warning_count}, Добре: {report.ok_count}")

    elif args.command == "report":
        db = SignatureDB.load(args.signatures)
        scanner = StingrayScanner(db)
        checker = SystemChecker()

        print("[Stingray] Перевірка системи...")
        sys_report = checker.run_all_checks()

        print(f"[Stingray] Сканування: {args.scan_path}")
        scan_report = scanner.scan_directory(args.scan_path)

        out = generate_report(sys_report, scan_report, args.output)
        print(f"[Stingray] Звіт збережено: {out}")

    elif args.command == "quarantine":
        qm = QuarantineManager(args.dir)
        if args.action == "list":
            entries = qm.list_entries()
            if not entries:
                print("[Stingray] Карантин порожній")
            for i, e in enumerate(entries):
                print(f"  [{i}] {e.original_path} — {e.threat_name} ({e.timestamp})")
        elif args.action == "restore":
            if args.index is None:
                print("Вкажіть --index")
                sys.exit(1)
            result = qm.restore_file(args.index)
            if result:
                print(f"[Stingray] Відновлено: {result}")
            else:
                print("[Stingray] Не знайдено")
        elif args.action == "delete":
            if args.index is None:
                print("Вкажіть --index")
                sys.exit(1)
            if qm.delete_entry(args.index):
                print("[Stingray] Видалено з карантину")
            else:
                print("[Stingray] Не знайдено")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
