"""
Full-transparency backtest engine for the 4-ETF DCA framework.

Reuses the LIVE logic (regime.py + profit_taking.py) so it tests the actual
strategy, not a re-implementation.

Design
------
- Flat $10,000/month DCA from the first month all 4 ETFs trade (~Apr 2010).
- Each month, classify the regime (VIX hysteresis + euphoria) and deploy the
  contribution into that regime's target ETFs:
      euphoria -> 100% to CASH reserve (pause)
      chop     -> QQQ 50% + SMH 50%
      bull/fear1 -> TQQQ 50% + SOXL 50%
      fear2    -> TQQQ 50% + SOXL 50%, funded by contribution + ALL saved cash
- Profit-taking (live evaluate()) each month: CAUTION trims, EXTREME trims more;
  proceeds -> cash reserve (re-deployed in the next Fear II).
- Benchmark B&H: same $10k/month into 100% QQQ, never sold.

Outputs
-------
  backtest.xlsx          - Monthly (full position-level), Summary, Notes
  backtest_summary.json  - compact metrics for the dashboard Backtest tab

Sharpe
------
  Investment Sharpe   = annualized Sharpe of monthly time-weighted returns
                        (equal-weighted — pure strategy skill, cash-flow neutral)
  Contribution Sharpe = same monthly returns CAPITAL-weighted by dollars deployed
                        (the 'growth of the asset' view of the DCA experience)
"""

import json
import re
import requests
import numpy as np
import pandas as pd
import yfinance as yf
import pandas_ta as ta
from bs4 import BeautifulSoup

from config import MONTHLY_BUDGET, ALLOCATIONS
import data as data_module          # noqa (kept for parity)
from regime import classify_raw, decide_regime
from profit_taking import evaluate

ETFS = ["QQQ", "TQQQ", "SMH", "SOXL"]
RF_ANNUAL = 0.0                     # risk-free for Sharpe (cash earns 0 here)
TXN_COST  = 0.001                   # 0.1% slippage per trade
XLSX = "backtest.xlsx"
JSON = "backtest_summary.json"
_HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}


# ── data ──────────────────────────────────────────────────────

def _close(tkr):
    s = yf.download(tkr, period="max", auto_adjust=True, progress=False)["Close"]
    if isinstance(s, pd.DataFrame):
        s = s.squeeze()
    return s.dropna()


def _cape_history():
    try:
        r = requests.get("https://www.multpl.com/shiller-pe/table/by-month",
                         timeout=20, headers=_HDR)
        soup = BeautifulSoup(r.text, "html.parser")
        recs = []
        for tr in soup.select("table#datatable tr")[1:]:
            c = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(c) >= 2:
                try:
                    recs.append((pd.to_datetime(c[0]), float(re.sub(r"[^0-9.]", "", c[1]))))
                except Exception:
                    pass
        return pd.DataFrame(recs, columns=["Date", "CAPE"]).set_index("Date").sort_index()["CAPE"]
    except Exception:
        return pd.Series(dtype="float64")


def build_monthly():
    print("Downloading data...")
    daily = pd.DataFrame({e: _close(e) for e in ETFS})
    daily["VIX"] = _close("^VIX")
    qqq = daily["QQQ"].astype(float)

    ind = pd.DataFrame(index=daily.index)
    for e in ETFS:
        ind[e] = daily[e]
    ind["VIX"]   = daily["VIX"]
    sma200 = qqq.rolling(200).mean()
    ind["above_200ma_pct"] = (qqq - sma200) / sma200 * 100
    ind["rsi"]             = ta.rsi(qqq, length=35)
    ind["return_12m_pct"]  = (qqq / qqq.shift(252) - 1) * 100

    monthly = ind.resample("ME").last()
    cape = _cape_history()
    monthly["cape"] = cape.reindex(monthly.index, method="ffill") if not cape.empty else np.nan

    # first month all 4 ETFs have a price
    ok = monthly[ETFS].notna().all(axis=1)
    monthly = monthly[ok.cummax()].dropna(subset=ETFS)
    return monthly


# ── helpers ───────────────────────────────────────────────────

def _annual_irr(cashflows):
    """Money-weighted annual return from monthly cashflows (list)."""
    def npv(r):
        return sum(cf / (1 + r) ** i for i, cf in enumerate(cashflows))
    lo, hi = -0.5, 1.0
    if npv(lo) * npv(hi) > 0:
        return float("nan")
    for _ in range(200):
        mid = (lo + hi) / 2
        v = npv(mid)
        if abs(v) < 1e-6:
            break
        if npv(lo) * v < 0:
            hi = mid
        else:
            lo = mid
    return (1 + mid) ** 12 - 1


def _sharpe(returns, weights=None):
    r = np.array(returns, dtype=float)
    if len(r) < 2:
        return float("nan")
    rf_m = (1 + RF_ANNUAL) ** (1/12) - 1
    ex = r - rf_m
    if weights is None:
        mu, sd = ex.mean(), ex.std(ddof=1)
    else:
        w = np.array(weights, dtype=float)
        w = w / w.sum()
        mu = np.sum(w * ex)
        sd = np.sqrt(np.sum(w * (ex - mu) ** 2))
    return float(mu / sd * np.sqrt(12)) if sd > 0 else float("nan")


def _sortino(returns):
    r = np.array(returns, dtype=float)
    rf_m = (1 + RF_ANNUAL) ** (1/12) - 1
    ex = r - rf_m
    dn = ex[ex < 0]
    if len(dn) < 2:
        return float("nan")
    dd = np.sqrt(np.mean(dn ** 2))
    return float(ex.mean() / dd * np.sqrt(12)) if dd > 0 else float("nan")


def _maxdd(twr_index):
    s = pd.Series(twr_index)
    return float((s / s.cummax() - 1).min() * 100)


def bh_sim(prices, contrib):
    """Buy & hold DCA into a single ETF: same $/month, never sold.
    Returns (nav_series, monthly_twr, twr_index)."""
    sh = 0.0
    navs, twr, twr_idx = [], [], []
    idx, prev = 1.0, None
    for p in prices:
        if prev is not None and prev > 0:
            tw = (sh * p) / prev - 1
            twr.append(tw); idx *= (1 + tw); twr_idx.append(idx)
        sh += contrib * (1 - TXN_COST) / p
        nav = sh * p
        navs.append(nav); prev = nav
    return navs, twr, twr_idx


# ── strategy simulation ───────────────────────────────────────

def simulate_strategy(m, dates, cap=None, reinvest=False):
    """
    Fully-invested adaptive strategy.
    cap=None              -> no cap (pure apples-to-apples).
    cap=0.25, reinvest=F  -> each December trim any ETF above 25% of NAV to CASH
                             ('Adaptive strategy with cash').
    cap=0.25, reinvest=T  -> each December rebalance to the cap, redeploying the
                             excess into the under-cap ETFs so it stays fully
                             invested. With 4 ETFs a 25% cap = equal-weight 25% each.
    Returns a dict with rows, twr/wts/twr_idx, alloc_hist (incl Cash), final, cashflows.
    """
    shares = {e: 0.0 for e in ETFS}
    cost   = {e: 0.0 for e in ETFS}
    cash   = 0.0
    raw_hist, rows, cashflows = [], [], []
    prev_nav = None
    twr, wts, twr_idx = [], [], []
    alloc_hist = {e: [] for e in ETFS}; alloc_hist["Cash"] = []
    idx = 1.0
    bh_sh = 0.0

    for i, dt in enumerate(dates):
        px = {e: float(m.loc[dt, e]) for e in ETFS}

        if prev_nav is not None and prev_nav > 0:
            v_pre = sum(shares[e] * px[e] for e in ETFS) + cash
            tw = v_pre / prev_nav - 1
            twr.append(tw); wts.append(prev_nav); idx *= (1 + tw); twr_idx.append(idx)

        d = {"vix": float(m.loc[dt, "VIX"]),
             "above_200ma_pct": float(m.loc[dt, "above_200ma_pct"]),
             "rsi": float(m.loc[dt, "rsi"]),
             "return_12m_pct": float(m.loc[dt, "return_12m_pct"])}
        raw = classify_raw(d)
        regime = decide_regime(raw, raw_hist)
        raw_hist.append(raw)

        tqqq_gain = ((px["TQQQ"]/(cost["TQQQ"]/shares["TQQQ"]))-1)*100 if shares["TQQQ"]>0 and cost["TQQQ"]>0 else None
        pt = evaluate({**d, "qqq_pe_fwd": None, "cape": (None if pd.isna(m.loc[dt,"cape"]) else float(m.loc[dt,"cape"])),
                       "tqqq_gain_pct": tqqq_gain})
        alert = pt["alert_level"]

        buys  = {e: 0.0 for e in ETFS}
        sells = {e: 0.0 for e in ETFS}

        # deploy the full contribution per regime (fully invested)
        contrib = MONTHLY_BUDGET
        cashflows.append(-contrib)
        alloc_key = {"euphoria": "chop", "fear2": "fear2_lev"}.get(regime, regime)
        for etf, w in ALLOCATIONS[alloc_key].items():
            if w > 0:
                dollars = contrib * w
                shares[etf] += dollars * (1 - TXN_COST) / px[etf]
                cost[etf]   += dollars
                buys[etf]   += dollars

        # ANNUAL DECEMBER REBALANCE: cap each ETF at `cap` of total NAV
        if cap and dt.month == 12:
            nav_now = sum(shares[e] * px[e] for e in ETFS) + cash
            capval = cap * nav_now
            # sell anything above the cap to cash
            for e in ETFS:
                val = shares[e] * px[e]
                if val > capval + 1:
                    frac = (val - capval) / val
                    sh = shares[e] * frac
                    shares[e] -= sh
                    cost[e]   *= (1 - frac)
                    cash += sh * px[e] * (1 - TXN_COST)
                    sells[e] += sh * px[e]
            # fully-invested mode: redeploy the freed cash into under-cap ETFs
            # (with 4 ETFs and a 25% cap this lands at equal-weight 25% each)
            if reinvest:
                for e in ETFS:
                    val = shares[e] * px[e]
                    need = capval - val
                    if need > 1 and cash > 1:
                        spend = min(need, cash)
                        shares[e] += spend * (1 - TXN_COST) / px[e]
                        cost[e]   += spend
                        cash      -= spend
                        buys[e]   += spend

        holdings_val = sum(shares[e] * px[e] for e in ETFS)
        nav = holdings_val + cash
        prev_nav = nav
        for e in ETFS:
            alloc_hist[e].append(round(shares[e] * px[e] / nav * 100, 1) if nav > 0 else 0.0)
        alloc_hist["Cash"].append(round(cash / nav * 100, 1) if nav > 0 else 0.0)

        bh_sh += contrib * (1 - TXN_COST) / px["QQQ"]
        rows.append({
            "Date": dt.date(), "Regime": regime, "ProfitTaking": alert, "Contribution": contrib,
            "Buy_QQQ": round(buys["QQQ"]), "Buy_TQQQ": round(buys["TQQQ"]),
            "Buy_SMH": round(buys["SMH"]), "Buy_SOXL": round(buys["SOXL"]),
            "Sell_TQQQ": round(sells["TQQQ"]), "Sell_SOXL": round(sells["SOXL"]),
            "Px_QQQ": round(px["QQQ"],2), "Px_TQQQ": round(px["TQQQ"],2),
            "Px_SMH": round(px["SMH"],2), "Px_SOXL": round(px["SOXL"],2),
            "Sh_QQQ": round(shares["QQQ"],1), "Sh_TQQQ": round(shares["TQQQ"],1),
            "Sh_SMH": round(shares["SMH"],1), "Sh_SOXL": round(shares["SOXL"],1),
            "Cash": round(cash), "Holdings_Value": round(holdings_val),
            "NAV": round(nav), "Cum_Contrib": round(sum(-c for c in cashflows)),
            "Monthly_TWR_%": round(twr[-1]*100,2) if twr else 0.0,
            "TWR_Index": round(idx,3), "BH_NAV": round(bh_sh * px["QQQ"]),
        })

    return {"rows": rows, "twr": twr, "wts": wts, "twr_idx": twr_idx,
            "alloc_hist": alloc_hist, "final": nav, "cashflows": cashflows}


def run():
    m = build_monthly()
    dates = m.index
    print(f"Backtest window: {dates[0].date()} -> {dates[-1].date()}  ({len(dates)} months)")

    main      = simulate_strategy(m, dates, cap=None)
    capped    = simulate_strategy(m, dates, cap=0.25)                  # excess -> cash
    capped_fi = simulate_strategy(m, dates, cap=0.25, reinvest=True)   # fully invested (equal-wt)

    rows = main["rows"]
    twr, wts, twr_idx = main["twr"], main["wts"], main["twr_idx"]
    alloc_hist = main["alloc_hist"]
    cashflows = main["cashflows"]
    final = main["final"]

    df = pd.DataFrame(rows)
    contributed = df["Cum_Contrib"].iloc[-1]
    years = (dates[-1] - dates[0]).days / 365.25
    cfs = [-MONTHLY_BUDGET] * len(dates)

    def metrics(name, twr_list, wts_list, twr_index, final_nav):
        ir = _annual_irr(cfs + [final_nav])
        return {
            "name": name,
            "final": round(final_nav),
            "profit": round(final_nav - contributed),
            "multiple": round(final_nav / contributed, 2),
            "twr_cagr": round(((twr_index[-1]) ** (1/years) - 1) * 100, 1) if twr_index else None,
            "irr_pct": round(ir * 100, 1) if ir == ir else None,
            "inv_sharpe": round(_sharpe(twr_list), 2),
            "contrib_sharpe": round(_sharpe(twr_list, wts_list), 2),
            "sortino": round(_sortino(twr_list), 2),
            "maxdd_pct": round(_maxdd(twr_index), 1) if twr_index else None,
            "win_rate": round(np.mean([1 if r > 0 else 0 for r in twr_list]) * 100) if twr_list else None,
            "best_mo": round(max(twr_list)*100,1) if twr_list else None,
            "worst_mo": round(min(twr_list)*100,1) if twr_list else None,
        }

    strat = metrics("Adaptive strategy", twr, wts, twr_idx, final)
    strat_cap = metrics("Adaptive + cash (25% cap)",
                        capped["twr"], capped["wts"], capped["twr_idx"], capped["final"])
    strat_cap_fi = metrics("Adaptive + 25% cap (fully invested)",
                           capped_fi["twr"], capped_fi["wts"], capped_fi["twr_idx"], capped_fi["final"])

    # ── Buy & Hold benchmarks for every ETF ──
    benchmarks, bench_curves = {}, {}
    for e in ETFS:
        prices = [float(m.loc[dt, e]) for dt in dates]
        navs, btwr, btwr_idx = bh_sim(prices, MONTHLY_BUDGET)
        benchmarks[e] = metrics(f"B&H {e}", btwr, navs[:-1], btwr_idx, navs[-1])
        bench_curves[e] = [round(v, 4) for v in ([1.0] + btwr_idx)]

    # growth-of-$1 time-weighted equity curves (start at 1.0)
    curve = {
        "dates": [d.strftime("%Y-%m") for d in dates],
        "strat": [round(v, 4) for v in ([1.0] + twr_idx)],
        "capped": [round(v, 4) for v in ([1.0] + capped["twr_idx"])],
        "capped_fi": [round(v, 4) for v in ([1.0] + capped_fi["twr_idx"])],
        **bench_curves,
    }

    # compact month-by-month table for the dashboard tab
    monthly = [{
        "d": r["Date"].strftime("%Y-%m") if hasattr(r["Date"], "strftime") else str(r["Date"])[:7],
        "reg": r["Regime"], "pt": r["ProfitTaking"], "c": r["Contribution"],
        "bq": r["Buy_QQQ"], "bt": r["Buy_TQQQ"], "bs": r["Buy_SMH"], "bx": r["Buy_SOXL"],
        "st": r["Sell_TQQQ"], "sx": r["Sell_SOXL"],
        "hq": r["Sh_QQQ"], "ht": r["Sh_TQQQ"], "hs": r["Sh_SMH"], "hx": r["Sh_SOXL"],
        "cash": r["Cash"], "nav": r["NAV"], "twr": r["Monthly_TWR_%"],
    } for r in rows]

    # regime distribution
    dist = df["Regime"].value_counts().to_dict()

    summary = {
        "start": str(dates[0].date()), "end": str(dates[-1].date()),
        "months": len(dates), "years": round(years, 1),
        "monthly_contribution": MONTHLY_BUDGET, "contributed": round(contributed),
        "growth_dollars": round(final - contributed),
        "growth_pct_of_final": round((final - contributed) / final * 100, 1),
        "strategy": strat, "strategy_capped": strat_cap, "strategy_capped_fi": strat_cap_fi,
        "bh": benchmarks["QQQ"], "benchmarks": benchmarks,
        "regime_distribution": {k: int(v) for k, v in dist.items()},
        "rf_annual": RF_ANNUAL,
        "curve": curve, "monthly": monthly,
        "alloc": {"dates": curve["dates"], **{e: alloc_hist[e] for e in ETFS}},
        "alloc_capped": {"dates": curve["dates"], **{e: capped["alloc_hist"][e] for e in ETFS},
                         "Cash": capped["alloc_hist"]["Cash"]},
        "alloc_capped_fi": {"dates": curve["dates"], **{e: capped_fi["alloc_hist"][e] for e in ETFS},
                            "Cash": capped_fi["alloc_hist"]["Cash"]},
    }

    _write_excel(df, summary)
    with open(JSON, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nContributed ${contributed:,.0f} over {years:.1f}y")
    print(f"{'':22s}{'NAV':>16s}{'mult':>8s}{'CAGR':>8s}{'invSh':>7s}{'maxDD':>8s}")
    def line(nm, d):
        print(f"{nm:22s}{('$'+format(d['final'],',')):>16s}{str(d['multiple'])+'x':>8s}"
              f"{str(d['twr_cagr'])+'%':>8s}{str(d['inv_sharpe']):>7s}{str(d['maxdd_pct'])+'%':>8s}")
    line("Adaptive strategy", strat)
    line("Adaptive +25% cap cash", strat_cap)
    line("Adaptive +25% cap FI", strat_cap_fi)
    for e in ETFS:
        line(f"B&H {e}", benchmarks[e])
    print(f"Wrote {XLSX} and {JSON}")
    return summary


def _write_excel(df, s):
    cols = [("Adaptive strategy", s["strategy"])] + [(f"B&H {e}", s["benchmarks"][e]) for e in ETFS]
    def mrow(label, key, fmt):
        return {"Metric": label, **{nm: fmt(d[key]) for nm, d in cols}}
    metric_rows = [
        mrow("Final NAV", "final", lambda v: f"${v:,}"),
        mrow("Total profit", "profit", lambda v: f"${v:,}"),
        mrow("Multiple on invested", "multiple", lambda v: f"{v}x"),
        mrow("Time-weighted CAGR", "twr_cagr", lambda v: f"{v}%/yr"),
        mrow("Money-weighted IRR", "irr_pct", lambda v: f"{v}%/yr"),
        mrow("Investment Sharpe (equal-wt)", "inv_sharpe", lambda v: f"{v}"),
        mrow("Contribution Sharpe (capital-wt)", "contrib_sharpe", lambda v: f"{v}"),
        mrow("Sortino", "sortino", lambda v: f"{v}"),
        mrow("Max drawdown (time-weighted)", "maxdd_pct", lambda v: f"{v}%"),
        mrow("Win rate (positive months)", "win_rate", lambda v: f"{v}%"),
        mrow("Best month", "best_mo", lambda v: f"{v}%"),
        mrow("Worst month", "worst_mo", lambda v: f"{v}%"),
    ]
    summ = pd.DataFrame(metric_rows, columns=["Metric"] + [nm for nm, _ in cols])
    hdr = pd.DataFrame([
        {"Metric": "Window", "Adaptive strategy": f"{s['start']} → {s['end']} ({s['years']} yrs, {s['months']} months)"},
        {"Metric": "Monthly contribution", "Adaptive strategy": f"${s['monthly_contribution']:,}"},
        {"Metric": "Total contributed", "Adaptive strategy": f"${s['contributed']:,}"},
        {"Metric": "", "Adaptive strategy": ""},
    ])
    summ = pd.concat([hdr, summ], ignore_index=True)
    dist = pd.DataFrame([(k, v) for k, v in s["regime_distribution"].items()],
                        columns=["Regime", "Months"])

    notes = pd.DataFrame({"Topic": [
        "Mode", "Contributions", "Allocation", "Euphoria", "Profit-taking",
        "Benchmark", "Investment Sharpe", "Contribution Sharpe", "TWR vs IRR",
        "Max drawdown", "Risk-free", "Transaction cost", "P/E signal",
    ], "Detail": [
        "APPLES-TO-APPLES: always fully invested — no cash, no profit-taking sells — so it is directly comparable to fully-invested Buy & Hold.",
        f"Flat ${MONTHLY_BUDGET:,}/month DCA, identical for strategy and every benchmark.",
        "Each month the full contribution buys the regime's target ETFs: bull/fear1/fear2 -> TQQQ+SOXL; chop -> QQQ+SMH.",
        "Euphoria deploys into the defensive unleveraged sleeve (QQQ+SMH) instead of holding cash — stays fully invested.",
        "Disabled in this comparison (the alert is still shown for context but triggers no sells).",
        "Buy & Hold = same $/month into 100% of one ETF, never sold.",
        "Annualized Sharpe of monthly time-weighted returns, EQUAL-weighted (pure strategy skill).",
        "Same monthly returns but CAPITAL-weighted by dollars deployed — the 'growth of the asset' view.",
        "TWR = cash-flow-neutral strategy return. IRR = money-weighted, reflects contribution timing.",
        "Computed on the time-weighted return index (contribution-neutral), so it's the true investment drawdown.",
        f"{RF_ANNUAL*100:.0f}% (cash earns 0 in this model). Sharpe = excess over this.",
        f"{TXN_COST*100:.1f}% per trade (slippage).",
        "QQQ P/E is unavailable historically, so the profit-taking monitor runs on its other 6 signals (incl. CAPE).",
    ]})

    out = XLSX
    try:
        open(out, "a").close()
    except PermissionError:
        out = XLSX.replace(".xlsx", "_new.xlsx")
        print(f"  ({XLSX} is open/locked — writing to {out} instead)")

    with pd.ExcelWriter(out, engine="openpyxl") as xl:
        df.to_excel(xl, sheet_name="Monthly", index=False)
        summ.to_excel(xl, sheet_name="Summary", index=False)
        dist.to_excel(xl, sheet_name="Summary", index=False, startrow=len(summ)+3)
        notes.to_excel(xl, sheet_name="Notes", index=False)
        wsm = xl.sheets["Monthly"]; wsm.freeze_panes = "B2"
        for col in wsm.columns:
            w = max(len(str(c.value)) if c.value is not None else 0 for c in col)
            wsm.column_dimensions[col[0].column_letter].width = min(max(w+1, 9), 16)
        wss = xl.sheets["Summary"]; wss.column_dimensions["A"].width = 34
        for col_letter in ("B", "C", "D", "E", "F"):
            wss.column_dimensions[col_letter].width = 18
        wsn = xl.sheets["Notes"]
        wsn.column_dimensions["A"].width = 22
        wsn.column_dimensions["B"].width = 95


if __name__ == "__main__":
    run()
