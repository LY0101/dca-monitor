# ── USER SETTINGS — edit these before first run ──────────────

MONTHLY_BUDGET = 10_000   # USD, normal months
FEAR2_BUDGET   = 30_000   # USD, VIX > 45 only

# Your average cost per share — update after each purchase
COST_BASIS = {
    "QQQ":  0.00,   # ← enter your avg cost
    "TQQQ": 0.00,
    "SMH":  0.00,
    "SOXL": 0.00,
}

# Your shares owned — update after each purchase
HOLDINGS = {
    "QQQ":  0,
    "TQQQ": 0,
    "SMH":  0,
    "SOXL": 0,
}

# ── ALLOCATIONS — 50/50 across all regimes ───────────────────
#
#  Bull:   TQQQ 50% + SOXL 50%   (leveraged, trending up)
#  Chop:   QQQ  50% + SMH  50%   (unleveraged, sideways)
#  Fear I: TQQQ 50% + SOXL 50%   (leveraged, buy the panic)
#  Fear II Split A: TQQQ 50% + SOXL 50%  (max aggression, $30K)
#  Fear II Split B: QQQ  50% + SMH  50%  (balanced, $30K)

ALLOCATIONS = {
    "bull":       {"TQQQ": 0.50, "SOXL": 0.50, "QQQ": 0.00, "SMH": 0.00},
    "chop":       {"TQQQ": 0.00, "SOXL": 0.00, "QQQ": 0.50, "SMH": 0.50},
    "fear1":      {"TQQQ": 0.50, "SOXL": 0.50, "QQQ": 0.00, "SMH": 0.00},
    "fear2_lev":  {"TQQQ": 0.50, "SOXL": 0.50, "QQQ": 0.00, "SMH": 0.00},
    "fear2_bal":  {"TQQQ": 0.00, "SOXL": 0.00, "QQQ": 0.50, "SMH": 0.50},
}

# Fear II split: "lev" = TQQQ/SOXL, "bal" = QQQ/SMH
# Change this on the day VIX > 45 based on your conviction
FEAR2_SPLIT = "lev"

# ── REGIME THRESHOLDS — VIX is the hard boundary ─────────────

VIX_THRESHOLDS = {
    "bull_max":  20,   # VIX < 20  → bull
    "chop_max":  30,   # VIX 20–30 → chop
    "fear1_max": 45,   # VIX 30–45 → fear1
                       # VIX > 45  → fear2
}

# ── HYSTERESIS — confirmation months required ─────────────────

CONFIRM = {
    "to_fear2": 0,   # immediate — window closes fast
    "to_fear1": 1,
    "to_chop":  1,
    "to_bull":  2,   # slowest — prevents FOMO re-entry
}

# ── PROFIT-TAKING THRESHOLDS — (elevated, extreme, bubble) ───

PROFIT_THRESHOLDS = {
    "qqq_pe_fwd":      (38,  45,  52),   # Nasdaq-100 forward P/E
    "rsi_14":          (78,  83,  88),   # QQQ 14-day RSI
    "above_200ma_pct": (30,  40,  50),   # % QQQ above 200-day SMA
    "vix_low":         (13,  11,  10),   # inverted: LOW VIX = complacency
    "return_12m_pct":  (50,  65,  80),   # QQQ 12-month return %
    "tqqq_gain_pct":   (200, 400, 700),  # TQQQ unrealized gain from cost %
}

HISTORY_FILE = "history.csv"
