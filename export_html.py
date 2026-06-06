import json
from datetime import datetime
from config import (COST_BASIS, HOLDINGS, MONTHLY_BUDGET, FEAR2_BUDGET,
                    ALLOCATIONS, CONFIRM, EUPHORIA_THRESHOLDS, EUPHORIA_SIGNALS_REQUIRED)

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
REGIME_COLOR = {"euphoria":"var(--orange)","bull":"var(--green)","chop":"var(--amber)","fear1":"var(--red)","fear2":"var(--purple)"}
ALERT_CLASS  = {"HOLD":"hold","WATCH":"watch","CAUTION":"caution","EXTREME":"extreme"}
ALERT_COLOR  = {"HOLD":"var(--green)","WATCH":"var(--amber)","CAUTION":"var(--red)","EXTREME":"var(--purple)"}
ETF_COLOR    = {"TQQQ":"var(--amber)","SOXL":"var(--red)","QQQ":"var(--ink)","SMH":"var(--ink)"}

# ── INVESTMENT TIPS — distilled wisdom. Append new ones here. ──
# Each: (category, color_var, title, one-liner)
INVESTMENT_TIPS = [
    ("Sizing", "var(--red)",
     "Cap the sleeve at ~10–15% of liquid net worth",
     "Position size is the only risk control that always works. Set the cap on PEAK exposure — including any crash doubledown."),
    ("Sizing", "var(--red)",
     "Could you survive the sleeve going to zero?",
     "The honest question isn't 'what's my return' — it's whether a near-total loss of the leveraged book leaves your life intact."),
    ("Structure", "var(--red)",
     "Run a barbell: huge safe core, small hot satellite",
     "Most wealth in T-bills/treasuries, a small slice in leverage. The T-bill fund IS your hedge — held separately, not bolted into the strategy."),
    ("Leverage", "var(--amber)",
     "3× ETFs only work in trends — they bleed in chop",
     "Daily rebalancing causes volatility decay: 15–30%/yr lost in sideways markets even if the index goes nowhere."),
    ("Leverage", "var(--amber)",
     "Recovery math is brutal — avoid deep drawdowns",
     "From −90% you need +900% to break even; from −97%, +3,200%. Dodging the drawdown beats chasing the upside."),
    ("Leverage", "var(--amber)",
     "Concentration is hidden: it's all one tech bet",
     "QQQ, TQQQ, SMH, SOXL overlap heavily. Diversify at the TOTAL-portfolio level (the safe core), not inside the sleeve."),
    ("Timing", "var(--purple)",
     "VIX is coincident, not predictive",
     "It spikes AFTER price falls. VIX > 45 is not the bottom — in 2008 it hit 45 in September, then the market fell ~30% more into March."),
    ("Timing", "var(--purple)",
     "Ladder crash deployment by depth, not a single lump",
     "Don't empty the reserve at the first panic print. Buy progressively more as drawdown deepens so you're never out of ammo at the bottom."),
    ("Timing", "var(--purple)",
     "Don't trust correlations in a crisis",
     "In 2022 stocks and long bonds fell together — the classic TQQQ/TMF hedge broke exactly when it was needed."),
    ("Discipline", "var(--green)",
     "Profit-taking sell order: SOXL → TQQQ → SMH → QQQ never",
     "Trim the highest-decay leverage first. QQQ is the permanent core and is never sold."),
    ("Discipline", "var(--green)",
     "Judge by MAR ratio, not raw return",
     "CAGR ÷ max drawdown is the real scoreboard. A strategy that returns less but draws down half as much usually wins long term."),
    ("Discipline", "var(--green)",
     "Beware the backtest — it only saw the good years",
     "TQQQ/SOXL launched in 2010, the best tech window ever. A 3× Nasdaq through 2000–02 was a near-total loss. Size for the regime you haven't seen."),
    ("Discipline", "var(--green)",
     "Hysteresis: slow to get aggressive, fast to get defensive",
     "Confirmation months stop you chasing FOMO into leverage; fear regimes switch immediately. Asymmetry by design."),
    ("Timing", "var(--purple)",
     "Euphoria can last for months — don't short the top",
     "Overheated ≠ imminent crash. Pause new buys and trim into strength; never bet against a melt-up with leverage."),
    ("Leverage", "var(--amber)",
     "Skip the daily circuit breaker",
     "Single-day stops whipsaw viciously on 3× ETFs, and you can't execute intraday on a framework you check once a day."),
    ("Timing", "var(--purple)",
     "CAPE catches valuation bubbles that momentum misses",
     "Shiller CAPE flagged BUBBLE at the 2000 top while VIX/momentum stayed calm. It's the one signal that sees an expensive market at low volatility."),
]


_BANDCOLOR = {"green":"var(--green)","amber":"var(--amber)","red":"var(--red)",
              "purple":"var(--purple)","orange":"var(--orange)","muted":"var(--muted)"}

# ── INDICATOR LEGEND — how each metric works + what the values mean ──
LEGEND = [
  ("Volatility", [
    {"name":"VIX — CBOE Volatility Index","tag":"implied volatility",
     "what":"The market's expected 30-day volatility of the S&P 500, implied by options prices. Often called the 'fear gauge' — it rises when investors pay up for downside protection.",
     "calc":"Derived live from S&P 500 option premiums. It is forward-looking (what traders EXPECT), not a measure of what already happened.",
     "bands":[("Below 15","Complacency — very calm, little fear priced in","green"),
              ("15 – 20","Normal bull-market range","green"),
              ("20 – 30","Chop — rising caution","amber"),
              ("30 – 45","Fear — panic conditions","red"),
              ("Above 45","Extreme fear — crash / once-per-decade","purple")],
     "use":"The hard boundary for the regime: <20 bull · 20–30 chop · 30–45 Fear I · >45 Fear II."},
    {"name":"Realized Volatility (1-month)","tag":"actual volatility",
     "what":"How much the price ACTUALLY moved over the last month — the real-world counterpart to VIX's expectation.",
     "calc":"Standard deviation of the last 21 daily log returns, annualized (×√252). Shown as a percentile vs the ticker's full history.",
     "bands":[("Below 33rd pctile","Calm — small actual swings","green"),
              ("33rd – 66th","Normal historical range","amber"),
              ("66th – 90th","Elevated — turbulent","red"),
              ("Above 90th","Extreme — historic stress","purple")],
     "use":"A leverage-decay gauge. High realized vol is when 3× ETFs bleed fastest. A big SMH-vs-QQQ gap warns specifically against SOXL."},
  ]),
  ("Trend & Momentum", [
    {"name":"RSI — Relative Strength Index (35-day)","tag":"momentum · 0–100",
     "what":"Measures how fast and how far price has risen vs fallen recently. High = overbought (gained a lot, fast); low = oversold.",
     "calc":"Wilder's RSI over 35 trading days of QQQ closes. We use 35 (not the standard 14) to filter noise — better suited to monthly DCA.",
     "bands":[("Below 30","Oversold — washed out","red"),
              ("30 – 45","Weak momentum","amber"),
              ("45 – 75","Healthy momentum","green"),
              ("78 / 83 / 88","Overbought → profit-taking elevated / extreme / bubble","purple")],
     "use":"Confirms bull health; one of the 7 profit-taking signals; part of the euphoria trigger (>70)."},
    {"name":"MACD (12 / 26 / 9)","tag":"trend",
     "what":"Moving Average Convergence Divergence — whether short-term momentum is accelerating above or below the longer trend.",
     "calc":"MACD line = 12-day EMA − 26-day EMA. Signal line = 9-day EMA of the MACD line. Compared on QQQ.",
     "bands":[("MACD line ABOVE signal","Bullish — upward momentum","green"),
              ("MACD line BELOW signal","Bearish — downward momentum","red")],
     "use":"A trend confirmation in the bull regime checklist."},
    {"name":"200-day Moving Average (distance above)","tag":"trend",
     "what":"The most-watched long-term trend line. How far price sits above/below it shows trend direction and how extended the market is.",
     "calc":"200-day simple moving average of QQQ closes; distance = (price − MA) ÷ MA.",
     "bands":[("Below 0%","Price under the MA — downtrend","red"),
              ("0 – 30%","Normal, healthy uptrend","green"),
              ("30% / 40% / 50%","Extended → profit-taking elevated / extreme / bubble","purple")],
     "use":"Trend confirmation; euphoria trigger (>18%); profit-taking signal."},
    {"name":"Drawdown from 52-week high","tag":"trend",
     "what":"How far below its highest point in the past year the price has fallen.",
     "calc":"(current price − highest close of trailing 252 days) ÷ that high.",
     "bands":[("Above −10%","Near highs","green"),
              ("−10% to −20%","Pullback","amber"),
              ("−20% to −35%","Correction / bear","red"),
              ("Below −35%","Deep bear","purple")],
     "use":"Context for Fear regimes and the buy-the-panic thesis."},
    {"name":"12-month return","tag":"momentum",
     "what":"Total price change over the past year — the big-picture momentum read.",
     "calc":"(price ÷ price 252 trading days ago) − 1, for QQQ.",
     "bands":[("Negative","Down year","red"),
              ("0 – 30%","Normal","green"),
              ("50% / 65% / 80%","Stretched → profit-taking elevated / extreme / bubble","purple")],
     "use":"Euphoria trigger (>30%); profit-taking signal."},
  ]),
  ("Valuation", [
    {"name":"Shiller CAPE","tag":"valuation ★",
     "what":"Cyclically-Adjusted P/E of the S&P 500 — the gold-standard long-term bubble gauge. Because it averages 10 years of earnings, one good year can't fool it.",
     "calc":"Price ÷ average inflation-adjusted earnings over the prior 10 years. Scraped live from multpl.com.",
     "bands":[("Below 28","Normal","green"),
              ("28 – 34","Elevated (90th–95th pctile)","amber"),
              ("34 – 40","Extreme (95th–99th)","red"),
              ("Above 40","Bubble — dot-com peak was 44","purple")],
     "use":"The Valuation Warning. VIX-independent, so it catches valuation bubbles (like 2000) that momentum/VIX miss. A Bubble reading alone forces ≥ CAUTION."},
    {"name":"QQQ P/E (trailing)","tag":"valuation",
     "what":"Price-to-earnings of the Nasdaq-100 — what you pay per dollar of the last year's earnings.",
     "calc":"Trailing 12-month P/E from Yahoo Finance.",
     "bands":[("Below 38×","Normal","green"),
              ("38× / 45× / 52×","Elevated / extreme / bubble","purple")],
     "use":"Second valuation input alongside CAPE."},
  ]),
  ("Relative Strength & Personal", [
    {"name":"SMH vs QQQ (20-day RS)","tag":"relative strength",
     "what":"Whether semiconductors are leading or lagging the broad Nasdaq over the last month — a risk-appetite tell.",
     "calc":"SMH's 20-day return minus QQQ's 20-day return.",
     "bands":[("Above −3%","Semis leading / neutral — healthy","green"),
              ("Below −3%","Semis lagging — caution","amber")],
     "use":"Confirms broad-market strength in the bull checklist."},
    {"name":"TQQQ gain vs your cost basis","tag":"personal",
     "what":"Your own unrealized gain on TQQQ — the only signal personal to your portfolio.",
     "calc":"(current price ÷ your average cost) − 1. Set your cost basis in config.py.",
     "bands":[("Below 200%","Normal","green"),
              ("200% / 400% / 700%","Trim → elevated / extreme / bubble","purple")],
     "use":"Profit-taking signal — locks in real gains after big leveraged run-ups."},
  ]),
]

LEGEND_CONCEPTS = [
  ("Implied vs Realized volatility",
   "VIX is IMPLIED — what option prices say traders expect. Realized vol is ACTUAL — what already happened. When realized is high but VIX is low, the market is moving a lot without pricing in fear (a notable divergence)."),
  ("Volatility decay (beta slippage)",
   "3× ETFs reset their leverage daily. In choppy markets this 'constant-leverage trap' loses money even if the index ends flat: +25% then −20% returns the index to start, but a 3× fund drops ~30%. This is why the framework avoids leverage in chop and high realized vol."),
  ("Percentile",
   "Where today's reading ranks against the metric's entire history. '90th percentile' means it has only been this high 10% of the time — instantly tells you if a value is normal or extreme."),
  ("Hysteresis",
   "Confirmation delays that stop the regime flip-flopping on noise. The framework is slow to turn aggressive (bull needs 2 months) and fast to turn defensive (Fear is immediate)."),
  ("Volatility × Valuation",
   "The key synthesis: high vol + cheap = opportunity (2008); high vol + expensive = bubble bursting (2000); low vol + expensive = complacency/top (2021); low vol + cheap = healthy accumulation."),
]


def _load_backtest():
    try:
        with open("backtest_summary.json") as f:
            return json.load(f)
    except Exception:
        return None


def _render_equity_chart(curve) -> str:
    """Inline SVG: growth of $1 (time-weighted, log scale) — strategy vs each
    Buy & Hold ETF, with the strategy's max-drawdown marked."""
    if not curve or not curve.get("strat"):
        return ""
    import math
    dates = curve["dates"]
    series = [("Adaptive strategy", curve["strat"], "#111827", 2.4)]
    if "capped" in curve:
        series.append(("Adaptive + 25% cap", curve["capped"], "#059669", 2.2))
    for etf, col in (("QQQ","#6b7280"),("SMH","#2563eb"),("TQQQ","#d97706"),("SOXL","#dc2626")):
        if etf in curve:
            series.append((f"B&H {etf}", curve[etf], col, 1.4))
    n = len(curve["strat"])
    W, H, L, R, T, Bm = 820, 380, 52, 16, 18, 30
    pw, ph = W - L - R, H - T - Bm
    allv = [v for _, s, _, _ in series for v in s if v > 0]
    lo = math.floor(math.log10(min(min(allv), 0.9)))
    hi = math.ceil(math.log10(max(allv)))
    def X(i): return L + (i / (n - 1)) * pw
    def Y(v): return T + (hi - math.log10(max(v, 10 ** lo))) / (hi - lo) * ph
    def poly(s): return " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(s))

    grid = ""
    for p in range(lo, hi + 1):
        yy = Y(10 ** p)
        grid += (f'<line x1="{L}" y1="{yy:.1f}" x2="{W-R}" y2="{yy:.1f}" stroke="#e8ebed" stroke-width="1"/>'
                 f'<text x="{L-6}" y="{yy+3:.1f}" text-anchor="end" font-size="9" fill="#9ca3af">${10**p:,.0f}</text>')
    seen = set(); ticks = ""
    for i, dt in enumerate(dates):
        yr = dt[:4]
        if yr not in seen and int(yr) % 2 == 0:
            seen.add(yr); xx = X(i)
            ticks += (f'<line x1="{xx:.1f}" y1="{T}" x2="{xx:.1f}" y2="{T+ph}" stroke="#f1f3f5" stroke-width="1"/>'
                      f'<text x="{xx:.1f}" y="{T+ph+14:.1f}" text-anchor="middle" font-size="9" fill="#9ca3af">{yr}</text>')

    strat = curve["strat"]
    peak = strat[0]; trough_i = 0; worst = 0.0; peak_at_worst = strat[0]
    for i, v in enumerate(strat):
        if v > peak: peak = v
        dd = v / peak - 1
        if dd < worst: worst, trough_i, peak_at_worst = dd, i, peak
    dd_mark = ""
    if worst < -0.05:
        xt = X(trough_i); y_pk = Y(peak_at_worst); y_tr = Y(strat[trough_i])
        dd_mark = (f'<line x1="{xt:.1f}" y1="{y_pk:.1f}" x2="{xt:.1f}" y2="{y_tr:.1f}" stroke="#111827" '
                   f'stroke-width="1.3" stroke-dasharray="3,3"/>'
                   f'<text x="{xt+5:.1f}" y="{(y_pk+y_tr)/2:.1f}" font-size="10" font-weight="700" fill="#111827">'
                   f'strategy {worst*100:.0f}%</text>')

    lines = "".join(f'<polyline fill="none" stroke="{c}" stroke-width="{w}" points="{poly(s)}"/>'
                    for _, s, c, w in series if _ != "Adaptive strategy")
    lines += f'<polyline fill="none" stroke="#111827" stroke-width="2.4" points="{poly(strat)}"/>'
    legend = "".join(
        f'<span style="display:flex;align-items:center;gap:5px"><span style="width:14px;height:3px;background:{c};display:inline-block;border-radius:2px"></span>{nm}</span>'
        for nm, _, c, _ in series)

    return f"""
    <div class="card" style="margin-bottom:12px">
      <div class="sec-title" style="margin-bottom:6px">Growth of $1 · time-weighted, log scale</div>
      <div style="display:flex;gap:14px;margin-bottom:6px;font-size:11px;flex-wrap:wrap">{legend}</div>
      <svg viewBox="0 0 {W} {H}" style="width:100%;height:auto;font-family:'IBM Plex Mono',monospace">
        {grid}{ticks}{lines}{dd_mark}
      </svg>
      <div class="note">Growth of $1 in each strategy (contribution-neutral). Log scale — equal vertical distance = equal % move.
      Note how the highest-returning lines (SOXL, TQQQ) also plunge the deepest.</div>
    </div>"""


def _render_monthly(rows) -> str:
    if not rows:
        return ""
    hdr = ("Date","Regime","Profit-take","Contrib","Buy QQQ","Buy TQQQ","Buy SMH","Buy SOXL",
           "Sell TQQQ","Sell SOXL","Sh QQQ","Sh TQQQ","Sh SMH","Sh SOXL","Cash","NAV","TWR %")
    th = "".join(f'<th class="r">{h}</th>' if i else f'<th>{h}</th>' for i, h in enumerate(hdr))
    def usd(v): return f"${v:,.0f}" if v else "—"
    def sh(v):  return f"{v:,.0f}" if v else "—"
    trs = ""
    for r in rows:
        rc = REGIME_COLOR.get(r["reg"], "var(--ink)")
        ac = ALERT_COLOR.get(r["pt"], "var(--muted)")
        tw = r["twr"]; twc = "var(--green)" if tw > 0 else "var(--red)" if tw < 0 else "var(--muted)"
        trs += (f'<tr><td style="white-space:nowrap">{r["d"]}</td>'
                f'<td style="color:{rc};font-weight:600">{r["reg"]}</td>'
                f'<td style="color:{ac}">{r["pt"]}</td>'
                f'<td class="r">{usd(r["c"])}</td>'
                f'<td class="r">{usd(r["bq"])}</td><td class="r">{usd(r["bt"])}</td>'
                f'<td class="r">{usd(r["bs"])}</td><td class="r">{usd(r["bx"])}</td>'
                f'<td class="r" style="color:var(--red)">{usd(r["st"])}</td>'
                f'<td class="r" style="color:var(--red)">{usd(r["sx"])}</td>'
                f'<td class="r">{sh(r["hq"])}</td><td class="r">{sh(r["ht"])}</td>'
                f'<td class="r">{sh(r["hs"])}</td><td class="r">{sh(r["hx"])}</td>'
                f'<td class="r">{usd(r["cash"])}</td>'
                f'<td class="r" style="font-weight:700">{usd(r["nav"])}</td>'
                f'<td class="r" style="color:{twc}">{tw:+.1f}%</td></tr>')
    return f"""
    <div class="sec-title" style="margin-top:18px">Month-by-Month · Full Position Detail</div>
    <div class="bt-scroll">
      <table class="tbl bt-tbl">
        <thead><tr>{th}</tr></thead>
        <tbody>{trs}</tbody>
      </table>
    </div>
    <div class="note">Every month: regime, profit-taking alert, the contribution, exactly what was bought and sold,
    shares held in each ETF, cash reserve, total NAV, and that month's time-weighted return. Scroll within the box.
    The same data (plus prices and the TWR index) is in <code>backtest.xlsx</code>.</div>"""


def _render_alloc_chart(alloc, title="Portfolio composition over time · % of holdings in each ETF", note=None) -> str:
    """Stacked-area SVG: % of the strategy's value in each ETF (and cash), every month."""
    if not alloc or not alloc.get("dates"):
        return ""
    dates = alloc["dates"]
    n = len(dates)
    order = [("QQQ", "#6b7280"), ("SMH", "#2563eb"), ("TQQQ", "#d97706"), ("SOXL", "#dc2626"), ("Cash", "#cbd5e1")]
    order = [(e, c) for e, c in order if e in alloc]
    if note is None:
        note = ("Each band is that ETF's share of the strategy's value each month (sums to 100%). Watch the leveraged "
                "bands (TQQQ amber, SOXL red) swell over time — both because most months are bull <em>and</em> because leverage "
                "compounds faster — quietly concentrating risk even though new chop-month money goes to QQQ/SMH.")
    W, H, L, R, T, Bm = 820, 300, 40, 16, 14, 28
    pw, ph = W - L - R, H - T - Bm
    def X(i): return L + (i / (n - 1)) * pw
    def Y(p): return T + (100 - p) / 100 * ph

    grid = ""
    for p in (0, 25, 50, 75, 100):
        yy = Y(p)
        grid += (f'<line x1="{L}" y1="{yy:.1f}" x2="{W-R}" y2="{yy:.1f}" stroke="#e8ebed" stroke-width="1"/>'
                 f'<text x="{L-6}" y="{yy+3:.1f}" text-anchor="end" font-size="9" fill="#9ca3af">{p}%</text>')
    seen = set(); ticks = ""
    for i, dt in enumerate(dates):
        yr = dt[:4]
        if yr not in seen and int(yr) % 2 == 0:
            seen.add(yr); xx = X(i)
            ticks += f'<text x="{xx:.1f}" y="{T+ph+14:.1f}" text-anchor="middle" font-size="9" fill="#9ca3af">{yr}</text>'

    cum = [0.0] * n
    areas = ""
    for etf, col in order:
        ser = alloc[etf]
        top = [cum[j] + ser[j] for j in range(n)]
        pts_top = " ".join(f"{X(j):.1f},{Y(top[j]):.1f}" for j in range(n))
        pts_bot = " ".join(f"{X(j):.1f},{Y(cum[j]):.1f}" for j in range(n - 1, -1, -1))
        areas += f'<polygon points="{pts_top} {pts_bot}" fill="{col}" fill-opacity="0.85" stroke="none"/>'
        cum = top
    legend = "".join(
        f'<span style="display:flex;align-items:center;gap:5px"><span style="width:12px;height:12px;background:{c};display:inline-block;border-radius:3px"></span>{e}</span>'
        for e, c in order)

    return f"""
    <div class="card" style="margin-bottom:12px">
      <div class="sec-title" style="margin-bottom:6px">{title}</div>
      <div style="display:flex;gap:14px;margin-bottom:6px;font-size:11px;flex-wrap:wrap">{legend}</div>
      <svg viewBox="0 0 {W} {H}" style="width:100%;height:auto;font-family:'IBM Plex Mono',monospace">
        {grid}{ticks}{areas}
      </svg>
      <div class="note">{note}</div>
    </div>"""


def _render_backtest(s) -> str:
    if not s:
        return ('<div class="card"><div style="color:var(--muted);font-size:13px;line-height:1.7">'
                'No backtest results yet. Run <code>python backtest_engine.py</code> to generate them.</div></div>')
    st = s["strategy"]
    cap = s.get("strategy_capped")
    bm = s.get("benchmarks", {})
    cols = [("Strategy", st)]
    if cap:
        cols.append(("Strat +25% cap", cap))
    cols += [(e, bm[e]) for e in ("QQQ","SMH","TQQQ","SOXL") if e in bm]

    def row(label, key, fmt, better="hi", note=""):
        vals = [d.get(key) for _, d in cols]
        nums = [v for v in vals if isinstance(v, (int, float))]
        win = (max(nums) if better == "hi" else min(nums)) if nums else None
        tds = ""
        for v in vals:
            green = (v == win and better in ("hi", "lo") and len(nums) > 1)
            col = "var(--green)" if green else "var(--ink)"
            tds += f'<td class="r" style="color:{col};font-weight:700">{fmt.format(v)}</td>'
        return f'<tr><td>{label}{("  ·  "+note) if note else ""}</td>{tds}</tr>'

    rows = (
        row("Final NAV", "final", "${:,.0f}") +
        row("Multiple on invested", "multiple", "{}x") +
        row("Time-weighted CAGR", "twr_cagr", "{}%/yr") +
        row("Money-weighted IRR", "irr_pct", "{}%/yr") +
        row("Investment Sharpe", "inv_sharpe", "{}", "hi", "equal-wt") +
        row("Contribution Sharpe", "contrib_sharpe", "{}", "hi", "capital-wt") +
        row("Sortino", "sortino", "{}") +
        row("Max drawdown", "maxdd_pct", "{}%", "hi", "less-negative wins") +
        row("Win rate", "win_rate", "{}%") +
        row("Worst month", "worst_mo", "{}%", "hi")
    )
    th = "".join(f'<th class="r">{nm}</th>' for nm, _ in cols)

    # verdict — compare strategy to the best benchmark on money and on Sharpe
    best_mult = max(cols, key=lambda c: c[1]["multiple"])
    best_shp  = max(cols, key=lambda c: c[1]["inv_sharpe"])
    verdict = (
        f"Fully invested, the adaptive strategy ({st['multiple']}×, Sharpe {st['inv_sharpe']}, {st['maxdd_pct']}% drawdown) "
        f"essentially replicated Buy &amp; Hold TQQQ — the regime-switching added no risk-adjusted value. "
    )
    if cap:
        verdict += (
            f"<strong>But capping each ETF at 25% every December (excess → cash) is a real improvement:</strong> it "
            f"<strong>halved the drawdown ({st['maxdd_pct']}% → {cap['maxdd_pct']}%)</strong> and lifted the Sharpe to "
            f"<strong>{cap['inv_sharpe']}</strong> (the best of any leveraged variant), while still compounding to "
            f"{cap['multiple']}× — more than 2× Buy &amp; Hold QQQ ({bm.get('QQQ',{}).get('multiple','?')}×). "
            f"You give up raw return ({st['multiple']}× → {cap['multiple']}×) to buy a far more survivable ride. "
        )
    verdict += (
        f"Unleveraged <strong>{best_shp[0]}</strong> still has the highest Sharpe overall ({best_shp[1]['inv_sharpe']}, "
        f"{best_shp[1]['maxdd_pct']}% drawdown). The takeaway: <strong>rebalancing/​capping concentration is the optimization that "
        f"actually moves risk-adjusted return</strong> — far more than the regime-switching does."
    )

    dist = s.get("regime_distribution", {})
    dist_order = ["euphoria","bull","chop","fear1","fear2"]
    dcol = {"euphoria":"var(--orange)","bull":"var(--green)","chop":"var(--amber)","fear1":"var(--red)","fear2":"var(--purple)"}
    dist_rows = "".join(
        f'<div class="alloc-bar-row"><div class="alloc-t" style="color:{dcol[k]};width:70px">{k}</div>'
        f'<div class="alloc-track"><div class="alloc-fill" style="width:{dist.get(k,0)/s["months"]*100:.0f}%;background:{dcol[k]}"></div></div>'
        f'<div class="alloc-p">{dist.get(k,0)}</div></div>'
        for k in dist_order if dist.get(k,0) > 0)

    return f"""
    <div class="card" style="margin-bottom:12px;border-left:3px solid var(--amber)">
      <div style="font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--amber);margin-bottom:6px">Verdict</div>
      <div style="font-size:13px;line-height:1.8;color:var(--ink)">{verdict}</div>
    </div>

    {_render_equity_chart(s.get("curve"))}

    {_render_alloc_chart(s.get("alloc"))}

    {_render_alloc_chart(s.get("alloc_capped"),
        title="With the 25% cap (Adaptive + cash) · composition incl. cash",
        note="Same strategy, but each December any ETF above 25% of the portfolio is trimmed to cash (grey band). "
             "No single position runs away — SOXL/TQQQ are held to 25% each and the trimmed gains build a growing cash buffer. "
             "This is what halved the drawdown.") if s.get("alloc_capped") else ""}

    <div class="card" style="margin-bottom:12px">
      <div class="bt-scroll" style="max-height:none">
        <table class="tbl">
          <thead><tr><th>Metric</th>{th}</tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
      <div class="note">Green = best in row. All columns receive an identical ${s['monthly_contribution']:,}/month; only the
      holdings differ. Each B&amp;H column = that ETF bought every month and never sold. Max drawdown is on the
      time-weighted (contribution-neutral) return index.</div>
    </div>

    <div class="grid2">
      <div class="card">
        <div class="sec-title" style="margin-bottom:10px">Two Sharpe ratios — what they mean</div>
        <div style="font-size:12px;line-height:1.8;color:var(--muted)">
          <strong style="color:var(--ink)">Investment Sharpe</strong> weights every month equally — pure strategy skill, independent of when you added cash.<br><br>
          <strong style="color:var(--ink)">Contribution Sharpe</strong> weights each month by the dollars at work — the "growth of the asset" view that reflects your real DCA experience (returns matter most once the pot is large).
        </div>
      </div>
      <div class="card">
        <div class="sec-title" style="margin-bottom:10px">Strategy months in each regime ({s['months']} total)</div>
        {dist_rows}
      </div>
    </div>

    {_render_monthly(s.get("monthly"))}

    <div class="note" style="margin-top:12px">Window {s['start']} → {s['end']} ({s['years']} yrs). Of the strategy's final NAV,
    <strong>{s['growth_pct_of_final']}%</strong> is market growth and the rest is contributed capital.</div>
    """


def _render_legend() -> str:
    out = ""
    for cat, items in LEGEND:
        out += f'<div class="sec-title" style="margin-top:22px">{cat}</div>'
        for it in items:
            rows = "".join(
                f'<tr><td style="white-space:nowrap;font-weight:600">{v}</td>'
                f'<td><span style="display:inline-block;width:7px;height:7px;border-radius:50%;'
                f'background:{_BANDCOLOR[c]};margin-right:7px"></span>{m}</td></tr>'
                for v, m, c in it["bands"])
            out += f"""
            <div class="card" style="margin-bottom:12px">
              <div style="display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:6px">
                <div style="font-size:14px;font-weight:700">{it['name']}</div>
                <div style="font-size:10px;font-weight:600;letter-spacing:.5px;text-transform:uppercase;color:var(--muted)">{it['tag']}</div>
              </div>
              <div style="font-size:12.5px;line-height:1.7;color:var(--ink);margin-top:8px">{it['what']}</div>
              <div style="font-size:12px;line-height:1.7;color:var(--muted);margin-top:8px"><strong style="color:var(--ink)">How it's measured:</strong> {it['calc']}</div>
              <table class="tbl" style="margin-top:10px">
                <thead><tr><th style="width:34%">Value</th><th>What it means</th></tr></thead>
                <tbody>{rows}</tbody>
              </table>
              <div style="font-size:11.5px;line-height:1.7;color:var(--muted);margin-top:10px;padding-top:10px;border-top:1px solid var(--s1)"><strong style="color:var(--ink)">In this framework:</strong> {it['use']}</div>
            </div>"""
    # concepts
    out += '<div class="sec-title" style="margin-top:22px">Key Concepts</div>'
    out += '<div class="card"><div class="sig-list">'
    for title, body in LEGEND_CONCEPTS:
        out += (f'<div style="padding:11px 0;border-bottom:1px solid var(--s1)">'
                f'<div style="font-size:13px;font-weight:700;margin-bottom:3px">{title}</div>'
                f'<div style="font-size:12px;line-height:1.7;color:var(--muted)">{body}</div></div>')
    out += '</div></div>'
    return out


def _render_tips() -> str:
    cats = {}
    for cat, color, title, body in INVESTMENT_TIPS:
        cats.setdefault((cat, color), []).append((title, body))
    blocks = ""
    for (cat, color), items in cats.items():
        rows = "".join(
            f"""<div class="tip-row">
                  <div class="tip-title">{t}</div>
                  <div class="tip-body">{b}</div>
                </div>""" for t, b in items)
        blocks += f"""<div class="tip-group" style="border-left-color:{color}">
            <div class="tip-cat" style="color:{color}">{cat}</div>
            {rows}
          </div>"""
    return blocks


def _rvol_color(pct):
    if pct is None:        return "var(--muted)"
    if pct < 33:           return "var(--green)"
    if pct < 66:           return "var(--amber)"
    if pct < 90:           return "var(--red)"
    return "var(--purple)"

def _rvol_word(pct):
    if pct is None:  return "N/A"
    if pct < 33:     return "Calm"
    if pct < 66:     return "Normal"
    if pct < 90:     return "Elevated"
    return "Extreme"

def _rvol_card(name, rvol, pct):
    c = _rvol_color(pct)
    rv_s  = f"{rvol:.0f}%" if rvol is not None else "N/A"
    pct_s = f"{pct:.0f}th pctile" if pct is not None else "—"
    barw  = pct if pct is not None else 0
    return f"""
    <div class="card" style="flex:1">
      <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px">
        <div style="font-size:12px;font-weight:600">{name} · 1-month realized vol</div>
        <div style="font-size:10px;font-weight:700;color:{c};text-transform:uppercase;letter-spacing:.5px">{_rvol_word(pct)}</div>
      </div>
      <div style="display:flex;align-items:baseline;gap:10px;margin-bottom:8px">
        <div style="font-family:'Syne',sans-serif;font-size:26px;font-weight:800;color:{c}">{rv_s}</div>
        <div style="font-size:11px;color:var(--muted)">annualized · {pct_s} of all history</div>
      </div>
      <div class="sig-bar-track" style="height:6px"><div class="sig-bar-fill" style="width:{barw}%;background:{c}"></div></div>
    </div>"""

def _rvol_interpretation(regime, qpct, spct):
    if qpct is None or spct is None:
        return "Realized-volatility data unavailable this run."
    avg = (qpct + spct) / 2
    gap = spct - qpct
    if avg >= 66:
        base = ("Actual price swings are <strong>elevated</strong> — and high realized volatility is exactly when "
                "leveraged ETFs bleed the most to decay. This reinforces staying OUT of TQQQ/SOXL.")
        if regime in ("bull", "euphoria"):
            base += " It also sits oddly against a low-VIX read: the market is moving a lot even while option-implied fear is muted."
    elif avg < 33:
        base = ("Markets are genuinely <strong>calm</strong> — small actual price swings, the friendliest tape for holding leverage.")
        if regime in ("bull", "euphoria"):
            base += " But calm + cheap options (low VIX) is also the classic complacency setup — watch the euphoria/valuation flags."
    else:
        base = "Realized volatility is in its <strong>normal</strong> historical range — neither calm nor stressed."
    if gap >= 25:
        base += (f" Semiconductors (SMH, {spct:.0f}th pctile) are far more turbulent than the broad Nasdaq (QQQ, {qpct:.0f}th) — "
                 "a specific warning against SOXL, the 3× semis fund.")
    return base


def _vol_valuation_signal(rvpct, cape, cape_score):
    """The volatility x valuation quadrant — the key synthesis.
    Returns (icon, headline, color, message) or None."""
    if rvpct is None or cape is None:
        return None
    hi_vol    = rvpct >= 66
    lo_vol    = rvpct < 40
    expensive = cape_score >= 2          # CAPE >= 34 (Extreme/Bubble)
    cheap     = cape_score == 0          # CAPE < 28
    cv = f"CAPE {cape}"
    rv = f"realized vol {rvpct:.0f}th pctile"
    if hi_vol and expensive:
        return ("🔴", "Bubble-bursting risk", "var(--red)",
            f"High volatility ({rv}) WHILE valuations are extreme ({cv}). Historically the most dangerous "
            f"combination — stress hitting an expensive market, as in 2000–02. Favor defense: pause new leverage, "
            f"trim into bounces, build the reserve.")
    if hi_vol and cheap:
        return ("🟢", "Stress + cheap = opportunity", "var(--green)",
            f"High volatility ({rv}) at LOW valuations ({cv}). Historically a great accumulation backdrop — "
            f"fear is high but you are not overpaying (e.g. late 2008–09). This is when the framework's "
            f"fear-buying earns its returns.")
    if lo_vol and expensive:
        return ("🟠", "Complacency at extremes", "var(--orange)",
            f"Calm markets ({rv}) at extreme valuations ({cv}). The classic late-cycle top setup — quiet and "
            f"expensive, as in 2021. Watch the euphoria and valuation flags closely.")
    if lo_vol and cheap:
        return ("🟢", "Calm and cheap", "var(--green)",
            f"Low volatility ({rv}) and low valuations ({cv}) — the healthiest backdrop for steady accumulation.")
    return ("⚪", "Mixed", "var(--muted)",
        f"{rv}, {cv}. No clear volatility×valuation extreme — read the individual signals above.")


def _render_quadrant(cape, qrv_p):
    """2×2 volatility × valuation map with a 'NOW' marker plotted continuously."""
    if cape is None or qrv_p is None:
        return ""
    qx   = max(6, min(94, (cape - 12) / (44 - 12) * 100))   # x: cheap→expensive
    qtop = max(10, min(90, 100 - qrv_p))                    # y: high vol at top
    expensive = cape >= 28
    hivol     = qrv_p >= 50
    active = ("tr" if expensive and hivol else "tl" if hivol
              else "br" if expensive else "bl")
    cells = {
        "tl": ("🟢","OPPORTUNITY","High vol · cheap — stress at low prices (e.g. 2008–09)","var(--green)","var(--green-bg)"),
        "tr": ("🔴","BUBBLE BURSTING","High vol · expensive — stress at extreme prices (e.g. 2000)","var(--red)","var(--red-bg)"),
        "bl": ("🟢","ACCUMULATE","Low vol · cheap — calm and inexpensive","var(--green)","var(--green-bg)"),
        "br": ("🟠","COMPLACENCY","Low vol · expensive — quiet top setup (e.g. 2021)","var(--orange)","var(--orange-bg)"),
    }
    def cell(k):
        ic, ttl, sub, col, bg = cells[k]
        act = " active" if k == active else ""
        op  = "1" if k == active else "0.55"
        return (f'<div class="qcell {k}{act}" style="color:{col};background:{bg};opacity:{op}">'
                f'<div class="qicon">{ic}</div><div class="qttl" style="color:{col}">{ttl}</div>'
                f'<div class="qsub">{sub}</div></div>')
    label_top = max(5, qtop - 12)
    return f"""
    <div style="font-size:10px;color:var(--muted);font-weight:600;text-align:center;margin-bottom:4px">↑ HIGHER REALIZED VOLATILITY</div>
    <div class="quad-box">
      {cell("tl")}{cell("tr")}{cell("bl")}{cell("br")}
      <div class="quad-now" style="left:{qx:.0f}%;top:{label_top:.0f}%">● YOU ARE HERE</div>
      <div class="quad-marker" style="left:{qx:.0f}%;top:{qtop:.0f}%"></div>
    </div>
    <div style="font-size:10px;color:var(--muted);font-weight:600;text-align:center;margin-top:4px">↓ LOWER REALIZED VOLATILITY</div>
    <div class="quad-axis-x">CHEAPER &nbsp;←&nbsp; VALUATION (Shiller CAPE) &nbsp;→&nbsp; MORE EXPENSIVE</div>
    """


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
    if regime == "euphoria":
        return "Overheated — pause new DCA, divert this month's cash to your reserve, and trim leverage slowly into strength."
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
    if regime == "euphoria":
        return (f"A complacent melt-up: VIX {vix:.1f} (low/complacent), QQQ {d['above_200ma_pct']:+.1f}% above its 200-day MA, "
                f"RSI {d['rsi']:.1f}, 12-month return {d['return_12m_pct']:+.1f}%. This is a fast caution flag — overheating, "
                f"not a crash call. Markets can stay euphoric for months, so do NOT short the top. Instead: "
                f"(1) pause new DCA — divert this month's budget to your T-bill reserve, building dry powder for the next Fear II; "
                f"(2) trim leveraged positions slowly into strength (SOXL first, then TQQQ) if the Profit-Taking or Valuation "
                f"warnings are also elevated; (3) never sell QQQ. The framework resumes Bull DCA automatically once signals cool.")
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
    cape    = d.get("cape")
    tg      = d.get("tqqq_gain_pct")
    qrv     = d.get("qqq_rvol");  qrv_p = d.get("qqq_rvol_pct")
    srv     = d.get("smh_rvol");  srv_p = d.get("smh_rvol_pct")
    _bt     = _load_backtest()
    n_hist  = len(history)

    consec = 0
    for s in reversed(history):
        if s == raw: consec += 1
        else: break

    rc   = REGIME_COLOR[regime]
    rcls = regime
    rlabel = {
        "euphoria": "🟠 EUPHORIA · Overheated",
        "bull":  "🟢 BULL · Trending Up",
        "chop":  "🟡 CHOP · Sideways",
        "fear1": "🔴 FEAR I · Panic Buying",
        "fear2": "🟣 FEAR II · Crash",
    }[regime]

    # Euphoria signal count (always compute for display)
    et = EUPHORIA_THRESHOLDS
    euph_signals = sum([
        vix             < et["vix_max"],
        abv_pct         > et["above_200ma_min"],
        rsi             > et["rsi_min"],
        ret12m          > et["ret_12m_min"],
    ])
    euph_details = [
        (f"VIX {vix:.1f} &lt; {et['vix_max']}",                vix             < et["vix_max"]),
        (f"QQQ {_p(abv_pct)} above its 200-day MA (&gt;{et['above_200ma_min']}%)", abv_pct > et["above_200ma_min"]),
        (f"QQQ RSI-35 {rsi:.1f} &gt; {et['rsi_min']}",        rsi             > et["rsi_min"]),
        (f"QQQ 12-month return {_p(ret12m)} &gt; {et['ret_12m_min']}%", ret12m  > et["ret_12m_min"]),
    ]
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
        _sig_row("QQQ drawdown from 52W high", _bar(abs(dd),0,50),    "var(--green)"if dd>-10 else"var(--amber)", _p(dd),       "bg"if dd>-10 else"ba", "✅ Near high"if dd>-10 else"⚠️ In drawdown") +
        _sig_row("QQQ RSI 35-day",         rsi,                   "var(--green)"if 45<=rsi<=75 else"var(--amber)", f"{rsi:.1f}", "bg"if 45<=rsi<=75 else"ba", "✅ Healthy"if 45<=rsi<=75 else"⚠️ Out of range") +
        _sig_row("QQQ MACD (12/26/9)",     75 if macd_b else 25,  "var(--green)"if macd_b else"var(--red)",  "Bullish"if macd_b else"Bearish", "bg"if macd_b else"br", "✅ Bullish"if macd_b else"❌ Bearish") +
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
    cape_v = f"{cape}" if cape else "N/A"
    tg_v   = _p(tg) if tg else "No cost basis set"

    pt_sigs = (
        _pt_sig_row("QQQ P/E (trailing)",
                    "QQQ's trailing 12-month price-to-earnings ratio, sourced from Yahoo Finance. "
                    "Reflects the weighted P/E of all 100 Nasdaq-100 holdings. "
                    "Elevated readings mean the market is priced for perfection — any earnings miss hits hard. "
                    "Dot-com peak (2000): 54×. Note: thresholds were calibrated for forward P/E; use this as a directional signal.",
                    _bar(pe,15,60)if pe else 0, scores["qqq_pe_fwd"], pe_v, "38× · 45× · 52×") +
        _pt_sig_row("Shiller CAPE (valuation)",
                    "The cyclically-adjusted P/E of the S&P 500 — price ÷ 10-year inflation-adjusted average earnings. "
                    "The gold-standard long-term bubble gauge: it smooths out the earnings cycle, so it can't be "
                    "fooled by one good year. It hit an all-time-high of 44 right before the 2000 dot-com crash. "
                    "This is the one signal that catches a VALUATION bubble even when volatility is high and momentum looks fine.",
                    _bar(cape,15,45)if cape else 0, scores["cape"], cape_v, "28 · 34 · 40") +
        _pt_sig_row("RSI 35-day (QQQ)",
                    "QQQ's Relative Strength Index calculated on 35 trading days of daily closing prices. "
                    "RSI measures how fast and how much QQQ has risen vs fallen recently, on a 0–100 scale. "
                    "A 35-day window is deliberately slower than the standard 14-day — it filters out short-term noise "
                    "and better suits monthly DCA decisions. "
                    "Above 78: QQQ has been gaining unusually fast for an extended period — momentum is likely stretched.",
                    _bar(rsi,40,100), scores["rsi_35"], f"{rsi:.1f}", "78 · 83 · 88") +
        _pt_sig_row("QQQ distance above 200-day MA",
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

    # ── valuation warning display ──
    val        = pt["valuation"]
    val_score  = val["score"]
    val_label  = val["label"]
    val_color  = ["var(--green)","var(--amber)","var(--red)","var(--purple)"][val_score]
    val_cls    = ["hold","watch","caution","extreme"][val_score]
    cape_disp  = f"{cape:.1f}" if cape else "N/A"
    pe_disp    = f"{pe:.1f}×" if pe else "N/A"
    val_msg = {
        3: (f"⚠️ BUBBLE valuation. Shiller CAPE {cape_disp} sits near dot-com extremes "
            f"(the 2000 peak was 44, the all-time high). This is the gauge that caught the dot-com top. "
            f"Pause new buying and trim leverage into strength — not because a crash is imminent, but because "
            f"forward returns from here are historically poor and the downside is large."),
        2: (f"Valuations EXTREME. CAPE {cape_disp} is in the top 5% of 150+ years of history. "
            f"Crash risk is elevated; favor caution over fresh leverage."),
        1: (f"Valuations ELEVATED. CAPE {cape_disp} is above the 90th percentile — rich, but not yet bubble territory."),
        0: (f"Valuations normal. CAPE {cape_disp}, QQQ P/E {pe_disp} — no valuation warning."),
    }[val_score]
    val_eyebrow = {3:"🟣 Valuation Warning · BUBBLE", 2:"🔴 Valuation Warning · EXTREME",
                   1:"🟡 Valuation Warning · ELEVATED", 0:"✅ Valuation · Normal"}[val_score]

    # ── regime tab entry conditions ──
    bull_conds = (
        _cond("VIX",                "Below 20",             f"{vix:.1f}",          vix<20) +
        _cond("QQQ vs 200-day MA",  "Above MA",             f"{'Above'if above else'Below'} ({_p(abv_pct)})", above) +
        _cond("QQQ RSI 35-day",     "45 – 75",              f"{rsi:.1f}",          45<=rsi<=75) +
        _cond("QQQ MACD",           "Line above signal",    "Bullish"if macd_b else"Bearish", macd_b) +
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
        _cond("QQQ vs 200-day MA",  "Below (expected)",     f"{'Above'if above else'Below'}",  not above) +
        _cond("QQQ drawdown from 52w high", "15 – 35%",     _p(dd),                -35<=dd<=-15) +
        _cond("QQQ RSI 35-day",     "Oversold (25–45)",     f"{rsi:.1f}",          rsi<45) +
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
  --orange:#ea580c;--orange-bg:#fff7ed;--orange-border:#fed7aa;
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
.rec-box.euphoria{{border-color:var(--orange-border);background:var(--orange-bg)}}
.rec-box.bull {{border-color:var(--green-border); background:var(--green-bg)}}
.rec-box.chop {{border-color:var(--amber-border); background:var(--amber-bg)}}
.rec-box.fear1{{border-color:var(--red-border);   background:var(--red-bg)}}
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
.alert-banner.hold    {{border-color:var(--green-border); background:var(--green-bg)}}
.alert-banner.watch   {{border-color:var(--amber-border); background:var(--amber-bg)}}
.alert-banner.caution {{border-color:var(--red-border);   background:var(--red-bg)}}
.alert-banner.extreme {{border-color:var(--purple-border);background:var(--purple-bg)}}
.alert-banner.euphoria{{border-color:var(--orange-border);background:var(--orange-bg)}}

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

/* ── INVESTMENT TIPS ── */
.tips-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.tip-group{{background:var(--card);border:1px solid var(--border);border-left:3px solid;border-radius:8px;padding:14px 16px;box-shadow:var(--shadow-xs)}}
.tip-cat{{font-size:10px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:10px}}
.tip-row{{padding:8px 0;border-top:1px solid var(--s1)}}
.tip-row:first-of-type{{border-top:none;padding-top:0}}
.tip-title{{font-size:12.5px;font-weight:600;line-height:1.4;margin-bottom:3px}}
.tip-body{{font-size:11.5px;color:var(--muted);line-height:1.6}}
@media(max-width:600px){{.tips-grid{{grid-template-columns:1fr}}}}

/* ── VOL × VALUATION QUADRANT ── */
.quad-box{{position:relative;display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;aspect-ratio:1.9/1;border-radius:10px;overflow:hidden;border:1px solid var(--border)}}
.qcell{{padding:12px 14px;display:flex;flex-direction:column;justify-content:center;gap:3px;transition:opacity .2s}}
.qcell.tl{{border-right:1px dashed var(--border2);border-bottom:1px dashed var(--border2)}}
.qcell.tr{{border-bottom:1px dashed var(--border2)}}
.qcell.bl{{border-right:1px dashed var(--border2)}}
.qcell .qicon{{font-size:13px}}
.qcell .qttl{{font-size:11.5px;font-weight:800;letter-spacing:.2px}}
.qcell .qsub{{font-size:10px;color:var(--muted);line-height:1.4}}
.qcell.active{{box-shadow:inset 0 0 0 3px currentColor}}
.quad-marker{{position:absolute;width:16px;height:16px;border-radius:50%;background:var(--ink);border:3px solid #fff;box-shadow:0 0 0 2px var(--ink),0 3px 8px rgba(0,0,0,.35);transform:translate(-50%,-50%);z-index:20}}
.quad-now{{position:absolute;transform:translate(-50%,-50%);background:var(--ink);color:#fff;font-size:9px;font-weight:700;letter-spacing:.5px;padding:2px 7px;border-radius:5px;white-space:nowrap;z-index:21}}
.quad-axis-x{{text-align:center;font-size:10px;color:var(--muted);margin-top:5px;font-weight:600;letter-spacing:.5px}}

/* ── BACKTEST tables ── */
.bt-scroll{{overflow:auto;max-height:460px;border:1px solid var(--border);border-radius:8px}}
.bt-tbl{{font-size:11px}}
.bt-tbl th{{position:sticky;top:0;background:var(--card);z-index:2;white-space:nowrap;padding:7px 9px}}
.bt-tbl td{{white-space:nowrap;padding:7px 9px}}
.bt-tbl td.r,.bt-tbl th.r{{font-family:'IBM Plex Mono',monospace}}

/* ── MOBILE BOTTOM NAV ── */
.mobile-nav{{display:none;position:fixed;bottom:0;left:0;right:0;z-index:200;background:rgba(255,255,255,.96);border-top:1px solid var(--border);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);padding-bottom:env(safe-area-inset-bottom)}}
.mobile-nav-inner{{display:flex;overflow-x:auto;scrollbar-width:none}}
.mobile-nav-inner::-webkit-scrollbar{{display:none}}
.mnav-btn{{flex:1 0 auto;min-width:60px;display:flex;flex-direction:column;align-items:center;gap:3px;padding:8px 4px;font-size:9px;font-weight:600;letter-spacing:.3px;color:var(--muted);background:none;border:none;cursor:pointer;transition:color .15s ease}}
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
  <button class="ntab" onclick="tab('backtest',this)">Backtest</button>
  <button class="ntab" onclick="tab('tips',this)">Tips</button>
  <button class="ntab" onclick="tab('legend',this)">Legend</button>
</div>

<!-- MOBILE BOTTOM NAV -->
<div class="mobile-nav">
  <div class="mobile-nav-inner">
    <button class="mnav-btn active" onclick="tabM('dashboard',this)"><div class="mnav-icon">📊</div>Dashboard</button>
    <button class="mnav-btn" onclick="tabM('portfolio',this)"><div class="mnav-icon">💼</div>Portfolio</button>
    <button class="mnav-btn" onclick="tabM('regime',this)"><div class="mnav-icon">🗺️</div>Regime</button>
    <button class="mnav-btn" onclick="tabM('profit',this)"><div class="mnav-icon">⚠️</div>Profit</button>
    <button class="mnav-btn" onclick="tabM('allocations',this)"><div class="mnav-icon">📐</div>Alloc</button>
    <button class="mnav-btn" onclick="tabM('backtest',this)"><div class="mnav-icon">🧪</div>Backtest</button>
    <button class="mnav-btn" onclick="tabM('tips',this)"><div class="mnav-icon">💡</div>Tips</button>
    <button class="mnav-btn" onclick="tabM('legend',this)"><div class="mnav-icon">📖</div>Legend</button>
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
      <div style="font-family:'Syne',sans-serif;font-size:40px;font-weight:800;color:{ac};line-height:1;">{fire}/7</div>
      <div style="font-size:10px;color:var(--muted);">signals</div>
    </div>
  </div>

  <div class="sec-title">Valuation Warning <span style="color:var(--light);font-weight:400;letter-spacing:0">· catches valuation bubbles that momentum misses (e.g. 2000)</span></div>
  <div class="alert-banner {val_cls}">
    <div>
      <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:{val_color};margin-bottom:4px;">{val_eyebrow}</div>
      <div style="font-size:13px;line-height:1.7;color:var(--ink);max-width:680px;">{val_msg}</div>
    </div>
    <div style="text-align:center;padding-left:24px;flex-shrink:0;">
      <div style="font-family:'Syne',sans-serif;font-size:34px;font-weight:800;color:{val_color};line-height:1;">{cape_disp}</div>
      <div style="font-size:10px;color:var(--muted);">CAPE · P/E {pe_disp}</div>
    </div>
  </div>

  <div class="stat-row">
    <div class="stat-cell">
      <div class="stat-label">VIX</div>
      <div class="stat-val" style="color:{vix_sc}">{vix:.1f}</div>
      <div class="stat-sub">{vix_sub}</div>
    </div>
    <div class="stat-cell">
      <div class="stat-label">QQQ vs 200-day MA</div>
      <div class="stat-val" style="color:{ma_sc}">{_p(abv_pct)}</div>
      <div class="stat-sub">{ma_sub}</div>
    </div>
    <div class="stat-cell">
      <div class="stat-label">QQQ RSI 35-day</div>
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
      <thead><tr><th>Regime</th><th>Trigger</th><th>What it means</th><th class="r">New DCA</th><th class="r">Confirm</th></tr></thead>
      <tbody>
        <tr><td style="color:var(--orange);font-weight:700">🟠 EUPHORIA</td><td>Multi-signal (3 of 4)</td><td>Overheated — stop buying, monitor for profit-taking</td><td class="r" style="color:var(--orange)">$0 — pause DCA</td><td class="r">{CONFIRM["to_euphoria"]} months</td></tr>
        <tr><td style="color:var(--green);font-weight:700">🟢 BULL</td><td>VIX &lt; 20</td><td>Trending up — leverage is fully justified</td><td class="r">TQQQ 50% + SOXL 50%</td><td class="r">{CONFIRM["to_bull"]} months</td></tr>
        <tr><td style="color:var(--amber);font-weight:700">🟡 CHOP</td><td>VIX 20–30</td><td>Sideways — decay erodes 3× ETFs, hold don't sell</td><td class="r">QQQ 50% + SMH 50%</td><td class="r">{CONFIRM["to_chop"]} month</td></tr>
        <tr><td style="color:var(--red);font-weight:700">🔴 FEAR I</td><td>VIX 30–45</td><td>Panic — leveraged ETFs at maximum discount</td><td class="r">TQQQ 50% + SOXL 50%</td><td class="r">{CONFIRM["to_fear1"]} month</td></tr>
        <tr><td style="color:var(--purple);font-weight:700">🟣 FEAR II</td><td>VIX &gt; 45</td><td>Crash — once-per-decade entry, triple budget</td><td class="r">Your choice (see Regime Guide)</td><td class="r">Immediate</td></tr>
      </tbody>
    </table>

    <!-- Euphoria multi-signal tracker -->
    <div style="margin-top:14px;padding:14px 16px;border-radius:8px;border:1.5px solid {'var(--orange-border)' if regime=='euphoria' else 'var(--border)'};background:{'var(--orange-bg)' if regime=='euphoria' else 'var(--s1)'}">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
        <div style="font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:{'var(--orange)' if regime=='euphoria' else 'var(--muted)'}">
          🟠 Euphoria Multi-Signal Tracker — {euph_signals}/{EUPHORIA_SIGNALS_REQUIRED} required to trigger
        </div>
        <div style="font-size:11px;font-weight:700;color:{'var(--orange)' if euph_signals>=EUPHORIA_SIGNALS_REQUIRED else 'var(--muted)'}">
          {'⚡ ACTIVE' if euph_signals>=EUPHORIA_SIGNALS_REQUIRED else f'{euph_signals}/4 signals'}
        </div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">
        {''.join(f"""<div style="display:flex;align-items:center;gap:8px;font-size:11px;padding:6px 8px;border-radius:6px;background:rgba(255,255,255,0.7)">
          <div style="width:8px;height:8px;border-radius:50%;background:{'var(--orange)' if ok else 'var(--border2)'};flex-shrink:0"></div>
          <span style="color:{'var(--ink)' if ok else 'var(--muted)'}">{label}</span>
        </div>""" for label, ok in euph_details)}
      </div>
    </div>
  </div>
  <div class="card">
    <div class="sig-list">{regime_sigs}</div>
    <div class="reg-summary" style="border-color:{rc};color:{rc}">{reg_summary}</div>
  </div>

  <div class="sec-title" style="margin-top:24px">Realized Volatility <span style="color:var(--light);font-weight:400;letter-spacing:0">· actual price movement vs VIX's implied fear</span></div>
  <div style="display:flex;gap:12px;flex-wrap:wrap">
    {_rvol_card("QQQ", qrv, qrv_p)}
    {_rvol_card("SMH", srv, srv_p)}
  </div>
  <div class="reg-summary" style="border-color:{_rvol_color((qrv_p+srv_p)/2) if (qrv_p is not None and srv_p is not None) else 'var(--border)'};color:var(--ink);margin-top:12px">
    {_rvol_interpretation(regime, qrv_p, srv_p)}
  </div>

  <div class="sec-title" style="margin-top:24px">Volatility × Valuation Map</div>
  <div class="card">
    {_render_quadrant(qrv_p, cape)}
  </div>
  {(lambda s: f'''
  <div class="card" style="margin-top:12px;border-left:3px solid {s[2]}">
    <div style="font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:{s[2]};margin-bottom:6px">
      {s[0]} Current read · {s[1]}
    </div>
    <div style="font-size:13px;line-height:1.7;color:var(--ink)">{s[3]}</div>
  </div>''' if s else '')(_vol_valuation_signal(qrv_p, cape, pt["scores"]["cape"]))}

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
    <button class="rtab{ra('euphoria')}" onclick="switchR('euphoria',this)">🟠 Euphoria · Overheated</button>
    <button class="rtab{ra('bull')}"     onclick="switchR('bull',this)">🟢 Bull · Trending</button>
    <button class="rtab{ra('chop')}"     onclick="switchR('chop',this)">🟡 Chop · Sideways</button>
    <button class="rtab{ra('fear1')}"    onclick="switchR('fear1',this)">🔴 Fear I · Panic</button>
    <button class="rtab{ra('fear2')}"    onclick="switchR('fear2',this)">🟣 Fear II · Crash</button>
  </div>

  <!-- EUPHORIA -->
  <div class="rpanel{ra('euphoria')}" id="rp-euphoria">
    <div class="rec-box euphoria" style="margin-bottom:16px">
      <div class="rec-eyebrow" style="color:var(--orange)">🟠 Euphoria · Multi-signal · 3 of 4 required{'  ·  Currently Active' if regime=='euphoria' else ''}</div>
      <div class="rec-headline">Market overheated — stop new DCA, protect your gains</div>
      <div class="rec-desc">Multiple signals are firing simultaneously that historically appear near market peaks. This is not a prediction of a crash — markets can stay euphoric for months. But deploying new capital with full leverage at these levels means buying near the top with maximum downside exposure. The right move: pause new DCA, hold existing positions, and use the Profit-Taking monitor to decide whether to trim.</div>
    </div>
    <div class="grid2">
      <div class="card">
        <div class="sec-title" style="margin-bottom:12px">Euphoria conditions · today's values</div>
        <table class="tbl"><thead><tr><th>Signal</th><th class="r">Threshold (need 3 of 4)</th><th class="r">Today</th></tr></thead>
        <tbody>
          {_cond("VIX", f"Below {EUPHORIA_THRESHOLDS['vix_max']}", f"{vix:.1f}", vix < EUPHORIA_THRESHOLDS["vix_max"])}
          {_cond("QQQ above 200-day MA", f"Above +{EUPHORIA_THRESHOLDS['above_200ma_min']}%", _p(abv_pct), abv_pct > EUPHORIA_THRESHOLDS["above_200ma_min"])}
          {_cond("QQQ RSI 35-day", f"Above {EUPHORIA_THRESHOLDS['rsi_min']}", f"{rsi:.1f}", rsi > EUPHORIA_THRESHOLDS["rsi_min"])}
          {_cond("QQQ 12-month return", f"Above +{EUPHORIA_THRESHOLDS['ret_12m_min']}%", _p(ret12m), ret12m > EUPHORIA_THRESHOLDS["ret_12m_min"])}
          {_cond("Signals firing", f"{EUPHORIA_SIGNALS_REQUIRED}+ of 4", f"{euph_signals}/4", euph_signals >= EUPHORIA_SIGNALS_REQUIRED)}
          {_cond("Confirmation", f"{CONFIRM['to_euphoria']} consecutive months", f"{consec} month{'s' if consec!=1 else ''}", consec >= CONFIRM["to_euphoria"] and regime == "euphoria")}
        </tbody></table>
      </div>
      <div class="card">
        <div class="sec-title" style="margin-bottom:12px">Action in Euphoria</div>
        <div style="font-size:13px;line-height:1.9">
          <div style="padding:12px;background:var(--orange-bg);border:1px solid var(--orange-border);border-radius:8px;margin-bottom:12px;color:var(--orange);font-weight:600">
            💰 New DCA this month: $0 — pause completely
          </div>
          <div style="font-size:12px;color:var(--muted);line-height:1.8">
            ✅ <strong>Hold</strong> all existing TQQQ, SOXL, QQQ, SMH positions<br>
            📊 <strong>Monitor</strong> the Profit-Taking tab weekly<br>
            ✂️ <strong>Trim</strong> only if Profit-Taking reaches CAUTION (4+ signals)<br>
            🔄 <strong>Resume</strong> DCA when euphoria signals drop below {EUPHORIA_SIGNALS_REQUIRED} of 4<br><br>
            <span style="color:var(--ink)">Euphoria reverts to Bull after 1 month of normalized signals.</span>
          </div>
        </div>
        <div class="note">Cannot jump from Euphoria to Fear without passing through Bull → Chop first. Euphoria requires 2 confirmed months before activating.</div>
      </div>
    </div>
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

  <!-- Current regime indicator -->
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;padding:14px 18px;background:var(--card);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow-xs)">
    <div style="width:12px;height:12px;border-radius:50%;background:{rc};box-shadow:0 0 0 3px {rc}33;flex-shrink:0"></div>
    <div>
      <div style="font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--muted);margin-bottom:2px">Current Regime</div>
      <div style="font-size:14px;font-weight:700;color:{rc}">{rlabel}</div>
    </div>
    <div style="margin-left:auto;font-size:11px;color:var(--muted);text-align:right">
      VIX {vix:.1f} · {n_hist} month{'s' if n_hist!=1 else ''} of history
    </div>
  </div>

  <div class="alert-banner {acls}" style="margin-bottom:20px">
    <div>
      <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:{ac};margin-bottom:4px">{pt_eyebrow}</div>
      <div style="font-size:15px;font-weight:600;margin-bottom:4px">{pt_hl}</div>
      <div style="font-size:12px;color:var(--muted)">{pt["action"]}</div>
    </div>
    <div style="padding-left:20px;flex-shrink:0;text-align:center">
      <div style="font-family:'Syne',sans-serif;font-size:44px;font-weight:800;color:{ac};line-height:1">{fire}/7</div>
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
        <span style="color:var(--red)">4–6 firing → CAUTION</span> — trim 15–25% of SOXL, then TQQQ<br>
        <span style="color:var(--purple)">7 firing → EXTREME</span> — trim 40–60% of all leveraged
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
      <thead><tr>
        <th>Indicator</th>
        <th class="r" style="color:var(--green)">✅ Normal</th>
        <th class="r" style="color:var(--amber)">🟡 Elevated</th>
        <th class="r" style="color:var(--red)">🔴 Extreme</th>
        <th class="r" style="color:var(--purple)">🟣 Bubble</th>
      </tr></thead>
      <tbody>
        <tr><td>QQQ P/E (trailing)</td><td class="r" style="color:var(--green)">below 38×</td><td class="r">38×+</td><td class="r">45×+</td><td class="r">52×+</td></tr>
        <tr style="background:var(--s1)"><td><strong>Shiller CAPE (valuation ★)</strong></td><td class="r" style="color:var(--green)">below 28</td><td class="r">28+</td><td class="r">34+</td><td class="r">40+ (dot-com=44)</td></tr>
        <tr><td>RSI 35-day (QQQ daily closes)</td><td class="r" style="color:var(--green)">below 78</td><td class="r">78+</td><td class="r">83+</td><td class="r">88+</td></tr>
        <tr><td>QQQ distance above 200-day MA</td><td class="r" style="color:var(--green)">below 30%</td><td class="r">30%+</td><td class="r">40%+</td><td class="r">50%+</td></tr>
        <tr>
          <td>
            VIX complacency
            <div style="font-size:10px;color:var(--amber);margin-top:2px;font-weight:500">
              ⚠️ Inverted — unusually LOW VIX is the warning. Low VIX = nobody buying protection = complacency.
            </div>
          </td>
          <td class="r" style="color:var(--green)">VIX ≥ 13<br><span style="font-size:10px;color:var(--muted)">(calm, normal)</span></td>
          <td class="r">VIX &lt; 13<br><span style="font-size:10px;color:var(--muted)">(complacent)</span></td>
          <td class="r">VIX &lt; 11<br><span style="font-size:10px;color:var(--muted)">(very complacent)</span></td>
          <td class="r">VIX &lt; 10<br><span style="font-size:10px;color:var(--muted)">(extreme)</span></td>
        </tr>
        <tr><td>12-month QQQ return</td><td class="r" style="color:var(--green)">below 50%</td><td class="r">50%+</td><td class="r">65%+</td><td class="r">80%+</td></tr>
        <tr><td>TQQQ gain vs your cost basis</td><td class="r" style="color:var(--green)">below 200%</td><td class="r">200%+</td><td class="r">400%+</td><td class="r">700%+</td></tr>
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

<!-- ══════════ BACKTEST ══════════ -->
<div class="panel" id="panel-backtest">
  <div class="sec-title">Backtest · Adaptive Strategy vs Buy &amp; Hold</div>
  <div class="card" style="margin-bottom:12px">
    <div style="font-size:12.5px;line-height:1.8;color:var(--muted)">
      Apples-to-apples backtest: the adaptive strategy is run <strong>fully invested</strong> — no cash, no
      profit-taking sells — so it is directly comparable to always-invested Buy &amp; Hold. Each month the full
      ${MONTHLY_BUDGET:,} contribution buys the regime's target ETFs (bull/fear → TQQQ+SOXL, chop/euphoria → QQQ+SMH),
      from the first month all four ETFs existed.
    </div>
  </div>
  {_render_backtest(_bt)}
</div>

<!-- ══════════ TIPS ══════════ -->
<div class="panel" id="panel-tips">
  <div class="sec-title">💡 Investment Tips · Hard-Won Wisdom</div>
  <div class="card" style="margin-bottom:12px">
    <div style="font-size:12.5px;line-height:1.8;color:var(--muted)">
      Distilled from strategy reviews — the principles behind this framework, grouped by theme.
      Revisited periodically as the strategy evolves.
    </div>
  </div>
  <div class="tips-grid">
    {_render_tips()}
  </div>
</div>

<!-- ══════════ LEGEND ══════════ -->
<div class="panel" id="panel-legend">
  <div class="sec-title">Indicator Legend · How Everything Works</div>
  <div class="card" style="margin-bottom:6px">
    <div style="font-size:12.5px;line-height:1.8;color:var(--muted)">
      Every technical indicator used across this dashboard, what it measures, how it's calculated, and what each
      value range signals. Colored dots match the thresholds used in the regime and profit-taking logic.
    </div>
  </div>
  {_render_legend()}
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
