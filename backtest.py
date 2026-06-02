"""
Backtest the 4-regime DCA strategy from 2010 to today.
Compares: Adaptive (regime-switching) vs Static (always bull/50-50 leveraged).

Run: python main.py --backtest
  or python backtest.py --start 2015-01-01 --monthly 500
"""

import argparse
import yfinance as yf
import pandas as pd
import numpy as np
from rich.console import Console
from rich.table   import Table
from rich         import box
from config import VIX_THRESHOLDS, ALLOCATIONS, MONTHLY_BUDGET

console = Console()


def run_backtest(start: str = "2010-01-01", monthly_budget: int = MONTHLY_BUDGET) -> None:
    console.print(f"\n[dim]Fetching historical data ({start} → today)...[/dim]")

    tickers = ["QQQ", "TQQQ", "SMH", "SOXL", "^VIX"]
    raw = yf.download(tickers, start=start, auto_adjust=True,
                      progress=False)["Close"]
    raw.columns = [c.replace("^", "") for c in raw.columns]

    # forward-fill gaps (TQQQ/SOXL launched 2010; early rows may be NaN)
    raw = raw.ffill().dropna()

    # resample to monthly (first trading day)
    monthly = raw.resample("MS").first()

    results = []
    sig_history: list[str] = []

    for i in range(len(monthly) - 1):
        row       = monthly.iloc[i]
        next_row  = monthly.iloc[i + 1]
        vix_val   = row["VIX"]

        # raw regime signal
        t = VIX_THRESHOLDS
        if   vix_val > t["fear1_max"]: raw_sig = "fear2"
        elif vix_val > t["chop_max"]:  raw_sig = "fear1"
        elif vix_val > t["bull_max"]:  raw_sig = "chop"
        else:                          raw_sig  = "bull"

        # simplified hysteresis (1-month confirm for all non-fear2)
        if not sig_history:
            regime = "chop"
        elif raw_sig == "fear2":
            regime = "fear2"
        elif raw_sig in ("fear1", "chop"):
            regime = raw_sig
        elif raw_sig == "bull":
            prev = sig_history[-1]
            if prev in ("fear1", "fear2"):
                regime = "chop"   # block fear → bull
            elif prev == "bull" and len(sig_history) >= 2 and sig_history[-2] == "bull":
                regime = "bull"
            else:
                regime = "chop"
        else:
            regime = sig_history[-1] if sig_history else "chop"

        sig_history.append(raw_sig)

        budget = MONTHLY_BUDGET * 3 if regime == "fear2" else monthly_budget
        alloc_key = "fear2_lev" if regime == "fear2" else regime

        next_prices = {
            "QQQ":  float(next_row["QQQ"]),
            "TQQQ": float(next_row["TQQQ"]),
            "SMH":  float(next_row["SMH"]),
            "SOXL": float(next_row["SOXL"]),
        }
        results.append({
            "date":        monthly.index[i],
            "regime":      regime,
            "raw_signal":  raw_sig,
            "vix":         round(vix_val, 1),
            "budget":      budget,
            "weights":     ALLOCATIONS[alloc_key],
            "static_w":    ALLOCATIONS["bull"],
            "prices":      next_prices,
        })

    # ── simulate ──────────────────────────────────────────────
    def simulate(results, adaptive: bool) -> pd.DataFrame:
        holdings  = {e: 0.0 for e in ["QQQ", "TQQQ", "SMH", "SOXL"]}
        total_inv = 0.0
        rows      = []

        for r in results:
            budget  = r["budget"] if adaptive else monthly_budget
            weights = r["weights"] if adaptive else r["static_w"]
            prices  = r["prices"]
            total_inv += budget

            for etf, w in weights.items():
                if w > 0 and prices[etf] > 0:
                    holdings[etf] += (w * budget) / prices[etf]

            port_val = sum(holdings[e] * prices[e] for e in holdings)
            rows.append({
                "date":    r["date"],
                "value":   port_val,
                "invested":total_inv,
                "regime":  r["regime"],
            })

        return pd.DataFrame(rows)

    adaptive = simulate(results, adaptive=True)
    static   = simulate(results, adaptive=False)

    # ── report ────────────────────────────────────────────────
    console.print()
    console.rule("[bold]BACKTEST RESULTS[/bold]", style="dim")

    t = Table(box=box.SIMPLE, show_header=True, header_style="dim")
    t.add_column("Metric",         width=28)
    t.add_column("Adaptive",       justify="right", style="green")
    t.add_column("Static (always bull)", justify="right", style="dim")

    def stats(df):
        final    = df["value"].iloc[-1]
        invested = df["invested"].iloc[-1]
        years    = (df["date"].iloc[-1] - df["date"].iloc[0]).days / 365.25
        cagr     = (final / invested) ** (1 / years) - 1 if years > 0 else 0
        mdd      = ((df["value"] / df["value"].cummax()) - 1).min() * 100
        return final, invested, cagr, mdd

    af, ai, ac, am = stats(adaptive)
    sf, si, sc, sm = stats(static)

    t.add_row("Total contributed",  f"${ai:>12,.0f}", f"${si:>12,.0f}")
    t.add_row("Final portfolio value", f"${af:>12,.0f}", f"${sf:>12,.0f}")
    t.add_row("Total return",       f"{(af/ai-1)*100:>+.1f}%",  f"{(sf/si-1)*100:>+.1f}%")
    t.add_row("CAGR (on invested)", f"{ac*100:>+.1f}%/yr",      f"{sc*100:>+.1f}%/yr")
    t.add_row("Max drawdown",       f"{am:.1f}%",               f"{sm:.1f}%")
    console.print(t)

    console.print(f"\n  Adaptive edge over static: [green]${af - sf:>,.0f}[/green]\n")

    # regime distribution
    counts = {}
    for r in results:
        counts[r["regime"]] = counts.get(r["regime"], 0) + 1
    total = len(results)
    console.print(f"  Regime distribution ({total} months):")
    colors = {"bull":"green","chop":"yellow","fear1":"red","fear2":"magenta"}
    for reg in ["bull","chop","fear1","fear2"]:
        cnt = counts.get(reg, 0)
        c   = colors[reg]
        console.print(f"    [{c}]{reg:<10}[/{c}]  {cnt:>3} months  ({cnt/total*100:.0f}%)")

    # save CSV
    adaptive["type"] = "adaptive"
    static["type"]   = "static"
    pd.concat([adaptive, static]).to_csv("backtest_results.csv", index=False)
    console.print(f"\n  [dim]Full results → backtest_results.csv[/dim]\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start",   default="2010-01-01")
    parser.add_argument("--monthly", default=MONTHLY_BUDGET, type=int)
    args = parser.parse_args()
    run_backtest(start=args.start, monthly_budget=args.monthly)
