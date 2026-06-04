"""
4-ETF DCA Monitor
─────────────────
Usage:
  python main.py              daily check — live regime + today's action
  python main.py --save       save this month's decision to history.csv
  python main.py --backtest   run historical backtest from 2010

Required: pip install -r requirements.txt
"""

import argparse
import sys
from datetime import date

from rich.console import Console
from rich.panel   import Panel
from rich.table   import Table
from rich.text    import Text
from rich         import box

from config import MONTHLY_BUDGET, FEAR2_BUDGET, COST_BASIS, HOLDINGS
import data as data_module
from regime       import classify_raw, load_history, decide_regime, get_allocation, save_month
from profit_taking import evaluate

console = Console()

# ── colour helpers ────────────────────────────────────────────

REGIME_COLOR = {
    "bull":  "green", "chop": "yellow",
    "fear1": "red",   "fear2": "magenta",
}
REGIME_LABEL = {
    "bull":  "🟢 BULL · Trending Up",
    "chop":  "🟡 CHOP · Sideways",
    "fear1": "🔴 FEAR I · Panic Buying",
    "fear2": "🟣 FEAR II · Crash",
}
ALERT_COLOR = {
    "HOLD": "green", "WATCH": "yellow",
    "CAUTION": "red", "EXTREME": "magenta",
}
SCORE_ICON = ["✅", "🟡", "🔴", "🟣"]


def pct(v, decimals=1):
    if v is None: return "N/A"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.{decimals}f}%"


def usd(v):
    if v is None: return "—"
    return f"${v:,.0f}"


# ── sections ──────────────────────────────────────────────────

def section_prices(d: dict) -> Panel:
    t = Table(box=box.SIMPLE, show_header=True, header_style="dim")
    t.add_column("ETF",        style="bold", width=6)
    t.add_column("Price",      justify="right")
    t.add_column("Cost basis", justify="right")
    t.add_column("Gain",       justify="right")
    t.add_column("Shares",     justify="right")
    t.add_column("Value",      justify="right")

    prices = {
        "QQQ":  d["qqq_price"],
        "TQQQ": d["tqqq_price"],
        "SMH":  d["smh_price"],
        "SOXL": d["soxl_price"],
    }
    for etf, price in prices.items():
        cost   = COST_BASIS.get(etf, 0)
        shares = HOLDINGS.get(etf, 0)
        gain   = ((price / cost) - 1) * 100 if cost > 0 else None
        val    = shares * price if shares > 0 else None
        gain_s = pct(gain) if gain is not None else "—"
        color  = "green" if (gain or 0) >= 0 else "red"
        t.add_row(
            etf,
            f"${price:,.2f}",
            f"${cost:,.2f}" if cost > 0 else "—",
            f"[{color}]{gain_s}[/{color}]",
            f"{shares:,}" if shares > 0 else "—",
            usd(val),
        )
    return Panel(t, title="Prices & Portfolio", border_style="dim")


def section_regime_indicators(d: dict) -> Panel:
    t = Table(box=box.SIMPLE, show_header=True, header_style="dim")
    t.add_column("Indicator",  width=24)
    t.add_column("Value",      justify="right")
    t.add_column("Status",     justify="right")

    rows = [
        ("VIX",
         f"{d['vix']:.1f}",
         ("✅ Bull zone", "green") if d["vix"] < 20
         else ("🔴 Chop/Fear", "red")),

        ("QQQ vs 200-day MA",
         f"{'Above' if d['above_200ma'] else 'Below'} ({pct(d['above_200ma_pct'])})",
         ("✅ Trending up", "green") if d["above_200ma"]
         else ("❌ Below 200MA", "red")),

        ("Drawdown from high",
         pct(d["drawdown_pct"]),
         ("✅ Near high", "green") if d["drawdown_pct"] > -10
         else ("⚠️  In drawdown", "yellow")),

        ("RSI 35-day (QQQ)",
         f"{d['rsi']:.1f}",
         ("✅ Healthy", "green") if 45 <= d["rsi"] <= 75
         else ("⚠️  Outside range", "yellow")),

        ("MACD",
         "Bullish" if d["macd_bull"] else "Bearish",
         ("✅ Above signal", "green") if d["macd_bull"]
         else ("❌ Below signal", "red")),

        ("SMH vs QQQ (20d RS)",
         pct(d["smh_rs_gap"]),
         ("✅ Semi leading", "green") if d["smh_rs_gap"] > -3
         else ("⚠️  Semi lagging", "yellow")),
    ]

    for label, val, (status, color) in rows:
        t.add_row(label, val, f"[{color}]{status}[/{color}]")

    return Panel(t, title="Regime Indicators", border_style="dim")


def section_profit_taking(d: dict, pt: dict) -> Panel:
    level  = pt["alert_level"]
    color  = ALERT_COLOR[level]
    firing = pt["firing"]

    t = Table(box=box.SIMPLE, show_header=True, header_style="dim")
    t.add_column("Indicator",  width=26)
    t.add_column("Value",      justify="right")
    t.add_column("Threshold",  justify="right")
    t.add_column("Status",     justify="right")

    labels = {
        "qqq_pe_fwd":      ("QQQ Forward P/E",       f"{d.get('qqq_pe_fwd') or 'N/A'}×", "38× / 45× / 52×"),
        "rsi_35":          ("RSI 35-day",             f"{d['rsi']:.1f}",                   "78 / 83 / 88"),
        "above_200ma_pct": ("Above 200MA",            pct(d["above_200ma_pct"]),            "30% / 40% / 50%"),
        "vix_low":         ("VIX complacency",        f"{d['vix']:.1f}",                   "<13 / <11 / <10"),
        "return_12m_pct":  ("12M QQQ return",         pct(d["return_12m_pct"]),             "50% / 65% / 80%"),
        "tqqq_gain_pct":   ("TQQQ gain vs cost",      pct(d.get("tqqq_gain_pct")),          "200% / 400% / 700%"),
    }
    icons = ["✅ Normal", "🟡 Elevated", "🔴 Extreme", "🟣 Bubble"]
    colors = ["green", "yellow", "red", "magenta"]

    for key, (label, val, threshold) in labels.items():
        sc = pt["scores"][key]
        t.add_row(label, val, threshold,
                  f"[{colors[sc]}]{icons[sc]}[/{colors[sc]}]")

    title = (f"Profit-Taking Monitor · "
             f"[{color}]{level}[/{color}] · {firing}/6 signals")
    return Panel(t, title=title, border_style=color)


def section_action(regime: str, alloc: dict, budget: int, pt: dict) -> Panel:
    color = REGIME_COLOR[regime]
    label = REGIME_LABEL[regime]

    t = Table(box=box.SIMPLE, show_header=True, header_style="dim")
    t.add_column("ETF",    style="bold", width=6)
    t.add_column("Weight", justify="right")
    t.add_column("Amount", justify="right", style="bold")
    t.add_column("Action", width=10)

    for etf, amt in alloc.items():
        if amt > 0:
            pct_s = f"{amt/budget*100:.0f}%"
            t.add_row(etf, pct_s, f"[{color}]${amt:,.0f}[/{color}]", "BUY")
        else:
            t.add_row(etf, "0%", "—", "—")

    t.add_section()
    t.add_row("TOTAL", "100%", f"[bold]${budget:,.0f}[/bold]", label)

    # profit-taking note
    pt_level  = pt["alert_level"]
    pt_color  = ALERT_COLOR[pt_level]
    pt_note   = Text(f"\nProfit-Taking: [{pt_level}]  {pt['action']}", style=pt_color)

    content = Text()
    content.append_text(pt_note)

    title = f"[bold]TODAY'S ACTION · [{color}]{label}[/{color}][/bold]"
    return Panel(t, title=title, border_style=color)


# ── main dashboard ────────────────────────────────────────────

def run_dashboard(save: bool = False, export_html: bool = False) -> None:
    console.print()
    console.rule(f"[bold]4-ETF DCA MONITOR[/bold]  ·  {date.today()}", style="dim")
    console.print()

    # fetch
    with console.status("[dim]Fetching live market data...[/dim]"):
        try:
            d = data_module.fetch_all()
        except Exception as e:
            console.print(f"[red]Data fetch failed: {e}[/red]")
            sys.exit(1)

    console.print("[dim]✓ Data fetched[/dim]\n")

    # regime
    history = load_history()
    raw     = classify_raw(d)
    regime  = decide_regime(raw, history)
    alloc, budget = get_allocation(regime)

    # profit-taking
    pt = evaluate(d)

    # ── print ──
    console.print(section_prices(d))
    console.print()
    console.print(section_regime_indicators(d))
    console.print()
    console.print(section_profit_taking(d, pt))
    console.print()
    console.print(section_action(regime, alloc, budget, pt))
    console.print()

    # extra warnings
    if regime == "fear2":
        console.print(Panel(
            f"[bold magenta]⚡ FEAR II ACTIVE[/bold magenta]\n"
            f"Deploy [bold]${FEAR2_BUDGET:,}[/bold] this month.\n"
            f"Split: [bold]{('TQQQ 50% + SOXL 50%') if 'lev' in str(alloc) else 'QQQ 50% + SMH 50%'}[/bold]\n"
            f"Change FEAR2_SPLIT in config.py if needed.",
            border_style="magenta"
        ))
        console.print()

    if pt["alert_level"] in ("CAUTION", "EXTREME"):
        console.print(Panel(
            f"[bold red]⚠️  PROFIT-TAKING ACTION REQUIRED[/bold red]\n"
            f"{pt['action']}\n\n"
            f"[dim]Confirm this level for 3 consecutive weeks before executing.\n"
            f"Sell order: SOXL first → TQQQ second → SMH only at EXTREME → QQQ never.[/dim]",
            border_style="red"
        ))
        console.print()

    # history note
    n = len(history)
    console.print(f"[dim]  Regime history: {n} month{'s' if n != 1 else ''} on record "
                  f"(raw signal today: {raw})[/dim]")

    if save:
        save_month(d, raw, regime, alloc)
        console.print(f"[green]  ✓ Saved to {data_module.HISTORY_FILE}[/green]")

    if export_html:
        from export_html import generate_html
        html = generate_html(d, regime, alloc, budget, pt, raw, history)
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html)
        console.print(f"[green]  ✓ Exported to index.html[/green]")

    console.print()


# ── entry point ───────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="4-ETF DCA Monitor")
    parser.add_argument("--save",     action="store_true",
                        help="Save this month's decision to history.csv")
    parser.add_argument("--html",     action="store_true",
                        help="Export dashboard to index.html")
    parser.add_argument("--backtest", action="store_true",
                        help="Run historical backtest from 2010")
    args = parser.parse_args()

    if args.backtest:
        from backtest import run_backtest
        run_backtest()
    else:
        run_dashboard(save=args.save, export_html=args.html)
