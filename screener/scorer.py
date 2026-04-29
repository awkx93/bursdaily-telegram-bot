import json
import logging
import os
import re

NARRATIVES_PATH = os.path.join(os.path.dirname(__file__), "narratives.json")

# Hard filter thresholds
MIN_PRICE = 0.20
MAX_PRICE = 3.00
MIN_AVG_VOLUME = 500_000
MIN_TRADED_VALUE = 500_000
MIN_ATR_PCT = 2.0
MIN_ADX = 20
MIN_RSI = 45
MAX_RSI = 78
MIN_RANGE_POSITION = 0.60
MIN_VOL_RATIO = 2.0


def _load_narratives() -> list[dict]:
    try:
        with open(NARRATIVES_PATH) as f:
            return json.load(f).get("active_themes", [])
    except Exception as e:
        logging.error(f"Failed to load narratives: {e}")
        return []


def _match_narrative(stock: dict, headlines: list[str], announcements: list[dict]) -> tuple[str, int]:
    """Return (narrative_name, bonus_points). Empty string = no match."""
    narratives = _load_narratives()
    code = stock.get("code", "").upper()
    name = stock.get("name", "").lower()
    all_text = " ".join(headlines).lower() + " ".join(
        a.get("subject", "") + a.get("company", "") for a in announcements
    ).lower()

    for theme in narratives:
        # Check if stock code directly in theme stock list
        in_stock_list = code in [s.upper() for s in theme.get("stocks", [])]
        # Check keyword match in news
        keyword_match = any(kw.lower() in all_text for kw in theme.get("keywords", []))

        if in_stock_list and keyword_match:
            return theme["name"], 15   # Strong: stock listed + news confirms
        if in_stock_list:
            return theme["name"], 10   # Stock in theme but no active news
        if keyword_match:
            # Check if stock sector matches
            return theme["name"], 5    # Theme active in news, sector play

    return "", 0


def _detect_catalyst(stock: dict, announcements: list[dict]) -> tuple[str, int]:
    """Return (catalyst description, points) from Bursa announcements."""
    name_lower = stock.get("name", "").lower()
    code = stock.get("code", "").upper()

    very_high = ["contract", "job award", "privatis", "acquisition", "merger", "takeover"]
    high = ["profit", "earnings", "revenue", "upgrade", "record", "beat"]
    medium = ["buyback", "bonus issue", "rights issue", "dividend", "placement"]

    for ann in announcements:
        company = ann.get("company", "").lower()
        subject = ann.get("subject", "").lower()

        if code.lower() not in company and name_lower[:6] not in company:
            continue

        for kw in very_high:
            if kw in subject:
                return f"Bursa: {ann['subject'][:60]}", 15
        for kw in high:
            if kw in subject:
                return f"Bursa: {ann['subject'][:60]}", 10
        for kw in medium:
            if kw in subject:
                return f"Bursa: {ann['subject'][:60]}", 6

    return "", 0


def passes_hard_filters(stock: dict, ind: dict) -> tuple[bool, str]:
    """Returns (passes, reason_if_failed)."""
    price = ind["close"]
    if not (MIN_PRICE <= price <= MAX_PRICE):
        return False, f"Price RM{price:.2f} outside RM{MIN_PRICE}–RM{MAX_PRICE}"
    if ind["vol_avg_20"] < MIN_AVG_VOLUME:
        return False, f"Avg volume {ind['vol_avg_20']:.0f} < {MIN_AVG_VOLUME:,}"
    if ind["daily_traded_value"] < MIN_TRADED_VALUE:
        return False, f"Traded value RM{ind['daily_traded_value']:.0f} < RM{MIN_TRADED_VALUE:,}"
    if ind["ema20"] <= ind["ema50"]:
        return False, "EMA20 <= EMA50"
    if price <= ind["ema20"]:
        return False, "Price below EMA20"
    if ind["atr_pct"] < MIN_ATR_PCT:
        return False, f"ATR% {ind['atr_pct']:.1f}% < {MIN_ATR_PCT}%"
    if ind["adx"] < MIN_ADX or ind["dmp"] <= ind["dmn"]:
        return False, f"ADX {ind['adx']:.1f} or trend not bullish"
    if not (MIN_RSI <= ind["rsi"] <= MAX_RSI):
        return False, f"RSI {ind['rsi']:.1f} outside {MIN_RSI}–{MAX_RSI}"
    if not ind["green_candle"]:
        return False, "Red candle"
    if ind["range_position"] < MIN_RANGE_POSITION:
        return False, f"Range position {ind['range_position']:.2f} < {MIN_RANGE_POSITION}"
    if not ind["higher_low"]:
        return False, "No higher low"
    return True, ""


def score_stock(
    stock: dict,
    ind: dict,
    vwap_poc: dict | None,
    klci_change: float,
    headlines: list[str],
    announcements: list[dict],
    session: str,
) -> dict:
    """Compute composite score and return enriched stock dict."""
    pts = 0
    breakdown = {}

    # 1. Volume surge (0–25 pts)
    vr = ind["vol_ratio"]
    vol_pts = min(int((vr / 5) * 25), 25)
    pts += vol_pts
    breakdown["volume_surge"] = vol_pts

    # 2. Price breakout (0–20 pts)
    if ind["breakout_20d"]:
        brk_pts = 20
    elif ind["close"] >= ind["high_20d"] * 0.98:
        brk_pts = 12   # within 2% of breakout
    else:
        brk_pts = 0
    pts += brk_pts
    breakdown["breakout"] = brk_pts

    # 3. Catalyst (0–15 pts)
    catalyst_desc, cat_pts = _detect_catalyst(stock, announcements)
    pts += cat_pts
    breakdown["catalyst"] = cat_pts
    breakdown["catalyst_desc"] = catalyst_desc

    # 4. RSI score (0–10 pts)
    rsi = ind["rsi"]
    if 55 <= rsi <= 68:
        rsi_pts = 10
    elif 50 <= rsi < 55 or 68 < rsi <= 72:
        rsi_pts = 6
    else:
        rsi_pts = 2
    pts += rsi_pts
    breakdown["rsi"] = rsi_pts

    # 5. MACD bullish (0–10 pts)
    if ind["macd_cross_days"] > 0:
        macd_pts = max(10 - (ind["macd_cross_days"] - 1) * 3, 4)
    elif ind["macd"] > ind["macd_signal"]:
        macd_pts = 5
    else:
        macd_pts = 0
    pts += macd_pts
    breakdown["macd"] = macd_pts

    # 6. Relative strength vs KLCI (0–5 pts)
    price_change_pct = (ind["close"] - ind["open"]) / ind["open"] * 100
    rs_pts = 5 if price_change_pct > klci_change else 0
    pts += rs_pts
    breakdown["relative_strength"] = rs_pts

    # 7. POC > VWAP — afternoon session only (0–10 pts)
    poc_pts = 0
    if session == "afternoon" and vwap_poc:
        poc_pts = 10 if vwap_poc.get("poc_above_vwap") else 0
    pts += poc_pts
    breakdown["poc_vwap"] = poc_pts

    # 8. EMA fresh cross bonus (0–5 pts)
    ema_pts = 5 if ind["ema_fresh_cross"] else 0
    pts += ema_pts
    breakdown["ema_fresh_cross"] = ema_pts

    # 9. Narrative match (required + bonus)
    narrative_name, nar_pts = _match_narrative(stock, headlines, announcements)
    pts += nar_pts
    breakdown["narrative"] = nar_pts
    breakdown["narrative_name"] = narrative_name

    return {
        **stock,
        **ind,
        **(vwap_poc or {}),
        "score": pts,
        "breakdown": breakdown,
        "catalyst_desc": catalyst_desc,
        "narrative_name": narrative_name,
        "price_change_pct": price_change_pct,
        "stop_loss": round(ind["close"] - 1.5 * ind["atr"], 3),
        "target1": round(ind["close"] * 1.05, 3),
        "target2": round(ind["close"] * 1.10, 3),
    }


def filter_and_rank(
    candidates: list[dict],
    session: str,
    klci_change: float,
    headlines: list[str],
    announcements: list[dict],
    top_n: int = 2,
    min_score: int = 65,
) -> list[dict]:
    """Apply hard filters, score, and return top N stocks."""
    results = []

    for item in candidates:
        ind = item.get("_ind")
        vwap_poc = item.get("_vwap_poc")
        if not ind:
            continue

        passed, reason = passes_hard_filters(item, ind)
        if not passed:
            logging.debug(f"EXCLUDED {item['code']}: {reason}")
            continue

        scored = score_stock(item, ind, vwap_poc, klci_change, headlines, announcements, session)

        # Narrative is required
        if not scored["narrative_name"]:
            logging.debug(f"EXCLUDED {item['code']}: No narrative match")
            continue

        if scored["score"] >= min_score:
            results.append(scored)
            logging.info(f"QUALIFIED {item['code']}: score={scored['score']}")

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_n]
