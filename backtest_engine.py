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


# ── strategy simulation ───────────────────────────────────────

def run():
    m = build_monthly()
    dates = m.index
    print(f"Backtest window: {dates[0].date()} -> {dates[-1].date()}  ({len(dates)} months)")

    shares = {e: 0.0 for e in ETFS}
    cost   = {e: 0.0 for e in ETFS}   # cumulative $ cost basis per ETF
    cash   = 0.0
    raw_hist = []
    rows = []
    prev_nav = None
    twr, wts, twr_idx = [], [], []
    idx = 1.0
    cashflows = []          # for IRR (contributions negative)

    # B&H benchmark (100% QQQ, same contributions)
    bh_sh = 0.0

    for i, dt in enumerate(dates):
        px = {e: float(m.loc[dt, e]) for e in ETFS}

        # 1) growth of existing holdings since last month (time-weighted return)
        if prev_nav is not None and prev_nav > 0:
            v_pre = sum(shares[e] * px[e] for e in ETFS) + cash
            tw = v_pre / prev_nav - 1
            twr.append(tw); wts.append(prev_nav); idx *= (1 + tw); twr_idx.append(idx)

        # 2) regime
        d = {"vix": float(m.loc[dt, "VIX"]),
             "above_200ma_pct": float(m.loc[dt, "above_200ma_pct"]),
             "rsi": float(m.loc[dt, "rsi"]),
             "return_12m_pct": float(m.loc[dt, "return_12m_pct"])}
        raw = classify_raw(d)
        regime = decide_regime(raw, raw_hist)
        raw_hist.append(raw)

        # 3) profit-taking (live evaluate; P/E unavailable historically -> None)
        tqqq_gain = ((px["TQQQ"]/(cost["TQQQ"]/shares["TQQQ"]))-1)*100 if shares["TQQQ"]>0 and cost["TQQQ"]>0 else None
        pt = evaluate({**d, "qqq_pe_fwd": None, "cape": (None if pd.isna(m.loc[dt,"cape"]) else float(m.loc[dt,"cape"])),
                       "tqqq_gain_pct": tqqq_gain})
        alert = pt["alert_level"]

        buys  = {e: 0.0 for e in ETFS}
        sells = {e: 0.0 for e in ETFS}

        # 3a) profit-taking trims -> cash (SOXL first, then TQQQ)
        trim = {"CAUTION": (0.20, 0.10), "EXTREME": (0.50, 0.50)}.get(alert)
        if trim:
            for etf, frac in (("SOXL", trim[0]), ("TQQQ", trim[1])):
                if shares[etf] > 0:
                    sh = shares[etf] * frac
                    proceeds = sh * px[etf] * (1 - TXN_COST)
                    shares[etf] -= sh
                    cost[etf]   *= (1 - frac)
                    cash += proceeds
                    sells[etf] += sh * px[etf]

        # 4) deploy this month's contribution per regime
        contrib = MONTHLY_BUDGET
        cashflows.append(-contrib)
        if regime == "euphoria":
            cash += contrib                       # pause -> reserve
        else:
            if regime == "fear2":
                deploy = contrib + cash; cash = 0.0   # spend the reserve in the crash
                alloc_key = "fear2_lev"
            else:
                deploy = contrib
                alloc_key = regime
            for etf, w in ALLOCATIONS[alloc_key].items():
                if w > 0:
                    dollars = deploy * w
                    sh = dollars * (1 - TXN_COST) / px[etf]
                    shares[etf] += sh
                    cost[etf]   += dollars
                    buys[etf]   += dollars

        # 5) record
        holdings_val = sum(shares[e] * px[e] for e in ETFS)
        nav = holdings_val + cash
        prev_nav = nav

        # B&H: contribution into QQQ
        bh_sh += contrib * (1 - TXN_COST) / px["QQQ"]
        bh_nav = bh_sh * px["QQQ"]

        rows.append({
            "Date": dt.date(), "Regime": regime, "ProfitTaking": alert,
            "Contribution": contrib,
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
            "TWR_Index": round(idx,3),
            "BH_NAV": round(bh_nav),
        })

    df = pd.DataFrame(rows)
    contributed = df["Cum_Contrib"].iloc[-1]
    final = df["NAV"].iloc[-1]
    bh_final = df["BH_NAV"].iloc[-1]
    years = (dates[-1] - dates[0]).days / 365.25

    # ── B&H time-weighted returns for its Sharpe ──
    bh_nav_series = df["BH_NAV"].values
    bh_contrib = MONTHLY_BUDGET
    bh_twr = []
    for i in range(1, len(bh_nav_series)):
        pre = bh_nav_series[i] - 0  # B&H grows then contributes; approximate growth
        # reconstruct: prev nav grew to (this nav - this contribution's shares value)
        bh_twr.append(bh_nav_series[i] / (bh_nav_series[i-1] + bh_contrib) - 1)

    def metrics(name, twr_list, wts_list, twr_index, final_nav, cfs):
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

    cfs = [-MONTHLY_BUDGET] * len(dates)
    strat = metrics("Adaptive strategy", twr, wts, twr_idx, final, cfs)

    # B&H twr index
    bh_idx, x = [], 1.0
    for r in bh_twr:
        x *= (1 + r); bh_idx.append(x)
    bh = metrics("Buy & Hold QQQ", bh_twr, bh_nav_series[:-1].tolist(), bh_idx, bh_final, cfs)

    # regime distribution
    dist = df["Regime"].value_counts().to_dict()

    summary = {
        "start": str(dates[0].date()), "end": str(dates[-1].date()),
        "months": len(dates), "years": round(years, 1),
        "monthly_contribution": MONTHLY_BUDGET, "contributed": round(contributed),
        "growth_dollars": round(final - contributed),
        "growth_pct_of_final": round((final - contributed) / final * 100, 1),
        "strategy": strat, "bh": bh,
        "regime_distribution": {k: int(v) for k, v in dist.items()},
        "rf_annual": RF_ANNUAL,
    }

    _write_excel(df, summary)
    with open(JSON, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nContributed ${contributed:,.0f} over {years:.1f}y")
    print(f"Strategy NAV ${strat['final']:,.0f}  ({strat['multiple']}x)  |  B&H QQQ ${bh['final']:,.0f}  ({bh['multiple']}x)")
    print(f"Investment Sharpe  strat {strat['inv_sharpe']}  vs B&H {bh['inv_sharpe']}")
    print(f"Contribution Sharpe strat {strat['contrib_sharpe']}  vs B&H {bh['contrib_sharpe']}")
    print(f"Max drawdown (TWR) strat {strat['maxdd_pct']}%  vs B&H {bh['maxdd_pct']}%")
    print(f"Wrote {XLSX} and {JSON}")
    return summary


def _write_excel(df, s):
    rows = [
        ("Window", f"{s['start']} → {s['end']} ({s['years']} yrs, {s['months']} months)"),
        ("Monthly contribution", f"${s['monthly_contribution']:,}"),
        ("Total contributed", f"${s['contributed']:,}"),
        ("", ""),
        ("METRIC", "ADAPTIVE STRATEGY  |  BUY & HOLD QQQ"),
        ("Final NAV", f"${s['strategy']['final']:,}   |   ${s['bh']['final']:,}"),
        ("Total profit (NAV − contributed)", f"${s['strategy']['profit']:,}   |   ${s['bh']['profit']:,}"),
        ("Multiple on invested", f"{s['strategy']['multiple']}x   |   {s['bh']['multiple']}x"),
        ("Time-weighted CAGR", f"{s['strategy']['twr_cagr']}%/yr   |   {s['bh']['twr_cagr']}%/yr"),
        ("Money-weighted IRR", f"{s['strategy']['irr_pct']}%/yr   |   {s['bh']['irr_pct']}%/yr"),
        ("Investment Sharpe (equal-wt)", f"{s['strategy']['inv_sharpe']}   |   {s['bh']['inv_sharpe']}"),
        ("Contribution Sharpe (capital-wt)", f"{s['strategy']['contrib_sharpe']}   |   {s['bh']['contrib_sharpe']}"),
        ("Sortino", f"{s['strategy']['sortino']}   |   {s['bh']['sortino']}"),
        ("Max drawdown (time-weighted)", f"{s['strategy']['maxdd_pct']}%   |   {s['bh']['maxdd_pct']}%"),
        ("Win rate (positive months)", f"{s['strategy']['win_rate']}%   |   {s['bh']['win_rate']}%"),
        ("Best / worst month", f"{s['strategy']['best_mo']}% / {s['strategy']['worst_mo']}%   |   {s['bh']['best_mo']}% / {s['bh']['worst_mo']}%"),
        ("", ""),
        ("Growth = $ from market", f"${s['growth_dollars']:,} ({s['growth_pct_of_final']}% of final NAV)"),
    ]
    summ = pd.DataFrame(rows, columns=["Metric", "Value"])
    dist = pd.DataFrame([(k, v) for k, v in s["regime_distribution"].items()],
                        columns=["Regime", "Months"])

    notes = pd.DataFrame({"Topic": [
        "Contributions", "Fear II reserve", "Euphoria", "Profit-taking",
        "Benchmark", "Investment Sharpe", "Contribution Sharpe", "TWR vs IRR",
        "Max drawdown", "Risk-free", "Transaction cost", "P/E signal",
    ], "Detail": [
        f"Flat ${MONTHLY_BUDGET:,}/month DCA, identical for strategy and benchmark.",
        "Cash saved in euphoria + profit-taking trims is deployed into TQQQ/SOXL during Fear II.",
        "Euphoria months route the contribution to cash (pause), not the market.",
        "Live evaluate(): CAUTION trims 20% SOXL + 10% TQQQ; EXTREME trims 50%/50%. Proceeds to cash.",
        "Buy & Hold = same $/month into 100% QQQ, never sold.",
        "Annualized Sharpe of monthly time-weighted returns, EQUAL-weighted (pure strategy skill).",
        "Same monthly returns but CAPITAL-weighted by dollars deployed — the 'growth of the asset' view.",
        "TWR = cash-flow-neutral strategy return. IRR = money-weighted, reflects contribution timing.",
        "Computed on the time-weighted return index (contribution-neutral), so it's the true investment drawdown.",
        f"{RF_ANNUAL*100:.0f}% (cash earns 0 in this model). Sharpe = excess over this.",
        f"{TXN_COST*100:.1f}% per trade (slippage).",
        "QQQ P/E is unavailable historically, so the profit-taking monitor runs on its other 6 signals (incl. CAPE).",
    ]})

    with pd.ExcelWriter(XLSX, engine="openpyxl") as xl:
        df.to_excel(xl, sheet_name="Monthly", index=False)
        summ.to_excel(xl, sheet_name="Summary", index=False)
        dist.to_excel(xl, sheet_name="Summary", index=False, startrow=len(summ)+3)
        notes.to_excel(xl, sheet_name="Notes", index=False)
        wsm = xl.sheets["Monthly"]; wsm.freeze_panes = "B2"
        for col in wsm.columns:
            w = max(len(str(c.value)) if c.value is not None else 0 for c in col)
            wsm.column_dimensions[col[0].column_letter].width = min(max(w+1, 9), 16)
        for nm in ("Summary", "Notes"):
            ws = xl.sheets[nm]
            ws.column_dimensions["A"].width = 34
            ws.column_dimensions["B"].width = 90


if __name__ == "__main__":
    run()
