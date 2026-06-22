#!/usr/bin/env python3
import json
from pathlib import Path

SYSTEMS = [
    {
        "name": "Train-Ticket",
        "slug": "train-ticket",
        "root": Path("/Users/dan/train-ticket-python"),
        "description": "Railway ticket booking benchmark and the strongest RQ2 evidence set.",
        "caveat": "Most stable system in the study.",
    },
    {
        "name": "Timescale OpenTelemetry Demo",
        "slug": "timescale",
        "root": Path("/Users/dan/timescale-otel-demo"),
        "description": "Lightweight password-generation microservice application with a strong observability stack.",
        "caveat": "Reward is not a pure runtime-performance score.",
    },
    {
        "name": "Spring Petclinic Microservices",
        "slug": "petclinic",
        "root": Path("/Users/dan/spring-petclinic-microservices"),
        "description": "Business-domain Spring Cloud microservice application with Prometheus-based runtime metrics.",
        "caveat": "Least stable system; sparse decision windows must be interpreted carefully.",
    },
]
SCENARIOS = [
    ("healthy", "Healthy"),
    ("latency_spike", "Latency Spike"),
    ("error_burst", "Error Burst"),
    ("throughput_drop", "Throughput Drop"),
]
POLICY_LABELS = {"q_learning": "Q-Learning", "sarsa": "SARSA", "bandit": "Bandit"}
POLICY_COLORS = {"q_learning": "#2563eb", "sarsa": "#c2410c", "bandit": "#0f766e"}
OUTPUT = Path("/Users/dan/rq2_all_three_systems_report.html")


def fmt(value, digits=3):
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def load_rows(system):
    root = system["root"] / "experiment_results" / "rq2"
    rows = []
    for path in sorted(root.glob("*.json")):
        payload = json.loads(path.read_text())
        status = payload.get("status", {})
        summary = payload.get("summary", {})
        decisions = payload.get("decisions", {}).get("items", [])
        rows.append(
            {
                "system": system["name"],
                "scenario": payload.get("scenario"),
                "policy": payload.get("policy"),
                "latency": float(status.get("avg_latency_ms", 0.0) or 0.0),
                "qps": float(status.get("qps", 0.0) or 0.0),
                "error_rate": float(status.get("error_rate", 0.0) or 0.0),
                "avg_reward": summary.get("avg_reward"),
                "avg_rate": float(summary.get("avg_rate", 0.0) or 0.0),
                "decision_count": int(summary.get("decision_count", len(decisions)) or len(decisions)),
                "zero_windows": sum(1 for item in decisions if not item.get("total")),
            }
        )
    return rows


def winner(rows, key, reverse=False):
    if not rows:
        return None
    return sorted(rows, key=lambda row: row[key], reverse=reverse)[0]


def scenario_table(rows):
    if not rows:
        return "<p class='caption'>No data available yet.</p>"
    parts = ["<table><thead><tr><th>Policy</th><th>Latency (ms)</th><th>QPS</th><th>Error Rate</th><th>Avg Reward (RL-internal)</th><th>Avg Rate</th><th>Decisions</th><th>Zero Windows</th></tr></thead><tbody>"]
    for row in rows:
        parts.append(
            f"<tr><td><span class='policy-badge'><span class='swatch' style='background:{POLICY_COLORS[row['policy']]}'></span>{POLICY_LABELS[row['policy']]}</span></td><td>{fmt(row['latency'],2)}</td><td>{fmt(row['qps'],3)}</td><td>{fmt(row['error_rate'],4)}</td><td>{fmt(row['avg_reward'],4)}</td><td>{fmt(row['avg_rate'],3)}</td><td>{row['decision_count']}</td><td>{row['zero_windows']}</td></tr>"
        )
    parts.append("</tbody></table>")
    return "".join(parts)


def build_html():
    system_sections = []
    all_rows = []
    for system in SYSTEMS:
        rows = load_rows(system)
        all_rows.extend(rows)
        scenario_blocks = []
        for scenario_key, scenario_title in SCENARIOS:
            scoped = [row for row in rows if row["scenario"] == scenario_key]
            lat_winner = winner(scoped, "latency", reverse=False)
            qps_winner = winner(scoped, "qps", reverse=True)
            reward_rows = [row for row in scoped if row["avg_reward"] is not None]
            reward_winner = winner(reward_rows, "avg_reward", reverse=True)
            scenario_blocks.append(
                f"<article class='card full'><div class='eyebrow'>{scenario_title}</div><h3>{scenario_title}</h3><div class='metric-grid'><div><span>Latency winner</span><strong>{POLICY_LABELS[lat_winner['policy']] if lat_winner else 'n/a'}</strong></div><div><span>QPS winner</span><strong>{POLICY_LABELS[qps_winner['policy']] if qps_winner else 'n/a'}</strong></div><div><span>RL reward leader (contextual)</span><strong>{POLICY_LABELS[reward_winner['policy']] if reward_winner else 'n/a'}</strong></div><div><span>Data quality</span><strong>{sum(r['zero_windows'] for r in scoped)} zero windows</strong></div></div>{scenario_table(scoped)}</article>"
            )
        system_sections.append(
            f"<section><h2>{system['name']}</h2><div class='grid'><article class='card full'><p>{system['description']}</p><p class='caption'>{system['caveat']}</p></article>{''.join(scenario_blocks)}</div></section>"
        )

    complete_runs = len(all_rows)
    html = f"""<!DOCTYPE html>
<html lang='en'>
<head>
  <meta charset='UTF-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1.0' />
  <title>RQ2 Cross-System Report</title>
  <style>
    :root {{ --ink:#102a43; --muted:#5b6878; --line:#d7e3ec; --shadow:0 18px 42px rgba(15,23,42,.08); }}
    body {{ margin:0; font-family: Georgia, 'Times New Roman', serif; color:var(--ink); background:linear-gradient(180deg,#f8fbfd,#ffffff 26%); }}
    .page {{ max-width:1200px; margin:0 auto; padding:28px 18px 64px; }}
    .hero,.card {{ background:#fff; border:1px solid var(--line); border-radius:20px; box-shadow:var(--shadow); }}
    .hero {{ padding:28px; }}
    .grid {{ display:grid; grid-template-columns:repeat(12,1fr); gap:14px; margin-top:16px; }}
    .card {{ padding:16px; grid-column:span 12; }}
    .summary {{ grid-column:span 4; }}
    h1,h2,h3 {{ color:#102a43; line-height:1.2; }}
    h1 {{ margin:0 0 10px; font-size:2.5rem; }}
    h2 {{ margin:34px 0 12px; font-size:1.4rem; border-bottom:1px solid #e5e7eb; padding-bottom:8px; }}
    h3 {{ margin:0 0 8px; font-size:1.05rem; }}
    p {{ line-height:1.65; }}
    .eyebrow {{ font-size:.8rem; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); margin-bottom:8px; }}
    .metric-grid {{ display:grid; grid-template-columns:repeat(2,1fr); gap:12px; margin-top:12px; }}
    .metric-grid div {{ border:1px solid var(--line); border-radius:12px; background:#fbfdff; padding:10px 12px; }}
    .metric-grid span {{ display:block; font-size:.82rem; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; }}
    .metric-grid strong {{ display:block; margin-top:4px; }}
    table {{ width:100%; border-collapse:collapse; margin-top:14px; font-size:.94rem; }}
    th,td {{ padding:10px 12px; border-top:1px solid var(--line); text-align:left; }}
    thead th {{ background:#eff6fb; border-top:none; }}
    .policy-badge {{ display:inline-flex; align-items:center; gap:8px; font-weight:600; }}
    .swatch {{ width:10px; height:10px; border-radius:999px; display:inline-block; }}
    .caption {{ color:var(--muted); font-size:.92rem; }}
    @media (max-width: 900px) {{ .summary {{ grid-column:span 12; }} .metric-grid {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <div class='page'>
    <section class='hero'>
      <div class='eyebrow'>Research Question 2</div>
      <h1>Cross-System RQ2 Report</h1>
      <p><strong>RQ2:</strong> How do RL-based adaptive tracing methods behave under different runtime changes, such as latency spikes, throughput drops, and error bursts?</p>
      <p>This report consolidates the runtime-change experiments for Train-Ticket, Timescale OpenTelemetry Demo, and Spring Petclinic Microservices. The comparison is intentionally inside the RL family: Q-Learning, SARSA, and Bandit.</p><p class='caption'>Latency, QPS, error rate, and data quality are the primary evidence. Reward is reported as RL-internal context rather than as a universally comparable score, because reward design differs across the applications.</p>
    </section>
    <section class='grid'>
      <article class='card summary'><div class='eyebrow'>Applications</div><h3>3 systems</h3><p class='caption'>Train-Ticket, Timescale OpenTelemetry Demo, Spring Petclinic Microservices.</p></article>
      <article class='card summary'><div class='eyebrow'>Scenario set</div><h3>4 runtime states</h3><p class='caption'>Healthy baseline plus latency spike, error burst, and throughput drop.</p></article>
      <article class='card summary'><div class='eyebrow'>Loaded runs</div><h3>{complete_runs}</h3><p class='caption'>Expected full matrix: 36 runs.</p></article>
    </section>
    {''.join(system_sections)}
  </div>
</body>
</html>"""
    OUTPUT.write_text(html, encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    build_html()
