from datetime import datetime
from config import COST_BASIS, HOLDINGS

REGIME_CSS = {
    "bull":  {"color": "#22c55e", "bg": "#052e16", "label": "🟢 BULL · Trending Up"},
    "chop":  {"color": "#eab308", "bg": "#1c1917", "label": "🟡 CHOP · Sideways"},
    "fear1": {"color": "#ef4444", "bg": "#2d0a0a", "label": "🔴 FEAR I · Panic Buying"},
    "fear2": {"color": "#a855f7", "bg": "#1a0030", "label": "🟣 FEAR II · Crash"},
}

ALERT_CSS = {
    "HOLD":    {"color": "#22c55e"},
    "WATCH":   {"color": "#eab308"},
    "CAUTION": {"color": "#ef4444"},
    "EXTREME": {"color": "#a855f7"},
}

SCORE_CSS = [
    {"color": "#22c55e", "label": "✅ Normal"},
    {"color": "#eab308", "label": "🟡 Elevated"},
    {"color": "#ef4444", "label": "🔴 Extreme"},
    {"color": "#a855f7", "label": "🟣 Bubble"},
]


def _pct(v, decimals=1):
    if v is None:
        return "N/A"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.{decimals}f}%"


def generate_html(d, regime, alloc, budget, pt, raw, history) -> str:
    now   = datetime.now().strftime("%Y-%m-%d %H:%M")
    today = datetime.now().strftime("%Y-%m-%d")

    rc = REGIME_CSS[regime]
    ac = ALERT_CSS[pt["alert_level"]]

    # ── price rows ──
    prices_map = {
        "QQQ": d["qqq_price"], "TQQQ": d["tqqq_price"],
        "SMH": d["smh_price"], "SOXL": d["soxl_price"],
    }
    price_rows = ""
    for etf, price in prices_map.items():
        cost   = COST_BASIS.get(etf, 0)
        shares = HOLDINGS.get(etf, 0)
        gain   = ((price / cost) - 1) * 100 if cost > 0 else None
        val    = shares * price if shares > 0 else None
        gain_s = _pct(gain) if gain is not None else "—"
        gc     = "#22c55e" if (gain or 0) >= 0 else "#ef4444"
        price_rows += f"""
        <tr>
          <td class="bold">{etf}</td>
          <td>${price:,.2f}</td>
          <td>{"${:,.2f}".format(cost) if cost > 0 else "—"}</td>
          <td style="color:{gc}">{gain_s}</td>
          <td>{"$" + f"{shares:,}" if shares > 0 else "—"}</td>
          <td>{"${:,.0f}".format(val) if val else "—"}</td>
        </tr>"""

    # ── regime indicator rows ──
    ri_rows = [
        ("VIX", f"{d['vix']:.1f}",
         ("✅ Bull zone", "#22c55e") if d["vix"] < 20 else ("🔴 Chop/Fear", "#ef4444")),
        ("QQQ vs 200-day MA",
         f"{'Above' if d['above_200ma'] else 'Below'} ({_pct(d['above_200ma_pct'])})",
         ("✅ Trending up", "#22c55e") if d["above_200ma"] else ("❌ Below 200MA", "#ef4444")),
        ("Drawdown from high", _pct(d["drawdown_pct"]),
         ("✅ Near high", "#22c55e") if d["drawdown_pct"] > -10 else ("⚠️ In drawdown", "#eab308")),
        ("RSI 14-day (QQQ)", f"{d['rsi']:.1f}",
         ("✅ Healthy", "#22c55e") if 45 <= d["rsi"] <= 75 else ("⚠️ Outside range", "#eab308")),
        ("MACD", "Bullish" if d["macd_bull"] else "Bearish",
         ("✅ Above signal", "#22c55e") if d["macd_bull"] else ("❌ Below signal", "#ef4444")),
        ("SMH vs QQQ (20d RS)", _pct(d["smh_rs_gap"]),
         ("✅ Semi leading", "#22c55e") if d["smh_rs_gap"] > -3 else ("⚠️ Semi lagging", "#eab308")),
    ]
    regime_rows = ""
    for label, val, (status, color) in ri_rows:
        regime_rows += f"""
        <tr>
          <td>{label}</td><td>{val}</td>
          <td style="color:{color}">{status}</td>
        </tr>"""

    # ── profit-taking rows ──
    pt_labels = {
        "qqq_pe_fwd":      ("QQQ Forward P/E",  f"{d.get('qqq_pe_fwd') or 'N/A'}×",  "38× / 45× / 52×"),
        "rsi_14":          ("RSI 14-day",        f"{d['rsi']:.1f}",                   "78 / 83 / 88"),
        "above_200ma_pct": ("Above 200MA",       _pct(d["above_200ma_pct"]),           "30% / 40% / 50%"),
        "vix_low":         ("VIX complacency",   f"{d['vix']:.1f}",                   "&lt;13 / &lt;11 / &lt;10"),
        "return_12m_pct":  ("12M QQQ return",    _pct(d["return_12m_pct"]),            "50% / 65% / 80%"),
        "tqqq_gain_pct":   ("TQQQ gain vs cost", _pct(d.get("tqqq_gain_pct")),         "200% / 400% / 700%"),
    }
    pt_rows = ""
    for key, (label, val, threshold) in pt_labels.items():
        sc = SCORE_CSS[pt["scores"][key]]
        pt_rows += f"""
        <tr>
          <td>{label}</td><td>{val}</td>
          <td class="dim">{threshold}</td>
          <td style="color:{sc['color']}">{sc['label']}</td>
        </tr>"""

    # ── action rows ──
    action_rows = ""
    for etf, amt in alloc.items():
        if amt > 0:
            action_rows += f"""
        <tr>
          <td class="bold">{etf}</td>
          <td>{amt/budget*100:.0f}%</td>
          <td style="color:{rc['color']};font-weight:bold">${amt:,.0f}</td>
          <td style="color:{rc['color']}">BUY</td>
        </tr>"""
        else:
            action_rows += f"""
        <tr class="dim">
          <td class="bold">{etf}</td><td>0%</td><td>—</td><td>—</td>
        </tr>"""

    # ── optional warning banners ──
    fear2_banner = ""
    if regime == "fear2":
        fear2_banner = f"""
<div class="card" style="border-color:#a855f7;background:#1a0030">
  <div style="color:#a855f7;font-weight:bold;font-size:1.1em">⚡ FEAR II ACTIVE</div>
  <p style="margin-top:8px">Deploy <strong>$30,000</strong> this month.
  Change <code>FEAR2_SPLIT</code> in config.py if needed.</p>
</div>"""

    caution_banner = ""
    if pt["alert_level"] in ("CAUTION", "EXTREME"):
        caution_banner = f"""
<div class="card" style="border-color:#ef4444;background:#2d0a0a">
  <div style="color:#ef4444;font-weight:bold;font-size:1.1em">⚠️ PROFIT-TAKING ACTION REQUIRED</div>
  <p style="margin-top:8px">{pt['action']}</p>
  <p style="margin-top:8px;color:#64748b">Confirm this level for 3 consecutive weeks before executing.
  Sell order: SOXL first → TQQQ second → SMH only at EXTREME → QQQ never.</p>
</div>"""

    n = len(history)
    history_note = f"Regime history: {n} month{'s' if n != 1 else ''} on record · raw signal today: {raw}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>4-ETF DCA Monitor · {today}</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{
      background:#0f172a;color:#e2e8f0;
      font-family:'Cascadia Code','Fira Code','Courier New',monospace;
      font-size:14px;padding:24px 16px;max-width:900px;margin:0 auto;
    }}
    h1{{
      font-size:1em;color:#94a3b8;text-align:center;
      border-top:1px solid #334155;border-bottom:1px solid #334155;
      padding:10px 0;margin-bottom:20px;letter-spacing:.05em;
    }}
    .card{{border:1px solid #334155;border-radius:6px;padding:16px;margin-bottom:14px}}
    .card-title{{color:#94a3b8;font-size:.85em;margin-bottom:10px;letter-spacing:.03em}}
    table{{width:100%;border-collapse:collapse}}
    th{{color:#64748b;font-weight:normal;text-align:left;padding:4px 6px 8px 0;
        font-size:.85em;border-bottom:1px solid #1e293b}}
    td{{padding:6px 6px 6px 0;vertical-align:middle}}
    tr+tr td{{border-top:1px solid #1e293b}}
    td:not(:first-child),th:not(:first-child){{text-align:right}}
    .bold{{font-weight:bold}}
    .dim{{color:#64748b}}
    .divider{{border-top:1px solid #334155;margin:10px 0}}
    .total-row td{{font-weight:bold;padding-top:10px}}
    .pt-action{{margin-top:10px;padding:10px;border-radius:4px;
                background:#1e293b;font-size:.9em;line-height:1.5}}
    .footer{{text-align:center;color:#475569;font-size:.8em;margin-top:20px;line-height:1.8}}
    code{{background:#1e293b;padding:1px 4px;border-radius:3px;font-size:.9em}}
    @media(max-width:600px){{body{{font-size:12px;padding:12px 8px}}}}
  </style>
</head>
<body>

<h1>4-ETF DCA MONITOR &nbsp;·&nbsp; {today}</h1>

<div class="card">
  <div class="card-title">Prices &amp; Portfolio</div>
  <table>
    <thead><tr>
      <th>ETF</th><th>Price</th><th>Cost basis</th>
      <th>Gain</th><th>Shares</th><th>Value</th>
    </tr></thead>
    <tbody>{price_rows}</tbody>
  </table>
</div>

<div class="card">
  <div class="card-title">Regime Indicators</div>
  <table>
    <thead><tr><th>Indicator</th><th>Value</th><th>Status</th></tr></thead>
    <tbody>{regime_rows}</tbody>
  </table>
</div>

<div class="card" style="border-color:{ac['color']}">
  <div class="card-title">
    Profit-Taking Monitor &nbsp;·&nbsp;
    <span style="color:{ac['color']}">{pt['alert_level']}</span>
    &nbsp;·&nbsp; {pt['firing']}/6 signals
  </div>
  <table>
    <thead><tr><th>Indicator</th><th>Value</th><th>Threshold</th><th>Status</th></tr></thead>
    <tbody>{pt_rows}</tbody>
  </table>
</div>

<div class="card" style="border-color:{rc['color']}">
  <div class="card-title" style="color:{rc['color']}">
    TODAY'S ACTION &nbsp;·&nbsp; {rc['label']}
  </div>
  <table>
    <thead><tr><th>ETF</th><th>Weight</th><th>Amount</th><th>Action</th></tr></thead>
    <tbody>{action_rows}</tbody>
  </table>
  <div class="divider"></div>
  <table><tbody>
    <tr class="total-row">
      <td>TOTAL</td><td>100%</td>
      <td style="color:{rc['color']}">${budget:,.0f}</td>
      <td style="color:{rc['color']}">{rc['label']}</td>
    </tr>
  </tbody></table>
  <div class="pt-action" style="color:{ac['color']}">
    Profit-Taking: [{pt['alert_level']}] &nbsp; {pt['action']}
  </div>
</div>

{fear2_banner}
{caution_banner}

<div class="footer">
  {history_note}<br>
  Last updated: {now}
</div>

</body>
</html>"""
