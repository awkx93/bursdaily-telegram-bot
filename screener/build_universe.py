"""
Build/refresh the full Bursa Malaysia stock universe.

Run manually:  python -m screener.build_universe
Run via CI:    called by universe_builder.yml every Sunday

Strategy (falls through in order):
  1. i3investor JSON API       — fastest, ~1000 stocks
  2. Bursa Malaysia website    — scrape paginated equities table
  3. Numeric code range scan   — brute-force yfinance (slow, always works)
"""
import json
import logging
import os
import re
import time

import requests
import yfinance as yf
import pandas as pd
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

OUTPUT = os.path.join(os.path.dirname(__file__), "bursa_stocks.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


# ---------------------------------------------------------------------------
# Source 1: i3investor JSON stock list
# ---------------------------------------------------------------------------

def _from_i3investor() -> list[dict]:
    try:
        resp = requests.get(
            "https://klse.i3investor.com/web/chart/stocklist",
            headers=HEADERS,
            timeout=20,
        )
        if not resp.ok:
            return []
        data = resp.json()
        if not isinstance(data, list) or len(data) < 100:
            return []

        stocks = []
        for item in data:
            raw_code = str(item.get("c", "")).strip()
            if not raw_code or not raw_code.isdigit():
                continue
            padded = raw_code.zfill(4)
            ticker = f"{padded}.KL"
            short = item.get("n", "") or padded
            full = item.get("d", "") or short
            stocks.append({"code": short, "ticker": ticker, "name": full})

        logging.info(f"i3investor: {len(stocks)} stocks")
        return stocks
    except Exception as e:
        logging.warning(f"i3investor failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Source 2: Bursa Malaysia equities prices page (paginated HTML table)
# ---------------------------------------------------------------------------

def _from_bursa_website() -> list[dict]:
    stocks = []
    markets = ["main", "ace", "leap"]

    for market in markets:
        for page in range(1, 30):
            try:
                url = (
                    "https://www.bursamalaysia.com/market_information/equities_prices"
                    f"?type={market}&page={page}"
                )
                resp = requests.get(
                    url,
                    headers={**HEADERS, "Accept": "text/html"},
                    timeout=15,
                )
                soup = BeautifulSoup(resp.text, "lxml")
                rows = soup.select("table tbody tr")
                if not rows:
                    break

                found_on_page = 0
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) < 2:
                        continue
                    code_text = cols[0].get_text(strip=True)
                    name_text = cols[1].get_text(strip=True) if len(cols) > 1 else ""

                    numeric = re.search(r"\d{4}", code_text)
                    if not numeric:
                        continue
                    padded = numeric.group().zfill(4)
                    ticker = f"{padded}.KL"
                    stocks.append({
                        "code": code_text.split()[0] or padded,
                        "ticker": ticker,
                        "name": name_text or padded,
                    })
                    found_on_page += 1

                if found_on_page == 0:
                    break
                time.sleep(0.5)
            except Exception as e:
                logging.warning(f"Bursa {market} page {page}: {e}")
                break

    logging.info(f"Bursa website: {len(stocks)} stocks")
    return stocks


# ---------------------------------------------------------------------------
# Source 3: Brute-force numeric code scan via yfinance (reliable fallback)
# ---------------------------------------------------------------------------

def _scan_yfinance() -> list[dict]:
    """
    Test every 4-digit code (0001–9999) in batches.
    Returns all tickers that yfinance returns valid Close data for.
    Slow (~3–5 min) but comprehensive — catches everything.
    """
    logging.info("Starting numeric code scan (3–5 min)...")
    all_tickers = [f"{i:04d}.KL" for i in range(1, 10000)]
    batch_size = 200
    valid = []

    for start in range(0, len(all_tickers), batch_size):
        batch = all_tickers[start:start + batch_size]
        try:
            raw = yf.download(
                batch,
                period="5d",
                progress=False,
                auto_adjust=True,
                group_by="ticker",
            )
            if raw is None or raw.empty:
                continue

            is_multi = isinstance(raw.columns, pd.MultiIndex)
            level0 = raw.columns.get_level_values(0) if is_multi else []

            for ticker in batch:
                try:
                    if is_multi:
                        if ticker not in level0:
                            continue
                        df = raw[ticker]
                    else:
                        df = raw

                    df = df.dropna(how="all")
                    if df.empty:
                        continue
                    close_val = df["Close"].iloc[-1]
                    if pd.isna(close_val) or float(close_val) <= 0:
                        continue

                    code = ticker.replace(".KL", "")
                    valid.append({"code": code, "ticker": ticker, "name": code})
                except Exception:
                    continue
        except Exception as e:
            logging.debug(f"Batch {start}: {e}")
            continue

        if start % 2000 == 0 and start > 0:
            logging.info(f"  Scanned {start}/9999, found {len(valid)} valid so far")
        time.sleep(0.3)

    logging.info(f"Code scan complete: {len(valid)} valid stocks")
    return valid


# ---------------------------------------------------------------------------
# Name enrichment via yfinance (for scan-sourced stocks with no names)
# ---------------------------------------------------------------------------

def _enrich_names(stocks: list[dict]) -> list[dict]:
    nameless = [s for s in stocks if s["name"] == s["code"]]
    if not nameless:
        return stocks

    logging.info(f"Enriching names for {len(nameless)} stocks...")
    for i in range(0, len(nameless), 20):
        chunk = nameless[i:i + 20]
        for s in chunk:
            try:
                info = yf.Ticker(s["ticker"]).info
                name = info.get("shortName") or info.get("longName") or ""
                if name:
                    s["name"] = name
            except Exception:
                pass
        time.sleep(0.5)

    return stocks


# ---------------------------------------------------------------------------
# Main build entry point
# ---------------------------------------------------------------------------

def build():
    stocks = _from_i3investor()

    if len(stocks) < 300:
        logging.info("Trying Bursa Malaysia website...")
        stocks = _from_bursa_website()

    if len(stocks) < 300:
        logging.info("Web sources insufficient, falling back to yfinance scan...")
        stocks = _scan_yfinance()
        stocks = _enrich_names(stocks)

    # Deduplicate by ticker
    seen: set[str] = set()
    unique = []
    for s in stocks:
        if s["ticker"] not in seen:
            seen.add(s["ticker"])
            unique.append(s)

    unique.sort(key=lambda x: x["ticker"])

    with open(OUTPUT, "w") as f:
        json.dump({"stocks": unique}, f, indent=2)

    logging.info(f"Saved {len(unique)} stocks to bursa_stocks.json")
    return len(unique)


if __name__ == "__main__":
    n = build()
    print(f"\nDone — {n} stocks saved to screener/bursa_stocks.json")
