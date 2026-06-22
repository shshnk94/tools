"""
monitor_server.py — Ping a remote server and email on failure.

Setup
-----
1. Create a .env file in the same directory as this script:

       gmail-app-password=xxxx xxxx xxxx xxxx
       email-handle=you@gmail.com

   To get a Gmail app password: Google Account → Security →
   2-Step Verification → App passwords → create one for "Mail".

2. Install dependencies:

       uv add python-dotenv   # or: pip install python-dotenv

Usage
-----
Send a test email to verify your .env is configured correctly:

    uv run python monitor_server.py --server <host> --test-email

One-shot check (for use in a cron job):

    uv run python monitor_server.py --server <host> --once

Run as a daemon (checks every 5 minutes by default):

    uv run python monitor_server.py --server <host>

Cron job (checks every 5 minutes, logs to /tmp/server_monitor.log):

    */5 * * * * /path/to/.venv/bin/python /path/to/monitor_server.py \\
        --server <host> --once >> /tmp/server_monitor.log 2>&1

All flags
---------
  --server          Hostname or IP to monitor (required)
  --email           Override the recipient address from .env
  --smtp-user       Override the sender address from .env
  --smtp-password   Override the app password from .env
  --smtp-host       SMTP host (default: smtp.gmail.com)
  --smtp-port       SMTP port (default: 587)
  --ping-count      Number of pings per check (default: 3)
  --ping-timeout    Ping timeout in seconds (default: 5)
  --interval        Seconds between checks in daemon mode (default: 300)
  --once            Run a single check and exit
  --test-email      Send a test email and exit without pinging
"""

import argparse
import smtplib
import socket
import subprocess
import sys
import time
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from dotenv import dotenv_values

_env = dotenv_values(Path(__file__).parent / ".env")


def make_parser():
    p = argparse.ArgumentParser(description="Monitor a remote server and send email alerts on downtime.")
    p.add_argument("--server", required=True, help="Hostname or IP of the server to monitor.")
    p.add_argument("--email", default=_env.get("email-handle"), help="Recipient email address for alerts.")
    p.add_argument("--smtp-user", default=_env.get("email-handle"), help="SMTP login (same as --email for Gmail).")
    p.add_argument("--smtp-password", default=_env.get("gmail-app-password"), help="SMTP app password.")
    p.add_argument("--smtp-host", default="smtp.gmail.com", help="SMTP host (default: smtp.gmail.com).")
    p.add_argument("--smtp-port", type=int, default=587, help="SMTP port (default: 587).")
    p.add_argument("--ping-count", type=int, default=3, help="Number of ICMP pings per check (default: 3).")
    p.add_argument("--ping-timeout", type=int, default=5, help="Ping timeout in seconds (default: 5).")
    p.add_argument("--interval", type=int, default=300, help="Seconds between checks in daemon mode (default: 300).")
    p.add_argument("--once", action="store_true", help="Run a single check and exit (for cron use).")
    p.add_argument("--test-email", action="store_true", help="Send a test email and exit without pinging.")
    return p


def is_reachable(server: str, count: int, timeout: int) -> bool:
    """Return True if the server responds to at least one ping."""
    try:
        # macOS expects -W in milliseconds, Linux in seconds
        w_value = timeout * 1000 if sys.platform == "darwin" else timeout
        result = subprocess.run(
            ["ping", "-c", str(count), "-W", str(w_value), server],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0
    except FileNotFoundError:
        # Fallback: try opening a TCP connection on port 22 (SSH)
        try:
            with socket.create_connection((server, 22), timeout=timeout):
                return True
        except OSError:
            return False


def send_email(args, subject: str, body: str):
    msg = EmailMessage()
    msg["From"] = args.smtp_user
    msg["To"] = args.email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(args.smtp_host, args.smtp_port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(args.smtp_user, args.smtp_password)
        smtp.send_message(msg)


def check_once(args) -> bool:
    """Ping the server. Send alert email if unreachable. Returns True if reachable."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    reachable = is_reachable(args.server, args.ping_count, args.ping_timeout)

    if reachable:
        print(f"[{now}] {args.server} is UP.")
        return True

    print(f"[{now}] {args.server} is UNREACHABLE — sending alert to {args.email}.")
    subject = f"[ALERT] Server unreachable: {args.server}"
    body = (
        f"Your server {args.server!r} did not respond to {args.ping_count} ping(s) "
        f"at {now}.\n\n"
        f"It may have lost power or network connectivity.\n\n"
        f"-- monitor_server.py"
    )
    try:
        send_email(args, subject, body)
        print(f"[{now}] Alert email sent to {args.email}.")
    except Exception as exc:
        print(f"[{now}] ERROR sending email: {exc}", file=sys.stderr)
    return False


def main():
    p = make_parser()
    args = p.parse_args()

    missing = [f for f in ("email", "smtp_user", "smtp_password") if not getattr(args, f)]
    if missing:
        p.error(f"Missing required values (set in .env or pass as flags): {', '.join(missing)}")

    if args.test_email:
        print(f"Sending test email to {args.email} ...")
        send_email(
            args,
            subject=f"[TEST] monitor_server.py is configured correctly",
            body=(
                f"This is a test message from monitor_server.py.\n\n"
                f"Monitoring target : {args.server}\n"
                f"Alert recipient   : {args.email}\n"
                f"SMTP host         : {args.smtp_host}:{args.smtp_port}\n"
            ),
        )
        print("Test email sent successfully.")
        return

    if args.once:
        check_once(args)
        return

    print(f"Starting monitoring loop — checking {args.server} every {args.interval}s.")
    print("Press Ctrl+C to stop.\n")
    while True:
        check_once(args)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
