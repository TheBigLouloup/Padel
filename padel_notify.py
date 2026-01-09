#!/usr/bin/env python3
import argparse
import csv
import json
import os
import subprocess
import sys
import time
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, List, Set, Tuple

CSV_PATH = Path("tournois_4padel.csv")
STATE_PATH = Path(".padel_state.json")
SCRAPER = Path("4padel.py")
EMAIL_CONFIG_PATH = Path(".padel_email.json")

ALLOWED_LEVELS = {"P100", "P250"}
URL = "https://www.4padel.fr/tournois"


def run_scraper() -> bool:
    """Run the 4padel scraper to refresh the CSV. Returns True if success."""
    if not SCRAPER.exists():
        print(f"❌ Scraper introuvable: {SCRAPER}")
        return False
    try:
        # Use the same Python interpreter
        result = subprocess.run([sys.executable, str(SCRAPER)], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ Échec exécution scraper:")
            print(result.stdout)
            print(result.stderr)
            return False
        # Optional: show brief output
        print(result.stdout.strip())
        return True
    except Exception as e:
        print(f"❌ Exception en lançant scraper: {e}")
        return False


def load_csv() -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    if not CSV_PATH.exists():
        print(f"ℹ️ CSV absent: {CSV_PATH}")
        return rows
    with CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def filter_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return [r for r in rows if r.get("niveau", "").upper() in ALLOWED_LEVELS]


def make_key(r: Dict[str, str]) -> Tuple[str, str, str, str]:
    return (
        r.get("club", ""),
        r.get("date", ""),
        r.get("heure", ""),
        r.get("nom", ""),
    )


def load_state() -> Set[Tuple[str, str, str, str]]:
    if not STATE_PATH.exists():
        return set()
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return set(tuple(x) for x in data)
    except Exception:
        return set()


def save_state(keys: Set[Tuple[str, str, str, str]]) -> None:
    data = [list(k) for k in sorted(keys)]
    STATE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def load_email_config() -> Dict[str, str] | None:
    if not EMAIL_CONFIG_PATH.exists():
        return None
    try:
        data = json.loads(EMAIL_CONFIG_PATH.read_text(encoding="utf-8"))
        required = {"smtp_host", "smtp_port", "smtp_user", "smtp_password", "from_email", "to_email"}
        if not required.issubset(set(data.keys())):
            print("⚠️ .padel_email.json incomplet: clés requises manquantes")
            return None
        return data
    except Exception as e:
        print(f"⚠️ Impossible de lire .padel_email.json: {e}")
        return None

def notify_email(config: Dict[str, str], subject: str, body: str) -> bool:
    import smtplib

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config["from_email"]
    msg["To"] = config["to_email"]
    msg.set_content(body)

    host = config.get("smtp_host")
    port = int(config.get("smtp_port", 587))
    user = config.get("smtp_user")
    password = config.get("smtp_password")
    use_ssl = bool(config.get("use_ssl", False))
    use_tls = bool(config.get("use_tls", True))

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(host, port) as server:
                server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port) as server:
                server.ehlo()
                if use_tls:
                    server.starttls()
                    server.ehlo()
                server.login(user, password)
                server.send_message(msg)
        return True
    except Exception as e:
        print(f"⚠️ Échec envoi email: {e}")
        return False


def notify_mac(title: str, message: str, subtitle: str = "") -> None:
    # Use AppleScript via osascript for native macOS notifications
    script = f'display notification "{message}" with title "{title}"' + (f' subtitle "{subtitle}"' if subtitle else "")
    try:
        subprocess.run(["osascript", "-e", script], check=False)
    except Exception as e:
        print(f"⚠️ Impossible d'afficher la notification: {e}")


def format_row(r: Dict[str, str]) -> str:
    return f"{r.get('niveau')} {r.get('nom')} — {r.get('club')} le {r.get('date')} à {r.get('heure')}"


def check_once(dry_run: bool = False, send_email: bool = False, batch_email: bool = False) -> int:
    # Refresh CSV from the scraper
    ok = run_scraper()
    if not ok:
        return 0

    rows = filter_rows(load_csv())
    current_keys = set(make_key(r) for r in rows)
    prev_keys = load_state()

    new_keys = current_keys - prev_keys
    new_rows = [r for r in rows if make_key(r) in new_keys]

    count = len(new_rows)
    if count == 0:
        print("✅ Aucun nouveau tournoi P100/P250")
    else:
        print(f"🆕 {count} nouveau(x) tournoi(x) P100/P250")
        for r in new_rows:
            msg = format_row(r)
            print("-", msg)
            if not dry_run:
                notify_mac("Nouveau tournoi 4PADEL", msg)

        # Email notifications
        if send_email and not dry_run:
            cfg = load_email_config()
            if not cfg:
                print("⚠️ Email non configuré (.padel_email.json manquant ou incomplet).")
            else:
                if batch_email:
                    subject = f"{count} nouveau(x) tournoi(x) 4PADEL (P100/P250)"
                    lines = [format_row(r) for r in new_rows]
                    body = "\n".join(lines) + f"\n\nPage: {URL}"
                    ok = notify_email(cfg, subject, body)
                    if ok:
                        print("📧 Email récapitulatif envoyé.")
                else:
                    for r in new_rows:
                        subject = f"Nouveau tournoi 4PADEL: {r.get('niveau')} {r.get('nom')}"
                        body = format_row(r) + f"\n\nPage: {URL}"
                        ok = notify_email(cfg, subject, body)
                        if ok:
                            print("📧 Email envoyé:", subject)

    # Persist new state (union of previous and current to avoid regressions)
    save_state(prev_keys | current_keys)
    return count


def main():
    parser = argparse.ArgumentParser(description="Notifier les nouveaux tournois P100/P250 de 4PADEL")
    parser.add_argument("--watch", action="store_true", help="Boucle de surveillance continue")
    parser.add_argument("--interval", type=int, default=15, help="Intervalle en minutes pour la surveillance continue")
    parser.add_argument("--dry-run", action="store_true", help="Ne pas envoyer de notifications, seulement afficher")
    parser.add_argument("--init", action="store_true", help="Initialiser l'état sans notifier (enregistre les tournois courants)")
    parser.add_argument("--email", action="store_true", help="Envoyer des emails en plus des notifications macOS")
    parser.add_argument("--batch-email", action="store_true", help="Envoyer un email unique récapitulatif au lieu d'un email par tournoi")
    args = parser.parse_args()

    if args.init:
        # Initialiser l'état à la liste actuelle sans notifier
        ok = run_scraper()
        if not ok:
            sys.exit(1)
        rows = filter_rows(load_csv())
        current_keys = set(make_key(r) for r in rows)
        save_state(current_keys)
        print(f"✅ État initialisé avec {len(current_keys)} tournois P100/P250")
        return

    if not args.watch:
        check_once(dry_run=args.dry_run, send_email=args.email, batch_email=args.batch_email)
        return

    # Watch mode
    print(f"👀 Surveillance active toutes {args.interval} min. Appuyez sur Ctrl+C pour arrêter.")
    try:
        while True:
            check_once(dry_run=args.dry_run, send_email=args.email, batch_email=args.batch_email)
            time.sleep(max(1, args.interval * 60))
    except KeyboardInterrupt:
        print("👋 Arrêt de la surveillance.")


if __name__ == "__main__":
    main()
