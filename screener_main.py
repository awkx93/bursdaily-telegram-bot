"""
Entry point for T+2 stock screener.
Called by GitHub Actions at 8:30am MYT (morning) and 2:00pm MYT (afternoon).

Usage:
    python screener_main.py --session morning
    python screener_main.py --session afternoon
"""
import argparse
import logging
import sys

from screener.tracker import init_db, record_signal
from screener.fetcher import (
    get_active_stocks,
    get_ohlcv,
    get_intraday,
    get_klci_change,
    get_bursa_announcements,
    get_edge_headlines,
)
from screener.indicators import compute, compute_vwap_poc
from screener.scorer import filter_and_rank
from screener.signals import send_signals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Hard limit: suppress all signals if KLCI down more than this
KLCI_SUPPRESS_THRESHOLD = -1.0


def run(session: str):
    logging.info(f"=== T+2 Screener starting — session: {session} ===")

    # Step 1: Market environment check
    klci_change = get_klci_change()
    logging.info(f"KLCI change: {klci_change:.2f}%")

    if klci_change < KLCI_SUPPRESS_THRESHOLD:
        logging.warning(f"KLCI down {klci_change:.2f}% — suppressing all signals")
        from screener.signals import _send_no_signal
        _send_no_signal(session)
        return

    # Step 2: Fetch active stocks universe (full Bursa universe)
    stocks = get_active_stocks()
    if not stocks:
        logging.error("No stocks fetched — sending no-signal message")
        from screener.signals import _send_no_signal
        _send_no_signal(session)
        return

    # Step 3: Fetch supporting data
    announcements = get_bursa_announcements()
    headlines = get_edge_headlines()

    # Step 4: Apply price pre-filter before pulling full OHLCV (saves API calls)
    candidates = [s for s in stocks if 0.20 <= s["price"] <= 3.00 and s["volume"] >= 500_000]
    logging.info(f"Pre-filtered to {len(candidates)} stocks (price + volume gate)")

    # Step 5: Pull OHLCV + compute indicators for each candidate
    enriched = []
    for stock in candidates:
        df = get_ohlcv(stock["ticker"], period_days=70)
        ind = compute(df)
        if not ind:
            continue

        vwap_poc = None
        if session == "afternoon":
            df_intra = get_intraday(stock["ticker"])
            vwap_poc = compute_vwap_poc(df_intra)

        stock["_ind"] = ind
        stock["_vwap_poc"] = vwap_poc
        enriched.append(stock)

    logging.info(f"Computed indicators for {len(enriched)} stocks")

    # Step 6: Filter, score, rank — return top 2
    top_stocks = filter_and_rank(
        candidates=enriched,
        session=session,
        klci_change=klci_change,
        headlines=headlines,
        announcements=announcements,
        top_n=2,
        min_score=65,
    )

    logging.info(f"Top {len(top_stocks)} signals found")

    # Step 7: Initialise tracker DB and record signals
    init_db()
    for stock in top_stocks:
        record_signal(stock, session)

    # Step 8: Send to Telegram
    send_signals(top_stocks, session, klci_change)
    logging.info("=== Screener complete ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--session",
        choices=["morning", "afternoon"],
        required=True,
        help="Which session to screen for",
    )
    args = parser.parse_args()
    run(args.session)
