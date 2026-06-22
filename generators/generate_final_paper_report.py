#!/usr/bin/env python3
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path('/Users/dan')
OUT = ROOT / 'final_adaptive_tracing_paper_report.html'
QUICKPIZZA_ROOT = ROOT / 'quickpizza' / 'experiment_results'

SYSTEMS = {
    'Train-Ticket': {
        'slug': 'train-ticket',
        'root': ROOT / 'train-ticket-python' / 'experiment_results',
        'domain': 'Railway ticket booking benchmark',
        'stack': 'Python microservices with adaptive tracing controller and experiment runners',
        'role': 'Largest and most stable application in the study; strongest evidence base',
        'rq1_winner': 'Q-Learning',
        'rq1_note': 'Most convincing overall RL result set with many decision windows and stable traces.',
    },
    'Timescale OpenTelemetry Demo': {
        'slug': 'timescale',
        'root': ROOT / 'timescale-otel-demo' / 'experiment_results',
        'domain': 'Password-generation microservice application',
        'stack': 'OpenTelemetry Collector, Promscale, TimescaleDB, Jaeger, Grafana',
        'role': 'Lightweight tracing-first microservice system with strong observability',
        'rq1_winner': 'Rule',
        'rq1_note': 'Shows that a transparent heuristic can still win on final latency.',
    },
    'Spring Petclinic Microservices': {
        'slug': 'petclinic',
        'root': ROOT / 'spring-petclinic-microservices' / 'experiment_results',
        'domain': 'Spring Cloud business-domain microservice application',
        'stack': 'API gateway, service discovery, config server, Zipkin, Prometheus',
        'role': 'Most realistic business application, but also the noisiest result set',
        'rq1_winner': 'Bandit',
        'rq1_note': 'Shows that a simpler RL family member can dominate under noisier runtime signals.',
    },
}

POLICIES = {
    'q_learning': {'label': 'Q-Learning', 'family': 'RL', 'color': '#2563eb'},
    'sarsa': {'label': 'SARSA', 'family': 'RL', 'color': '#c2410c'},
    'bandit': {'label': 'Bandit', 'family': 'RL', 'color': '#0f766e'},
    'rule': {'label': 'Rule', 'family': 'Non-RL', 'color': '#64748b'},
    'kmeans': {'label': 'K-Means', 'family': 'Non-RL', 'color': '#15803d'},
    'fixed_rate': {'label': 'Fixed Rate', 'family': 'Baseline', 'color': '#7c3aed'},
}

RQ2_SCENARIOS = [
    ('healthy', 'Healthy'),
    ('latency_spike', 'Latency Spike'),
    ('error_burst', 'Error Burst'),
    ('throughput_drop', 'Throughput Drop'),
]
RQ1_SCENARIOS = [('healthy', 'Healthy'), ('faulted', 'Faulted')]


def fmt(value, digits=2):
    if value is None:
        return 'n/a'
    return f'{value:.{digits}f}'


def load_rq1_rows():
    rows = []
    for system, meta in SYSTEMS.items():
        for path in sorted(meta['root'].glob('*.json')):
            payload = json.loads(path.read_text())
            policy = payload.get('policy')
            if not policy:
                # fixed-rate baseline, only used as context
                rows.append({
                    'system': system,
                    'policy': 'fixed_rate',
                    'scenario': payload.get('scenario', f"rate_{payload.get('sampling_rate', 'unknown')}") ,
                    'latency': payload['metrics'].get('avg_latency_ms', 0.0),
                    'qps': payload['metrics'].get('qps', 0.0),
                    'error_rate': payload['metrics'].get('error_rate', 0.0),
                    'avg_reward': None,
                    'avg_rate': payload.get('sampling_rate'),
                    'decision_count': 0,
                    'zero_windows': 0,
                    'kind': 'baseline',
                })
                continue
            summary = payload.get('summary', {})
            status = payload.get('status', {})
            decisions = payload.get('decisions', {}).get('items', [])
            rows.append({
                'system': system,
                'policy': policy,
                'scenario': payload.get('scenario'),
                'latency': float(status.get('avg_latency_ms', 0.0) or 0.0),
                'qps': float(status.get('qps', 0.0) or 0.0),
                'error_rate': float(status.get('error_rate', 0.0) or 0.0),
                'avg_reward': summary.get('avg_reward'),
                'avg_rate': summary.get('avg_rate'),
                'decision_count': int(summary.get('decision_count', len(decisions)) or len(decisions)),
                'zero_windows': sum(1 for item in decisions if not item.get('total')),
                'kind': 'policy',
            })
    return rows


def load_rq2_rows():
    rows = []
    for system, meta in SYSTEMS.items():
        for path in sorted((meta['root'] / 'rq2').glob('*.json')):
            payload = json.loads(path.read_text())
            summary = payload.get('summary', {})
            status = payload.get('status', {})
            decisions = payload.get('decisions', {}).get('items', [])
            rows.append({
                'system': system,
                'policy': payload['policy'],
                'scenario': payload['scenario'],
                'latency': float(status.get('avg_latency_ms', 0.0) or 0.0),
                'qps': float(status.get('qps', 0.0) or 0.0),
                'error_rate': float(status.get('error_rate', 0.0) or 0.0),
                'avg_reward': summary.get('avg_reward'),
                'avg_rate': summary.get('avg_rate'),
                'decision_count': int(summary.get('decision_count', len(decisions)) or len(decisions)),
                'zero_windows': sum(1 for item in decisions if not item.get('total')),
            })
    return rows


def winner(rows, key, reverse=False):
    return sorted(rows, key=lambda r: r[key], reverse=reverse)[0] if rows else None


def rq1_summary(rows):
    out = []
    for system in SYSTEMS:
        sys_rows = [r for r in rows if r['system'] == system and r['kind'] == 'policy']
        for scenario, label in RQ1_SCENARIOS:
            scoped = [r for r in sys_rows if r['scenario'] == scenario]
            latency = winner(scoped, 'latency', reverse=False)
            qps = winner(scoped, 'qps', reverse=True)
            reward = winner([r for r in scoped if r['policy'] in {'q_learning', 'sarsa', 'bandit'} and r['avg_reward'] is not None], 'avg_reward', reverse=True)
            out.append({
                'system': system,
                'scenario': label,
                'latency_winner': latency,
                'qps_winner': qps,
                'reward_winner': reward,
            })
    return out


def rq2_summary(rows):
    out = []
    for system in SYSTEMS:
        sys_rows = [r for r in rows if r['system'] == system]
        for scenario, label in RQ2_SCENARIOS:
            scoped = [r for r in sys_rows if r['scenario'] == scenario]
            latency = winner(scoped, 'latency', reverse=False)
            qps = winner(scoped, 'qps', reverse=True)
            reward = winner(scoped, 'avg_reward', reverse=True)
            out.append({
                'system': system,
                'scenario': label,
                'latency_winner': latency,
                'qps_winner': qps,
                'reward_winner': reward,
                'zero_windows': sum(r['zero_windows'] for r in scoped),
            })
    return out


def donut_svg(values, colors, label):
    total = sum(values) or 1
    radius = 54
    circ = 2 * 3.141592653589793 * radius
    start = 0.0
    parts = [f"<svg width='160' height='160' viewBox='0 0 160 160' aria-label='{label}'>",
             "<circle r='54' cx='80' cy='80' fill='none' stroke='#e6edf5' stroke-width='22' />"]
    for value, color in zip(values, colors):
        arc = circ * value / total
        parts.append(
            f"<circle r='{radius}' cx='80' cy='80' fill='none' stroke='{color}' stroke-width='22' "
            f"stroke-dasharray='{arc:.2f} {circ-arc:.2f}' stroke-dashoffset='{-start:.2f}' transform='rotate(-90 80 80)' />"
        )
        start += arc
    parts.append("<text x='80' y='75' text-anchor='middle' font-size='12' fill='#5b6878'>cases</text>")
    parts.append(f"<text x='80' y='98' text-anchor='middle' font-size='22' font-weight='700' fill='#12344d'>{sum(values)}</text>")
    parts.append('</svg>')
    return ''.join(parts)


def bar_rows(items, max_value=None, digits=2, suffix=''):
    if max_value is None:
        max_value = max((item['value'] for item in items), default=1.0) or 1.0
    rows = []
    for item in items:
        value = item['value']
        width = 100 * value / max_value if max_value else 0
        rows.append(
            f"<div class='bar-row'><div class='bar-label'><span class='swatch' style='background:{item['color']}'></span>{item['label']}</div>"
            f"<div class='bar-track'><div class='bar-fill' style='width:{width:.1f}%;background:{item['color']}'></div></div>"
            f"<div class='bar-value'>{fmt(value, digits)}{suffix}</div></div>"
        )
    return ''.join(rows)


def table_rows_rq1(summary_rows):
    out = []
    for row in summary_rows:
        out.append(
            '<tr>'
            f"<td>{row['system']}</td>"
            f"<td>{row['scenario']}</td>"
            f"<td>{POLICIES[row['latency_winner']['policy']]['label']}</td>"
            f"<td>{fmt(row['latency_winner']['latency'], 2)} ms</td>"
            f"<td>{POLICIES[row['qps_winner']['policy']]['label']}</td>"
            f"<td>{fmt(row['qps_winner']['qps'], 3)}</td>"
            f"<td>{POLICIES[row['reward_winner']['policy']]['label'] if row['reward_winner'] else 'n/a'}</td>"
            f"<td>{fmt(row['reward_winner']['avg_reward'], 4) if row['reward_winner'] else 'n/a'}</td>"
            '</tr>'
        )
    return ''.join(out)


def table_rows_rq2(summary_rows):
    out = []
    for row in summary_rows:
        out.append(
            '<tr>'
            f"<td>{row['system']}</td>"
            f"<td>{row['scenario']}</td>"
            f"<td>{POLICIES[row['latency_winner']['policy']]['label']}</td>"
            f"<td>{fmt(row['latency_winner']['latency'], 2)} ms</td>"
            f"<td>{POLICIES[row['qps_winner']['policy']]['label']}</td>"
            f"<td>{fmt(row['qps_winner']['qps'], 3)}</td>"
            f"<td>{POLICIES[row['reward_winner']['policy']]['label']}</td>"
            f"<td>{fmt(row['reward_winner']['avg_reward'], 4)}</td>"
            f"<td>{row['zero_windows']}</td>"
            '</tr>'
        )
    return ''.join(out)


def taxonomy_rows():
    rows = [
        ('Fixed Rate', 'Static baseline', 'No runtime adaptation; constant configured rate.', 'Configuration time only', 'None after startup', 'Reference point for what is lost without adaptation.'),
        ('Rule', 'Heuristic threshold control', 'Change tracing when thresholds are crossed.', 'Thresholds on latency, errors, counts, or similar runtime signals', 'Low', 'Strong when system behavior is predictable and operational transparency matters.'),
        ('K-Means', 'Clustering-based control', 'Map similar runtime states to representative rates.', 'Recent latency, throughput, and error features grouped into clusters', 'Moderate', 'Useful middle ground between static thresholds and full RL.'),
        ('Bandit', 'RL-based action-value control', 'Choose the rate with the best immediate observed payoff.', 'Short-horizon reward from recent behavior', 'Moderate', 'Strong on noisy systems where low-overhead adaptation is valuable.'),
        ('SARSA', 'RL-based value-learning', 'Learn state-action values on-policy while exploring.', 'State bins derived from runtime metrics plus current action', 'High', 'Most exploratory RL method in this project; useful when controlled exploration helps.'),
        ('Q-Learning', 'RL-based value-learning', 'Learn long-run state-action value off-policy.', 'State bins derived from runtime metrics and delayed reward', 'High', 'Strongest option when enough decisions and stable feedback are available.'),
    ]
    out = []
    key_map = {'Fixed Rate': 'fixed_rate', 'Rule': 'rule', 'K-Means': 'kmeans', 'Bandit': 'bandit', 'SARSA': 'sarsa', 'Q-Learning': 'q_learning'}
    for method, kind, goal, signals, overhead, takeaway in rows:
        color = POLICIES[key_map[method]]['color']
        out.append(
            f"<tr><td><span class='policy-badge'><span class='swatch' style='background:{color}'></span>{method}</span></td><td>{kind}</td><td>{goal}</td><td>{signals}</td><td>{overhead}</td><td>{takeaway}</td></tr>"
        )
    return ''.join(out)


def complexity_svg():
    items = [
        ('Fixed Rate', 'Baseline', '#7c3aed', 1),
        ('Rule', 'Threshold', '#64748b', 2),
        ('K-Means', 'Cluster', '#15803d', 3),
        ('Bandit', 'Immediate value', '#0f766e', 4),
        ('SARSA', 'On-policy RL', '#c2410c', 5),
        ('Q-Learning', 'Off-policy RL', '#2563eb', 6),
    ]
    svg = ["<svg viewBox='0 0 940 220' role='img' aria-label='Adaptive tracing complexity ladder'>"]
    x = 20
    for label, subtitle, color, level in items:
        y = 30 + (6 - level) * 4
        svg.append(f"<rect x='{x}' y='{y}' width='138' height='144' rx='20' fill='{color}' opacity='0.94'></rect>")
        svg.append(f"<text x='{x+18}' y='{y+40}' fill='white' font-size='23' font-family='Georgia, serif'>{label}</text>")
        svg.append(f"<text x='{x+18}' y='{y+72}' fill='white' font-size='14' font-family='Georgia, serif'>{subtitle}</text>")
        svg.append(f"<text x='{x+18}' y='{y+112}' fill='white' font-size='13' font-family='Georgia, serif'>complexity level {level}</text>")
        x += 150
    svg.append('</svg>')
    return ''.join(svg)


def load_quickpizza_extension():
    policy_rows = []
    baseline_rows = []
    for path in sorted(QUICKPIZZA_ROOT.glob('*.json')):
        payload = json.loads(path.read_text())
        policy = payload.get('policy')
        if policy:
            status = payload.get('status', {})
            summary = payload.get('summary', {})
            decisions = payload.get('decisions', {}).get('items', [])
            policy_rows.append({
                'policy': policy,
                'scenario': payload.get('scenario'),
                'latency': float(status.get('avg_latency_ms', 0.0) or 0.0),
                'qps': float(status.get('qps', 0.0) or 0.0),
                'error_rate': float(status.get('error_rate', 0.0) or 0.0),
                'avg_reward': summary.get('avg_reward'),
                'avg_rate': summary.get('avg_rate'),
                'decision_count': int(summary.get('decision_count', len(decisions)) or len(decisions)),
            })
        else:
            metrics = payload.get('metrics', {})
            baseline_rows.append({
                'scenario': payload.get('scenario'),
                'sampling_rate': payload.get('sampling_rate'),
                'latency': float(metrics.get('avg_latency_ms', 0.0) or 0.0),
                'qps': float(metrics.get('qps', 0.0) or 0.0),
                'error_rate': float(metrics.get('error_rate', 0.0) or 0.0),
            })

    return {
        'policy_rows': policy_rows,
        'baseline_rows': baseline_rows,
        'best_latency': winner(policy_rows, 'latency', reverse=False),
        'best_qps': winner(policy_rows, 'qps', reverse=True),
        'best_reward': winner([row for row in policy_rows if row['avg_reward'] is not None], 'avg_reward', reverse=True),
    }


def build_html():
    rq1_rows = load_rq1_rows()
    rq2_rows = load_rq2_rows()
    quickpizza = load_quickpizza_extension()
    rq1_policies = [r for r in rq1_rows if r['kind'] == 'policy']
    rq1_baselines = [r for r in rq1_rows if r['kind'] == 'baseline']
    rq1_summary_rows = rq1_summary(rq1_rows)
    rq2_summary_rows = rq2_summary(rq2_rows)

    # Aggregates
    rq1_latency_family = Counter(POLICIES[row['latency_winner']['policy']]['family'] for row in rq1_summary_rows)
    rq1_qps_family = Counter(POLICIES[row['qps_winner']['policy']]['family'] for row in rq1_summary_rows)
    rq1_policy_latency = Counter(row['latency_winner']['policy'] for row in rq1_summary_rows)
    rq1_policy_qps = Counter(row['qps_winner']['policy'] for row in rq1_summary_rows)

    rq2_policy_latency = Counter(row['latency_winner']['policy'] for row in rq2_summary_rows)
    rq2_policy_qps = Counter(row['qps_winner']['policy'] for row in rq2_summary_rows)
    rq2_policy_reward = Counter(row['reward_winner']['policy'] for row in rq2_summary_rows)

    adaptive_rate_values = []
    for row in rq1_policies + rq2_rows:
        if row['avg_rate'] is not None:
            adaptive_rate_values.append({'label': POLICIES[row['policy']]['label'], 'value': row['avg_rate'], 'color': POLICIES[row['policy']]['color']})
    avg_rate_by_policy = []
    for pol in ['rule', 'kmeans', 'bandit', 'sarsa', 'q_learning']:
        vals = [row['avg_rate'] for row in rq1_policies + rq2_rows if row['policy'] == pol and row['avg_rate'] is not None]
        avg_rate_by_policy.append({'label': POLICIES[pol]['label'], 'value': sum(vals) / len(vals), 'color': POLICIES[pol]['color']})

    # Data quality
    rq1_quality = {
        sys: {
            'runs': len([r for r in rq1_policies if r['system'] == sys]),
            'avg_decisions': sum(r['decision_count'] for r in rq1_policies if r['system'] == sys) / len([r for r in rq1_policies if r['system'] == sys]),
            'zero_windows': sum(r['zero_windows'] for r in rq1_policies if r['system'] == sys),
        }
        for sys in SYSTEMS
    }
    rq2_quality = {
        sys: {
            'runs': len([r for r in rq2_rows if r['system'] == sys]),
            'avg_decisions': sum(r['decision_count'] for r in rq2_rows if r['system'] == sys) / len([r for r in rq2_rows if r['system'] == sys]),
            'zero_windows': sum(r['zero_windows'] for r in rq2_rows if r['system'] == sys),
        }
        for sys in SYSTEMS
    }

    html = f"""<!DOCTYPE html>
<html lang='en'>
<head>
  <meta charset='UTF-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1.0' />
  <title>Adaptive Tracing Across Three Completed Systems, with a Preliminary QuickPizza Extension</title>
  <style>
    :root {{
      --ink:#102a43; --muted:#5b6878; --line:#d7e3ec; --shadow:0 20px 50px rgba(15,23,42,.08);
      --navy:#12344d; --teal:#0f766e; --amber:#b45309; --red:#b91c1c; --blue:#2563eb; --slate:#64748b; --green:#15803d; --purple:#7c3aed;
    }}
    * {{ box-sizing:border-box; }}
    html {{ scroll-behavior:smooth; }}
    body {{ margin:0; color:var(--ink); font-family: Georgia, 'Times New Roman', serif; background:linear-gradient(180deg,#f6fafc,#ffffff 26%); line-height:1.68; }}
    .page {{ max-width:1240px; margin:0 auto; padding:30px 18px 72px; }}
    .title-page,.card {{ background:#fff; border:1px solid var(--line); border-radius:22px; box-shadow:var(--shadow); }}
    .title-page {{ padding:38px 36px; position:relative; overflow:hidden; }}
    .title-page::after {{ content:''; position:absolute; right:-110px; top:-120px; width:320px; height:320px; border-radius:50%; background:radial-gradient(circle at 30% 30%, rgba(37,99,235,.16), rgba(37,99,235,0)); }}
    h1,h2,h3,h4 {{ color:var(--navy); line-height:1.2; }}
    h1 {{ margin:0 0 12px; font-size:clamp(2rem, 1.3rem + 2vw, 3rem); letter-spacing:-0.02em; }}
    h2 {{ margin:40px 0 12px; padding-bottom:8px; border-bottom:1px solid #e5e7eb; font-size:1.45rem; }}
    h3 {{ margin:0 0 10px; font-size:1.08rem; }}
    h4 {{ margin:0 0 8px; font-size:1rem; }}
    p {{ margin:10px 0; }}
    .eyebrow {{ text-transform:uppercase; letter-spacing:.09em; font-size:.82rem; color:var(--muted); margin-bottom:8px; }}
    .lead {{ font-size:1.08rem; max-width:92ch; }}
    .meta {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:18px; }}
    .pill {{ display:inline-flex; align-items:center; gap:8px; padding:7px 12px; border-radius:999px; border:1px solid var(--line); background:#f8fbfd; color:var(--muted); font-size:.93rem; }}
    .dot,.swatch {{ width:10px; height:10px; border-radius:999px; display:inline-block; }}
    .grid {{ display:grid; grid-template-columns:repeat(12,1fr); gap:14px; }}
    .card {{ grid-column:span 12; padding:16px 16px 14px; }}
    .summary {{ grid-column:span 3; }}
    .three-up {{ grid-column:span 4; }}
    .two-up {{ grid-column:span 6; }}
    .full {{ grid-column:span 12; }}
    .callout {{ border-left:4px solid var(--teal); background:#f0fdfa; }}
    .warning {{ border-left:4px solid var(--amber); background:#fffbeb; }}
    .danger {{ border-left:4px solid var(--red); background:#fef2f2; }}
    .caption,.subtle {{ color:var(--muted); font-size:.93rem; }}
    .summary-k {{ font-size:.82rem; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); margin-bottom:8px; }}
    .summary-v {{ font-size:1.55rem; color:var(--navy); font-weight:700; }}
    .summary-note {{ margin-top:6px; color:var(--muted); font-size:.92rem; }}
    .metric-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-top:12px; }}
    .metric-grid div {{ border:1px solid var(--line); border-radius:12px; background:#fbfdff; padding:10px 12px; }}
    .metric-grid span {{ display:block; font-size:.82rem; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; }}
    .metric-grid strong {{ display:block; margin-top:4px; color:var(--navy); }}
    table {{ width:100%; border-collapse:collapse; margin-top:14px; font-size:.94rem; }}
    th,td {{ padding:10px 12px; border-top:1px solid var(--line); text-align:left; vertical-align:top; }}
    thead th {{ background:#eff6fb; border-top:none; }}
    tbody tr:hover td {{ background:#f8fbfd; }}
    .policy-badge {{ display:inline-flex; align-items:center; gap:8px; font-weight:600; }}
    .bar-chart {{ display:grid; gap:10px; margin-top:12px; }}
    .bar-row {{ display:grid; grid-template-columns:180px 1fr 90px; gap:10px; align-items:center; }}
    .bar-track {{ height:16px; border-radius:999px; background:#e8eef5; overflow:hidden; }}
    .bar-fill {{ height:100%; border-radius:999px; }}
    .bar-value {{ text-align:right; color:var(--muted); font-variant-numeric:tabular-nums; }}
    .donut-wrap {{ display:flex; align-items:center; gap:20px; flex-wrap:wrap; }}
    .legend {{ display:grid; gap:8px; }}
    .legend-item {{ display:flex; align-items:center; gap:8px; }}
    .toc ol {{ margin:0; padding-left:22px; line-height:1.9; }}
    .toc a {{ color:var(--navy); text-decoration:none; }}
    .toc a:hover {{ text-decoration:underline; }}
    .smallcaps {{ font-variant:small-caps; letter-spacing:.04em; }}
    .foot {{ font-size:.88rem; color:var(--muted); }}
    ol.refs {{ padding-left:22px; }}
    ol.refs li {{ margin:0 0 12px 0; line-height:1.6; }}
    @media print {{ .page {{ max-width:none; padding:0; }} .title-page,.card {{ box-shadow:none; }} a {{ color:inherit; text-decoration:none; }} }}
    @media (max-width: 980px) {{ .summary,.three-up,.two-up {{ grid-column:span 12; }} .metric-grid {{ grid-template-columns:1fr; }} .bar-row {{ grid-template-columns:1fr; }} table {{ display:block; overflow-x:auto; }} }}
  </style>
</head>
<body>
  <div class='page'>
    <section class='title-page' id='top'>
      <div class='eyebrow'>Final Research Paper</div>
      <h1>Adaptive Tracing Across Three Completed Systems, with a Preliminary QuickPizza Extension</h1>
      <p class='lead'>This paper presents a comparative study of adaptive tracing across three completed microservice applications, then adds a documented fourth-system extension using Grafana QuickPizza. The completed core evaluates reinforcement-learning and non-reinforcement-learning controllers under matched operating conditions, examines controller behavior under targeted runtime changes, and synthesizes the implemented methods into a practical taxonomy for engineering use. The QuickPizza addition is reported as preliminary evidence rather than as a fully symmetric fourth RQ1/RQ2 dataset.</p>
      <div class='meta'>
        <div class='pill'><span class='dot' style='background:#2563eb'></span>Comparative controller evaluation</div>
        <div class='pill'><span class='dot' style='background:#0f766e'></span>Runtime-change analysis</div>
        <div class='pill'><span class='dot' style='background:#7c3aed'></span>Taxonomy and design guidance</div>
        <div class='pill'><span class='dot' style='background:#15803d'></span>Completed applications: Train-Ticket, Timescale Demo, Petclinic</div>
        <div class='pill'><span class='dot' style='background:#b45309'></span>Preliminary extension: Grafana QuickPizza</div>
      </div>
      <div class='meta' style='margin-top:24px;'>
        <div class='pill'>Date: 2026-06-18</div>
        <div class='pill'>Format: paper-style HTML report</div>
        <div class='pill'>Evidence base: {len(rq1_policies)} completed controller-comparison runs + {len(rq1_baselines)} completed fixed-rate baselines + {len(rq2_rows)} completed runtime-change RL runs + {len(quickpizza['policy_rows'])} QuickPizza healthy-policy runs + {len(quickpizza['baseline_rows'])} QuickPizza fixed-rate checks</div>
      </div>
    </section>

    <section id='abstract'>
      <h2>Abstract</h2>
      <div class='card callout'>
        <p>This study investigates adaptive tracing across three completed microservice applications: Train-Ticket, the Timescale OpenTelemetry Demo, and Spring Petclinic Microservices. It then adds a preliminary fourth-system extension using Grafana QuickPizza. The completed core has three analytical objectives: first, to compare reinforcement-learning and non-reinforcement-learning tracing controllers under matched operating conditions; second, to examine how RL controllers behave under runtime changes such as latency spikes, error bursts, and throughput drops; and third, to derive a practical taxonomy of adaptive tracing strategies from the completed experiments.</p>
        <p>The completed cross-system results show that there is <strong>no universal best controller</strong>. Q-Learning is the strongest overall method on Train-Ticket, the rule-based baseline gives the best final latency on the Timescale application, and Bandit is the strongest Petclinic policy on final runtime metrics. Under runtime-change scenarios, Bandit wins the most latency cases overall, while SARSA wins the most throughput cases. The QuickPizza extension shows that the instrumentation path and adaptive-control hooks are working on a fourth application, and its current healthy-only results suggest that SARSA is the strongest runtime policy in that preliminary slice while Q-Learning has the highest contextual RL reward. Because QuickPizza does not yet have a full faulted controller matrix or a complete RQ2 matrix, it is reported as preliminary evidence rather than folded into the completed three-system totals.</p>
      </div>
    </section>

    <section id='contents'>
      <h2>Contents</h2>
      <div class='card toc'>
        <ol>
          <li><a href='#introduction'>Introduction</a></li>
          <li><a href='#objectives'>Study Objectives and Scope</a></li>
          <li><a href='#systems'>Experimental Systems</a></li>
          <li><a href='#quickpizza-extension'>Preliminary QuickPizza Extension</a></li>
          <li><a href='#methodology'>Methodology</a></li>
          <li><a href='#comparative-results'>Comparative Evaluation of Controller Families</a></li>
          <li><a href='#runtime-results'>Controller Behavior Under Runtime Changes</a></li>
          <li><a href='#taxonomy-results'>Taxonomy and Design Guidance</a></li>
          <li><a href='#discussion'>Discussion</a></li>
          <li><a href='#limitations'>Threats to Validity and Limitations</a></li>
          <li><a href='#conclusion'>Conclusion</a></li>
          <li><a href='#references'>References</a></li>
          <li><a href='#appendix'>Appendix</a></li>
        </ol>
      </div>
    </section>

    <section id='introduction'>
      <h2>1. Introduction</h2>
      <div class='grid'>
        <article class='card two-up'>
          <p>Distributed tracing is essential for observing microservice applications, but a fixed tracing configuration forces an undesirable tradeoff. High sampling improves visibility while increasing telemetry cost; low sampling reduces overhead while weakening diagnostic power. Adaptive tracing addresses this problem by modifying the tracing rate at runtime according to observed system behavior. The study is grounded in established distributed tracing literature and platforms, including Dapper, X-Trace, OpenTelemetry, Jaeger, and Zipkin, together with project readings on adaptive observability and RL-guided logging.</p>
          <p>The practical question is not whether adaptation is useful in principle. The practical question is <em>which kind</em> of adaptive tracing is strongest under realistic conditions. This report therefore treats adaptive tracing as a control problem and evaluates multiple controller families rather than a single adaptive algorithm.</p>
        </article>
        <article class='card two-up'>
          <p>The project evaluates five adaptive controllers: <strong>Q-Learning</strong>, <strong>SARSA</strong>, <strong>Bandit</strong>, <strong>Rule</strong>, and <strong>K-Means</strong>. These span both RL and non-RL approaches. The report then extends the comparison beyond static healthy/faulted conditions by introducing controlled runtime changes, and finally synthesizes the methods into a taxonomy of adaptive tracing strategies.</p>
          <p>The result is a combined engineering and research contribution: a cross-system comparison, a runtime-change study, a method taxonomy grounded in implemented experiments rather than only conceptual classification, and a documented fourth-system extension that tests whether the same workflow can be moved onto Grafana QuickPizza.</p>
        </article>
        <article class='card full callout'>
          <h3>1.1 Why this work is useful</h3>
          <p>This study is intended to support a practical decision that observability teams face in real systems: how to retain diagnostically useful traces without paying unnecessary telemetry cost under changing workload conditions. The value of the work is therefore not only that it compares algorithms, but that it translates the comparison into controller-selection guidance.</p>
          <p>In practical terms, the paper helps answer three operational questions: when a simple transparent heuristic is sufficient, when reinforcement learning becomes worthwhile, and how much the answer depends on the runtime behavior of the application itself. That practical usefulness is central to the interpretation of the results.</p>
        </article>
      </div>
    </section>

    <section id='objectives'>
      <h2>2. Study Objectives and Scope</h2>
      <div class='grid'>
        <article class='card summary'><div class='summary-k'>Objective A</div><div class='summary-v'>Controller comparison</div><div class='summary-note'>Compare RL and non-RL adaptive tracing under matched system conditions.</div></article>
        <article class='card summary'><div class='summary-k'>Objective B</div><div class='summary-v'>Runtime-change behavior</div><div class='summary-note'>Evaluate RL controllers under latency spikes, error bursts, and throughput drops.</div></article>
        <article class='card summary'><div class='summary-k'>Objective C</div><div class='summary-v'>Taxonomy</div><div class='summary-note'>Classify adaptive tracing types by goals, decision signals, and observed behavior.</div></article>
        <article class='card summary'><div class='summary-k'>Scope</div><div class='summary-v'>3 + 1 systems</div><div class='summary-note'>Three completed systems plus a preliminary QuickPizza extension.</div></article>
        <article class='card full callout'>
          <p><strong>Objective A:</strong> compare RL-based adaptive tracing with non-RL baselines, such as rule-based and clustering-based methods, when all methods are evaluated under the same microservice system and the same runtime conditions.</p>
          <p><strong>Objective B:</strong> examine how RL-based adaptive tracing methods behave under different runtime changes, specifically latency spikes, throughput drops, and error bursts.</p>
          <p><strong>Objective C:</strong> identify the main types of adaptive tracing and explain how they differ in goals, decision signals, and tracing behavior.</p>
          <p><strong>Extension objective:</strong> verify that the same adaptive-tracing workflow can be transferred onto Grafana QuickPizza and produce credible preliminary evidence without yet claiming a completed fourth-system comparison.</p>
        </article>
      </div>
    </section>

    <section id='systems'>
      <h2>3. Experimental Systems</h2>
      <div class='card'>
        <table>
          <thead><tr><th>System</th><th>Domain</th><th>Technical Role in the Study</th><th>Observability / Tracing Context</th><th>Controller-Comparison Winner</th></tr></thead>
          <tbody>
            {''.join(f"<tr><td>{name}</td><td>{meta['domain']}</td><td>{meta['role']}</td><td>{meta['stack']}</td><td>{meta['rq1_winner']}</td></tr>" for name, meta in SYSTEMS.items())}
            <tr><td>Grafana QuickPizza</td><td>Pizza recommendation microservice application</td><td>Fourth-system extension used to test transfer of the adaptive tracing workflow onto a Grafana-maintained observability demo</td><td>Grafana local stack with Alloy, Prometheus, Tempo, Loki, Pyroscope, Grafana, and QuickPizza microservices</td><td>Preliminary healthy-only result: {POLICIES[quickpizza['best_latency']['policy']]['label'] if quickpizza['best_latency'] else 'n/a'}</td></tr>
          </tbody>
        </table>
      </div>
      <div class='grid' style='margin-top:16px;'>
        {''.join(f"<article class='card three-up'><div class='eyebrow'>{name}</div><h3>{meta['rq1_winner']}</h3><p>{meta['rq1_note']}</p><p class='caption'>{meta['role']}</p></article>" for name, meta in SYSTEMS.items())}
        <article class='card three-up'><div class='eyebrow'>Grafana QuickPizza</div><h3>{POLICIES[quickpizza['best_latency']['policy']]['label'] if quickpizza['best_latency'] else 'Preliminary'}</h3><p>Instrumentation and adaptive-control hooks are working on a fourth application, but the current evidence covers healthy-policy runs and fixed-rate checks rather than a full faulted matrix.</p><p class='caption'>Fourth-system extension used to test transfer of the adaptive tracing workflow onto a Grafana-maintained observability demo</p></article>
      </div>
    </section>

    <section id='quickpizza-extension'>
      <h2>4. Preliminary QuickPizza Extension</h2>
      <div class='grid'>
        <article class='card full callout'>
          <p><strong>Status as of June 18, 2026:</strong> the QuickPizza Grafana stack is running locally, <code>POST /api/pizza</code> is responding successfully, and the local Grafana and Prometheus endpoints are reachable. This means the fourth system is operational enough to produce preliminary adaptive-tracing evidence rather than only configuration notes.</p>
          <p>The evidence is intentionally reported as <strong>preliminary</strong>. The current QuickPizza dataset contains healthy-policy runs for Bandit, Q-Learning, Rule, and SARSA, plus fixed-rate checks for healthy, latency-spike, and error-burst scenarios. It does <strong>not</strong> yet include a complete healthy/faulted controller matrix, a K-Means run, or a full RQ2-style runtime-change matrix for the adaptive policies.</p>
        </article>
        <article class='card two-up'>
          <h3>Runtime validation</h3>
          <div class='metric-grid'>
            <div><span>QuickPizza API</span><strong><code>POST /api/pizza</code> returned 200</strong></div>
            <div><span>Grafana UI</span><strong><code>http://localhost:3000/</code> returned 200</strong></div>
            <div><span>Prometheus API</span><strong><code>http://localhost:9090/</code> returned query responses</strong></div>
          </div>
          <p class='caption'>Container validation also showed the QuickPizza services plus Alloy, Tempo, Loki, Pyroscope, Prometheus, Grafana, and Postgres running.</p>
        </article>
        <article class='card two-up warning'>
          <h3>Current observability caveat</h3>
          <p>The telemetry stack is not fully clean yet. Prometheus answered queries, but scrape status was only partially healthy during validation: <code>public-api</code> and <code>ws</code> were up, while several other targets still reported <code>up=0</code>. This does not block basic experimentation, but it weakens any claim that QuickPizza already has complete fourth-system observability parity with the other systems.</p>
        </article>
        <article class='card full'>
          <h3>Healthy-policy results currently available</h3>
          <table>
            <thead><tr><th>Policy</th><th>Scenario</th><th>Latency (ms)</th><th>QPS</th><th>Error Rate</th><th>Avg Reward</th><th>Avg Rate</th><th>Decisions</th></tr></thead>
            <tbody>
              {''.join(
                  f"<tr><td><span class='policy-badge'><span class='swatch' style='background:{POLICIES[row['policy']]['color']}'></span>{POLICIES[row['policy']]['label']}</span></td><td>{row['scenario'].title()}</td><td>{fmt(row['latency'], 2)}</td><td>{fmt(row['qps'], 3)}</td><td>{fmt(row['error_rate'], 4)}</td><td>{fmt(row['avg_reward'], 4) if row['avg_reward'] is not None else 'n/a'}</td><td>{fmt(row['avg_rate'], 3) if row['avg_rate'] is not None else 'n/a'}</td><td>{row['decision_count']}</td></tr>"
                  for row in quickpizza['policy_rows']
              )}
            </tbody>
          </table>
          <p class='caption'>On the current healthy slice, {POLICIES[quickpizza['best_latency']['policy']]['label'] if quickpizza['best_latency'] else 'n/a'} has the lowest latency, {POLICIES[quickpizza['best_qps']['policy']]['label'] if quickpizza['best_qps'] else 'n/a'} has the highest throughput, and {POLICIES[quickpizza['best_reward']['policy']]['label'] if quickpizza['best_reward'] else 'n/a'} has the highest contextual RL reward.</p>
        </article>
        <article class='card full'>
          <h3>Fixed-rate checks currently available</h3>
          <table>
            <thead><tr><th>Scenario</th><th>Sampling Rate</th><th>Latency (ms)</th><th>QPS</th><th>Error Rate</th></tr></thead>
            <tbody>
              {''.join(
                  f"<tr><td>{row['scenario'].replace('_', ' ').title()}</td><td>{fmt(row['sampling_rate'], 2) if row['sampling_rate'] is not None else 'n/a'}</td><td>{fmt(row['latency'], 2)}</td><td>{fmt(row['qps'], 3)}</td><td>{fmt(row['error_rate'], 4)}</td></tr>"
                  for row in quickpizza['baseline_rows']
              )}
            </tbody>
          </table>
        </article>
        <article class='card full callout'>
          <h3>Interpretation of the QuickPizza extension</h3>
          <p>The QuickPizza extension strengthens the project in a narrower way than the three completed systems. It shows that the adaptive-tracing workflow is transferable to a Grafana-maintained demo application with a realistic observability stack. The current evidence is enough to justify reporting QuickPizza as an operational fourth system under construction, but it is not enough to rewrite the completed cross-system RQ1 and RQ2 totals as if the fourth system were already symmetric with the other three.</p>
          <p>The immediate next step is to complete the missing QuickPizza controller matrix, add the missing K-Means and faulted-policy runs, and then rerun the cross-system synthesis with four fully comparable systems.</p>
        </article>
      </div>
    </section>

    <section id='methodology'>
      <h2>5. Methodology</h2>
      <div class='grid'>
        <article class='card two-up'>
          <h3>5.1 Adaptive tracing controllers</h3>
          <p>The study evaluates five adaptive controllers. <strong>Q-Learning</strong> and <strong>SARSA</strong> are value-learning RL methods. <strong>Bandit</strong> is a simpler RL action-value controller with weaker assumptions about longer-term dynamics. <strong>Rule</strong> is a threshold-based heuristic baseline. <strong>K-Means</strong> is a clustering-based baseline that maps recent runtime states to representative sampling rates.</p>
          <p>The common action space is a discrete set of tracing rates: <code>0.05</code>, <code>0.10</code>, <code>0.20</code>, <code>0.50</code>, and <code>0.80</code>. This keeps the comparison operationally consistent across applications.</p>
        </article>
        <article class='card two-up'>
          <h3>5.2 Measured outputs</h3>
          <p>The primary outputs are <strong>latency</strong>, <strong>QPS</strong> (throughput), <strong>error rate</strong>, and <strong>trace totals</strong>. For RL methods, <strong>average reward</strong> is also reported. Reward is useful for RL-internal interpretation, but it is not treated as a universally comparable system-quality score because reward design differs across the applications, especially in the Timescale system.</p>
          <p>Data quality is tracked through <strong>decision counts</strong> and <strong>zero-window counts</strong>, because sparse windows weaken the reliability of adaptive-control conclusions.</p>
        </article>
        <article class='card full'>
          <h3>5.3 Study design by analytical objective</h3>
          <table>
            <thead><tr><th>Objective</th><th>Compared methods</th><th>Scenario structure</th><th>Main outputs</th></tr></thead>
            <tbody>
              <tr><td>Comparative evaluation</td><td>Q-Learning, SARSA, Bandit, Rule, K-Means</td><td>Healthy and faulted per system</td><td>Final latency, final QPS, error rate, contextual RL reward</td></tr>
              <tr><td>Runtime-change analysis</td><td>Q-Learning, SARSA, Bandit</td><td>Healthy, latency spike, error burst, throughput drop</td><td>Latency/QPS winners per scenario, average selected rate, data quality</td></tr>
              <tr><td>QuickPizza extension</td><td>Current healthy-policy slice plus fixed-rate checks</td><td>Healthy adaptive runs, plus fixed-rate healthy / latency-spike / error-burst checks</td><td>Operational validation, preliminary latency/QPS/error behavior, workflow transferability</td></tr>
              <tr><td>Taxonomy synthesis</td><td>Taxonomy synthesis over implemented methods</td><td>Uses completed controller-comparison and runtime-change evidence; no new experiment matrix</td><td>Method categories, decision signals, behavior patterns, operational implications</td></tr>
            </tbody>
          </table>
        </article>
        <article class='card full warning'>
          <h3>5.4 Methodological caveats carried into the final synthesis</h3>
          <ul>
            <li>Reward is reported as <strong>contextual RL evidence</strong>, not as a uniformly comparable cross-system winner metric.</li>
            <li>The applications are not symmetric in evidence quality. Train-Ticket is the strongest result set, Timescale is valid but has reward-design caveats, and Petclinic is complete but much sparser.</li>
            <li>Fault injection mechanisms differ by application because the systems expose different operational controls. The study therefore emphasizes within-system comparisons first and then cross-system synthesis second.</li>
            <li>QuickPizza is a preliminary extension only. It is included for workflow-transfer evidence, not counted as a completed fourth system in the core comparative totals.</li>
          </ul>
        </article>
      </div>
    </section>

    <section id='comparative-results'>
      <h2>6. Comparative Evaluation of Controller Families</h2>
      <div class='grid'>
        <article class='card full callout'>
          <p><strong>Finding:</strong> RL-based adaptive tracing is consistently competitive, but there is no universal winner across the three completed applications. Q-Learning is strongest on Train-Ticket, the rule-based baseline is strongest on Timescale final latency, and Bandit is strongest on Petclinic final runtime metrics. QuickPizza is reported separately as preliminary because its matrix is not yet complete.</p>
        </article>
        <article class='card three-up'>
          <h3>Latency winner family split</h3>
          <p class='subtle'>Across the six completed system-scenario cases, RL methods win latency more often than non-RL methods.</p>
          <div class='donut-wrap'>{donut_svg([rq1_latency_family.get('RL',0), rq1_latency_family.get('Non-RL',0)], ['#2563eb','#64748b'], 'Controller-comparison latency family split')}<div class='legend'><div class='legend-item'><span class='swatch' style='background:#2563eb'></span>RL wins: {rq1_latency_family.get('RL',0)}</div><div class='legend-item'><span class='swatch' style='background:#64748b'></span>Non-RL wins: {rq1_latency_family.get('Non-RL',0)}</div></div></div>
        </article>
        <article class='card three-up'>
          <h3>QPS winner family split</h3>
          <p class='subtle'>Throughput leaders are even more RL-heavy in the completed three-system comparison.</p>
          <div class='donut-wrap'>{donut_svg([rq1_qps_family.get('RL',0), rq1_qps_family.get('Non-RL',0)], ['#0f766e','#64748b'], 'Controller-comparison QPS family split')}<div class='legend'><div class='legend-item'><span class='swatch' style='background:#0f766e'></span>RL wins: {rq1_qps_family.get('RL',0)}</div><div class='legend-item'><span class='swatch' style='background:#64748b'></span>Non-RL wins: {rq1_qps_family.get('Non-RL',0)}</div></div></div>
        </article>
        <article class='card three-up'>
          <h3>Policy win counts</h3>
          <div class='bar-chart'>
            {bar_rows([
                {'label':'Bandit latency', 'value': rq1_policy_latency.get('bandit',0), 'color':'#0f766e'},
                {'label':'Q-Learning latency', 'value': rq1_policy_latency.get('q_learning',0), 'color':'#2563eb'},
                {'label':'Rule latency', 'value': rq1_policy_latency.get('rule',0), 'color':'#64748b'},
                {'label':'SARSA QPS', 'value': rq1_policy_qps.get('sarsa',0), 'color':'#c2410c'},
                {'label':'Bandit QPS', 'value': rq1_policy_qps.get('bandit',0), 'color':'#0f766e'},
            ], max_value=3, digits=0)}
          </div>
          <p class='caption'>Reward is intentionally omitted from the headline win chart because reward interpretation is not symmetric across the systems. The preliminary QuickPizza extension is also excluded from this aggregate count.</p>
        </article>
        <article class='card full'>
          <h3>Cross-system winner summary</h3>
          <table>
            <thead><tr><th>Application</th><th>Scenario</th><th>Lowest final latency</th><th>Latency value</th><th>Highest final QPS</th><th>QPS value</th><th>Contextual RL reward leader</th><th>Avg reward (contextual)</th></tr></thead>
            <tbody>{table_rows_rq1(rq1_summary_rows)}</tbody>
          </table>
          <p class='caption'>Contextual RL reward is shown only as controller-specific support evidence. It is not treated as a fully comparable cross-system winner metric.</p>
        </article>
        <article class='card full'>
          <h3>Interpretation</h3>
          <ul>
            <li><strong>Train-Ticket</strong> provides the clearest evidence for Q-Learning. It combines strong faulted performance, strong contextual reward, and a mature decision horizon.</li>
            <li><strong>Timescale</strong> shows that a transparent heuristic can still outperform RL on final latency. This matters because it prevents an overgeneralized "RL always wins" conclusion.</li>
            <li><strong>Petclinic</strong> shows that a simpler RL family member, Bandit, can be preferable when the runtime signal is noisier and operational stability matters more than deeper value learning.</li>
          </ul>
        </article>
        <article class='card full callout'>
          <h3>What these results mean</h3>
          <p>The main meaning of the controller-comparison results is that complexity alone does not guarantee better adaptive tracing. More sophisticated learning-based control can be highly effective, but its advantage depends on whether the application produces a stable enough feedback signal to support learning. When the signal is cleaner, deeper RL can justify its additional complexity. When the signal is less stable, simpler methods may be more reliable and easier to operate.</p>
          <p>For practitioners, this means that controller choice should be framed as an engineering fit problem rather than an algorithm race. The correct question is not which controller won overall, but which controller is most appropriate for the operational characteristics of the target system.</p>
        </article>
      </div>
    </section>

    <section id='runtime-results'>
      <h2>7. Controller Behavior Under Runtime Changes</h2>
      <div class='grid'>
        <article class='card full callout'>
          <p><strong>Finding:</strong> RL behavior under runtime change is not uniform. Across the twelve system-scenario cases, <strong>Bandit</strong> wins the most latency cases ({rq2_policy_latency.get('bandit',0)}), <strong>SARSA</strong> wins the most QPS cases ({rq2_policy_qps.get('sarsa',0)}), and contextual reward leadership is split across all three RL policies. This indicates that different RL controllers react differently to degradation patterns rather than sharing one common adaptation profile.</p>
        </article>
        <article class='card three-up'>
          <h3>Latency wins</h3>
          <div class='bar-chart'>{bar_rows([
            {'label':'Bandit', 'value': rq2_policy_latency.get('bandit',0), 'color':'#0f766e'},
            {'label':'Q-Learning', 'value': rq2_policy_latency.get('q_learning',0), 'color':'#2563eb'},
            {'label':'SARSA', 'value': rq2_policy_latency.get('sarsa',0), 'color':'#c2410c'},
          ], max_value=max(rq2_policy_latency.values()), digits=0)}</div>
        </article>
        <article class='card three-up'>
          <h3>QPS wins</h3>
          <div class='bar-chart'>{bar_rows([
            {'label':'SARSA', 'value': rq2_policy_qps.get('sarsa',0), 'color':'#c2410c'},
            {'label':'Q-Learning', 'value': rq2_policy_qps.get('q_learning',0), 'color':'#2563eb'},
            {'label':'Bandit', 'value': rq2_policy_qps.get('bandit',0), 'color':'#0f766e'},
          ], max_value=max(rq2_policy_qps.values()), digits=0)}</div>
        </article>
        <article class='card three-up'>
          <h3>Average selected tracing rate</h3>
          <div class='bar-chart'>{bar_rows(avg_rate_by_policy, max_value=max(item['value'] for item in avg_rate_by_policy), digits=3)}</div>
          <p class='caption'>Across the full experiment set, Rule is the most aggressive controller on average, while Bandit and Q-Learning remain comparatively conservative.</p>
        </article>
        <article class='card full'>
          <h3>Cross-system scenario summary</h3>
          <table>
            <thead><tr><th>Application</th><th>Scenario</th><th>Latency winner</th><th>Latency value</th><th>QPS winner</th><th>QPS value</th><th>Contextual RL reward leader</th><th>Avg reward</th><th>Zero windows</th></tr></thead>
            <tbody>{table_rows_rq2(rq2_summary_rows)}</tbody>
          </table>
          <p class='caption'>Reward remains RL-internal context. The primary runtime evidence in this section is latency, QPS, error rate, and data quality.</p>
        </article>
        <article class='card two-up'>
          <h3>System-level data quality</h3>
          <table>
            <thead><tr><th>System</th><th>Comparison runs</th><th>Comparison avg decisions</th><th>Comparison zero windows</th><th>Runtime-change runs</th><th>Runtime-change avg decisions</th><th>Runtime-change zero windows</th></tr></thead>
            <tbody>
              {''.join(f"<tr><td>{sys}</td><td>{rq1_quality[sys]['runs']}</td><td>{fmt(rq1_quality[sys]['avg_decisions'],1)}</td><td>{rq1_quality[sys]['zero_windows']}</td><td>{rq2_quality[sys]['runs']}</td><td>{fmt(rq2_quality[sys]['avg_decisions'],1)}</td><td>{rq2_quality[sys]['zero_windows']}</td></tr>" for sys in SYSTEMS)}
            </tbody>
          </table>
        </article>
        <article class='card two-up warning'>
          <h3>Interpretation</h3>
          <ul>
            <li><strong>Train-Ticket</strong> remains the strongest environment for learning-oriented policies because it supplies long decision horizons and stable traffic.</li>
            <li><strong>Timescale</strong> exposes reward-design weakness most clearly. The latency-spike case shows that contextual reward can look strong even when latency becomes extreme, so runtime metrics must remain primary.</li>
            <li><strong>Petclinic</strong> remains usable but sparse. Its results still contribute meaningfully, but the short decision horizon makes the claims there weaker than in Train-Ticket.</li>
          </ul>
        </article>
        <article class='card full callout'>
          <h3>What these results mean</h3>
          <p>The runtime-change results show that reinforcement-learning controllers do not share one common adaptation behavior. One method can be better at controlling latency, while another can preserve throughput more effectively under the same disturbance. This means that runtime-change behavior is itself a design criterion, not just a secondary observation.</p>
          <p>For operations teams, the implication is direct: controller evaluation should include the kinds of disturbances that actually matter in deployment. A method that looks strong in a stable scenario may not be the right choice if the real concern is bursty slowdown, transient failures, or throughput instability.</p>
        </article>
      </div>
    </section>

    <section id='taxonomy-results'>
      <h2>8. Taxonomy and Design Guidance</h2>
      <div class='grid'>
        <article class='card full callout'>
          <p><strong>Finding:</strong> Adaptive tracing is best understood as a family of control strategies rather than one technique. The completed project supports a five-part practical taxonomy: fixed-rate baseline, rule-based control, clustering-based control, bandit-style RL control, and value-learning RL control.</p>
        </article>
        <article class='card full'>
          <h3>Adaptive tracing taxonomy</h3>
          <table>
            <thead><tr><th>Method</th><th>Type</th><th>Main goal</th><th>Decision signals</th><th>Operational overhead</th><th>Observed practical takeaway</th></tr></thead>
            <tbody>{taxonomy_rows()}</tbody>
          </table>
        </article>
        <article class='card full'>
          <h3>Complexity and decision-making ladder</h3>
          {complexity_svg()}
          <p class='caption'>This is a project-specific conceptual ladder, not a measured experimental ranking. It captures the increasing modeling and operational complexity from fixed-rate baselines to value-learning RL controllers.</p>
        </article>
        <article class='card two-up'>
          <h3>Taxonomy grounded in project evidence</h3>
          <ul>
            <li><strong>Fixed rate</strong> remains a necessary reference because it shows the cost of having no runtime adaptation at all.</li>
            <li><strong>Rule</strong> is the strongest non-RL method when runtime structure is predictable and operational transparency is a priority.</li>
            <li><strong>K-Means</strong> behaves like a moderate data-driven controller and is useful when hand-written thresholds are undesirable but full RL is unnecessary.</li>
            <li><strong>Bandit</strong> occupies the middle ground between simple heuristics and deeper RL, and it is especially effective on noisier systems such as Petclinic.</li>
            <li><strong>SARSA</strong> is the most exploratory RL method in the pooled project evidence.</li>
            <li><strong>Q-Learning</strong> is strongest when there is enough stable feedback to make long-run reward learning worthwhile.</li>
          </ul>
        </article>
        <article class='card two-up'>
          <h3>Why this synthesis matters</h3>
          <p>This synthesis prevents an overly simplistic binary framing of adaptive tracing. The completed experiments do not support a single universal controller. Instead, they support a taxonomy in which controller families differ in <strong>goals</strong>, <strong>decision signals</strong>, <strong>exploration behavior</strong>, and <strong>operational cost</strong>. This is the right abstraction for making deployment decisions in practice.</p>
          <p class='caption'>The final report treats taxonomy as the conceptual synthesis that explains the comparative and runtime-change findings rather than as a standalone experiment.</p>
        </article>
        <article class='card full callout'>
          <h3>What these results mean</h3>
          <p>The taxonomy matters because it converts a long list of experimental observations into a clearer design model. Instead of treating adaptive tracing as a single technique, the paper shows that it should be understood as a family of strategies that trade off interpretability, responsiveness, data requirements, and operational cost in different ways.</p>
          <p>This gives the results a practical meaning beyond benchmarking: it provides a vocabulary for selecting, justifying, and communicating adaptive tracing choices in real engineering settings.</p>
        </article>
      </div>
    </section>

    <section id='discussion'>
      <h2>9. Discussion</h2>
      <div class='grid'>
        <article class='card two-up'>
          <h3>9.1 What the project shows overall</h3>
          <p>The strongest project-level conclusion is that <strong>controller choice must be matched to the system</strong>. Q-Learning is best when the environment supplies rich and stable feedback, as in Train-Ticket. Rule-based control remains highly competitive when latency can be improved through transparent threshold logic, as in the Timescale system. Bandit becomes attractive when the system is real-world oriented but noisier, as in Petclinic.</p>
          <p>This means adaptive tracing should be treated as a design-space choice rather than a search for one algorithmic winner. The QuickPizza extension adds a practical secondary conclusion: the workflow itself appears portable to a fourth, Grafana-centered demo stack even before the full comparison matrix is finished.</p>
        </article>
        <article class='card two-up'>
          <h3>9.2 Operational guidance</h3>
          <ul>
            <li>Use <strong>Q-Learning</strong> when long decision horizons and stable telemetry make long-run value learning realistic.</li>
            <li>Use <strong>Bandit</strong> when quick, low-overhead adaptation is needed and the environment is noisy or sparse.</li>
            <li>Use <strong>Rule</strong> when transparency, predictability, and ease of explanation are more important than model sophistication.</li>
            <li>Use <strong>K-Means</strong> when a moderate data-driven controller is preferred over manual thresholds.</li>
            <li>Treat <strong>SARSA</strong> as the most exploratory RL option in this project, useful when controlled exploration is acceptable.</li>
          </ul>
        </article>
        <article class='card full warning'>
          <h3>9.3 Reward should not dominate the final interpretation</h3>
          <p>Reward was necessary to drive the RL controllers, but it cannot be allowed to dominate the final report. The Timescale results demonstrate why: the reward signal can look favorable even when the runtime outcome is poor. For that reason, the final synthesis prioritizes latency, QPS, error rate, and data quality over reward in the main findings.</p>
        </article>
        <article class='card full callout'>
          <h3>9.4 Practical usefulness for engineers and operators</h3>
          <ul>
            <li><strong>If the system is stable and feedback is rich,</strong> Q-Learning is a credible choice because it can exploit longer decision horizons.</li>
            <li><strong>If transparency and ease of explanation matter,</strong> Rule-based control remains attractive and can still win on important metrics.</li>
            <li><strong>If the environment is noisy or sparse,</strong> Bandit offers a useful middle ground between adaptability and operational simplicity.</li>
            <li><strong>If the goal is controller selection rather than algorithm advocacy,</strong> the study gives a practical basis for matching controller family to system behavior.</li>
          </ul>
        </article>
      </div>
    </section>

    <section id='limitations'>
      <h2>10. Threats to Validity and Limitations</h2>
      <div class='grid'>
        <article class='card full danger'>
          <ul>
            <li><strong>Unequal evidence quality:</strong> Train-Ticket is materially stronger than the other two systems. Petclinic is the weakest due to short runs and sparse decision windows.</li>
            <li><strong>QuickPizza is not yet a fully comparable fourth system:</strong> the current extension lacks a completed faulted controller matrix, lacks K-Means, and still has partial scrape-health issues in Prometheus.</li>
            <li><strong>Reward comparability:</strong> reward functions differ across systems, so cross-system reward comparisons are contextual rather than absolute.</li>
            <li><strong>Scenario heterogeneity:</strong> the exact fault or degradation mechanism differs by application because the systems expose different control surfaces.</li>
            <li><strong>Different telemetry backends:</strong> the systems use different data paths and observability stacks, which is realistic but introduces methodological heterogeneity.</li>
            <li><strong>Limited repetition:</strong> the study uses completed matrices rather than repeated statistical replications for every scenario-policy combination.</li>
          </ul>
        </article>
      </div>
    </section>

    <section id='conclusion'>
      <h2>11. Conclusion</h2>
      <div class='card callout'>
        <p>This project evaluated adaptive tracing across three completed microservice systems through a controller-comparison study, a runtime-change study, and a taxonomy synthesis, then added a preliminary QuickPizza extension. The combined evidence shows that RL-based adaptive tracing is consistently competitive but not universally dominant: Q-Learning leads Train-Ticket, Rule leads Timescale final latency, and Bandit leads Petclinic final runtime metrics. The runtime-change analysis shows that RL controllers respond differently to degradation patterns rather than exhibiting one common adaptation profile. The taxonomy synthesis shows that adaptive tracing is best understood as a family of control strategies, not as a single technique.</p>
        <p>The final engineering conclusion is direct: <strong>there is no single best adaptive tracing controller for all microservice systems</strong>. The correct choice depends on the stability of the runtime signal, the need for operational transparency, and the quality of the feedback available for learning.</p>
        <p>The broader practical conclusion is equally important: the usefulness of adaptive tracing lies in giving teams a structured way to balance observability value against telemetry cost under realistic runtime conditions. The QuickPizza extension pushes that conclusion further by showing that the workflow can be moved onto a fourth system, even though that fourth dataset is not yet complete enough to change the core comparative totals.</p>
      </div>
    </section>

    <section id='references'>
      <h2>12. References</h2>
      <div class='grid'>
        <article class='card full'>
          <p class='caption'>The paper is grounded in a combination of foundational distributed tracing literature, observability platform documentation, and additional project readings consulted during the literature-review phase.</p>
          <ol class='refs'>
            <li>Sigelman, B. H., Barroso, L. A., Burrows, M., Stephenson, P., Plakal, M., Beaver, D., Jaspan, S., and Shanbhag, C. <em>Dapper, a Large-Scale Distributed Systems Tracing Infrastructure</em>. Google technical report, 2010.</li>
            <li>Fonseca, R., Porter, G., Katz, R. H., Shenker, S., and Stoica, I. <em>X-Trace: A Pervasive Network Tracing Framework</em>. NSDI, 2007.</li>
            <li>Kaldor, J., Mace, J., Bejda, M., Gao, E., Kuropatwa, W., O'Neill, J., Ong, K., Schaller, B., Shan, P., Viscomi, B., Venkataraman, V., Veeraraghavan, K., Werner, K., and Zhou, Y. <em>Canopy: An End-to-End Performance Tracing and Analysis System</em>. SOSP, 2017.</li>
            <li>Mace, J., Roelke, R., and Fonseca, R. <em>Pivot Tracing: Dynamic Causal Monitoring for Distributed Systems</em>. SOSP, 2015.</li>
            <li>OpenTelemetry Project. <em>OpenTelemetry Documentation and Demo Materials</em>. Used for instrumentation, collector configuration, and architecture review during the project. Relevant local systems include the Timescale OpenTelemetry Demo and the Astronomy Shop reading bundle.</li>
            <li>Jaeger Project. <em>Jaeger Documentation and HotROD/Tracing References</em>. Used as part of the tracing literature and tooling context for the project.</li>
            <li>Zipkin Project. <em>Zipkin Documentation</em>. Used for tracing backend interpretation in the Spring Petclinic experiments.</li>
            <li><em>An Adaptive Logging System (ALS): Enhancing Software Logging with Reinforcement Learning Techniques</em>. Additional project reading consulted during the literature review.</li>
            <li>Additional locally stored readings consulted during the literature review included an NSDI 2023 reading on trace collection and sampling, an adaptive tracing / observability review, and an arXiv reading on adaptive observability. These informed the study framing but were not used as standalone experimental data sources.</li>
            <li>Internal project records and generated experiment reports were also used during synthesis. These are documented in the appendix as study artifacts rather than formal external references.</li>
          </ol>
        </article>
      </div>
    </section>

    <section id='appendix'>
      <h2>13. Appendix</h2>
      <div class='grid'>
        <article class='card two-up'>
          <h3>Source artifacts used in this final report</h3>
          <ul>
            <li><code>/Users/dan/rq1_all_three_systems_report.html</code></li>
            <li><code>/Users/dan/rq2_all_three_systems_report.html</code></li>
            <li><code>/Users/dan/rq3_adaptive_tracing_taxonomy_report.html</code></li>
            <li><code>/Users/dan/train-ticket-python/experiment_results</code></li>
            <li><code>/Users/dan/timescale-otel-demo/experiment_results</code></li>
            <li><code>/Users/dan/spring-petclinic-microservices/experiment_results</code></li>
            <li><code>/Users/dan/quickpizza/experiment_results</code></li>
            <li><code>/Users/dan/quickpizza/QUICKPIZZA_ADAPTIVE_NOTES.md</code></li>
          </ul>
        </article>
        <article class='card two-up'>
          <h3>Document note</h3>
          <p>This paper-style report is synthesized directly from the completed experiment outputs, the reviewed cross-system reports, and the current QuickPizza extension artifacts. It is intended to replace the earlier question-by-question presentation with one integrated final narrative suitable for final write-up and later LaTeX conversion.</p>
          <p class='foot'><a href='#top'>Back to top</a></p>
        </article>
      </div>
    </section>
  </div>
</body>
</html>
"""
    OUT.write_text(html, encoding='utf-8')
    print(OUT)


if __name__ == '__main__':
    build_html()
