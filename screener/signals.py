import logging
import os
from datetime import datetime, timedelta

import requests

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_THREAD_ID = os.environ.get("TELEGRAM_THREAD_ID", "")

API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def _t2_date() -> str:
    """Return T+2 date skipping weekends."""
    d = datetime.today()
    days_added = 0
    while days_added < 2:
        d += timedelta(days=1)
        if d.weekday() < 5:
            days_added += 1
    return d.strftime("%d %b %Y")


def _tick(val: bool) -> str:
    return "✅" if val else "❌"


def _format_signal(stock: dict, rank: int, total: int, session: str, klci_change: float) -> str:
    session_label = "🌅 MORNING" if session == "morning" else "☀️ AFTERNOON"
    time_label = "8:30AM" if session == "morning" else "2:00PM"
    entry_label = "9:00am open" if session == "morning" else "2:30pm open"

    klci_str = f"+{klci_change:.2f}%" if klci_change >= 0 else f"{klci_change:.2f}%"
    price_str = f"+{stock['price_change_pct']:.1f}%" if stock['price_change_pct'] >= 0 else f"{stock['price_change_pct']:.1f}%"

    poc_line = ""
    if session == "afternoon" and stock.get("vwap"):
        poc_line = f"\nPOC RM{stock['poc']:.3f} {'>' if stock.get('poc_above_vwap') else '<'} VWAP RM{stock['vwap']:.3f} {_tick(stock.get('poc_above_vwap', False))}"

    catalyst_line = f"\n📰 Catalyst\n{stock['catalyst_desc']}" if stock.get("catalyst_desc") else "\n📰 Catalyst\nNone detected"

    lines = [
        f"{session_label} SIGNAL — {time_label}",
        f"{datetime.today().strftime('%d %b %Y')} | KLCI: {klci_str}",
        "",
        f"{'─' * 26}",
        f"🟢 #{rank} of {total} — {stock['code']} ({stock.get('ticker','').replace('.KL','')})",
        f"{stock['name']}",
        "",
        f"Score: {stock['score']}/100 | RM{stock['close']:.3f} ({price_str})",
        f"Volume: {stock['vol_ratio']:.1f}x avg ({stock['volume']:,} vs {int(stock['vol_avg_20']):,} avg)",
        "",
        f"📖 Narrative",
        f"{stock['narrative_name']}",
        "",
        f"📊 Technicals",
        f"EMA20 {'>' if stock['ema20'] > stock['ema50'] else '<'} EMA50 {_tick(stock['ema20'] > stock['ema50'])} {'| Fresh cross ✅' if stock.get('ema_fresh_cross') else ''}",
        f"RSI: {stock['rsi']:.1f} {_tick(50 <= stock['rsi'] <= 72)} | ADX: {stock['adx']:.1f} {_tick(stock['adx'] >= 20)}",
        f"20D Breakout: {_tick(stock['breakout_20d'])} | Higher Low: {_tick(stock['higher_low'])}",
        f"Green candle: {_tick(stock['green_candle'])} | Range: {stock['range_position']*100:.0f}% {_tick(stock['range_position'] >= 0.60)}",
        f"ATR: {stock['atr_pct']:.1f}% {_tick(stock['atr_pct'] >= 2)}{poc_line}",
        catalyst_line,
        "",
        f"⚠️ Trade Plan",
        f"Entry:    RM{stock['close']:.3f} ({entry_label})",
        f"Stop:     RM{stock['stop_loss']:.3f} (-{(stock['close']-stock['stop_loss'])/stock['close']*100:.1f}%)",
        f"Target 1: RM{stock['target1']:.3f} (+5%) → exit 50%",
        f"Target 2: RM{stock['target2']:.3f} (+10%) → trail rest",
        f"T+2 Exit: {_t2_date()} EOD — HARD RULE",
        f"{'─' * 26}",
    ]
    return "\n".join(lines)


def send_signals(stocks: list[dict], session: str, klci_change: float):
    """Send top signals to the Telegram group topic."""
    if not stocks:
        _send_no_signal(session)
        return

    for i, stock in enumerate(stocks, 1):
        msg = _format_signal(stock, i, len(stocks), session, klci_change)
        _send(msg)


def _send_no_signal(session: str):
    label = "MORNING" if session == "morning" else "AFTERNOON"
    msg = (
        f"🔕 {label} SCAN — No Signals\n"
        f"{datetime.today().strftime('%d %b %Y')}\n\n"
        f"No stocks met all criteria today.\n"
        f"Stay flat for this session."
    )
    _send(msg)


def _send(text: str):
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if TELEGRAM_THREAD_ID:
        payload["message_thread_id"] = int(TELEGRAM_THREAD_ID)

    resp = requests.post(f"{API_URL}/sendMessage", json=payload, timeout=10)
    if not resp.ok:
        logging.error(f"Telegram send failed: {resp.status_code} {resp.text}")
    else:
        logging.info("Signal sent to Telegram")
