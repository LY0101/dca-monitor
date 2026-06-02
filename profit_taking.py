from config import PROFIT_THRESHOLDS, COST_BASIS
from data import PRICES_LIVE

ALERT_MAP = {
    0: "HOLD",
    1: "HOLD",
    2: "WATCH",
    3: "WATCH",
    4: "CAUTION",
    5: "CAUTION",
    6: "EXTREME",
}

ACTIONS = {
    "HOLD":    "No action. Continue DCA as normal.",
    "WATCH":   "Stop new SOXL DCA only. All other positions continue. Check weekly.",
    "CAUTION": "Trim 15–25% of SOXL first, then TQQQ proportionally. "
               "Confirm 3 consecutive weeks before executing. "
               "Proceeds → money market (Fear II reserve).",
    "EXTREME": "Trim 40–60% of all leveraged positions (SOXL then TQQQ). "
               "QQQ and SMH: hold. Dot-com-level readings. "
               "Proceeds → money market (Fear II reserve).",
}


def _score(key: str, value, inverted: bool = False) -> int:
    """0 = normal, 1 = elevated, 2 = extreme, 3 = bubble."""
    if value is None:
        return 0
    t = PROFIT_THRESHOLDS[key]
    if inverted:   # lower is worse (VIX complacency)
        if   value < t[2]: return 3
        elif value < t[1]: return 2
        elif value < t[0]: return 1
        return 0
    else:
        if   value >= t[2]: return 3
        elif value >= t[1]: return 2
        elif value >= t[0]: return 1
        return 0


def evaluate(data: dict) -> dict:
    """
    Score all 6 profit-taking indicators.
    Returns scores, firing count, alert level, and action string.
    """
    scores = {
        "qqq_pe_fwd":      _score("qqq_pe_fwd",      data.get("qqq_pe_fwd")),
        "rsi_14":          _score("rsi_14",           data["rsi"]),
        "above_200ma_pct": _score("above_200ma_pct",  data["above_200ma_pct"]),
        "vix_low":         _score("vix_low",          data["vix"],  inverted=True),
        "return_12m_pct":  _score("return_12m_pct",   data["return_12m_pct"]),
        "tqqq_gain_pct":   _score("tqqq_gain_pct",    data.get("tqqq_gain_pct")),
    }
    firing      = sum(1 for s in scores.values() if s >= 1)
    alert_level = ALERT_MAP.get(firing, "EXTREME")

    return {
        "scores":      scores,
        "firing":      firing,
        "alert_level": alert_level,
        "action":      ACTIONS[alert_level],
    }
