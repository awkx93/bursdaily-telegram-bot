import sqlite3
import logging
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tracker.db")


def _conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_date   TEXT NOT NULL,
                session       TEXT NOT NULL,
                code          TEXT NOT NULL,
                name          TEXT NOT NULL,
                score         INTEGER,
                narrative     TEXT,
                signal_price  REAL NOT NULL,
                stop_loss     REAL,
                target1       REAL,
                target2       REAL,
                t2_date       TEXT NOT NULL,
                t1_close      REAL,
                t2_close      REAL,
                exit_price    REAL,
                exit_type     TEXT,
                pnl_pct       REAL,
                result        TEXT,
                status        TEXT DEFAULT 'pending'
            )
        """)
        con.commit()


def _next_trading_day(d: datetime, n: int) -> datetime:
    """Advance n trading days from d, skipping weekends."""
    count = 0
    while count < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            count += 1
    return d


def record_signal(stock: dict, session: str):
    """Insert a new signal into the tracker DB."""
    today = datetime.today()
    t2 = _next_trading_day(today, 2)

    try:
        with _conn() as con:
            con.execute("""
                INSERT INTO signals
                (signal_date, session, code, name, score, narrative,
                 signal_price, stop_loss, target1, target2, t2_date, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (
                today.strftime("%Y-%m-%d"),
                session,
                stock.get("code", ""),
                stock.get("name", ""),
                stock.get("score"),
                stock.get("narrative_name", ""),
                stock.get("close"),
                stock.get("stop_loss"),
                stock.get("target1"),
                stock.get("target2"),
                t2.strftime("%Y-%m-%d"),
            ))
            con.commit()
        logging.info(f"Recorded signal: {stock.get('code')} T+2={t2.strftime('%Y-%m-%d')}")
    except Exception as e:
        logging.error(f"Failed to record signal: {e}")


def close_t2_positions(today_str: str) -> list[dict]:
    """
    Find all pending signals where t2_date = today.
    Fetch T+2 closing price, compute P&L, mark closed.
    Returns list of closed signals for reporting.
    """
    import yfinance as yf

    with _conn() as con:
        rows = con.execute("""
            SELECT id, code, name, score, narrative, signal_price,
                   stop_loss, target1, target2, session, signal_date
            FROM signals
            WHERE t2_date = ? AND status = 'pending'
        """, (today_str,)).fetchall()

    closed = []
    for row in rows:
        (sid, code, name, score, narrative, signal_price,
         stop_loss, target1, target2, session, signal_date) = row

        t2_close = _fetch_close(f"{code}.KL")
        if t2_close is None:
            logging.warning(f"Could not fetch close for {code} — skipping")
            continue

        pnl_pct = (t2_close - signal_price) / signal_price * 100

        # Determine exit type
        if t2_close <= stop_loss:
            exit_type = "stop_hit"
        elif t2_close >= target2:
            exit_type = "target2"
        elif t2_close >= target1:
            exit_type = "target1"
        else:
            exit_type = "t2_exit"

        if pnl_pct > 0.5:
            result = "WIN"
        elif pnl_pct < -0.5:
            result = "LOSS"
        else:
            result = "BREAKEVEN"

        with _conn() as con:
            con.execute("""
                UPDATE signals
                SET t2_close=?, exit_price=?, exit_type=?, pnl_pct=?, result=?, status='closed'
                WHERE id=?
            """, (t2_close, t2_close, exit_type, pnl_pct, result, sid))
            con.commit()

        closed.append({
            "code": code,
            "name": name,
            "score": score,
            "narrative": narrative,
            "signal_price": signal_price,
            "stop_loss": stop_loss,
            "target1": target1,
            "target2": target2,
            "t2_close": t2_close,
            "exit_price": t2_close,
            "exit_type": exit_type,
            "pnl_pct": pnl_pct,
            "result": result,
            "session": session,
            "signal_date": signal_date,
        })

    return closed


def get_weekly_signals(week_start: str, week_end: str) -> list[dict]:
    """Return all closed signals for a given week."""
    with _conn() as con:
        rows = con.execute("""
            SELECT code, name, score, narrative, signal_price, t2_close,
                   pnl_pct, result, exit_type, session, signal_date, t2_date
            FROM signals
            WHERE status = 'closed'
              AND signal_date BETWEEN ? AND ?
            ORDER BY signal_date, session
        """, (week_start, week_end)).fetchall()

    return [_row_to_dict(r) for r in rows]


def get_all_closed_signals() -> list[dict]:
    """Return all closed signals since inception."""
    with _conn() as con:
        rows = con.execute("""
            SELECT code, name, score, narrative, signal_price, t2_close,
                   pnl_pct, result, exit_type, session, signal_date, t2_date
            FROM signals
            WHERE status = 'closed'
            ORDER BY signal_date, session
        """).fetchall()

    return [_row_to_dict(r) for r in rows]


def get_inception_date() -> str:
    """Return the date of the first ever signal."""
    with _conn() as con:
        row = con.execute("SELECT MIN(signal_date) FROM signals").fetchone()
    return row[0] if row and row[0] else "N/A"


def _row_to_dict(row: tuple) -> dict:
    keys = ["code", "name", "score", "narrative", "signal_price", "t2_close",
            "pnl_pct", "result", "exit_type", "session", "signal_date", "t2_date"]
    return dict(zip(keys, row))


def _fetch_close(ticker: str) -> float | None:
    """Fetch latest closing price via yfinance."""
    import yfinance as yf
    try:
        df = yf.download(ticker, period="2d", progress=False, auto_adjust=True)
        if df.empty:
            return None
        return float(df["Close"].iloc[-1])
    except Exception as e:
        logging.warning(f"yfinance close fetch failed for {ticker}: {e}")
        return None
