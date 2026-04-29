import logging
import re
import json
import os
from datetime import datetime, timedelta

import requests
import yfinance as yf
import pandas as pd
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

KLCI_TICKER = "^KLSE"
STOCKS_PATH = os.path.join(os.path.dirname(__file__), "bursa_stocks.json")


def _load_stock_universe() -> list[dict]:
    with open(STOCKS_PATH) as f:
        data = json.load(f)
    stocks = data.get("stocks", [])
    # Deduplicate by code
    seen = set()
    unique = []
    for s in stocks:
        if s["code"] not in seen:
            seen.add(s["code"])
            unique.append(s)
    return unique


def get_active_stocks(max_stocks: int = 150) -> list[dict]:
    """
    Load Bursa stock universe then fetch latest price + volume via yfinance.
    Returns stocks pre-filtered by price and volume floors.
    """
    universe = _load_stock_universe()
    tickers = [s["ticker"] for s in universe]
    code_map = {s["ticker"]: s for s in universe}

    logging.info(f"Downloading latest data for {len(tickers)} tickers...")

    try:
        # Batch download last 2 days for price/volume snapshot
        raw = yf.download(
            tickers,
            period="2d",
            progress=False,
            auto_adjust=True,
            group_by="ticker",
        )
    except Exception as e:
        logging.error(f"yfinance batch download failed: {e}")
        return []

    results = []
    for ticker in tickers:
        try:
            if len(tickers) == 1:
                df = raw
            else:
                if ticker not in raw.columns.get_level_values(0):
                    continue
                df = raw[ticker]

            df = df.dropna(how="all")
            if df.empty:
                continue

            price = float(df["Close"].iloc[-1])
            volume = int(df["Volume"].iloc[-1])

            if price <= 0 or volume <= 0:
                continue

            stock_info = code_map[ticker]
            results.append({
                "code": stock_info["code"],
                "name": stock_info["name"],
                "price": price,
                "volume": volume,
                "ticker": ticker,
            })
        except Exception:
            continue

    logging.info(f"Fetched latest data for {len(results)} stocks")
    return results[:max_stocks]


def get_ohlcv(ticker: str, period_days: int = 70) -> pd.DataFrame | None:
    """Download OHLCV history for a single ticker via yfinance."""
    try:
        df = yf.download(
            ticker,
            period="3mo",
            interval="1d",
            progress=False,
            auto_adjust=True,
        )
        if df is None or df.empty:
            logging.warning(f"Empty OHLCV for {ticker}")
            return None
        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        df.columns = [str(c).strip().title() for c in df.columns]
        df = df.dropna(how="all")
        if len(df) < 20:
            logging.warning(f"Insufficient OHLCV rows ({len(df)}) for {ticker}")
            return None
        return df
    except Exception as e:
        logging.warning(f"yfinance OHLCV failed for {ticker}: {e}")
        return None


def get_intraday(ticker: str) -> pd.DataFrame | None:
    """Download today's 1-min intraday data for VWAP/POC calculation."""
    try:
        df = yf.download(ticker, period="1d", interval="1m", progress=False, auto_adjust=True)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        df.columns = [str(c).strip().title() for c in df.columns]
        return df
    except Exception as e:
        logging.warning(f"Intraday fetch failed for {ticker}: {e}")
        return None


def get_klci_change() -> float:
    """Return today's KLCI % change. Returns 0.0 on failure."""
    try:
        df = yf.download(KLCI_TICKER, period="5d", progress=False, auto_adjust=True)
        df = df.dropna()
        if len(df) < 2:
            return 0.0
        closes = df["Close"].values
        return float((closes[-1] - closes[-2]) / closes[-2] * 100)
    except Exception:
        return 0.0


def get_bursa_announcements() -> list[dict]:
    """Scrape recent Bursa Malaysia company announcements."""
    announcements = []
    try:
        url = "https://www.bursamalaysia.com/market_information/announcements/company_announcement"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "lxml")

        for row in soup.select("table tbody tr")[:50]:
            cols = row.find_all("td")
            if len(cols) < 4:
                continue
            try:
                announcements.append({
                    "date": cols[0].get_text(strip=True),
                    "company": cols[1].get_text(strip=True),
                    "subject": cols[3].get_text(strip=True),
                })
            except IndexError:
                continue

        logging.info(f"Fetched {len(announcements)} Bursa announcements")
    except Exception as e:
        logging.error(f"Bursa announcement fetch failed: {e}")

    return announcements


def get_edge_headlines() -> list[str]:
    """Return recent Edge Malaysia headlines for narrative matching."""
    headlines = []
    try:
        resp = requests.get(
            "https://theedgemalaysia.com/categories/corporate",
            headers=HEADERS,
            timeout=15,
        )
        soup = BeautifulSoup(resp.text, "lxml")
        script = soup.find("script", id="__NEXT_DATA__")
        if script:
            data = json.loads(script.string)
            raw = data["props"]["pageProps"].get("corporateData", [])
            headlines = [item.get("title", "") for item in raw[:30] if item.get("title")]
    except Exception as e:
        logging.error(f"Edge headline fetch failed: {e}")
    return headlines
