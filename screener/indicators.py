import pandas as pd
import pandas_ta as ta
import numpy as np


def compute(df: pd.DataFrame) -> dict | None:
    """Compute all technical indicators. Returns dict or None if data insufficient."""
    if df is None or len(df) < 50:
        return None

    try:
        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]

        # EMAs
        ema20 = ta.ema(close, length=20)
        ema50 = ta.ema(close, length=50)

        # RSI
        rsi = ta.rsi(close, length=14)

        # MACD
        macd_df = ta.macd(close, fast=12, slow=26, signal=9)
        macd_line = macd_df["MACD_12_26_9"]
        macd_signal = macd_df["MACDs_12_26_9"]

        # ATR
        atr = ta.atr(high, low, close, length=14)

        # ADX
        adx_df = ta.adx(high, low, close, length=14)
        adx = adx_df["ADX_14"]
        dmp = adx_df["DMP_14"]
        dmn = adx_df["DMN_14"]

        # Volume ratio vs 20-day avg
        vol_avg_20 = volume.rolling(20).mean()
        vol_ratio = volume.iloc[-1] / vol_avg_20.iloc[-1] if vol_avg_20.iloc[-1] > 0 else 0

        # 20-day high breakout
        high_20d = high.iloc[-21:-1].max()
        breakout = close.iloc[-1] > high_20d

        # Close position in daily range
        daily_range = high.iloc[-1] - low.iloc[-1]
        range_position = (close.iloc[-1] - low.iloc[-1]) / daily_range if daily_range > 0 else 0

        # Higher Low proxy (10-day rolling min rising)
        low_now = low.rolling(10).min().iloc[-1]
        low_prev = low.rolling(10).min().iloc[-6]
        higher_low = low_now > low_prev

        # Green candle (close > open)
        open_price = df["Open"].iloc[-1]
        green_candle = close.iloc[-1] > open_price

        # MACD bullish cross within last 3 days
        macd_cross_days = 0
        for i in range(1, 4):
            if (macd_line.iloc[-i] > macd_signal.iloc[-i] and
                    macd_line.iloc[-(i + 1)] <= macd_signal.iloc[-(i + 1)]):
                macd_cross_days = i
                break

        # EMA fresh cross (EMA20 crossed above EMA50 within last 5 days)
        ema_fresh_cross = False
        for i in range(1, 6):
            if (ema20.iloc[-i] > ema50.iloc[-i] and
                    ema20.iloc[-(i + 1)] <= ema50.iloc[-(i + 1)]):
                ema_fresh_cross = True
                break

        return {
            "close": float(close.iloc[-1]),
            "open": float(open_price),
            "high": float(high.iloc[-1]),
            "low": float(low.iloc[-1]),
            "volume": int(volume.iloc[-1]),
            "vol_avg_20": float(vol_avg_20.iloc[-1]),
            "vol_ratio": float(vol_ratio),
            "ema20": float(ema20.iloc[-1]),
            "ema50": float(ema50.iloc[-1]),
            "rsi": float(rsi.iloc[-1]),
            "macd": float(macd_line.iloc[-1]),
            "macd_signal": float(macd_signal.iloc[-1]),
            "macd_cross_days": macd_cross_days,
            "atr": float(atr.iloc[-1]),
            "atr_pct": float(atr.iloc[-1] / close.iloc[-1] * 100),
            "adx": float(adx.iloc[-1]),
            "dmp": float(dmp.iloc[-1]),
            "dmn": float(dmn.iloc[-1]),
            "breakout_20d": bool(breakout),
            "high_20d": float(high_20d),
            "range_position": float(range_position),
            "higher_low": bool(higher_low),
            "green_candle": bool(green_candle),
            "ema_fresh_cross": bool(ema_fresh_cross),
            "daily_traded_value": float(close.iloc[-1] * volume.iloc[-1]),
        }
    except Exception as e:
        return None


def compute_vwap_poc(df_intraday: pd.DataFrame) -> dict | None:
    """Compute VWAP and Point of Control from intraday 1-min data."""
    if df_intraday is None or df_intraday.empty:
        return None

    try:
        df = df_intraday.copy()
        df["typical_price"] = (df["High"] + df["Low"] + df["Close"]) / 3
        df["tp_vol"] = df["typical_price"] * df["Volume"]

        vwap = df["tp_vol"].cumsum().iloc[-1] / df["Volume"].cumsum().iloc[-1]

        # POC — price level with highest volume (bin into 0.005 increments)
        df["price_bin"] = (df["typical_price"] / 0.005).round() * 0.005
        poc_series = df.groupby("price_bin")["Volume"].sum()
        poc = float(poc_series.idxmax())

        return {
            "vwap": float(vwap),
            "poc": poc,
            "poc_above_vwap": poc > vwap,
        }
    except Exception:
        return None
