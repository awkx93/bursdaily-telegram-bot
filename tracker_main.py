"""
Track record entry point. Two modes:

    python tracker_main.py --mode close     # 5:30pm daily — close T+2 positions
    python tracker_main.py --mode weekly    # Monday 8am — weekly + cumulative summary
"""
import argparse
import logging
import os
import requests
from datetime import datetime, timedelta

from screener.tracker import (
    init_db,
    close_t2_positions,
    get_weekly_signals,
    get_all_closed_signals,
    get_inception_date,
)
from screener.reports import format_t2_result, format_weekly_summary, format_cumulative

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_SIGNAL_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TRACK_RECORD_THREAD_ID = os.environ.get("TELEGRAM_TRACK_RECORD_THREAD_ID", "")
API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def _send(text: str):
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if TRACK_RECORD_THREAD_ID:
        payload["message_thread_id"] = int(TRACK_RECORD_THREAD_ID)

    resp = requests.post(f"{API_URL}/sendMessage", json=payload, timeout=10)
    if not resp.ok:
        logging.error(f"Telegram send failed: {resp.status_code} {resp.text}")
    else:
        logging.info("Track record message sent")


def run_close():
    """Close all T+2 positions due today and send results."""
    today = datetime.today().strftime("%Y-%m-%d")
    logging.info(f"Closing T+2 positions for {today}")

    init_db()
    closed = close_t2_positions(today)

    if not closed:
        logging.info("No T+2 positions to close today")
        return

    for signal in closed:
        msg = format_t2_result(signal)
        _send(msg)
        logging.info(f"Result sent: {signal['code']} {signal['result']} {signal['pnl_pct']:.1f}%")


def run_weekly():
    """Send weekly summary + cumulative since inception."""
    init_db()

    # Last Monday to last Friday
    today = datetime.today()
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_friday = last_monday + timedelta(days=4)

    week_start = last_monday.strftime("%Y-%m-%d")
    week_end = last_friday.strftime("%Y-%m-%d")
    week_label_start = last_monday.strftime("%d %b")
    week_label_end = last_friday.strftime("%d %b %Y")

    weekly_signals = get_weekly_signals(week_start, week_end)
    all_signals = get_all_closed_signals()
    inception = get_inception_date()

    # Send weekly summary
    weekly_msg = format_weekly_summary(weekly_signals, week_label_start, week_label_end)
    _send(weekly_msg)

    # Send cumulative
    cumulative_msg = format_cumulative(all_signals, inception)
    _send(cumulative_msg)

    logging.info(f"Weekly + cumulative summaries sent ({len(weekly_signals)} weekly, {len(all_signals)} total)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["close", "weekly"],
        required=True,
        help="close = T+2 position close | weekly = weekly + cumulative summary",
    )
    args = parser.parse_args()

    if args.mode == "close":
        run_close()
    elif args.mode == "weekly":
        run_weekly()
