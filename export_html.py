import json
from datetime import datetime
from config import COST_BASIS, HOLDINGS, MONTHLY_BUDGET, FEAR2_BUDGET, ALLOCATIONS, CONFIRM

# ── helpers ──────────────────────────────────────────────────

def _p(v, d=1):
    if v is None: return "N/A"
    return f"{'+'if v>=0 else''}{v:.{d}f}%"

def _bar(v, lo, hi):
    if v is None: return 0
    return round(min(100, max(0, (v - lo) / (hi - lo) * 100)), 1)

SCORE_BADGE = [
    "<span class='badge bg'>Normal</span>",
    "<span class='badge ba'>🟡 Elevated</span>",
    "<span class='badge br'>🔴 Extreme</span>",
    "<span class='badge bp'>🟣 Bubble</span>",
]
SCORE_COLOR  = ["var(--green)", "var(--amber)", "var(--red)", "var(--purple)"]
REGIME_COLOR = {"bull":"var(--green)","chop":"var(--amber)","fear1":"var(--red)","fear2":"var(--purple)"}
ALERT_CLASS  = {"HOLD":"hold","WATCH":"watch","CAUTION":"caution","EXTREME":"extreme"}
ALERT_COLOR  = {"HOLD":"var(--green)","WATCH":"var(--amber)","CAUTION":"var(--red)","EXTREME":"var(--purple)"}
ETF_COLOR    = {"TQQQ":"var(--amber)","SOXL":"var(--red)","QQQ":"var(--ink)","SMH":"var(--ink)"}


def _cond(signal, threshold, today_val, met, neutral=False):
    if neutral:
        color, icon = "var(--muted)", "·"
    else:
        color = "var(--green)" if met else "var(--red)"
        icon  = "✅" if met else "❌"
    return (f'<tr><td>{signal}</td>'
            f'<td class="r" style="color:var(--muted)">{threshold}</td>'
            f'<td class="r" style="color:{color}">{today_val} {icon}</td></tr>')


def _headline(regime, budget, raw):
    if regime == "bull":
        return f"Deploy ${budget:,} this month into TQQQ + SOXL"
    if regime == "chop" and raw == "bull":
        return f"Deploy ${budget:,} into QQQ + SMH — awaiting 2-month bull confirmation"
    if regime == "chop":
        return f"Deploy ${budget:,} into QQQ + SMH only — no new leveraged buys"
    if regime == "fear1":
        return f"Deploy ${budget:,} into TQQQ + SOXL at panic discount"
    if regime == "fear2":
        return f"⚡ Deploy ${budget:,} now — once-per-decade crash entry"
    return f"Deploy ${budget:,} this month"


def _desc(d, regime, raw, n):
    vix = d["vix"]
    if regime == "bull":
        return (f"VIX at {vix:.1f} is well below the 20 threshold. QQQ is "
                f"{d['above_200ma_pct']:+.1f}% above its 200-day moving average and RSI at "
                f"{d['rsi']:.1f} is in the healthy 45–75 range. Leverage is fully justified — "
                f"trending markets offset volatility decay costs. This is the core DCA environment "
                f"the framework is built for.")
    if regime == "chop" and raw == "bull":
        return (f"VIX at {vix:.1f} is signalling bull, but the system requires 2 consecutive "
                f"confirmed months before switching ({n} month{'s'if n!=1 else''} on record so far). "
                f"New DCA stays in QQQ/SMH to avoid leveraged decay in an unconfirmed trend. "
                f"Existing TQQQ and SOXL positions are held — not sold.")
    if regime == "chop":
        return (f"VIX at {vix:.1f} — sideways market conditions. 3× ETFs lose 15–30%/year from "
                f"volatility decay when markets aren't trending. New DCA is redirected to QQQ and SMH, "
                f"which carry zero structural drag. Existing leveraged positions are held — full "
                f"upside retained when the trend resumes.")
    if regime == "fear1":
        return (f"VIX at {vix:.1f} — market panic zone. TQQQ and SOXL are deeply discounted. "
                f"QQQ is {abs(d['drawdown_pct']):.1f}% below its 52-week high. Buying here means "
                f"the most shares per dollar of the entire bull-chop-fear cycle. The 20-year thesis "
                f"is unchanged — only the price changed.")
    if regime == "fear2":
        return (f"VIX at {vix:.1f} — systemic market panic. Deploy ${FEAR2_BUDGET:,} immediately. "
                f"COVID March 2020 peaked at VIX 82; GFC October 2008 peaked at VIX 89. These were "
                f"the single best DCA entries in any 20-year plan. Activate your pre-funded Fear II "
                f"reserve now.")
    return ""


def _sig_row(name, width, bar_color, val, badge_cls, badge_text):
    return f"""
      <div class="sig-row">
        <div class="sig-name">{name}</div>
        <div class="sig-bar-track"><div class="sig-bar-fill" style="width:{width}%;background:{bar_color}"></div></div>
        <div class="sig-val">{val}</div>
        <div class="sig-status"><span class="badge {badge_cls}">{badge_text}</span></div>
      </div>"""


def _pt_sig_row(name, desc, width, score, val, threshold):
    return f"""
      <div class="sig-row pt-sig-row">
        <div class="sig-name-block">
          <div class="sig-name">{name}</div>
          <div class="sig-desc">{desc}</div>
        </div>
        <div class="sig-bar-track" style="margin-top:6px"><div class="sig-bar-fill" style="width:{width}%;background:{SCORE_COLOR[score]}"></div></div>
        <div class="sig-val">{val}</div>
        <div class="sig-sub">{threshold}</div>
        <div class="sig-status">{SCORE_BADGE[score]}</div>
      </div>"""


def _alloc_bars(weights, budget_val):
    html = ""
    for etf, w in weights.items():
        ec  = ETF_COLOR.get(etf, "var(--ink)")
        amt = budget_val * w
        if w > 0:
            html += f"""
      <div class="alloc-bar-row">
        <div class="alloc-t" style="color:{ec}">{etf}</div>
        <div class="alloc-track"><div class="alloc-fill" style="width:{w*100:.0f}%;background:{ec}"></div></div>
        <div class="alloc-p">{w*100:.0f}%</div>
        <div class="alloc-d" style="color:{ec}">${amt:,.0f}</div>
      </div>"""
        else:
            html += f"""
      <div class="alloc-bar-row">
        <div class="alloc-t" style="color:var(--muted)">{etf}</div>
        <div class="alloc-track"></div>
        <div class="alloc-p" style="color:var(--muted)">0%</div>
        <div class="alloc-d" style="color:var(--muted)">—</div>
      </div>"""
    return html


# ── main ─────────────────────────────────────────────────────

def generate_html(d, regime, alloc, budget, pt, raw, history) -> str:
    now   = datetime.now().strftime("%Y-%m-%d %H:%M")
    today = datetime.now().strftime("%Y-%m-%d")

    vix     = d["vix"]
    rsi     = d["rsi"]
    above   = d["above_200ma"]
    abv_pct = d["above_200ma_pct"]
    dd      = d["drawdown_pct"]
    macd_b  = d["macd_bull"]
    smh_gap = d["smh_rs_gap"]
    ret12m  = d["return_12m_pct"]
    pe      = d.get("qqq_pe_fwd")
    tg      = d.get("tqqq_gain_pct")
    n_hist  = len(history)

    consec = 0
    for s in reversed(history):
        if s == raw: consec += 1
        else: break

    rc   = REGIME_COLOR[regime]
    rcls = regime
    ac   = ALERT_COLOR[pt["alert_level"]]
    acls = ALERT_CLASS[pt["alert_level"]]
    fire = pt["firing"]
    scores = pt["scores"]

    headline    = _headline(regime, budget, raw)
    description = _desc(d, regime, raw, n_hist)

    # ── recommendation ETF cards ──
    alloc_cards = ""
    for etf, amt in alloc.items():
        ec = ETF_COLOR.get(etf, "var(--ink)")
        if amt > 0:
            pct_s = f"{amt/budget*100:.0f}%"
            alloc_cards += f"""
      <div class="rec-etf">
        <div class="rec-etf-ticker" style="color:{ec}">{etf}</div>
        <div class="rec-etf-pct">{pct_s}</div>
        <div class="rec-etf-amt" style="color:{ec}">${amt:,.0f}</div>
      </div>"""
        else:
            alloc_cards += f"""
      <div class="rec-etf" style="opacity:0.28;">
        <div class="rec-etf-ticker">{etf}</div>
        <div class="rec-etf-pct">0%</div>
        <div class="rec-etf-amt">—</div>
      </div>"""

    # ── stat row ──
    vix_sub   = ("Bull zone · below 20" if vix<20 else
                 "Chop zone · 20–30"   if vix<30 else
                 "Fear I · 30–45"      if vix<45 else "Fear II · above 45")
    vix_sc    = ("var(--green)" if vix<20 else "var(--amber)" if vix<30
                 else "var(--red)" if vix<45 else "var(--purple)")
    ma_sub    = "Above 200-day MA" if above else "Below 200-day MA"
    ma_sc     = "var(--green)" if above else "var(--red)"
    rsi_sub   = ("Healthy range" if 45<=rsi<=75 else
                 "Oversold — below 45" if rsi<45 else "Overbought — above 75")
    rsi_sc    = "var(--green)" if 45<=rsi<=75 else "var(--amber)"
    consec_sc = "var(--green)" if consec >= 2 else "var(--amber)"
    consec_s  = f"{consec} month{'s'if consec!=1 else''}"

    # ── price table rows ──
    prices_map = {"QQQ":d["qqq_price"],"TQQQ":d["tqqq_price"],
                  "SMH":d["smh_price"],"SOXL":d["soxl_price"]}
    subtitles  = {"QQQ":"Nasdaq-100 · 1×","TQQQ":"3× Nasdaq · Leveraged",
                  "SMH":"Semiconductor · 1×","SOXL":"3× Semiconductor · Leveraged"}
    price_rows = ""
    for etf, price in prices_map.items():
        cost    = COST_BASIS.get(etf, 0)
        shares  = HOLDINGS.get(etf, 0)
        gain    = ((price/cost)-1)*100 if cost>0 else None
        val     = shares*price if shares>0 else None
        gc      = "var(--green)" if (gain or 0)>=0 else "var(--red)"
        gain_s  = _p(gain) if gain is not None else "—"
        val_s   = f"${val:,.0f}" if val else "—"
        cost_s  = f"${cost:,.2f}" if cost>0 else "—"
        shares_s = f"{shares:,}" if shares>0 else "—"
        price_rows += f"""
        <tr>
          <td><div class="t-name">{etf}</div><div class="t-sub">{subtitles[etf]}</div></td>
          <td class="r">${price:,.2f}</td>
          <td class="r" id="d-{etf.lower()}-cost">{cost_s}</td>
          <td class="r" style="color:{gc}" id="d-{etf.lower()}-gain">{gain_s}</td>
          <td class="r" id="d-{etf.lower()}-shares">{shares_s}</td>
          <td class="r" id="d-{etf.lower()}-val">{val_s}</td>
        </tr>"""

    # ── regime indicator rows ──
    vix_w  = _bar(vix, 0, 65)
    vix_bc = ("var(--green)" if vix<20 else "var(--amber)" if vix<30
              else "var(--red)" if vix<45 else "var(--purple)")
    vix_bx = ("bg" if vix<20 else "ba" if vix<30 else "br" if vix<45 else "bp")
    vix_bt = ("✅ Bull zone" if vix<20 else "🟡 Chop zone" if vix<30
              else "🔴 Fear I" if vix<45 else "🟣 Fear II")

    ma_val = f"{'Above'if above else'Below'} ({_p(abv_pct)})"

    regime_sigs = (
        _sig_row("VIX Level",              _bar(vix,0,65),        vix_bc,              f"{vix:.1f}",  vix_bx, vix_bt) +
        _sig_row("QQQ vs 200-day MA",      _bar(abv_pct,-20,60),  "var(--green)"if above else"var(--red)",   ma_val,       "bg"if above else"br", "✅ Above"if above else"❌ Below") +
        _sig_row("Drawdown from 52W high", _bar(abs(dd),0,50),    "var(--green)"if dd>-10 else"var(--amber)", _p(dd),       "bg"if dd>-10 else"ba", "✅ Near high"if dd>-10 else"⚠️ In drawdown") +
        _sig_row("RSI 35-day (QQQ)",       rsi,                   "var(--green)"if 45<=rsi<=75 else"var(--amber)", f"{rsi:.1f}", "bg"if 45<=rsi<=75 else"ba", "✅ Healthy"if 45<=rsi<=75 else"⚠️ Out of range") +
        _sig_row("MACD Signal",            75 if macd_b else 25,  "var(--green)"if macd_b else"var(--red)",  "Bullish"if macd_b else"Bearish", "bg"if macd_b else"br", "✅ Bullish"if macd_b else"❌ Bearish") +
        _sig_row("SMH vs QQQ (20-day RS)", _bar(smh_gap,-15,15),  "var(--green)"if smh_gap>-3 else"var(--amber)", _p(smh_gap), "bg"if smh_gap>-3 else"ba", "✅ Leading"if smh_gap>-3 else"⚠️ Lagging")
    )

    # regime summary callout
    if raw == regime:
        reg_summary = f"VIX {vix:.1f} → <strong>{regime.upper()}</strong> confirmed · {consec} month{'s'if consec!=1 else''} on record."
    elif raw == "bull" and regime == "chop":
        reg_summary = (f"VIX {vix:.1f} signals <strong>BULL</strong> — staying <strong>CHOP</strong> "
                       f"until 2 consecutive bull months confirmed ({consec} month{'s'if consec!=1 else''} so far).")
    elif raw == "fear2":
        reg_summary = f"VIX {vix:.1f} → <strong>FEAR II</strong> — deploy immediately, no confirmation needed."
    else:
        reg_summary = (f"VIX {vix:.1f} · raw signal: <strong>{raw.upper()}</strong> · "
                       f"confirmed regime: <strong>{regime.upper()}</strong> (hysteresis active).")

    # ── profit-taking signal rows ──
    pe_v   = f"{pe}×" if pe else "N/A"
    tg_v   = _p(tg) if tg else "No cost basis set"

    pt_sigs = (
        _pt_sig_row("QQQ P/E (trailing)",
                    "QQQ's trailing 12-month price-to-earnings ratio, sourced from Yahoo Finance. "
                    "Reflects the weighted P/E of all 100 Nasdaq-100 holdings. "
                    "Elevated readings mean the market is priced for perfection — any earnings miss hits hard. "
                    "Dot-com peak (2000): 54×. Note: thresholds were calibrated for forward P/E; use this as a directional signal.",
                    _bar(pe,15,60)if pe else 0, scores["qqq_pe_fwd"], pe_v, "38× · 45× · 52×") +
        _pt_sig_row("RSI 35-day (QQQ)",
                    "QQQ's Relative Strength Index calculated on 35 trading days of daily closing prices. "
                    "RSI measures how fast and how much QQQ has risen vs fallen recently, on a 0–100 scale. "
                    "A 35-day window is deliberately slower than the standard 14-day — it filters out short-term noise "
                    "and better suits monthly DCA decisions. "
                    "Above 78: QQQ has been gaining unusually fast for an extended period — momentum is likely stretched.",
                    _bar(rsi,40,100), scores["rsi_35"], f"{rsi:.1f}", "78 · 83 · 88") +
        _pt_sig_row("Distance above 200-day MA",
                    "How far QQQ's current price sits above its 200-day simple moving average of daily closes. "
                    "The 200MA is the most-watched long-term trend line. When QQQ runs 30%+ above it, "
                    "the market is historically extended — sharp pullbacks become more likely even without a trend reversal. "
                    "Historically, readings above 40% have preceded corrections of 15–25%.",
                    _bar(abv_pct,0,60), scores["above_200ma_pct"], _p(abv_pct), "30% · 40% · 50%") +
        _pt_sig_row("VIX Complacency (inverted signal)",
                    "The CBOE VIX measures the market's expected 30-day S&P 500 volatility, derived from options prices. "
                    "This indicator is INVERTED — a lower VIX is more dangerous here. "
                    "When VIX drops below 13, traders are paying almost nothing for downside protection, "
                    "signalling extreme complacency. Historically, VIX below 10–12 has preceded significant corrections. "
                    "Normal bull market VIX range: 13–20.",
                    _bar(20-vix,0,15)if vix<20 else 0, scores["vix_low"], f"{vix:.1f}", "below 13 · 11 · 10") +
        _pt_sig_row("12-month QQQ return",
                    "QQQ's total price return over the past 252 trading days (~1 calendar year), using daily closes. "
                    "A 50%+ one-year gain puts QQQ in historically stretched territory — "
                    "forward returns over the following 12 months are significantly below average when this fires. "
                    "This is not a timing signal — it measures whether recent gains have been unusually large "
                    "and whether a cooling-off period is statistically overdue.",
                    _bar(ret12m,-10,100), scores["return_12m_pct"], _p(ret12m), "50% · 65% · 80%") +
        _pt_sig_row("TQQQ gain vs your cost basis",
                    "Your personal unrealized gain on TQQQ: (current price ÷ your avg cost basis − 1). "
                    "Set your cost basis in config.py — this signal does nothing until you do. "
                    "When TQQQ has tripled from your purchase price (+200%), trimming a portion locks in "
                    "real gains before a mean-reversion can erase them. "
                    "This is the only indicator personal to your portfolio — the other 5 are market-wide signals.",
                    _bar(tg,0,800)if tg else 0, scores["tqqq_gain_pct"], tg_v, "200% · 400% · 700%")
    )

    # ── VIX regime map ──
    vix_map_pct = round(min(vix, 65) / 65 * 100, 1)

    pt_eyebrow_map = {
        "HOLD":    f"✅ Hold · {fire} of 6 signals elevated",
        "WATCH":   f"🟡 Watch · {fire} of 6 signals elevated",
        "CAUTION": f"🔴 Caution · {fire} of 6 signals firing",
        "EXTREME": f"🟣 Extreme · {fire} of 6 — act immediately",
    }
    pt_headline_map = {
        "HOLD":    "No selling — continue DCA as normal",
        "WATCH":   "Pause new SOXL DCA only — all other positions continue",
        "CAUTION": "Trim 15–25% of SOXL first, then TQQQ proportionally",
        "EXTREME": "Trim 40–60% of all leveraged positions — SOXL then TQQQ",
    }
    pt_eyebrow  = pt_eyebrow_map[pt["alert_level"]]
    pt_hl       = pt_headline_map[pt["alert_level"]]

    # ── regime tab entry conditions ──
    bull_conds = (
        _cond("VIX",                "Below 20",             f"{vix:.1f}",          vix<20) +
        _cond("QQQ vs 200MA",       "Above MA",             f"{'Above'if above else'Below'} ({_p(abv_pct)})", above) +
        _cond("RSI 35-day",         "45 – 75",              f"{rsi:.1f}",          45<=rsi<=75) +
        _cond("MACD",               "Line above signal",    "Bullish"if macd_b else"Bearish", macd_b) +
        _cond("SMH vs QQQ (20d RS)","Above −3%",            _p(smh_gap),           smh_gap>-3) +
        _cond("Confirmation needed","2 consecutive months", f"{consec} month{'s'if consec!=1 else''}", consec>=2)
    )
    chop_conds = (
        _cond("VIX",                "20 – 30",              f"{vix:.1f}",          20<=vix<30) +
        _cond("Switch from Bull",   "1 month",              "1-month confirmation",True, neutral=True) +
        _cond("Switch from Fear",   "2 months",             "2-month confirmation",True, neutral=True) +
        _cond("New DCA",            "QQQ + SMH only",       "No new leveraged buys",True,neutral=True)
    )
    fear1_conds = (
        _cond("VIX",                "30 – 45",              f"{vix:.1f}",          30<=vix<45) +
        _cond("QQQ vs 200MA",       "Below (expected)",     f"{'Above'if above else'Below'}",  not above) +
        _cond("Drawdown from high", "15 – 35%",             _p(dd),                -35<=dd<=-15) +
        _cond("RSI 35-day",         "Oversold (25–45)",     f"{rsi:.1f}",          rsi<45) +
        _cond("Confirmation",       "1 month",              f"{consec} month{'s'if consec!=1 else''}", consec>=1)
    )
    fear2_conds = (
        _cond("VIX",                "Above 45",             f"{vix:.1f}",          vix>45) +
        _cond("Budget",             f"${FEAR2_BUDGET:,} (3×)","Pre-funded reserve", True, neutral=True) +
        _cond("Confirmation",       "None — immediate",     "Deploy same day",     True, neutral=True)
    )

    # ── allocation bars for regime tab ──
    bull_bars  = _alloc_bars(ALLOCATIONS["bull"],      MONTHLY_BUDGET)
    chop_bars  = _alloc_bars(ALLOCATIONS["chop"],      MONTHLY_BUDGET)
    fear1_bars = _alloc_bars(ALLOCATIONS["fear1"],     MONTHLY_BUDGET)
    fear2_bars = _alloc_bars(ALLOCATIONS["fear2_lev"], FEAR2_BUDGET)

    def ra(r): return " active" if regime==r else ""  # regime tab active

    # ── JS data ──
    prices_js    = json.dumps({"QQQ":d["qqq_price"],"TQQQ":d["tqqq_price"],
                               "SMH":d["smh_price"],"SOXL":d["soxl_price"]})
    config_pf_js = json.dumps({
        "qqq": {"shares":HOLDINGS["QQQ"], "cost":COST_BASIS["QQQ"]},
        "tqqq":{"shares":HOLDINGS["TQQQ"],"cost":COST_BASIS["TQQQ"]},
        "smh": {"shares":HOLDINGS["SMH"], "cost":COST_BASIS["SMH"]},
        "soxl":{"shares":HOLDINGS["SOXL"],"cost":COST_BASIS["SOXL"]},
    })
    alloc_js = json.dumps({
        "bull": ALLOCATIONS["bull"], "chop": ALLOCATIONS["chop"],
        "fear1":ALLOCATIONS["fear1"],"fear2":ALLOCATIONS["fear2_lev"],
    })

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DCA Monitor · {today}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;700&family=Syne:wght@700;800&display=swap" rel="stylesheet">
<style>
:root {{
  --bg:#f4f6f8; --card:#ffffff; --s1:#f1f3f5; --s2:#e8ebed;
  --border:#e2e5e9; --border2:#cdd2d8;
  --ink:#111827; --muted:#6b7280; --light:#9ca3af;
  --green:#059669; --green-bg:#ecfdf5; --green-border:#6ee7b7;
  --amber:#d97706; --amber-bg:#fffbeb; --amber-border:#fcd34d;
  --red:#dc2626;   --red-bg:#fff1f2;   --red-border:#fca5a5;
  --purple:#7c3aed;--purple-bg:#f5f3ff;--purple-border:#c4b5fd;
  --shadow-xs:0 1px 2px rgba(0,0,0,.04);
  --shadow-sm:0 1px 3px rgba(0,0,0,.07),0 1px 2px rgba(0,0,0,.04);
  --shadow:0 4px 6px -1px rgba(0,0,0,.07),0 2px 4px -2px rgba(0,0,0,.04);
  --radius:10px;
}}
*{{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}}
html{{scroll-behavior:smooth}}
body{{
  font-family:'Inter',system-ui,-apple-system,sans-serif;
  background:var(--bg);color:var(--ink);
  font-size:13px;line-height:1.6;
  -webkit-font-smoothing:antialiased;
}}

/* ── TOP BAR ── */
.topbar{{
  background:rgba(255,255,255,.92);
  border-bottom:1px solid var(--border);
  padding:0 20px;height:52px;
  display:flex;align-items:center;justify-content:space-between;
  position:sticky;top:0;z-index:100;
  backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);
}}
.topbar-logo{{font-family:'Syne',sans-serif;font-size:16px;font-weight:800;letter-spacing:-.5px}}
.topbar-logo span{{color:var(--green)}}
.topbar-right{{display:flex;align-items:center;gap:12px}}
.live-dot{{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--muted)}}
.dot{{width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 0 2.5px rgba(5,150,105,.18)}}
.topbar-date{{font-size:11px;color:var(--muted);font-family:'IBM Plex Mono',monospace}}

/* ── REFRESH BUTTON ── */
.refresh-btn{{
  display:flex;align-items:center;gap:5px;
  font-size:11px;font-weight:600;font-family:'IBM Plex Mono',monospace;
  color:var(--muted);background:var(--card);
  border:1px solid var(--border);border-radius:8px;
  padding:5px 11px;cursor:pointer;transition:all .15s ease;
  box-shadow:var(--shadow-xs);
}}
.refresh-btn:hover{{color:var(--ink);border-color:var(--border2);box-shadow:var(--shadow-sm)}}
.refresh-btn svg{{transition:transform .5s cubic-bezier(.4,0,.2,1)}}
.refresh-btn.spinning svg{{transform:rotate(360deg)}}

/* ── DESKTOP NAV ── */
.nav{{
  background:rgba(255,255,255,.92);border-bottom:1px solid var(--border);
  display:flex;overflow-x:auto;scrollbar-width:none;padding:0 20px;
  backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);
}}
.nav::-webkit-scrollbar{{display:none}}
.ntab{{
  padding:13px 0;margin-right:24px;font-size:12px;font-weight:500;
  border:none;background:transparent;color:var(--muted);cursor:pointer;
  border-bottom:2px solid transparent;margin-bottom:-1px;white-space:nowrap;
  transition:color .15s ease;flex-shrink:0;
}}
.ntab:hover{{color:var(--ink)}}
.ntab.active{{color:var(--ink);border-bottom-color:var(--green)}}

/* ── LAYOUT ── */
.page{{max-width:1040px;margin:0 auto;padding:24px 20px 90px}}
.panel{{display:none}}
.panel.active{{display:block;animation:fadein .2s cubic-bezier(.4,0,.2,1) both}}
@keyframes fadein{{from{{opacity:0;transform:translateY(5px)}}to{{opacity:1;transform:none}}}}

/* ── SECTION TITLES ── */
.sec-title{{
  font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;
  color:var(--muted);margin-bottom:12px;
  display:flex;align-items:center;gap:10px;
}}
.sec-title::after{{content:'';flex:1;height:1px;background:var(--border)}}

/* ── CARDS ── */
.card{{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:18px;box-shadow:var(--shadow-xs)}}

/* ── GRIDS ── */
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
.grid3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}}

/* ── RECOMMENDATION BOX ── */
.rec-box{{border-radius:var(--radius);border:1.5px solid;padding:22px 24px;margin-bottom:22px}}
.rec-box.bull {{border-color:var(--green-border);background:var(--green-bg)}}
.rec-box.chop {{border-color:var(--amber-border);background:var(--amber-bg)}}
.rec-box.fear1{{border-color:var(--red-border);  background:var(--red-bg)}}
.rec-box.fear2{{border-color:var(--purple-border);background:var(--purple-bg)}}
.rec-eyebrow{{font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:8px;font-family:'IBM Plex Mono',monospace}}
.rec-headline{{font-family:'Syne',sans-serif;font-size:22px;font-weight:800;letter-spacing:-.5px;line-height:1.2;margin-bottom:10px}}
.rec-desc{{font-size:12.5px;line-height:1.85;color:var(--muted);max-width:680px}}
.rec-alloc{{display:flex;gap:10px;margin-top:18px;flex-wrap:wrap}}
.rec-etf{{
  display:flex;flex-direction:column;align-items:center;
  min-width:74px;padding:12px 14px;
  background:rgba(255,255,255,.75);border-radius:8px;
  border:1px solid rgba(0,0,0,.07);backdrop-filter:blur(4px);
}}
.rec-etf-ticker{{font-size:13px;font-weight:700;font-family:'IBM Plex Mono',monospace}}
.rec-etf-pct{{font-size:10px;color:var(--muted);margin-top:2px}}
.rec-etf-amt{{font-size:14px;font-weight:700;margin-top:4px;font-family:'IBM Plex Mono',monospace}}

/* ── ALERT BANNER ── */
.alert-banner{{border-radius:var(--radius);border:1.5px solid;padding:18px 20px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center}}
.alert-banner.hold   {{border-color:var(--green-border);background:var(--green-bg)}}
.alert-banner.watch  {{border-color:var(--amber-border);background:var(--amber-bg)}}
.alert-banner.caution{{border-color:var(--red-border);  background:var(--red-bg)}}
.alert-banner.extreme{{border-color:var(--purple-border);background:var(--purple-bg)}}

/* ── STAT ROW ── */
.stat-row{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:22px}}
.stat-cell{{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:16px;box-shadow:var(--shadow-xs);transition:box-shadow .15s ease}}
.stat-cell:hover{{box-shadow:var(--shadow-sm)}}
.stat-label{{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:6px}}
.stat-val{{font-size:24px;font-weight:700;font-family:'Syne',sans-serif;line-height:1}}
.stat-sub{{font-size:10px;color:var(--muted);margin-top:4px}}

/* ── TABLES ── */
.tbl{{width:100%;border-collapse:collapse;font-size:12px}}
.tbl th{{text-align:left;padding:9px 12px;font-size:10px;font-weight:600;letter-spacing:.8px;text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--border)}}
.tbl th.r{{text-align:right}}
.tbl td{{padding:11px 12px;border-bottom:1px solid var(--s1);vertical-align:middle}}
.tbl td.r{{text-align:right;font-family:'IBM Plex Mono',monospace}}
.tbl tr:last-child td{{border-bottom:none}}
.tbl tr:hover td{{background:var(--s1);transition:background .1s ease}}
.t-name{{font-weight:600}}
.t-sub{{font-size:10px;color:var(--muted);margin-top:1px}}

/* ── BADGES ── */
.badge{{
  display:inline-block;font-size:9px;font-weight:700;
  padding:3px 9px;border-radius:100px;
  letter-spacing:.4px;text-transform:uppercase;
  font-family:'IBM Plex Mono',monospace;
}}
.bg{{background:var(--green-bg); color:var(--green); border:1px solid var(--green-border)}}
.ba{{background:var(--amber-bg); color:var(--amber); border:1px solid var(--amber-border)}}
.br{{background:var(--red-bg);   color:var(--red);   border:1px solid var(--red-border)}}
.bp{{background:var(--purple-bg);color:var(--purple);border:1px solid var(--purple-border)}}
.bm{{background:var(--s1);       color:var(--muted); border:1px solid var(--border)}}

/* ── SIGNAL ROWS ── */
.sig-list{{display:flex;flex-direction:column}}
.sig-row{{display:grid;grid-template-columns:190px 1fr 90px 110px 90px;gap:10px;align-items:center;padding:11px 0;border-bottom:1px solid var(--s1)}}
.sig-row:last-child{{border-bottom:none}}
.sig-name{{font-size:12px;font-weight:500}}
.sig-bar-track{{height:5px;background:var(--s2);border-radius:100px;overflow:hidden}}
.sig-bar-fill{{height:100%;border-radius:100px;animation:fillBar .9s cubic-bezier(.4,0,.2,1) both}}
@keyframes fillBar{{from{{width:0!important}}}}
.sig-val{{font-size:12px;text-align:right;font-weight:600;font-family:'IBM Plex Mono',monospace}}
.sig-sub{{font-size:10px;color:var(--muted);text-align:right;font-family:'IBM Plex Mono',monospace}}
.sig-status{{text-align:right}}
.sig-name-block{{display:flex;flex-direction:column;gap:3px}}
.sig-desc{{font-size:11px;color:var(--muted);line-height:1.5}}
.pt-sig-row{{grid-template-columns:210px 1fr 80px 130px 90px;align-items:start;padding:14px 0}}

/* ── ALLOCATION BARS ── */
.alloc-bar-row{{display:flex;align-items:center;gap:12px;padding:9px 0;border-bottom:1px solid var(--s1)}}
.alloc-bar-row:last-child{{border-bottom:none}}
.alloc-t{{font-size:13px;font-weight:700;width:48px;flex-shrink:0;font-family:'IBM Plex Mono',monospace}}
.alloc-track{{flex:1;height:6px;background:var(--s2);border-radius:100px;overflow:hidden}}
.alloc-fill{{height:100%;border-radius:100px;animation:fillBar .9s cubic-bezier(.4,0,.2,1) both}}
.alloc-p{{font-size:11px;color:var(--muted);width:32px;text-align:right;font-family:'IBM Plex Mono',monospace}}
.alloc-d{{font-size:13px;font-weight:700;width:68px;text-align:right;font-family:'IBM Plex Mono',monospace}}

/* ── REGIME TABS ── */
.rtabs{{display:flex;border-bottom:1px solid var(--border);margin-bottom:20px;overflow-x:auto;scrollbar-width:none}}
.rtabs::-webkit-scrollbar{{display:none}}
.rtab{{padding:10px 0;margin-right:24px;font-size:12px;font-weight:500;border:none;background:transparent;color:var(--muted);cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px;transition:color .15s ease;white-space:nowrap;flex-shrink:0}}
.rtab.active{{color:var(--ink);border-bottom-color:var(--green)}}
.rpanel{{display:none}}
.rpanel.active{{display:block;animation:fadein .15s ease both}}

/* ── REGIME MAP ── */
.regime-map-track{{display:flex;height:34px;border-radius:8px;overflow:hidden;margin:20px 0 6px;position:relative}}
.rz{{display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;letter-spacing:.3px;text-transform:uppercase}}
.vix-marker{{position:absolute;top:0;bottom:0;width:2.5px;z-index:5;transform:translateX(-50%);border-radius:2px}}
.vix-marker-label{{position:absolute;top:-20px;transform:translateX(-50%);font-size:10px;font-weight:700;white-space:nowrap;font-family:'IBM Plex Mono',monospace}}
.reg-summary{{margin-top:14px;padding:12px 14px;border-radius:8px;background:rgba(255,255,255,.8);border-left:3px solid;font-size:12px;line-height:1.6}}

/* ── PORTFOLIO ── */
.portfolio-form{{display:grid;grid-template-columns:repeat(2,1fr);gap:20px}}
.pf-label{{font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--muted)}}
.pf-input-wrap{{display:flex;border:1.5px solid var(--border2);border-radius:8px;overflow:hidden;background:#fff;transition:border-color .15s ease,box-shadow .15s ease}}
.pf-input-wrap:focus-within{{border-color:var(--green);box-shadow:0 0 0 3px rgba(5,150,105,.1)}}
.pf-prefix{{padding:10px 12px;background:var(--s1);font-size:12px;color:var(--muted);border-right:1px solid var(--border);flex-shrink:0;font-family:'IBM Plex Mono',monospace}}
.pf-input{{border:none;outline:none;padding:10px 12px;font-family:'IBM Plex Mono',monospace;font-size:13px;color:var(--ink);background:#fff;width:100%}}
.pf-value-col{{background:var(--s1);border:1px solid var(--border);border-radius:8px;padding:10px 12px;font-size:13px;font-weight:700;font-family:'IBM Plex Mono',monospace}}
.pf-total{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:12px}}
.pf-total-cell{{background:var(--s1);border:1px solid var(--border);border-radius:var(--radius);padding:16px;text-align:center}}
.pf-total-label{{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:6px}}
.pf-total-val{{font-family:'Syne',sans-serif;font-size:22px;font-weight:700}}
.pf-save-btn{{margin-top:16px;padding:11px 24px;background:var(--ink);color:#fff;border:none;border-radius:8px;font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:700;letter-spacing:.5px;cursor:pointer;transition:all .15s ease;box-shadow:var(--shadow-xs)}}
.pf-save-btn:hover{{background:#1e2f40;box-shadow:var(--shadow);transform:translateY(-1px)}}
.pf-saved-notice{{display:none;font-size:11px;color:var(--green);margin-left:12px;font-weight:600}}

/* ── SLIDER ── */
.slider-wrap{{display:flex;align-items:center;gap:14px}}
.slider-wrap input[type=range]{{flex:1;accent-color:var(--green);cursor:pointer}}
.slider-val{{font-family:'Syne',sans-serif;font-size:18px;font-weight:700;min-width:80px}}

/* ── MISC ── */
.note{{font-size:11px;color:var(--muted);line-height:1.8;margin-top:12px;padding-top:12px;border-top:1px solid var(--border)}}
.footer{{text-align:center;color:var(--light);font-size:11px;margin-top:32px;line-height:1.8;font-family:'IBM Plex Mono',monospace}}

/* ── MOBILE BOTTOM NAV ── */
.mobile-nav{{display:none;position:fixed;bottom:0;left:0;right:0;z-index:200;background:rgba(255,255,255,.96);border-top:1px solid var(--border);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);padding-bottom:env(safe-area-inset-bottom)}}
.mobile-nav-inner{{display:flex}}
.mnav-btn{{flex:1;display:flex;flex-direction:column;align-items:center;gap:3px;padding:8px 4px;font-size:9px;font-weight:600;letter-spacing:.3px;color:var(--muted);background:none;border:none;cursor:pointer;transition:color .15s ease}}
.mnav-btn.active{{color:var(--green)}}
.mnav-icon{{font-size:18px;line-height:1}}

/* ── RESPONSIVE ── */
@media(max-width:768px){{
  .stat-row{{grid-template-columns:1fr 1fr;gap:8px}}
  .grid3{{grid-template-columns:1fr}}
}}
@media(max-width:600px){{
  .page{{padding:16px 14px 96px}}
  .grid2{{grid-template-columns:1fr}}
  .stat-row{{grid-template-columns:1fr 1fr;gap:8px}}
  .stat-val{{font-size:20px}}
  .rec-headline{{font-size:18px}}
  .rec-box{{padding:16px 18px}}
  .sig-row{{grid-template-columns:1fr auto;gap:8px}}
  .sig-row>*:nth-child(2),.sig-row>*:nth-child(3){{display:none}}
  .pt-sig-row{{grid-template-columns:1fr auto;gap:8px}}
  .pt-sig-row>*:nth-child(2),.pt-sig-row>*:nth-child(3),.pt-sig-row>*:nth-child(4){{display:none}}
  .portfolio-form,.pf-total{{grid-template-columns:1fr}}
  .tbl th:nth-child(n+4),.tbl td:nth-child(n+4){{display:none}}
  .alert-banner{{flex-direction:column;gap:12px;align-items:flex-start}}
  .nav{{display:none}}
  .mobile-nav{{display:block}}
}}
</style>
</head>
<body>

<!-- TOP BAR -->
<div class="topbar">
  <div class="topbar-logo">DCA<span>·</span>Monitor</div>
  <div class="topbar-right">
    <div class="live-dot"><div class="dot"></div>Updated: {now}</div>
    <button class="refresh-btn" id="refresh-btn" onclick="refreshPage()" title="Reload page (R)">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
      Refresh <span style="color:var(--light);font-size:10px;margin-left:2px">[R]</span>
    </button>
    <div class="topbar-date" id="clock"></div>
  </div>
</div>

<!-- DESKTOP NAV -->
<div class="nav">
  <button class="ntab active" onclick="tab('dashboard',this)">Dashboard</button>
  <button class="ntab" onclick="tab('portfolio',this)">My Portfolio</button>
  <button class="ntab" onclick="tab('regime',this)">Regime Guide</button>
  <button class="ntab" onclick="tab('profit',this)">Profit-Taking</button>
  <button class="ntab" onclick="tab('allocations',this)">Allocations</button>
</div>

<!-- MOBILE BOTTOM NAV -->
<div class="mobile-nav">
  <div class="mobile-nav-inner">
    <button class="mnav-btn active" onclick="tabM('dashboard',this)"><div class="mnav-icon">📊</div>Dashboard</button>
    <button class="mnav-btn" onclick="tabM('portfolio',this)"><div class="mnav-icon">💼</div>Portfolio</button>
    <button class="mnav-btn" onclick="tabM('regime',this)"><div class="mnav-icon">🗺️</div>Regime</button>
    <button class="mnav-btn" onclick="tabM('profit',this)"><div class="mnav-icon">⚠️</div>Profit</button>
    <button class="mnav-btn" onclick="tabM('allocations',this)"><div class="mnav-icon">📐</div>Alloc</button>
  </div>
</div>

<div class="page">

<!-- ══════════ DASHBOARD ══════════ -->
<div class="panel active" id="panel-dashboard">

  <div class="sec-title">Current Recommendation</div>
  <div class="rec-box {rcls}">
    <div class="rec-eyebrow" style="color:{rc}">Regime: {regime.upper()} · {today}</div>
    <div class="rec-headline">{headline}</div>
    <div class="rec-desc">{description}</div>
    <div class="rec-alloc">{alloc_cards}</div>
  </div>

  <div class="sec-title">Profit-Taking Status</div>
  <div class="alert-banner {acls}">
    <div>
      <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:{ac};margin-bottom:4px;">{pt_eyebrow}</div>
      <div style="font-size:14px;font-weight:600;margin-bottom:3px;">{pt_hl}</div>
      <div style="font-size:12px;color:var(--muted);">{pt["action"]}</div>
    </div>
    <div style="text-align:center;padding-left:24px;flex-shrink:0;">
      <div style="font-family:'Syne',sans-serif;font-size:40px;font-weight:800;color:{ac};line-height:1;">{fire}/6</div>
      <div style="font-size:10px;color:var(--muted);">signals</div>
    </div>
  </div>

  <div class="stat-row">
    <div class="stat-cell">
      <div class="stat-label">VIX</div>
      <div class="stat-val" style="color:{vix_sc}">{vix:.1f}</div>
      <div class="stat-sub">{vix_sub}</div>
    </div>
    <div class="stat-cell">
      <div class="stat-label">QQQ vs 200MA</div>
      <div class="stat-val" style="color:{ma_sc}">{_p(abv_pct)}</div>
      <div class="stat-sub">{ma_sub}</div>
    </div>
    <div class="stat-cell">
      <div class="stat-label">RSI 35-day</div>
      <div class="stat-val" style="color:{rsi_sc}">{rsi:.1f}</div>
      <div class="stat-sub">{rsi_sub}</div>
    </div>
    <div class="stat-cell">
      <div class="stat-label">Raw signal streak</div>
      <div class="stat-val" style="color:{consec_sc}">{consec_s}</div>
      <div class="stat-sub">of {raw.upper()} in a row</div>
    </div>
  </div>

  <div class="sec-title">Live Prices</div>
  <div class="card" style="padding:0">
    <table class="tbl">
      <thead><tr>
        <th>ETF</th>
        <th class="r">Price</th>
        <th class="r">Your cost basis</th>
        <th class="r">Unrealized gain</th>
        <th class="r">Shares</th>
        <th class="r">Position value</th>
      </tr></thead>
      <tbody>{price_rows}</tbody>
    </table>
  </div>

  <div class="sec-title" style="margin-top:24px">Regime Indicators</div>
  <div class="card" style="margin-bottom:14px">
    <div style="font-size:10px;font-weight:600;letter-spacing:1px;text-transform:uppercase;color:var(--muted);margin-bottom:6px">VIX Regime Map — which zone are we in?</div>
    <div style="position:relative;padding-top:22px">
      <div class="vix-marker-label" style="left:{vix_map_pct}%;color:{vix_sc}">VIX {vix:.1f} ▼</div>
      <div class="vix-marker" style="left:{vix_map_pct}%;background:{vix_sc}"></div>
      <div class="regime-map-track">
        <div class="rz" style="width:30.8%;background:var(--green-bg);color:var(--green);border:1px solid var(--green-border)">🟢 BULL · &lt;20</div>
        <div class="rz" style="width:15.4%;background:var(--amber-bg);color:var(--amber);border:1px solid var(--amber-border);border-left:none">🟡 CHOP · 20-30</div>
        <div class="rz" style="width:23.1%;background:var(--red-bg);color:var(--red);border:1px solid var(--red-border);border-left:none">🔴 FEAR I · 30-45</div>
        <div class="rz" style="width:30.8%;background:var(--purple-bg);color:var(--purple);border:1px solid var(--purple-border);border-left:none">🟣 FEAR II · &gt;45</div>
      </div>
    </div>
    <table class="tbl" style="margin-top:14px">
      <thead><tr><th>Regime</th><th>VIX range</th><th>What it means</th><th class="r">New DCA goes to</th><th class="r">Confirm</th></tr></thead>
      <tbody>
        <tr><td style="color:var(--green);font-weight:700">🟢 BULL</td><td>Below 20</td><td>Trending up — leverage is fully justified</td><td class="r">TQQQ 50% + SOXL 50%</td><td class="r">${CONFIRM["to_bull"]} months</td></tr>
        <tr><td style="color:var(--amber);font-weight:700">🟡 CHOP</td><td>20 – 30</td><td>Sideways — decay erodes 3× ETFs, hold don't sell</td><td class="r">QQQ 50% + SMH 50%</td><td class="r">${CONFIRM["to_chop"]} month</td></tr>
        <tr><td style="color:var(--red);font-weight:700">🔴 FEAR I</td><td>30 – 45</td><td>Panic — leveraged ETFs at maximum discount</td><td class="r">TQQQ 50% + SOXL 50%</td><td class="r">${CONFIRM["to_fear1"]} month</td></tr>
        <tr><td style="color:var(--purple);font-weight:700">🟣 FEAR II</td><td>Above 45</td><td>Crash — once-per-decade entry, triple budget</td><td class="r">Your choice (see Regime Guide)</td><td class="r">Immediate</td></tr>
      </tbody>
    </table>
  </div>
  <div class="card">
    <div class="sig-list">{regime_sigs}</div>
    <div class="reg-summary" style="border-color:{rc};color:{rc}">{reg_summary}</div>
  </div>

</div>

<!-- ══════════ PORTFOLIO ══════════ -->
<div class="panel" id="panel-portfolio">
  <div class="sec-title">My Holdings</div>
  <div class="card" style="margin-bottom:20px">
    <div style="font-size:12px;color:var(--muted);margin-bottom:18px;line-height:1.8;">
      Your shares and cost basis are pre-loaded from <code>config.py</code>. You can also edit them
      here — changes save to your browser and update position values and profit-taking signals.
    </div>
    <div class="portfolio-form">
      <!-- QQQ -->
      <div>
        <div class="pf-label" style="color:var(--ink);margin-bottom:10px">QQQ · Nasdaq-100 · 1×</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div style="display:flex;flex-direction:column;gap:6px">
            <div class="pf-label">Shares owned</div>
            <div class="pf-input-wrap"><input class="pf-input" id="pf-qqq-shares" type="number" min="0" step="1" oninput="calcPortfolio()"></div>
          </div>
          <div style="display:flex;flex-direction:column;gap:6px">
            <div class="pf-label">Avg cost / share</div>
            <div class="pf-input-wrap"><div class="pf-prefix">$</div><input class="pf-input" id="pf-qqq-cost" type="number" min="0" step="0.01" oninput="calcPortfolio()"></div>
          </div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:8px">
          <div style="display:flex;flex-direction:column;gap:6px"><div class="pf-label">Market value</div><div class="pf-value-col" id="pf-qqq-mval">—</div></div>
          <div style="display:flex;flex-direction:column;gap:6px"><div class="pf-label">Unrealized gain</div><div class="pf-value-col" id="pf-qqq-ugain">—</div></div>
        </div>
      </div>
      <!-- TQQQ -->
      <div>
        <div class="pf-label" style="color:var(--amber);margin-bottom:10px">TQQQ · 3× Nasdaq · Leveraged</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div style="display:flex;flex-direction:column;gap:6px">
            <div class="pf-label">Shares owned</div>
            <div class="pf-input-wrap"><input class="pf-input" id="pf-tqqq-shares" type="number" min="0" step="1" oninput="calcPortfolio()"></div>
          </div>
          <div style="display:flex;flex-direction:column;gap:6px">
            <div class="pf-label">Avg cost / share</div>
            <div class="pf-input-wrap"><div class="pf-prefix">$</div><input class="pf-input" id="pf-tqqq-cost" type="number" min="0" step="0.01" oninput="calcPortfolio()"></div>
          </div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:8px">
          <div style="display:flex;flex-direction:column;gap:6px"><div class="pf-label">Market value</div><div class="pf-value-col" id="pf-tqqq-mval">—</div></div>
          <div style="display:flex;flex-direction:column;gap:6px"><div class="pf-label">Unrealized gain</div><div class="pf-value-col" id="pf-tqqq-ugain">—</div></div>
        </div>
      </div>
      <!-- SMH -->
      <div>
        <div class="pf-label" style="color:var(--ink);margin-bottom:10px">SMH · Semiconductor ETF · 1×</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div style="display:flex;flex-direction:column;gap:6px">
            <div class="pf-label">Shares owned</div>
            <div class="pf-input-wrap"><input class="pf-input" id="pf-smh-shares" type="number" min="0" step="1" oninput="calcPortfolio()"></div>
          </div>
          <div style="display:flex;flex-direction:column;gap:6px">
            <div class="pf-label">Avg cost / share</div>
            <div class="pf-input-wrap"><div class="pf-prefix">$</div><input class="pf-input" id="pf-smh-cost" type="number" min="0" step="0.01" oninput="calcPortfolio()"></div>
          </div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:8px">
          <div style="display:flex;flex-direction:column;gap:6px"><div class="pf-label">Market value</div><div class="pf-value-col" id="pf-smh-mval">—</div></div>
          <div style="display:flex;flex-direction:column;gap:6px"><div class="pf-label">Unrealized gain</div><div class="pf-value-col" id="pf-smh-ugain">—</div></div>
        </div>
      </div>
      <!-- SOXL -->
      <div>
        <div class="pf-label" style="color:var(--red);margin-bottom:10px">SOXL · 3× Semiconductor · Leveraged</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div style="display:flex;flex-direction:column;gap:6px">
            <div class="pf-label">Shares owned</div>
            <div class="pf-input-wrap"><input class="pf-input" id="pf-soxl-shares" type="number" min="0" step="1" oninput="calcPortfolio()"></div>
          </div>
          <div style="display:flex;flex-direction:column;gap:6px">
            <div class="pf-label">Avg cost / share</div>
            <div class="pf-input-wrap"><div class="pf-prefix">$</div><input class="pf-input" id="pf-soxl-cost" type="number" min="0" step="0.01" oninput="calcPortfolio()"></div>
          </div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:8px">
          <div style="display:flex;flex-direction:column;gap:6px"><div class="pf-label">Market value</div><div class="pf-value-col" id="pf-soxl-mval">—</div></div>
          <div style="display:flex;flex-direction:column;gap:6px"><div class="pf-label">Unrealized gain</div><div class="pf-value-col" id="pf-soxl-ugain">—</div></div>
        </div>
      </div>
    </div>
    <div class="pf-total">
      <div class="pf-total-cell"><div class="pf-total-label">Total market value</div><div class="pf-total-val" id="pf-total-val">—</div></div>
      <div class="pf-total-cell"><div class="pf-total-label">Total cost basis</div><div class="pf-total-val" id="pf-total-cost">—</div></div>
      <div class="pf-total-cell"><div class="pf-total-label">Total unrealized gain</div><div class="pf-total-val" id="pf-total-gain">—</div></div>
    </div>
    <div style="margin-top:16px;display:flex;align-items:center">
      <button class="pf-save-btn" onclick="savePortfolio()">Save to browser</button>
      <span class="pf-saved-notice" id="saved-notice">✓ Saved</span>
    </div>
  </div>

  <div class="sec-title">Position Weights</div>
  <div class="card" id="pf-weights-card">
    <div style="font-size:12px;color:var(--muted)">Enter your holdings above to see position weights.</div>
  </div>
</div>

<!-- ══════════ REGIME GUIDE ══════════ -->
<div class="panel" id="panel-regime">
  <div class="sec-title">Regime System</div>
  <div class="rtabs">
    <button class="rtab{ra('bull')}"  onclick="switchR('bull',this)">🟢 Bull · Trending</button>
    <button class="rtab{ra('chop')}"  onclick="switchR('chop',this)">🟡 Chop · Sideways</button>
    <button class="rtab{ra('fear1')}" onclick="switchR('fear1',this)">🔴 Fear I · Panic</button>
    <button class="rtab{ra('fear2')}" onclick="switchR('fear2',this)">🟣 Fear II · Crash</button>
  </div>

  <!-- BULL -->
  <div class="rpanel{ra('bull')}" id="rp-bull">
    <div class="rec-box bull" style="margin-bottom:16px">
      <div class="rec-eyebrow" style="color:var(--green)">Regime 1 · Bull · VIX below 20{'  ·  Currently Active' if regime=='bull' else ''}</div>
      <div class="rec-headline">Market trending up — leverage is justified</div>
      <div class="rec-desc">VIX below 20 means volatility is low and the market is trending. 3× ETFs compound fastest in this regime because trend gains exceed volatility decay. The 200MA being above price confirms the long-term direction. RSI in the 45–75 range means momentum is real but not overextended — optimal DCA entry conditions.</div>
    </div>
    <div class="grid2">
      <div class="card">
        <div class="sec-title" style="margin-bottom:12px">Entry conditions · today's values</div>
        <table class="tbl"><thead><tr><th>Signal</th><th class="r">Bull threshold</th><th class="r">Today</th></tr></thead>
        <tbody>{bull_conds}</tbody></table>
      </div>
      <div class="card">
        <div class="sec-title" style="margin-bottom:12px">Monthly allocation · ${MONTHLY_BUDGET:,}</div>
        {bull_bars}
        <div class="note">Switching TO Bull requires 2 consecutive months of confirmed signals. Cannot jump directly from Fear to Bull — must pass through Chop first.</div>
      </div>
    </div>
  </div>

  <!-- CHOP -->
  <div class="rpanel{ra('chop')}" id="rp-chop">
    <div class="rec-box chop" style="margin-bottom:16px">
      <div class="rec-eyebrow" style="color:var(--amber)">Regime 2 · Chop · VIX 20–30{'  ·  Currently Active' if regime=='chop' else ''}</div>
      <div class="rec-headline">Sideways market — stop feeding the decay machine</div>
      <div class="rec-desc">In sideways markets, 3× ETFs lose 15–30% per year from volatility decay alone — even if the underlying index goes nowhere. Redirect new DCA to QQQ and SMH, which have zero structural drag. Existing leveraged positions are held — not sold. You retain full upside when the trend resumes. This is a pause, not a retreat.</div>
    </div>
    <div class="grid2">
      <div class="card">
        <div class="sec-title" style="margin-bottom:12px">Chop conditions · today's values</div>
        <table class="tbl"><thead><tr><th>Signal</th><th class="r">Chop rule</th><th class="r">Today</th></tr></thead>
        <tbody>{chop_conds}</tbody></table>
      </div>
      <div class="card">
        <div class="sec-title" style="margin-bottom:12px">Monthly allocation · ${MONTHLY_BUDGET:,}</div>
        {chop_bars}
        <div class="note">Existing TQQQ and SOXL positions: hold, do not sell. Only new DCA is redirected. Full leveraged exposure retained for when the trend resumes.</div>
      </div>
    </div>
  </div>

  <!-- FEAR I -->
  <div class="rpanel{ra('fear1')}" id="rp-fear1">
    <div class="rec-box fear1" style="margin-bottom:16px">
      <div class="rec-eyebrow" style="color:var(--red)">Regime 3 · Fear I · VIX 30–45{'  ·  Currently Active' if regime=='fear1' else ''}</div>
      <div class="rec-headline">Market panic — buy leveraged at maximum discount</div>
      <div class="rec-desc">Counterintuitive but mathematically sound: SOXL and TQQQ are typically 40–70% cheaper during Fear I than at the previous bull peak. DCA here buys the most shares per dollar of the entire cycle. When the bull eventually resumes, those cheap shares produce outsized returns. The 20-year thesis hasn't changed — only the price. Confirmation: 1 month.</div>
    </div>
    <div class="grid2">
      <div class="card">
        <div class="sec-title" style="margin-bottom:12px">Fear I conditions · today's values</div>
        <table class="tbl"><thead><tr><th>Signal</th><th class="r">Fear I range</th><th class="r">Today</th></tr></thead>
        <tbody>{fear1_conds}</tbody></table>
      </div>
      <div class="card">
        <div class="sec-title" style="margin-bottom:12px">Monthly allocation · ${MONTHLY_BUDGET:,}</div>
        {fear1_bars}
        <div class="note">Normal $10,000 budget. Contrarian — buy leveraged at deep discount. Recovery from VIX 30–45 events historically takes 6–18 months, then new highs.</div>
      </div>
    </div>
  </div>

  <!-- FEAR II -->
  <div class="rpanel{ra('fear2')}" id="rp-fear2">
    <div class="rec-box fear2" style="margin-bottom:16px">
      <div class="rec-eyebrow" style="color:var(--purple)">⚡ Regime 4 · Fear II · VIX above 45{'  ·  Currently Active' if regime=='fear2' else ''}</div>
      <div class="rec-headline">Once-per-decade crash — triple budget, deploy immediately</div>
      <div class="rec-desc">VIX above 45 represents systemic market panic. COVID March 2020 peaked at VIX 82; GFC October 2008 peaked at VIX 89. These were the single best DCA entries in any 20-year plan. No confirmation needed — the window closes fast. Triple the normal budget. Choose Split A or Split B on the day based on your conviction. Your pre-funded Fear II reserve is for exactly this moment.</div>
    </div>
    <div class="grid2">
      <div class="card">
        <div class="sec-title" style="margin-bottom:12px">Fear II conditions · today's values</div>
        <table class="tbl"><thead><tr><th>Signal</th><th class="r">Fear II rule</th><th class="r">Today</th></tr></thead>
        <tbody>{fear2_conds}</tbody></table>
      </div>
      <div class="card">
        <div class="sec-title" style="margin-bottom:12px">Split A · Max aggression · ${FEAR2_BUDGET:,}</div>
        {fear2_bars}
        <div class="note">Split B alternative: QQQ 50% + SMH 50% at the same $30,000 budget. Use Split B if systemic collapse risk is unclear. Change FEAR2_SPLIT in config.py.</div>
      </div>
    </div>
  </div>
</div>

<!-- ══════════ PROFIT-TAKING ══════════ -->
<div class="panel" id="panel-profit">
  <div class="sec-title">Profit-Taking Monitor</div>

  <div class="alert-banner {acls}" style="margin-bottom:20px">
    <div>
      <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:{ac};margin-bottom:4px">{pt_eyebrow}</div>
      <div style="font-size:15px;font-weight:600;margin-bottom:4px">{pt_hl}</div>
      <div style="font-size:12px;color:var(--muted)">{pt["action"]}</div>
    </div>
    <div style="padding-left:20px;flex-shrink:0;text-align:center">
      <div style="font-family:'Syne',sans-serif;font-size:44px;font-weight:800;color:{ac};line-height:1">{fire}/6</div>
      <div style="font-size:10px;color:var(--muted)">signals</div>
    </div>
  </div>

  <div class="card" style="margin-bottom:14px">
    <div class="sec-title" style="margin-bottom:12px">How it works</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;font-size:12px;line-height:1.9">
      <div>
        <div style="font-weight:700;margin-bottom:4px">Step 1 — Score each indicator (0–3)</div>
        <span style="color:var(--green)">0 · Normal</span> — below the warning threshold<br>
        <span style="color:var(--amber)">1 · Elevated</span> — first threshold crossed<br>
        <span style="color:var(--red)">2 · Extreme</span> — second threshold crossed<br>
        <span style="color:var(--purple)">3 · Bubble</span> — dot-com level, rare
      </div>
      <div>
        <div style="font-weight:700;margin-bottom:4px">Step 2 — Count how many are firing (≥1)</div>
        <span style="color:var(--green)">0–1 firing → HOLD</span> — continue DCA as normal<br>
        <span style="color:var(--amber)">2–3 firing → WATCH</span> — pause new SOXL DCA only<br>
        <span style="color:var(--red)">4–5 firing → CAUTION</span> — trim 15–25% of SOXL, then TQQQ<br>
        <span style="color:var(--purple)">6 firing → EXTREME</span> — trim 40–60% of all leveraged
      </div>
    </div>
    <div style="margin-top:14px;padding:10px 14px;background:var(--amber-bg);border:1px solid var(--amber-border);border-radius:4px;font-size:12px;line-height:1.8;color:var(--ink)">
      <strong>⚠️ Confirm rule:</strong> CAUTION or EXTREME must hold for <strong>3 consecutive weeks</strong> before any selling. A single elevated reading is not enough — the market needs to sustain the signal. Sell order when action is required: <strong>SOXL first → TQQQ second → SMH only at Extreme → QQQ never.</strong>
    </div>
  </div>

  <div class="card" style="margin-bottom:16px">
    <div class="sec-title" style="margin-bottom:16px">6 Indicators · today's readings</div>
    <div class="sig-list">{pt_sigs}</div>
  </div>

  <div class="grid3" style="margin-bottom:16px">
    <div class="card" style="border-color:var(--amber-border);background:var(--amber-bg)">
      <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--amber);margin-bottom:8px">🟡 Watch · 2–3 signals</div>
      <div style="font-size:15px;font-weight:700;margin-bottom:6px">No selling</div>
      <div style="font-size:11px;color:var(--muted);line-height:1.8">Pause new SOXL DCA only. All other positions continue as normal. Check again next week.</div>
    </div>
    <div class="card" style="border-color:var(--red-border);background:var(--red-bg)">
      <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--red);margin-bottom:8px">🔴 Caution · 4–5 signals</div>
      <div style="font-size:15px;font-weight:700;margin-bottom:6px">Trim 15–25%</div>
      <div style="font-size:11px;color:var(--muted);line-height:1.8">Sell SOXL first, then TQQQ proportionally. Confirm 3 consecutive weeks at this level. Proceeds → Fear II reserve.</div>
    </div>
    <div class="card" style="border-color:var(--purple-border);background:var(--purple-bg)">
      <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--purple);margin-bottom:8px">🟣 Extreme · 5–6 signals</div>
      <div style="font-size:15px;font-weight:700;margin-bottom:6px">Trim 40–60%</div>
      <div style="font-size:11px;color:var(--muted);line-height:1.8">Major leveraged reduction. SOXL then TQQQ. SMH only at Extreme. QQQ is never sold. Dot-com level readings.</div>
    </div>
  </div>

  <div class="card">
    <div class="sec-title" style="margin-bottom:12px">Indicator thresholds — elevated · extreme · bubble</div>
    <table class="tbl">
      <thead><tr><th>Indicator</th><th class="r">Normal</th><th class="r">🟡 Elevated</th><th class="r">🔴 Extreme</th><th class="r">🟣 Bubble</th></tr></thead>
      <tbody>
        <tr><td>QQQ P/E (trailing)</td><td class="r" style="color:var(--muted)">below 38×</td><td class="r">38×+</td><td class="r">45×+</td><td class="r">52×+</td></tr>
        <tr><td>RSI 35-day</td><td class="r" style="color:var(--muted)">below 78</td><td class="r">78+</td><td class="r">83+</td><td class="r">88+</td></tr>
        <tr><td>Distance above 200MA</td><td class="r" style="color:var(--muted)">below 30%</td><td class="r">30%+</td><td class="r">40%+</td><td class="r">50%+</td></tr>
        <tr><td>VIX (complacency, inverted)</td><td class="r" style="color:var(--muted)">above 13</td><td class="r">&lt;13</td><td class="r">&lt;11</td><td class="r">&lt;10</td></tr>
        <tr><td>12-month QQQ return</td><td class="r" style="color:var(--muted)">below 50%</td><td class="r">50%+</td><td class="r">65%+</td><td class="r">80%+</td></tr>
        <tr><td>TQQQ gain vs cost basis</td><td class="r" style="color:var(--muted)">below 200%</td><td class="r">200%+</td><td class="r">400%+</td><td class="r">700%+</td></tr>
      </tbody>
    </table>
  </div>
</div>

<!-- ══════════ ALLOCATIONS ══════════ -->
<div class="panel" id="panel-allocations">
  <div class="sec-title">Allocation Calculator</div>

  <div class="card" style="margin-bottom:20px">
    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:14px">
      <div style="flex:1;min-width:220px">
        <div style="font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--muted);margin-bottom:6px">Monthly Budget</div>
        <div class="slider-wrap">
          <input type="range" id="budgetSlider" min="1000" max="50000" step="500" value="{MONTHLY_BUDGET}" oninput="updateBudget(this.value)">
          <div class="slider-val" id="budgetDisplay">${MONTHLY_BUDGET:,}</div>
        </div>
      </div>
      <div style="font-size:11px;color:var(--muted);max-width:260px;line-height:1.8">Fear II budget is automatically 3× this amount. Drag the slider to see dollar amounts for all 4 regimes.</div>
    </div>
  </div>

  <div class="grid2">
    <div class="card" style="border-color:var(--green-border)">
      <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--green);margin-bottom:12px">🟢 Bull · VIX &lt; 20</div>
      <div id="bull-alloc"></div>
      <div class="note">Confirmation: 2 consecutive months · Cannot switch directly from Fear</div>
    </div>
    <div class="card" style="border-color:var(--amber-border)">
      <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--amber);margin-bottom:12px">🟡 Chop · VIX 20–30</div>
      <div id="chop-alloc"></div>
      <div class="note">Confirmation: 1 month from Bull · Hold existing leveraged positions</div>
    </div>
    <div class="card" style="border-color:var(--red-border)">
      <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--red);margin-bottom:12px">🔴 Fear I · VIX 30–45</div>
      <div id="fear1-alloc"></div>
      <div class="note">Confirmation: 1 month · Contrarian — buy leveraged at maximum discount</div>
    </div>
    <div class="card" style="border-color:var(--purple-border)">
      <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--purple);margin-bottom:12px">🟣 Fear II · VIX &gt; 45</div>
      <div id="fear2-alloc"></div>
      <div class="note">Confirmation: None — deploy immediately · 3× normal budget</div>
    </div>
  </div>

  <div class="sec-title" style="margin-top:28px">Sell Order — Profit-Taking</div>
  <div class="card">
    <table class="tbl">
      <thead><tr><th>#</th><th>ETF</th><th>When to sell</th><th>Why this order</th><th class="r">QQQ sold?</th></tr></thead>
      <tbody>
        <tr><td style="color:var(--red);font-weight:700">1st</td><td><strong>SOXL</strong></td><td>Caution level (4+ signals)</td><td>Highest decay · worst max drawdown (−97%)</td><td class="r">No</td></tr>
        <tr><td style="color:var(--amber);font-weight:700">2nd</td><td><strong>TQQQ</strong></td><td>Caution level, after SOXL</td><td>High decay · −82% historical max drawdown</td><td class="r">No</td></tr>
        <tr><td style="color:var(--muted)">3rd</td><td>SMH</td><td>Extreme only (5–6 signals)</td><td>No decay — only at dot-com-level readings</td><td class="r">No</td></tr>
        <tr><td style="color:var(--green);font-weight:700">Never</td><td><strong>QQQ</strong></td><td>—</td><td>No decay · lowest fee · 20-year core position</td><td class="r" style="color:var(--green)">Never</td></tr>
      </tbody>
    </table>
  </div>
</div>

</div><!-- /page -->

<div class="footer">Last updated: {now} &nbsp;·&nbsp; {n_hist} month{'s'if n_hist!=1 else''} of regime history on record</div>

<script>
// ── injected live data ──
const PRICES     = {prices_js};
const CONFIG_PF  = {config_pf_js};
const ALLOC_W    = {alloc_js};
const ETF_COLORS = {{QQQ:'var(--ink)',TQQQ:'var(--amber)',SMH:'var(--ink)',SOXL:'var(--red)'}};

// ── refresh ──
function refreshPage(){{
  const btn=document.getElementById('refresh-btn');
  btn.classList.add('spinning');
  setTimeout(()=>location.reload(true),300);
}}
document.addEventListener('keydown',e=>{{
  if(e.key==='r'||e.key==='R'){{
    if(document.activeElement.tagName!=='INPUT')refreshPage();
  }}
}});

// ── clock ──
function updateClock(){{
  const n=new Date();
  document.getElementById('clock').textContent=
    n.toLocaleDateString('en-US',{{month:'short',day:'numeric',year:'numeric'}})+
    '  '+n.toLocaleTimeString('en-US',{{hour:'2-digit',minute:'2-digit'}});
}}
updateClock(); setInterval(updateClock,10000);

// ── nav tabs ──
function tab(id,btn){{
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.ntab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.mnav-btn').forEach(t=>t.classList.remove('active'));
  document.getElementById('panel-'+id).classList.add('active');
  btn.classList.add('active');
  // sync mobile nav
  document.querySelectorAll('.mnav-btn').forEach(b=>{{
    if(b.getAttribute('onclick')&&b.getAttribute('onclick').includes("'"+id+"'"))b.classList.add('active');
  }});
  window.scrollTo({{top:0,behavior:'smooth'}});
}}
function tabM(id,btn){{
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.ntab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.mnav-btn').forEach(t=>t.classList.remove('active'));
  document.getElementById('panel-'+id).classList.add('active');
  btn.classList.add('active');
  // sync desktop nav
  document.querySelectorAll('.ntab').forEach(b=>{{
    if(b.getAttribute('onclick')&&b.getAttribute('onclick').includes("'"+id+"'"))b.classList.add('active');
  }});
  window.scrollTo({{top:0,behavior:'smooth'}});
}}
function switchR(id,btn){{
  document.querySelectorAll('.rpanel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.rtab').forEach(t=>t.classList.remove('active'));
  document.getElementById('rp-'+id).classList.add('active');
  btn.classList.add('active');
}}

// ── portfolio ──
const PF_KEYS=['qqq','tqqq','smh','soxl'];
const PF_ETF={{qqq:'QQQ',tqqq:'TQQQ',smh:'SMH',soxl:'SOXL'}};

function fmt(n){{
  if(!isFinite(n))return'—';
  return'$'+(Math.abs(n)>=1e3?Math.round(n).toLocaleString():n.toFixed(2));
}}
function fmtP(n){{
  if(!isFinite(n))return'—';
  return(n>=0?'+':'')+n.toFixed(1)+'%';
}}

function loadPortfolio(){{
  const saved=JSON.parse(localStorage.getItem('dca_portfolio')||'null');
  const src=saved||CONFIG_PF;
  PF_KEYS.forEach(k=>{{
    document.getElementById('pf-'+k+'-shares').value=src[k]?.shares||'';
    document.getElementById('pf-'+k+'-cost').value  =src[k]?.cost  ||'';
  }});
  calcPortfolio();
}}

function savePortfolio(){{
  const data={{}};
  PF_KEYS.forEach(k=>{{
    data[k]={{
      shares:parseFloat(document.getElementById('pf-'+k+'-shares').value)||0,
      cost:  parseFloat(document.getElementById('pf-'+k+'-cost').value)||0,
    }};
  }});
  localStorage.setItem('dca_portfolio',JSON.stringify(data));
  const n=document.getElementById('saved-notice');
  n.style.display='inline';setTimeout(()=>n.style.display='none',2500);
  calcPortfolio();
}}

function calcPortfolio(){{
  let totalVal=0,totalCost=0;const weights=[];
  PF_KEYS.forEach(k=>{{
    const etf=PF_ETF[k];
    const shares=parseFloat(document.getElementById('pf-'+k+'-shares').value)||0;
    const cost  =parseFloat(document.getElementById('pf-'+k+'-cost').value)||0;
    const price =PRICES[etf];
    const mval  =shares*price;
    const basis =shares*cost;
    const gain  =cost>0?((price/cost)-1)*100:NaN;
    document.getElementById('pf-'+k+'-mval').textContent =shares>0?fmt(mval):'—';
    const ge=document.getElementById('pf-'+k+'-ugain');
    ge.textContent=shares>0&&cost>0?fmtP(gain):'—';
    ge.style.color=gain>=0?'var(--green)':gain<0?'var(--red)':'inherit';
    totalVal+=mval; totalCost+=basis;
    if(shares>0) weights.push({{etf,val:mval,color:ETF_COLORS[etf]}});
  }});
  const gPct=totalCost>0?((totalVal/totalCost)-1)*100:NaN;
  document.getElementById('pf-total-val').textContent =totalVal>0?fmt(totalVal):'—';
  document.getElementById('pf-total-cost').textContent=totalCost>0?fmt(totalCost):'—';
  const tg=document.getElementById('pf-total-gain');
  tg.textContent=totalCost>0?fmtP(gPct):'—';
  tg.style.color=gPct>=0?'var(--green)':gPct<0?'var(--red)':'inherit';
  const wc=document.getElementById('pf-weights-card');
  if(totalVal>0){{
    wc.innerHTML=weights.map(w=>`
      <div class="alloc-bar-row">
        <div class="alloc-t" style="color:${{w.color}}">${{w.etf}}</div>
        <div class="alloc-track"><div class="alloc-fill" style="width:${{(w.val/totalVal*100).toFixed(1)}}%;background:${{w.color}}"></div></div>
        <div class="alloc-p">${{(w.val/totalVal*100).toFixed(1)}}%</div>
        <div class="alloc-d">${{fmt(w.val)}}</div>
      </div>`).join('');
  }} else {{
    wc.innerHTML='<div style="font-size:12px;color:var(--muted)">Enter your holdings above to see position weights.</div>';
  }}
}}

// ── allocation calculator ──
function renderAlloc(regime,budget,id){{
  const w=ALLOC_W[regime];
  document.getElementById(id).innerHTML=Object.entries(w).map(([etf,wt])=>{{
    const amt=Math.round(wt*budget);
    const c=wt>0?ETF_COLORS[etf]:'var(--muted)';
    return`<div class="alloc-bar-row">
      <div class="alloc-t" style="color:${{c}}">${{etf}}</div>
      <div class="alloc-track"><div class="alloc-fill" style="width:${{wt*100}}%;background:${{c}}"></div></div>
      <div class="alloc-p" style="color:${{c}}">${{(wt*100).toFixed(0)}}%</div>
      <div class="alloc-d" style="color:${{wt>0?'var(--ink)':'var(--muted)'}};font-weight:${{wt>0?700:400}}">${{wt>0?'$'+amt.toLocaleString():'—'}}</div>
    </div>`;
  }}).join('');
}}

function updateBudget(val){{
  const b=parseInt(val);
  document.getElementById('budgetDisplay').textContent='$'+b.toLocaleString();
  renderAlloc('bull', b,    'bull-alloc');
  renderAlloc('chop', b,    'chop-alloc');
  renderAlloc('fear1',b,    'fear1-alloc');
  renderAlloc('fear2',b*3,  'fear2-alloc');
}}

// ── init ──
loadPortfolio();
updateBudget({MONTHLY_BUDGET});
</script>
</body>
</html>"""
