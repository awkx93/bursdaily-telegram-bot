from datetime import datetime, timedelta


def _pnl_str(pnl: float) -> str:
    return f"+{pnl:.1f}%" if pnl >= 0 else f"{pnl:.1f}%"


def _result_icon(result: str) -> str:
    return {"WIN": "✅", "LOSS": "❌", "BREAKEVEN": "➖"}.get(result, "")


def format_t2_result(signal: dict) -> str:
    pnl = signal["pnl_pct"]
    icon = "🟢" if signal["result"] == "WIN" else ("🔴" if signal["result"] == "LOSS" else "⚪")
    exit_labels = {
        "stop_hit": "Stop loss hit",
        "target1": "Target 1 hit (+5%)",
        "target2": "Target 2 hit (+10%)",
        "t2_exit": "T+2 close exit",
    }

    lines = [
        f"📋 T+2 RESULT — {signal['code']}",
        f"{signal['name']}",
        "",
        f"{icon} {signal['result']} | {_pnl_str(pnl)}",
        "",
        f"Signal date:  {signal['signal_date']} ({signal['session'].title()})",
        f"Entry price:  RM{signal['signal_price']:.3f}",
        f"T+2 close:    RM{signal['t2_close']:.3f}",
        f"Exit type:    {exit_labels.get(signal['exit_type'], signal['exit_type'])}",
        f"Score:        {signal['score']}/100",
        f"Narrative:    {signal['narrative']}",
    ]
    return "\n".join(lines)


def format_weekly_summary(signals: list[dict], week_start: str, week_end: str) -> str:
    if not signals:
        return (
            f"📊 WEEKLY TRACK RECORD\n"
            f"{week_start} – {week_end}\n\n"
            f"No closed signals this week."
        )

    wins = [s for s in signals if s["result"] == "WIN"]
    losses = [s for s in signals if s["result"] == "LOSS"]
    breakevens = [s for s in signals if s["result"] == "BREAKEVEN"]

    win_rate = len(wins) / len(signals) * 100
    avg_win = sum(s["pnl_pct"] for s in wins) / len(wins) if wins else 0
    avg_loss = sum(s["pnl_pct"] for s in losses) / len(losses) if losses else 0
    total_pnl = sum(s["pnl_pct"] for s in signals)

    best = max(signals, key=lambda x: x["pnl_pct"])
    worst = min(signals, key=lambda x: x["pnl_pct"])

    # Score breakdown
    high_score = [s for s in signals if s["score"] >= 80]
    low_score = [s for s in signals if s["score"] < 80]
    high_wins = sum(1 for s in high_score if s["result"] == "WIN")
    low_wins = sum(1 for s in low_score if s["result"] == "WIN")

    lines = [
        f"📊 WEEKLY TRACK RECORD",
        f"{week_start} – {week_end}",
        f"{'─' * 28}",
        f"Signals:   {len(signals)}",
        f"Winners:   {len(wins)} ({win_rate:.0f}%) ✅",
        f"Losers:    {len(losses)} ({100-win_rate:.0f}%) ❌",
        f"Breakeven: {len(breakevens)} ➖",
        f"",
        f"Avg winner:  {_pnl_str(avg_win)}",
        f"Avg loser:   {_pnl_str(avg_loss)}",
        f"Week P&L:    {_pnl_str(total_pnl)} (sum)",
        f"",
        f"Best:  {best['code']} {_pnl_str(best['pnl_pct'])} (score {best['score']})",
        f"Worst: {worst['code']} {_pnl_str(worst['pnl_pct'])} (score {worst['score']})",
        f"",
        f"By Score",
        f"≥80:   {high_wins}/{len(high_score)} won" if high_score else "≥80:   no signals",
        f"65–79: {low_wins}/{len(low_score)} won" if low_score else "65–79: no signals",
    ]

    # Narrative breakdown
    narratives: dict[str, list] = {}
    for s in signals:
        n = s.get("narrative", "Unknown")
        narratives.setdefault(n, []).append(s)

    if narratives:
        lines.append("")
        lines.append("By Narrative")
        for n, sigs in sorted(narratives.items(), key=lambda x: -len(x[1])):
            nw = sum(1 for s in sigs if s["result"] == "WIN")
            lines.append(f"{n[:20]}: {nw}/{len(sigs)} won")

    return "\n".join(lines)


def format_cumulative(signals: list[dict], inception_date: str) -> str:
    if not signals:
        return (
            f"📈 CUMULATIVE TRACK RECORD\n"
            f"Since: {inception_date}\n\n"
            f"No closed signals yet."
        )

    wins = [s for s in signals if s["result"] == "WIN"]
    losses = [s for s in signals if s["result"] == "LOSS"]
    breakevens = [s for s in signals if s["result"] == "BREAKEVEN"]

    win_rate = len(wins) / len(signals) * 100
    avg_win = sum(s["pnl_pct"] for s in wins) / len(wins) if wins else 0
    avg_loss = abs(sum(s["pnl_pct"] for s in losses) / len(losses)) if losses else 0
    total_pnl = sum(s["pnl_pct"] for s in signals)
    profit_factor = (avg_win * len(wins)) / (avg_loss * len(losses)) if losses and avg_loss > 0 else float("inf")

    best = max(signals, key=lambda x: x["pnl_pct"])
    worst = min(signals, key=lambda x: x["pnl_pct"])

    today = datetime.today().strftime("%d %b %Y")

    # Score breakdown
    high_score = [s for s in signals if s["score"] >= 80]
    low_score = [s for s in signals if s["score"] < 80]
    high_wins = sum(1 for s in high_score if s["result"] == "WIN")
    low_wins = sum(1 for s in low_score if s["result"] == "WIN")

    # Session breakdown
    morning = [s for s in signals if s["session"] == "morning"]
    afternoon = [s for s in signals if s["session"] == "afternoon"]
    m_wins = sum(1 for s in morning if s["result"] == "WIN")
    a_wins = sum(1 for s in afternoon if s["result"] == "WIN")

    lines = [
        f"📈 CUMULATIVE TRACK RECORD",
        f"Since: {inception_date} | As of: {today}",
        f"{'─' * 28}",
        f"Total signals: {len(signals)}",
        f"Winners:   {len(wins)} ({win_rate:.1f}%) ✅",
        f"Losers:    {len(losses)} ({len(losses)/len(signals)*100:.1f}%) ❌",
        f"Breakeven: {len(breakevens)} ➖",
        f"",
        f"Avg winner:     {_pnl_str(avg_win)}",
        f"Avg loser:      -{avg_loss:.1f}%",
        f"Profit factor:  {profit_factor:.2f}",
        f"Total P&L:      {_pnl_str(total_pnl)} (sum)",
        f"",
        f"Best ever:  {best['code']} {_pnl_str(best['pnl_pct'])} ({best['signal_date']})",
        f"Worst ever: {worst['code']} {_pnl_str(worst['pnl_pct'])} ({worst['signal_date']})",
        f"",
        f"By Score",
        f"≥80:   {high_wins}/{len(high_score)} won ({high_wins/len(high_score)*100:.0f}%)" if high_score else "≥80:   no signals",
        f"65–79: {low_wins}/{len(low_score)} won ({low_wins/len(low_score)*100:.0f}%)" if low_score else "65–79: no signals",
        f"",
        f"By Session",
        f"Morning:   {m_wins}/{len(morning)} won ({m_wins/len(morning)*100:.0f}%)" if morning else "Morning:   no signals",
        f"Afternoon: {a_wins}/{len(afternoon)} won ({a_wins/len(afternoon)*100:.0f}%)" if afternoon else "Afternoon: no signals",
    ]

    # Top narratives
    narratives: dict[str, list] = {}
    for s in signals:
        n = s.get("narrative", "Unknown")
        narratives.setdefault(n, []).append(s)

    if narratives:
        lines.append("")
        lines.append("By Narrative")
        for n, sigs in sorted(narratives.items(), key=lambda x: -len(x[1])):
            nw = sum(1 for s in sigs if s["result"] == "WIN")
            rate = nw / len(sigs) * 100
            flag = " 🔥" if rate >= 70 else ""
            lines.append(f"{n[:22]}: {nw}/{len(sigs)} ({rate:.0f}%){flag}")

    return "\n".join(lines)
