import logging
import re
import json
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


def get_active_stocks(max_stocks: int = 150) -> list[dict]:
    """Scrape top active stocks by volume from KLSE Screener."""
    stocks = []
    try:
        url = "https://klsescreener.com/v2/screener/quote_results"
        params = {
            "board": "",
            "sector": "",
            "sortby": "volume",
            "sortorder": "desc",
            "per_page": max_stocks,
        }
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "lxml")

        for row in soup.select("table tbody tr"):
            cols = row.find_all("td")
            if len(cols) < 6:
                continue
            try:
                name_tag = cols[1].find("a")
                if not name_tag:
                    continue
                code = cols[0].get_text(strip=True)
                name = name_tag.get_text(strip=True)
                price_text = cols[2].get_text(strip=True).replace(",", "")
                volume_text = cols[5].get_text(strip=True).replace(",", "")
                price = float(price_text) if price_text else 0
                volume = int(volume_text) if volume_text.isdigit() else 0

                if price and volume:
                    stocks.append({
                        "code": code,
                        "name": name,
                        "price": price,
                        "volume": volume,
                        "ticker": f"{code}.KL",
                    })
            except (ValueError, IndexError):
                continue

        logging.info(f"Fetched {len(stocks)} active stocks from KLSE Screener")
    except Exception as e:
        logging.error(f"Failed to fetch active stocks: {e}")

    return stocks


def get_ohlcv(ticker: str, period_days: int = 60) -> pd.DataFrame | None:
    """Download OHLCV history for a single ticker via yfinance."""
    try:
        end = datetime.today()
        start = end - timedelta(days=period_days)
        df = yf.download(ticker, start=start.strftime("%Y-%m-%d"),
                         end=end.strftime("%Y-%m-%d"), progress=False, auto_adjust=True)
        if df.empty or len(df) < 20:
            return None
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        df = df.rename(columns=str.title)
        return df
    except Exception as e:
        logging.warning(f"yfinance failed for {ticker}: {e}")
        return None


def get_intraday(ticker: str) -> pd.DataFrame | None:
    """Download today's 1-min intraday data for VWAP/POC calculation."""
    try:
        df = yf.download(ticker, period="1d", interval="1m",
                         progress=False, auto_adjust=True)
        if df.empty:
            return None
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        df = df.rename(columns=str.title)
        return df
    except Exception as e:
        logging.warning(f"Intraday fetch failed for {ticker}: {e}")
        return None


def get_klci_change() -> float:
    """Return today's KLCI % change. Positive = market up."""
    try:
        df = yf.download(KLCI_TICKER, period="2d", progress=False, auto_adjust=True)
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
                date_str = cols[0].get_text(strip=True)
                company = cols[1].get_text(strip=True)
                subject = cols[3].get_text(strip=True)
                announcements.append({
                    "date": date_str,
                    "company": company,
                    "subject": subject,
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
            headers=HEADERS, timeout=15
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
