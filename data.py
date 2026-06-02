import yfinance as yf
import pandas_ta as ta
import requests
from bs4 import BeautifulSoup
from config import COST_BASIS

PRICES_LIVE = {}   # populated on fetch, used across modules

def fetch_all() -> dict:
    """
    Fetch all live market data.
    Returns a single flat dict with every indicator needed.
    Raises on network failure — let main.py handle.
    """
    tickers = ["QQQ", "TQQQ", "SMH", "SOXL", "^VIX"]
    raw = {}
    for t in tickers:
        df = yf.download(t, period="15mo", auto_adjust=True,
                         progress=False)
        raw[t] = df["Close"].squeeze().dropna()

    qqq  = raw["QQQ"]
    smh  = raw["SMH"]
    tqqq = raw["TQQQ"]
    soxl = raw["SOXL"]
    vix  = raw["^VIX"]

    # ── prices ──
    qqq_price  = float(qqq.iloc[-1])
    smh_price  = float(smh.iloc[-1])
    tqqq_price = float(tqqq.iloc[-1])
    soxl_price = float(soxl.iloc[-1])
    vix_now    = float(vix.iloc[-1])

    # populate global for other modules
    global PRICES_LIVE
    PRICES_LIVE = {
        "QQQ": qqq_price, "TQQQ": tqqq_price,
        "SMH": smh_price, "SOXL": soxl_price,
    }

    # ── regime indicators ──
    sma200       = float(qqq.rolling(200).mean().iloc[-1])
    high_52w     = float(qqq.rolling(252).max().iloc[-1])
    drawdown_pct = (qqq_price - high_52w) / high_52w * 100
    above_200ma  = qqq_price > sma200
    above_200pct = (qqq_price - sma200) / sma200 * 100

    rsi = float(ta.rsi(qqq, length=14).iloc[-1])

    macd_df     = ta.macd(qqq, fast=12, slow=26, signal=9)
    macd_bull   = (float(macd_df["MACD_12_26_9"].iloc[-1]) >
                   float(macd_df["MACDs_12_26_9"].iloc[-1]))

    qqq_20d     = float(qqq.iloc[-1])  / float(qqq.iloc[-21])  - 1
    smh_20d     = float(smh.iloc[-1])  / float(smh.iloc[-21])  - 1
    smh_rs_gap  = (smh_20d - qqq_20d) * 100

    # ── profit-taking indicators ──
    ret_12m = (qqq_price / float(qqq.iloc[-253]) - 1) * 100

    tqqq_cost = COST_BASIS.get("TQQQ", 0)
    tqqq_gain = ((tqqq_price / tqqq_cost) - 1) * 100 if tqqq_cost > 0 else None

    # ── forward P/E (scraped) ──
    qqq_pe_fwd = _fetch_pe()

    return {
        # prices
        "qqq_price":       round(qqq_price, 2),
        "tqqq_price":      round(tqqq_price, 2),
        "smh_price":       round(smh_price, 2),
        "soxl_price":      round(soxl_price, 2),
        "vix":             round(vix_now, 2),
        # regime
        "sma200":          round(sma200, 2),
        "above_200ma":     above_200ma,
        "above_200ma_pct": round(above_200pct, 1),
        "drawdown_pct":    round(drawdown_pct, 1),
        "rsi":             round(rsi, 1),
        "macd_bull":       macd_bull,
        "smh_rs_gap":      round(smh_rs_gap, 2),
        # profit-taking
        "return_12m_pct":  round(ret_12m, 1),
        "qqq_pe_fwd":      qqq_pe_fwd,
        "tqqq_gain_pct":   round(tqqq_gain, 1) if tqqq_gain is not None else None,
    }


def _fetch_pe() -> float | None:
    """Scrape Nasdaq-100 forward P/E from multpl.com."""
    try:
        r = requests.get(
            "https://www.multpl.com/nasdaq-pe-ratio",
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        soup = BeautifulSoup(r.text, "html.parser")
        el = soup.find("div", {"id": "current"})
        if el:
            return float(el.text.strip().replace(",", ""))
    except Exception:
        pass
    return None   # will show as "manual input needed" in report
