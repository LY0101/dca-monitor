import csv, os
from datetime import date
from config import (VIX_THRESHOLDS, CONFIRM, ALLOCATIONS, MONTHLY_BUDGET,
                    FEAR2_BUDGET, FEAR2_SPLIT, HISTORY_FILE,
                    EUPHORIA_THRESHOLDS, EUPHORIA_SIGNALS_REQUIRED)


def _euphoria_signals(data: dict) -> int:
    """Count how many of the 4 euphoria signals are currently firing."""
    t = EUPHORIA_THRESHOLDS
    return sum([
        data["vix"]             < t["vix_max"],
        data["above_200ma_pct"] > t["above_200ma_min"],
        data["rsi"]             > t["rsi_min"],
        data["return_12m_pct"]  > t["ret_12m_min"],
    ])


def classify_raw(data: dict) -> str:
    """
    Returns raw regime signal for this moment.
    VIX is the hard boundary for fear/chop.
    In the bull VIX zone, euphoria is checked as a multi-signal overlay.
    """
    v = data["vix"]
    t = VIX_THRESHOLDS
    if   v > t["fear1_max"]: return "fear2"
    elif v > t["chop_max"]:  return "fear1"
    elif v > t["bull_max"]:  return "chop"
    else:
        # Bull VIX zone — check for euphoria overlay
        if _euphoria_signals(data) >= EUPHORIA_SIGNALS_REQUIRED:
            return "euphoria"
        return "bull"


def load_history() -> list[str]:
    """Load past raw_signal values from CSV, oldest first."""
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, newline="") as f:
        return [row["raw_signal"] for row in csv.DictReader(f)]


def decide_regime(raw: str, history: list[str]) -> str:
    """
    Apply hysteresis rules.

    Spectrum (coolest → hottest):
      fear2 → fear1 → chop → bull → euphoria

    Rules:
      fear2    → immediate (0 months)
      fear1    → 1 month confirmation
      chop     → 1 month from bull/euphoria; 2 months from fear
      bull     → 2 months; cannot come directly from fear
      euphoria → fast caution flag (1 month); raised when overheated, not from fear
    """
    if not history:
        return "chop"   # safe default on first run

    prev = history[-1]

    # Fear II: always immediate — window closes in days
    if raw == "fear2":
        return "fear2"

    # Fear I: 1 month confirmation
    if raw == "fear1":
        return "fear1" if prev in ("fear1", "fear2") else prev

    # Chop: fast from bull/euphoria; 2 months from fear
    if raw == "chop":
        if prev in ("fear1", "fear2"):
            if len(history) >= 2 and history[-2] in ("fear1", "fear2", "chop"):
                return "chop"
            return prev
        return "chop"   # fast switch from bull or euphoria

    # Bull: 2 months; cannot jump from fear; can drop from euphoria in 1 month
    if raw == "bull":
        if prev in ("fear1", "fear2"):
            return "chop"           # block fear → bull
        if prev in ("bull", "euphoria"):
            return "bull"           # natural or cooling from euphoria
        if len(history) >= 2 and history[-2] in ("bull", "euphoria"):
            return "bull"
        return "chop"

    # Euphoria: FAST caution flag — raise as soon as overheating appears in the
    # bull/chop zone. Don't jump straight out of fear (let the trend normalize).
    if raw == "euphoria":
        if prev in ("euphoria", "bull", "chop"):
            return "euphoria"
        return prev                 # coming from fear — wait for normalization

    return "chop"


def get_allocation(regime: str) -> tuple[dict, int]:
    """
    Returns ({ETF: dollar_amount}, total_budget).
    Euphoria: $0 deploy — no new DCA.
    Fear II:  3× budget with configured split.
    """
    if regime == "euphoria":
        alloc  = {etf: 0 for etf in ALLOCATIONS["euphoria"]}
        return alloc, 0
    if regime == "fear2":
        key    = f"fear2_{FEAR2_SPLIT}"
        budget = FEAR2_BUDGET
    else:
        key    = regime
        budget = MONTHLY_BUDGET

    alloc = {etf: round(w * budget, 2) for etf, w in ALLOCATIONS[key].items()}
    return alloc, budget


def euphoria_signal_count(data: dict) -> int:
    """Expose signal count for display purposes."""
    return _euphoria_signals(data)


def save_month(data: dict, raw: str, regime: str, alloc: dict) -> None:
    """Append this month's decision to history.csv."""
    file_exists = os.path.exists(HISTORY_FILE)
    fields = [
        "date", "raw_signal", "regime", "vix", "rsi",
        "drawdown_pct", "above_200ma_pct",
        "alloc_QQQ", "alloc_TQQQ", "alloc_SMH", "alloc_SOXL",
    ]
    with open(HISTORY_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "date":            date.today().isoformat(),
            "raw_signal":      raw,
            "regime":          regime,
            "vix":             data["vix"],
            "rsi":             data["rsi"],
            "drawdown_pct":    data["drawdown_pct"],
            "above_200ma_pct": data["above_200ma_pct"],
            "alloc_QQQ":       alloc.get("QQQ", 0),
            "alloc_TQQQ":      alloc.get("TQQQ", 0),
            "alloc_SMH":       alloc.get("SMH", 0),
            "alloc_SOXL":      alloc.get("SOXL", 0),
        })
