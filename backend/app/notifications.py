import html
import os

import httpx

from app.models import JobRecord


def build_job_alert(job: JobRecord) -> str:
    screening = job.screening or {}
    score = screening.get("score", 0)
    salary = "Not disclosed"
    if job.salary_min is not None:
        currency = job.salary_currency or ""
        salary = f"{currency} {job.salary_min:,.0f}"
        if job.salary_max is not None:
            salary += f" – {currency} {job.salary_max:,.0f}"
        if job.salary_period:
            salary += f" / {job.salary_period}"

    apply_url = html.escape(job.apply_url or "", quote=True)
    lines = [
        "🔎 <b>New job match — AI Job Hunter</b>",
        f"<b>{html.escape(job.title)}</b> at <b>{html.escape(job.company)}</b>",
        f"📍 {html.escape(job.location or 'Location not specified')}",
        f"💰 {html.escape(salary)}",
        f"🎯 Match score: <b>{score}/100</b>",
    ]
    if apply_url:
        lines.append(f'🔗 <a href="{apply_url}">View job / application</a>')
    lines.append("This is a job discovery alert, not an application confirmation.")
    return "\n".join(lines)


def send_telegram_message(text: str) -> tuple[bool, str | None]:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return False, "Telegram is not configured; set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        response = httpx.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            return False, payload.get("description", "Telegram API rejected the message.")
        return True, None
    except (httpx.HTTPError, ValueError) as exc:
        return False, str(exc)
