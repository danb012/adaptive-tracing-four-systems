
#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "experiment_results" / "rq2"
REPORTS_DIR = ROOT / "reports"
REPORT_PATH = REPORTS_DIR / "rq2_train_ticket_report.html"
SYSTEM_NAME = "Train-Ticket"
DESCRIPTION = "Train-Ticket is the strongest and most stable application in the project. For RQ2 it serves as the reference system for understanding how RL-based adaptive tracing reacts to explicit runtime changes."
CAVEAT = "This is the most reliable RQ2 target. If the same trend appears here and also on the other systems, that trend is likely meaningful."
POLICIES = ["q_learning", "sarsa", "bandit"]
POLICY_LABELS = {"q_learning": "Q-Learning", "sarsa": "SARSA", "bandit": "Bandit"}
POLICY_COLORS = {"q_learning": "#2563eb", "sarsa": "#c2410c", "bandit": "#0f766e"}
SCENARIOS = [
    ("healthy", "Healthy"),
    ("latency_spike", "Latency Spike"),
    ("error_burst", "Error Burst"),
    ("throughput_drop", "Throughput Drop"),
]
SCENARIO_TEXT = {"healthy": "Baseline operating condition with the existing low-error traffic profile.", "latency_spike": "Large service-side delays on order and travel without intentionally raising the error rate.", "error_burst": "Elevated order and travel error rates while keeping delay close to the baseline.", "throughput_drop": "Heavy delay plus a mild error increase, intended to reduce completed request throughput."}


def load_rows():
    rows = []
    for scenario, _ in SCENARIOS:
        for policy in POLICIES:
            path = RESULTS_DIR / f"{policy}__balanced__{scenario}.json"
            if not path.exists():
                continue
            payload = json.loads(path.read_text())
            status = payload.get("status", {})
            summary = payload.get("summary", {})
            decisions = payload.get("decisions", {}).get("items", [])
            zero_windows = sum(1 for item in decisions if not item.get("total"))
            rows.append({
                "scenario": scenario,
                "policy": policy,
                "latency": float(status.get("avg_latency_ms", 0.0) or 0.0),
                "qps": float(status.get("qps", 0.0) or 0.0),
                "error_rate": float(status.get("error_rate", 0.0) or 0.0),
                "avg_reward": summary.get("avg_reward"),
                "avg_rate": float(summary.get("avg_rate", 0.0) or 0.0),
                "decision_count": int(summary.get("decision_count", len(decisions)) or len(decisions)),
                "zero_windows": zero_windows,
            })
    return rows


def fmt(value, digits=3):
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def winner_for(rows, scenario, key, reverse=False):
    scoped = [row for row in rows if row["scenario"] == scenario]
    if not scoped:
        return None
    return sorted(scoped, key=lambda row: row[key], reverse=reverse)[0]


def bar_chart(rows, scenario, key, label, lower_is_better):
    scoped = [row for row in rows if row["scenario"] == scenario]
    if not scoped:
        return "<p class='caption'>No data available.</p>"
    values = [row[key] for row in scoped]
    ceiling = max(values) or 1.0
    blocks = []
    for row in scoped:
        width = 100.0 * (row[key] / ceiling) if ceiling else 0.0
        blocks.append(
            f"<div class='bar-row'><div class='bar-label'><span class='swatch' style='background:{POLICY_COLORS[row['policy']]}'></span>{POLICY_LABELS[row['policy']]}</div><div class='bar-track'><div class='bar-fill' style='width:{width:.1f}%;background:{POLICY_COLORS[row['policy']]}'></div></div><div class='bar-value'>{fmt(row[key], 3)}</div></div>"
        )
    direction = "Lower is better." if lower_is_better else "Higher is better."
    return f"<div class='bar-chart'>{''.join(blocks)}</div><p class='caption'>{label}. {direction}</p>"


def scenario_table(rows, scenario):
    scoped = [row for row in rows if row["scenario"] == scenario]
    if not scoped:
        return "<p class='caption'>No data available for this scenario yet.</p>"
    parts = ["<table><thead><tr><th>Policy</th><th>Latency (ms)</th><th>QPS</th><th>Error Rate</th><th>Avg Reward</th><th>Avg Rate</th><th>Decisions</th><th>Zero Windows</th></tr></thead><tbody>"]
    for row in scoped:
        parts.append(
            f"<tr><td><span class='policy-badge'><span class='swatch' style='background:{POLICY_COLORS[row['policy']]}'></span>{POLICY_LABELS[row['policy']]}</span></td><td>{fmt(row['latency'], 2)}</td><td>{fmt(row['qps'], 3)}</td><td>{fmt(row['error_rate'], 4)}</td><td>{fmt(row['avg_reward'], 4)}</td><td>{fmt(row['avg_rate'], 3)}</td><td>{row['decision_count']}</td><td>{row['zero_windows']}</td></tr>"
        )
    parts.append("</tbody></table>")
    return ''.join(parts)


def build_html(rows):
    REPORTS_DIR.mkdir(exist_ok=True)
    scenario_cards = []
    for scenario, title in SCENARIOS:
        lat_winner = winner_for(rows, scenario, "latency", reverse=False)
        qps_winner = winner_for(rows, scenario, "qps", reverse=True)
        reward_rows = [row for row in rows if row["avg_reward"] is not None]
        reward_winner = winner_for(reward_rows, scenario, "avg_reward", reverse=True)
        zero_total = sum(row["zero_windows"] for row in rows if row["scenario"] == scenario)
        scenario_cards.append(
            f"<article class='card full'><div class='eyebrow'>{title}</div><h3>{title}</h3><p>{SCENARIO_TEXT[scenario]}</p><div class='metric-grid'><div><span>Latency winner</span><strong>{POLICY_LABELS[lat_winner['policy']] if lat_winner else 'n/a'}</strong></div><div><span>QPS winner</span><strong>{POLICY_LABELS[qps_winner['policy']] if qps_winner else 'n/a'}</strong></div><div><span>RL reward leader</span><strong>{POLICY_LABELS[reward_winner['policy']] if reward_winner else 'n/a'}</strong></div><div><span>Decision quality</span><strong>{zero_total} zero windows total</strong></div></div><div class='two-col'><div>{bar_chart(rows, scenario, 'latency', 'Latency by policy', True)}</div><div>{bar_chart(rows, scenario, 'qps', 'Throughput by policy', False)}</div></div>{scenario_table(rows, scenario)}</article>"
        )
    scenario_definition_cards = ''.join(
        f"<article class='card summary'><div class='eyebrow'>{title}</div><p>{SCENARIO_TEXT[key]}</p></article>" for key, title in SCENARIOS
    )
    return f"""<!DOCTYPE html>
<html lang='en'>
<head>
  <meta charset='UTF-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1.0' />
  <title>RQ2 Report - {SYSTEM_NAME}</title>
  <style>
    :root {{ --ink:#102a43; --muted:#5b6878; --line:#d7e3ec; --shadow:0 18px 42px rgba(15,23,42,.08); }}
    body {{ margin:0; font-family: Georgia, 'Times New Roman', serif; color:var(--ink); background:linear-gradient(180deg,#f8fbfd,#ffffff 26%); }}
    .page {{ max-width:1180px; margin:0 auto; padding:28px 18px 64px; }}
    .hero,.card {{ background:#fff; border:1px solid var(--line); border-radius:20px; box-shadow:var(--shadow); }}
    .hero {{ padding:28px; }}
    .grid {{ display:grid; grid-template-columns:repeat(12,1fr); gap:14px; margin-top:16px; }}
    .card {{ padding:16px; grid-column:span 12; }}
    .summary {{ grid-column:span 4; }}
    h1,h2,h3 {{ color:#102a43; line-height:1.2; }}
    h1 {{ margin:0 0 10px; font-size:2.4rem; }}
    h2 {{ margin:34px 0 12px; font-size:1.35rem; border-bottom:1px solid #e5e7eb; padding-bottom:8px; }}
    h3 {{ margin:0 0 8px; font-size:1.05rem; }}
    p {{ line-height:1.65; }}
    .pill {{ display:inline-flex; align-items:center; gap:8px; padding:7px 11px; border-radius:999px; border:1px solid var(--line); margin-right:8px; margin-top:10px; color:var(--muted); }}
    .swatch {{ width:10px; height:10px; border-radius:999px; display:inline-block; }}
    .eyebrow {{ font-size:.8rem; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); margin-bottom:8px; }}
    .metric-grid,.two-col {{ display:grid; grid-template-columns:repeat(2,1fr); gap:12px; margin-top:12px; }}
    .metric-grid div {{ border:1px solid var(--line); border-radius:12px; background:#fbfdff; padding:10px 12px; }}
    .metric-grid span {{ display:block; font-size:.82rem; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; }}
    .metric-grid strong {{ display:block; margin-top:4px; }}
    table {{ width:100%; border-collapse:collapse; margin-top:14px; font-size:.94rem; }}
    th,td {{ padding:10px 12px; border-top:1px solid var(--line); text-align:left; }}
    thead th {{ background:#eff6fb; border-top:none; }}
    .policy-badge {{ display:inline-flex; align-items:center; gap:8px; font-weight:600; }}
    .bar-chart {{ display:grid; gap:10px; margin-top:10px; }}
    .bar-row {{ display:grid; grid-template-columns:160px 1fr 80px; gap:10px; align-items:center; }}
    .bar-track {{ height:16px; border-radius:999px; background:#e8eef5; overflow:hidden; }}
    .bar-fill {{ height:100%; border-radius:999px; }}
    .bar-value {{ text-align:right; color:var(--muted); font-variant-numeric:tabular-nums; }}
    .caption {{ color:var(--muted); font-size:.92rem; }}
    @media (max-width: 900px) {{ .summary {{ grid-column:span 12; }} .metric-grid,.two-col {{ grid-template-columns:1fr; }} .bar-row {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <div class='page'>
    <section class='hero'>
      <div class='eyebrow'>Research Question 2</div>
      <h1>RQ2 Runtime-Change Report: {SYSTEM_NAME}</h1>
      <p>{DESCRIPTION}</p>
      <p><strong>RQ2:</strong> How do RL-based adaptive tracing methods behave under different runtime changes, such as latency spikes, throughput drops, and error bursts?</p>
      <div>
        <span class='pill'><span class='swatch' style='background:#2563eb'></span>Q-Learning</span>
        <span class='pill'><span class='swatch' style='background:#c2410c'></span>SARSA</span>
        <span class='pill'><span class='swatch' style='background:#0f766e'></span>Bandit</span>
      </div>
    </section>

    <section class='grid'>
      <article class='card summary'><div class='eyebrow'>Scenario count</div><h3>{len(SCENARIOS)}</h3><p class='caption'>Healthy baseline plus three explicit runtime-change scenarios.</p></article>
      <article class='card summary'><div class='eyebrow'>Policies compared</div><h3>3 RL methods</h3><p class='caption'>The RQ2 focus is on behavior inside the RL family rather than RL vs non-RL.</p></article>
      <article class='card summary'><div class='eyebrow'>Reporting caveat</div><h3>Important</h3><p class='caption'>{CAVEAT}</p></article>
    </section>

    <section>
      <h2>Scenario Definitions</h2>
      <div class='grid'>{scenario_definition_cards}</div>
    </section>

    <section>
      <h2>Results by Runtime Change</h2>
      <div class='grid'>{''.join(scenario_cards)}</div>
    </section>

    <section>
      <h2>Interpretation</h2>
      <div class='grid'>
        <article class='card full'>
          <p>This report focuses on how the three RL methods react when the runtime condition changes, not on whether RL beats non-RL baselines. The key outputs are the final latency, final throughput, observed error rate, selected tracing rate, and the number of clean decision windows.</p>
          <p>The main things to look for are whether a policy raises tracing when the system degrades, whether it stabilizes after the change, and whether its runtime metrics remain controlled rather than oscillating or collapsing.</p>
          <p>{CAVEAT}</p>
        </article>
      </div>
    </section>
  </div>
</body>
</html>"""


def main() -> int:
    rows = load_rows()
    html = build_html(rows)
    REPORT_PATH.write_text(html, encoding="utf-8")
    print(REPORT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
