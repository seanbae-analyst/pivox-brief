"""Email delivery for the morning brief — key-gated, graceful, provider CASCADE.

Tries providers in order and uses the first that's configured AND succeeds, so a dead
SendGrid free tier silently falls through to Gmail SMTP (free, your own account):

  1. SendGrid  — SENDGRID_API_KEY            (HTTPS, requests)
  2. Gmail SMTP — GMAIL_USER + GMAIL_APP_PASSWORD  (stdlib smtplib, $0 / no quota wall)

Common env:
  BRIEF_TO    — recipient(s), comma-separated   (required to send at all)
  BRIEF_FROM  — sender for SendGrid (default noreply@pivoxquant.com; must be a verified
                SendGrid sender). Gmail SMTP always sends from GMAIL_USER.

send_brief() returns a status string; the CLI prints it. No new dependency.
"""
from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText

import requests

_TIMEOUT = 20


def _sendgrid(key: str, sender: str, to: list[str], subject: str, text: str) -> str:
    body = {
        "personalizations": [{"to": [{"email": e} for e in to]}],
        "from": {"email": sender, "name": "Pivox Brief"},
        "subject": subject,
        "content": [{"type": "text/plain", "value": text}],
    }
    r = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        json=body, headers={"Authorization": f"Bearer {key}"}, timeout=_TIMEOUT,
    )
    if r.status_code in (200, 201, 202):
        return f"sent via SendGrid → {', '.join(to)}"
    raise RuntimeError(f"SendGrid {r.status_code}: {r.text[:160]}")


def _gmail(user: str, app_pw: str, to: list[str], subject: str, text: str) -> str:
    msg = MIMEText(text, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = f"Pivox Brief <{user}>"
    msg["To"] = ", ".join(to)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=_TIMEOUT) as s:
        s.login(user, app_pw.replace(" ", ""))  # app passwords are shown space-separated
        s.sendmail(user, to, msg.as_string())
    return f"sent via Gmail SMTP → {', '.join(to)}"


def send_brief(brief: dict) -> str:
    to = [e.strip() for e in (os.environ.get("BRIEF_TO") or "").split(",") if e.strip()]
    if not to:
        return "delivery off (set BRIEF_TO + a provider in .env to enable)"
    n = len(brief.get("alerts") or [])
    flag = f"🚨 큰 움직임 {n}건 · " if n else ""
    subject = f"{flag}시장심리 브리핑 {brief['as_of']} — {brief['headline']}"
    text = brief["text"]

    attempts: list[tuple[str, callable]] = []
    sg = os.environ.get("SENDGRID_API_KEY")
    if sg:
        sender = os.environ.get("BRIEF_FROM", "noreply@pivoxquant.com")
        attempts.append(("SendGrid", lambda: _sendgrid(sg, sender, to, subject, text)))
    gu, gp = os.environ.get("GMAIL_USER"), os.environ.get("GMAIL_APP_PASSWORD")
    if gu and gp:
        attempts.append(("Gmail", lambda: _gmail(gu, gp, to, subject, text)))

    if not attempts:
        return "delivery off (set SENDGRID_API_KEY or GMAIL_USER+GMAIL_APP_PASSWORD in .env)"

    errors = []
    for name, fn in attempts:
        try:
            return fn()
        except Exception as e:
            errors.append(f"{name}: {type(e).__name__} {e}")
    return "send FAILED — " + " | ".join(errors)
