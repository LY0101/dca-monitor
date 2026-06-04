import re
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

    rsi = float(ta.rsi(qqq, length=35).iloc[-1])

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


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _valid_pe(v) -> bool:
    """Sanity-check a P/E value (must be a positive number between 10 and 500)."""
    try:
        return 10 < float(v) < 500
    except (TypeError, ValueError):
        return False


def _fetch_pe() -> float | None:
    """
    Fetch QQQ / Nasdaq-100 P/E ratio from multiple sources in priority order.

    1. yfinance  — forwardPE then trailingPE from Yahoo Finance (same data
                   provider we already use, zero extra dependencies)
    2. multpl.com — Nasdaq trailing P/E page with robust selector fallback
    3. macrotrends — embedded JSON in the page script tags
    """

    # ── Source 1: yfinance ────────────────────────────────────────────────
    try:
        info = yf.Ticker("QQQ").info
        for key in ("forwardPE", "trailingPE"):
            v = info.get(key)
            if _valid_pe(v):
                return round(float(v), 1)
    except Exception:
        pass

    # ── Source 2: multpl.com ──────────────────────────────────────────────
    try:
        r = requests.get(
            "https://www.multpl.com/nasdaq-pe-ratio",
            timeout=10,
            headers=_HEADERS,
        )
        soup = BeautifulSoup(r.text, "html.parser")
        # Try several selectors — site structure changes occasionally
        for tag, attrs in [
            ("div",  {"id": "current"}),
            ("span", {"id": "current"}),
            ("div",  {"id": "current-value"}),
            ("div",  {"class": "current"}),
        ]:
            el = soup.find(tag, attrs)
            if el:
                text = re.sub(r"[^\d.]", "", el.get_text().strip().split()[0])
                if text and _valid_pe(text):
                    return round(float(text), 1)
    except Exception:
        pass

    # ── Source 3: macrotrends ─────────────────────────────────────────────
    try:
        r = requests.get(
            "https://www.macrotrends.net/stocks/charts/QQQ/"
            "invesco-qqq-trust-series-1/pe-ratio",
            timeout=10,
            headers=_HEADERS,
        )
        # Current value is embedded in a <div class="current-value"> or
        # as the first entry in the data table
        soup = BeautifulSoup(r.text, "html.parser")
        el = soup.find("div", {"class": "current-value"})
        if el:
            text = re.sub(r"[^\d.]", "", el.get_text().strip())
            if text and _valid_pe(text):
                return round(float(text), 1)
        # Fallback: first data row in the table
        rows = soup.select("table.historical_data_table tr")
        for row in rows[1:3]:          # skip header, try first two rows
            cells = row.find_all("td")
            if len(cells) >= 2:
                text = re.sub(r"[^\d.]", "", cells[1].get_text().strip())
                if text and _valid_pe(text):
                    return round(float(text), 1)
    except Exception:
        pass

    return None   # will show as "N/A" in report — enter manually if needed
