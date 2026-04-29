import logging
import requests
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

MAX_MESSAGE_LEN = 4000  # Telegram hard limit is 4096; leave headroom


def send_batch(articles: list[dict]):
    if not articles:
        return
    chunks = _build_chunks(articles)
    for chunk in chunks:
        _send(chunk)


def _build_chunks(articles: list[dict]) -> list[str]:
    """Split articles into messages that fit within Telegram's character limit."""
    chunks = []
    current = []
    current_len = 0

    for a in articles:
        line1 = "*" + escape(a["title"]) + "*"
        line2 = "[Read full story](" + a["url"] + ")"
        block = line1 + "\n" + line2
        block_len = len(block) + 2  # +2 for the separating blank line

        if current and current_len + block_len > MAX_MESSAGE_LEN:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0

        current.append(block)
        current_len += block_len

    if current:
        chunks.append("\n\n".join(current))
    return chunks


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
        logging.info(f"Sent batch of articles to Telegram")


def escape(text: str) -> str:
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\{c}" if c in special else c for c in text)
