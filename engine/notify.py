"""Email delivery for the morning brief — key-gated and graceful (same posture as the
rest of the engine). Inert until BOTH env vars are set, so it never blocks a build:

  SENDGRID_API_KEY   — the SendGrid API key (the pivoxquant project already has one)
  BRIEF_TO           — recipient(s), comma-separated
  BRIEF_FROM         — optional sender (default noreply@pivoxquant.com)

send_brief() returns a status string; the CLI prints it. No new dependency — plain HTTPS
to SendGrid v3. If you'd rather use Gmail SMTP, swap _sendgrid() for an smtplib call; the
gate and signature stay the same.
"""
from __future__ import annotations

import os

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
        return f"sent → {', '.join(to)}"
    return f"send FAILED — SendGrid {r.status_code}: {r.text[:200]}"


def send_brief(brief: dict) -> str:
    key = os.environ.get("SENDGRID_API_KEY")
    to = [e.strip() for e in (os.environ.get("BRIEF_TO") or "").split(",") if e.strip()]
    if not key or not to:
        return "delivery off (set SENDGRID_API_KEY + BRIEF_TO in .env to enable)"
    sender = os.environ.get("BRIEF_FROM", "noreply@pivoxquant.com")
    # subject leads with the alert count so a 'big day' is visible without opening
    n = len(brief.get("alerts") or [])
    flag = f"🚨 큰 움직임 {n}건 · " if n else ""
    subject = f"{flag}시장심리 브리핑 {brief['as_of']} — {brief['headline']}"
    try:
        return _sendgrid(key, sender, to, subject, brief["text"])
    except Exception as e:
        return f"send FAILED — {type(e).__name__}: {e}"
