"""
Historical weekly regime classification — longest available data.

Pulls the longest daily history yfinance offers for each instrument, computes
the SAME indicators the live framework uses (daily basis), samples them at each
week's close (Friday), classifies the regime each week, and writes an Excel file.

Output: historical_regime.xlsx
  Sheet "Weekly"   — full weekly time series (levels, VIX, indicators, regime)
  Sheet "Summary"  — regime distribution over the whole period and per decade
  Sheet "Notes"    — column definitions and methodology

Regime logic mirrors regime.py / config.py:
  VIX hard boundary:  >45 fear2 | 30-45 fear1 | 20-30 chop | <20 bull
  Euphoria overlay (only inside the bull VIX zone): 3 of 4 signals →
     VIX<15, QQQ >25% above 200d MA, RSI35 >72, 12M return >45%

Hysteresis is re-expressed in WEEKS (months x ~4.33):
  to bull            : 9 weeks (slow — avoid FOMO)
  to chop / fear1    : 4 weeks
  to fear2           : immediate
  euphoria           : fast caution flag — 1 week to raise, 2 weeks to lower
  fear -> bull/euphoria is blocked: reroute through chop first
"""

import re
import requests
import numpy as np
import pandas as pd
import yfinance as yf
import pandas_ta as ta
from bs4 import BeautifulSoup
from config import (EUPHORIA_THRESHOLDS as ET, EUPHORIA_SIGNALS_REQUIRED as EREQ,
                    PROFIT_THRESHOLDS, VALUATION_LABELS)

OUT = "historical_regime.xlsx"
_HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}


def fetch_cape_history() -> pd.Series:
    """Monthly Shiller CAPE history scraped from multpl.com (back to 1871)."""
    try:
        r = requests.get("https://www.multpl.com/shiller-pe/table/by-month",
                         timeout=20, headers=_HDR)
        soup = BeautifulSoup(r.text, "html.parser")
        recs = []
        for tr in soup.select("table#datatable tr")[1:]:
            c = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(c) >= 2:
                try:
                    recs.append((pd.to_datetime(c[0]),
                                 float(re.sub(r"[^0-9.]", "", c[1]))))
                except Exception:
                    pass
        s = pd.DataFrame(recs, columns=["Date", "CAPE"]).set_index("Date").sort_index()["CAPE"]
        print(f"  CAPE   {s.index[0].date()} -> {s.index[-1].date()}  ({len(s)} months)")
        return s
    except Exception as e:
        print(f"  CAPE   fetch failed ({e}) — column will be blank")
        return pd.Series(dtype="float64")


def _cape_score(v) -> int:
    if pd.isna(v):
        return 0
    t = PROFIT_THRESHOLDS["cape"]
    return 3 if v >= t[2] else 2 if v >= t[1] else 1 if v >= t[0] else 0

TICKERS = {
    "QQQ":  "QQQ",
    "TQQQ": "TQQQ",
    "SMH":  "SMH",
    "SOXL": "SOXL",
    "VIX":  "^VIX",
}


def _series(tkr: str) -> pd.Series:
    """Longest available daily adjusted close as a Series."""
    df = yf.download(tkr, period="max", auto_adjust=True, progress=False)
    if df is None or df.empty:
        return pd.Series(dtype="float64")
    s = df["Close"]
    if isinstance(s, pd.DataFrame):
        s = s.squeeze()
    return s.dropna()


def fetch_daily() -> pd.DataFrame:
    print("Downloading longest available history for each instrument...")
    data = {}
    for name, tkr in TICKERS.items():
        s = _series(tkr)
        if not s.empty:
            print(f"  {name:5s} {s.index[0].date()} -> {s.index[-1].date()}  ({len(s)} days)")
        else:
            print(f"  {name:5s} NO DATA")
        data[name] = s
    df = pd.DataFrame(data)
    return df


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """All indicators on the DAILY series (same definitions as the live tool)."""
    qqq = df["QQQ"].astype("float64")
    smh = df["SMH"].astype("float64")

    out = pd.DataFrame(index=df.index)
    out["QQQ"]  = df["QQQ"]
    out["TQQQ"] = df["TQQQ"]
    out["SMH"]  = df["SMH"]
    out["SOXL"] = df["SOXL"]
    out["VIX"]  = df["VIX"]

    sma200 = qqq.rolling(200).mean()
    high52 = qqq.rolling(252).max()
    out["QQQ_200d_SMA"]        = sma200
    out["QQQ_above_200ma_pct"] = (qqq - sma200) / sma200 * 100
    out["QQQ_drawdown_52w_pct"] = (qqq - high52) / high52 * 100
    out["RSI_35"]              = ta.rsi(qqq, length=35)

    macd = ta.macd(qqq, fast=12, slow=26, signal=9)
    if macd is not None and "MACD_12_26_9" in macd:
        out["MACD_bull"] = macd["MACD_12_26_9"] > macd["MACDs_12_26_9"]
    else:
        out["MACD_bull"] = np.nan

    qqq_20d = qqq / qqq.shift(21) - 1
    smh_20d = smh / smh.shift(21) - 1
    out["SMH_vs_QQQ_20d_RS_pct"] = (smh_20d - qqq_20d) * 100

    out["QQQ_return_12m_pct"] = (qqq / qqq.shift(252) - 1) * 100

    # 1-month (21d) annualized realized volatility + percentile vs full history
    for name, series in (("QQQ", qqq), ("SMH", smh)):
        ret = np.log(series / series.shift(1))
        rv  = ret.rolling(21).std() * np.sqrt(252) * 100
        out[f"{name}_rvol"] = rv
        out[f"{name}_rvol_pctile"] = rv.rank(pct=True) * 100  # percentile vs all history

    return out


# ── regime classification ────────────────────────────────────

def euphoria_signal_count(vix, above_pct, rsi, ret12m) -> int:
    if any(pd.isna(x) for x in (vix, above_pct, rsi, ret12m)):
        return 0
    return int(sum([vix < ET["vix_max"], above_pct > ET["above_200ma_min"],
                    rsi > ET["rsi_min"], ret12m > ET["ret_12m_min"]]))


def classify_raw(vix, above_pct, rsi, ret12m) -> str:
    if pd.isna(vix):
        return ""
    if   vix > 45: return "fear2"
    elif vix > 30: return "fear1"
    elif vix > 20: return "chop"
    else:
        if euphoria_signal_count(vix, above_pct, rsi, ret12m) >= EREQ:
            return "euphoria"
        return "bull"


REQUIRED_WEEKS = {"bull": 9, "chop": 4, "fear1": 4}  # fear2 immediate
EUPH_IN  = 1   # weeks of overheating to RAISE the euphoria caution flag (fast)
EUPH_OUT = 2   # weeks of non-euphoria before lowering it (stay cautious a bit)


def apply_weekly_hysteresis(raws: list[str]) -> list[str]:
    """
    Euphoria is a fast caution flag (like the fear side), not a slow trend
    confirmation (like bull). It raises quickly when overheating appears and
    lowers a few weeks after it fades, reverting to bull.
    """
    current = "chop"          # safe default at series start
    pend, cnt = None, 0
    out = []
    for raw in raws:
        if raw == "":
            out.append(current)
            continue

        if raw == "fear2":
            current, pend, cnt = "fear2", None, 0

        elif current == "euphoria":
            # fast exit after EUPH_OUT non-euphoria weeks
            if raw == "euphoria":
                pend, cnt = None, 0
            else:
                cnt = cnt + 1 if pend == "_exit" else 1
                pend = "_exit"
                if cnt >= EUPH_OUT:
                    current = raw           # bull/chop/fear1 as observed
                    pend, cnt = None, 0

        elif raw == "euphoria":
            # raise the flag quickly (only reachable from the bull VIX zone)
            cnt = cnt + 1 if pend == "euphoria" else 1
            pend = "euphoria"
            if cnt >= EUPH_IN:
                current, pend, cnt = "euphoria", None, 0

        elif raw == current:
            pend, cnt = None, 0

        else:
            # block fear -> aggressive: reroute through chop immediately
            if current in ("fear1", "fear2") and raw in ("bull", "euphoria"):
                current, pend, cnt = "chop", None, 0
            else:
                cnt = cnt + 1 if raw == pend else 1
                pend = raw
                if cnt >= REQUIRED_WEEKS.get(raw, 4):
                    current, pend, cnt = raw, None, 0
        out.append(current)
    return out


def main():
    daily = fetch_daily()
    ind = compute_indicators(daily)

    # weekly Friday snapshot of every column
    weekly = ind.resample("W-FRI").last()
    # need at least VIX + the core QQQ indicators present
    weekly = weekly.dropna(subset=["VIX", "QQQ", "QQQ_above_200ma_pct", "RSI_35", "QQQ_return_12m_pct"])

    # merge historical Shiller CAPE (monthly, forward-filled to weekly)
    cape = fetch_cape_history()
    weekly["CAPE"] = cape.reindex(weekly.index, method="ffill") if not cape.empty else np.nan

    # classify
    euph, raw = [], []
    for _, r in weekly.iterrows():
        euph.append(euphoria_signal_count(r["VIX"], r["QQQ_above_200ma_pct"], r["RSI_35"], r["QQQ_return_12m_pct"]))
        raw.append(classify_raw(r["VIX"], r["QQQ_above_200ma_pct"], r["RSI_35"], r["QQQ_return_12m_pct"]))
    weekly["euphoria_signals"] = euph
    weekly["raw_regime"] = raw
    weekly["regime_hysteresis"] = apply_weekly_hysteresis(raw)
    # valuation warning (CAPE-based historically; live version also uses QQQ P/E)
    weekly["valuation_warning"] = [VALUATION_LABELS[_cape_score(v)] for v in weekly["CAPE"]]

    # volatility x valuation quadrant
    def _vv(rvpct, cape):
        if pd.isna(rvpct) or pd.isna(cape):
            return ""
        sc = _cape_score(cape)
        hi, lo = rvpct >= 66, rvpct < 40
        exp, cheap = sc >= 2, sc == 0
        if hi and exp:    return "Bubble-bursting risk"
        if hi and cheap:  return "Stress + cheap (opportunity)"
        if lo and exp:    return "Complacency at extremes"
        if lo and cheap:  return "Calm & cheap"
        return "Mixed"
    weekly["vol_valuation"] = [_vv(rp, cp) for rp, cp in zip(weekly["QQQ_rvol_pctile"], weekly["CAPE"])]

    # tidy for output
    weekly = weekly.reset_index().rename(columns={"index": "Date", "Date": "Date"})
    weekly["Date"] = pd.to_datetime(weekly["Date"]).dt.date

    cols = ["Date", "QQQ", "TQQQ", "SMH", "SOXL", "VIX",
            "QQQ_200d_SMA", "QQQ_above_200ma_pct", "QQQ_drawdown_52w_pct",
            "RSI_35", "MACD_bull", "SMH_vs_QQQ_20d_RS_pct", "QQQ_return_12m_pct",
            "QQQ_rvol", "QQQ_rvol_pctile", "SMH_rvol", "SMH_rvol_pctile",
            "CAPE", "valuation_warning", "vol_valuation",
            "euphoria_signals", "raw_regime", "regime_hysteresis"]
    weekly = weekly[cols]

    # round numerics
    rnd = {"QQQ":2,"TQQQ":2,"SMH":2,"SOXL":2,"VIX":2,"QQQ_200d_SMA":2,
           "QQQ_above_200ma_pct":1,"QQQ_drawdown_52w_pct":1,"RSI_35":1,
           "SMH_vs_QQQ_20d_RS_pct":2,"QQQ_return_12m_pct":1,"CAPE":1,
           "QQQ_rvol":1,"QQQ_rvol_pctile":0,"SMH_rvol":1,"SMH_rvol_pctile":0}
    for c, n in rnd.items():
        weekly[c] = weekly[c].round(n)

    # ── summary sheet ──
    def dist(frame, col):
        vc = frame[col].value_counts()
        total = len(frame)
        order = ["euphoria","bull","chop","fear1","fear2"]
        rows = []
        for reg in order:
            c = int(vc.get(reg, 0))
            rows.append({"regime": reg, "weeks": c, "pct": round(c/total*100, 1) if total else 0})
        return pd.DataFrame(rows)

    summ_raw  = dist(weekly, "raw_regime").rename(columns={"weeks":"weeks_raw","pct":"pct_raw"})
    summ_hyst = dist(weekly, "regime_hysteresis").rename(columns={"weeks":"weeks_hyst","pct":"pct_hyst"})
    summary = summ_raw.merge(summ_hyst, on="regime")

    # per-decade distribution (hysteresis regime)
    wk = weekly.copy()
    wk["decade"] = (pd.to_datetime(wk["Date"]).dt.year // 10 * 10).astype(str) + "s"
    decade = (wk.groupby(["decade","regime_hysteresis"]).size()
                .unstack(fill_value=0))
    for reg in ["euphoria","bull","chop","fear1","fear2"]:
        if reg not in decade.columns:
            decade[reg] = 0
    decade = decade[["euphoria","bull","chop","fear1","fear2"]].reset_index()

    notes = pd.DataFrame({"Column / Topic": [
        "Date", "QQQ / TQQQ / SMH / SOXL", "VIX",
        "QQQ_200d_SMA", "QQQ_above_200ma_pct", "QQQ_drawdown_52w_pct",
        "RSI_35", "MACD_bull", "SMH_vs_QQQ_20d_RS_pct", "QQQ_return_12m_pct",
        "QQQ_rvol / SMH_rvol (+ _pctile)", "",
        "CAPE", "valuation_warning", "vol_valuation",
        "euphoria_signals", "raw_regime", "regime_hysteresis",
        "METHOD: indicators", "METHOD: VIX bands", "METHOD: euphoria",
        "METHOD: hysteresis", "DATA",
    ], "Definition": [
        "Friday weekly close (last trading day of the week).",
        "Weekly closing level, split-/dividend-adjusted. Blank before each fund's inception (TQQQ/SOXL 2010).",
        "CBOE Volatility Index weekly close — the hard regime boundary.",
        "200-DAY simple moving average of QQQ (computed on daily data).",
        "% QQQ sits above its 200-day SMA.",
        "% QQQ is below its trailing 52-week (252-day) high.",
        "35-day RSI of QQQ daily closes (slower than standard 14d).",
        "True when MACD line (12/26/9) is above its signal line.",
        "QQQ-relative 20-day return of SMH (semis leadership). Blank before SMH data.",
        "QQQ trailing 12-month (252-day) % return.",
        "1-month (21-day) annualized realized volatility of QQQ / SMH (std of daily log returns x sqrt(252)). *_pctile = where that reading ranks vs the ticker's full history (0-100).",
        "(see QQQ_rvol)",
        "Shiller CAPE (S&P 500 cyclically-adjusted P/E), monthly, forward-filled. The dot-com bubble gauge — peaked at 44 in Dec 1999.",
        "Valuation warning level from CAPE: Normal <28 | Elevated 28+ | Extreme 34+ | Bubble 40+. VIX-independent, so it catches the 2000 top the VIX regime missed.",
        "Volatility x valuation quadrant: high realized vol + expensive = bubble-bursting risk; high vol + cheap = opportunity; low vol + expensive = complacency; low vol + cheap = calm & cheap.",
        "How many of the 4 euphoria signals fire (VIX<16, >18% above 200MA, RSI35>70, 12M ret>30%).",
        "Instantaneous regime that week (VIX bands + euphoria overlay). No smoothing.",
        "Regime after weekly hysteresis smoothing — the one the framework would actually act on.",
        "All indicators computed on DAILY data (matching the live tool), then sampled at Friday close.",
        ">45 fear2 | 30-45 fear1 | 20-30 chop | <20 bull.",
        "Inside bull VIX zone, 3 of 4 signals -> euphoria (overheated, pause DCA).",
        "Months x ~4.33 weeks: euphoria/bull 9w, chop/fear1 4w, fear2 immediate; fear->bull rerouted via chop.",
        "Source: Yahoo Finance via yfinance, period='max'. Regime history limited by QQQ (1999) + VIX.",
    ]})

    out_path = OUT
    try:
        open(out_path, "a").close()
    except PermissionError:
        out_path = OUT.replace(".xlsx", "_new.xlsx")
        print(f"  ({OUT} is open/locked — writing to {out_path} instead)")

    with pd.ExcelWriter(out_path, engine="openpyxl") as xl:
        weekly.to_excel(xl, sheet_name="Weekly", index=False)
        summary.to_excel(xl, sheet_name="Summary", index=False, startrow=1)
        decade.to_excel(xl, sheet_name="Summary", index=False, startrow=len(summary)+5)
        notes.to_excel(xl, sheet_name="Notes", index=False)

        # light formatting: widths + freeze header
        wsW = xl.sheets["Weekly"]
        wsW.freeze_panes = "A2"
        for col_cells in wsW.columns:
            width = max(len(str(c.value)) if c.value is not None else 0 for c in col_cells)
            wsW.column_dimensions[col_cells[0].column_letter].width = min(max(width + 2, 10), 22)
        ws = xl.sheets["Summary"]
        ws["A1"] = "Regime distribution over full period (raw vs hysteresis)"
        ws[f"A{len(summary)+5}"] = "Weeks per regime by decade (hysteresis)"
        for col_cells in xl.sheets["Notes"].columns:
            xl.sheets["Notes"].column_dimensions[col_cells[0].column_letter].width = 95 if col_cells[0].column_letter == "B" else 26

    print(f"\nWrote {OUT}")
    print(f"  {len(weekly)} weekly rows: {weekly['Date'].iloc[0]} -> {weekly['Date'].iloc[-1]}")
    print("\nRegime distribution (hysteresis):")
    print(summary[["regime","weeks_hyst","pct_hyst"]].to_string(index=False))


if __name__ == "__main__":
    main()
