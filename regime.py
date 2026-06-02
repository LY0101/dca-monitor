import csv, os
from datetime import date
from config import VIX_THRESHOLDS, CONFIRM, ALLOCATIONS, MONTHLY_BUDGET, FEAR2_BUDGET, FEAR2_SPLIT, HISTORY_FILE


def classify_raw(data: dict) -> str:
    """
    VIX is the hard boundary. Returns raw signal for this moment.
    Hysteresis is applied separately in decide_regime().
    """
    v = data["vix"]
    t = VIX_THRESHOLDS
    if   v > t["fear1_max"]: return "fear2"
    elif v > t["chop_max"]:  return "fear1"
    elif v > t["bull_max"]:  return "chop"
    else:                     return "bull"


def load_history() -> list[str]:
    """Load past raw_signal values from CSV, oldest first."""
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, newline="") as f:
        return [row["raw_signal"] for row in csv.DictReader(f)]


def decide_regime(raw: str, history: list[str]) -> str:
    """
    Apply hysteresis rules.

    Rules:
      fear2 → immediate (0 months)
      fear1 → 1 month confirmation
      chop  → 1 month from bull, 2 months from fear
      bull  → 2 months confirmation, cannot come directly from fear
      fear  → bull is BLOCKED (must pass through chop first)
    """
    if not history:
        return "chop"   # safe default on first run

    prev = history[-1]

    # Fear II: always immediate — window closes in days
    if raw == "fear2":
        return "fear2"

    # Fear I: hold for 1 month
    if raw == "fear1":
        return "fear1" if prev in ("fear1", "fear2") else prev

    # Chop: 1 month from bull; 2 months from fear
    if raw == "chop":
        if prev in ("fear1", "fear2"):
            # need 1 confirmed month already in chop or fear before switching
            if len(history) >= 2 and history[-2] in ("fear1", "fear2", "chop"):
                return "chop"
            return prev
        return "chop"   # fast switch from bull

    # Bull: 2 months; cannot jump from fear
    if raw == "bull":
        if prev in ("fear1", "fear2"):
            return "chop"   # block direct fear → bull
        if prev == "bull":
            return "bull"   # already there
        # need previous month also bull
        if len(history) >= 2 and history[-2] == "bull":
            return "bull"
        return "chop"       # only 1 month — keep waiting

    return "chop"


def get_allocation(regime: str) -> tuple[dict, int]:
    """
    Returns ({ETF: dollar_amount}, total_budget).
    Fear II uses 3× budget and the configured split.
    """
    if regime == "fear2":
        key    = f"fear2_{FEAR2_SPLIT}"
        budget = FEAR2_BUDGET
    else:
        key    = regime
        budget = MONTHLY_BUDGET

    alloc = {etf: round(w * budget, 2) for etf, w in ALLOCATIONS[key].items()}
    return alloc, budget


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
