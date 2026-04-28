import logging
import requests
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def send_article(title: str, summary: str | None, url: str, source: str):
    text = "*" + escape(title) + "*" + "\n\n" + "[Read full story](" + url + ")"
    _send(text)


def _send(text: str):
    resp = requests.post(
        f"{API_URL}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": True,
        },
        timeout=10,
    )
    if not resp.ok:
        logging.error(f"Telegram send failed: {resp.status_code} {resp.text}")
    else:
        logging.info("Message sent to Telegram")


def escape(text: str) -> str:
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\{c}" if c in special else c for c in text)
