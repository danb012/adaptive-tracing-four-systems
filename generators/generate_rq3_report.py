#!/usr/bin/env python3
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path('/Users/dan')
OUT = ROOT / 'rq3_adaptive_tracing_taxonomy_report.html'

SYSTEMS = {
    'Train-Ticket': ROOT / 'train-ticket-python' / 'experiment_results',
    'Timescale OpenTelemetry Demo': ROOT / 'timescale-otel-demo' / 'experiment_results',
    'Spring Petclinic Microservices': ROOT / 'spring-petclinic-microservices' / 'experiment_results',
}
POLICY_INFO = {
    'q_learning': {
        'label': 'Q-Learning',
        'type': 'RL-based value-learning',
        'goal': 'Maximize long-run reward while adapting the sampling rate conservatively.',
        'signals': 'Current runtime state bins derived from error rate, latency, and throughput.',
        'behavior': 'Off-policy temporal-difference learner; tends to be conservative until degradation becomes clear.',
        'color': '#2563eb',
    },
    'sarsa': {
        'label': 'SARSA',
        'type': 'RL-based value-learning',
        'goal': 'Adapt tracing while learning from the action actually taken by the current policy.',
        'signals': 'Same runtime state bins as Q-Learning, but updated on-policy.',
        'behavior': 'On-policy RL method; often more exploratory and more willing to move off the minimum rate.',
        'color': '#c2410c',
    },
    'bandit': {
        'label': 'Bandit',
        'type': 'RL-based action-value control',
        'goal': 'Choose the sampling rate with the best observed payoff without learning a full transition model.',
        'signals': 'Immediate reward from recent runtime behavior, indexed by coarse state.',
        'behavior': 'Simpler RL family member; often stable and low-overhead, especially on Petclinic.',
        'color': '#0f766e',
    },
    'rule': {
        'label': 'Rule',
        'type': 'Heuristic threshold control',
        'goal': 'Raise or lower tracing based on explicit runtime thresholds.',
        'signals': 'Direct thresholds on error rate, latency, or event count depending on the system.',
        'behavior': 'Deterministic and easy to explain; can be strong when system behavior is predictable.',
        'color': '#64748b',
    },
    'kmeans': {
        'label': 'K-Means',
        'type': 'Clustering-based control',
        'goal': 'Map similar runtime states to a representative sampling level.',
        'signals': 'Cluster assignment from recent latency, error, and throughput features.',
        'behavior': 'Data-driven but not reward-learning; often behaves like a moderate fixed-rate controller.',
        'color': '#15803d',
    },
    'fixed_rate': {
        'label': 'Fixed Rate',
        'type': 'Static baseline',
        'goal': 'Keep tracing constant regardless of runtime conditions.',
        'signals': 'None after configuration time.',
        'behavior': 'Not adaptive; useful as a baseline for interpreting controller behavior.',
        'color': '#7c3aed',
    },
}
TYPE_COLORS = {
    'Static baseline': '#7c3aed',
    'Heuristic threshold control': '#64748b',
    'Clustering-based control': '#15803d',
    'RL-based action-value control': '#0f766e',
    'RL-based value-learning': '#2563eb',
}

SCENARIO_LABELS = {
    'healthy': 'Healthy',
    'faulted': 'Faulted',
    'latency_spike': 'Latency Spike',
    'error_burst': 'Error Burst',
    'throughput_drop': 'Throughput Drop',
}


def load_runs():
    rows = []
    for system_name, root in SYSTEMS.items():
        for rq, folder in [('RQ1', root), ('RQ2', root / 'rq2')]:
            if not folder.exists():
                continue
            for path in sorted(folder.glob('*.json')):
                payload = json.loads(path.read_text())
                policy = payload.get('policy') or 'fixed_rate'
                summary = payload.get('summary', {})
                status = payload.get('status', payload.get('metrics', {}))
                decisions = payload.get('decisions', {}).get('items', [])
                configured_rate = payload.get('sampling_rate')
                avg_rate = summary.get('avg_rate')
                if avg_rate is None and policy == 'fixed_rate':
                    avg_rate = configured_rate
                avg_reward = summary.get('avg_reward')
                if policy in {'rule', 'kmeans', 'fixed_rate'}:
                    avg_reward = None
                rows.append({
                    'system': system_name,
                    'rq': rq,
                    'policy': policy,
                    'scenario': payload.get('scenario', f"rate_{configured_rate or 'unknown'}"),
                    'avg_rate': avg_rate,
                    'avg_reward': avg_reward,
                    'configured_rate': configured_rate,
                    'latency': status.get('avg_latency_ms', 0.0),
                    'qps': status.get('qps', 0.0),
                    'error_rate': status.get('error_rate', 0.0),
                    'decision_count': summary.get('decision_count', len(decisions) if decisions else 0),
                    'zero_windows': sum(1 for item in decisions if not item.get('total')),
                    'is_adaptive': policy != 'fixed_rate',
                })
    return rows


def avg(values):
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def fmt(value, digits=3):
    if value is None:
        return 'n/a'
    return f'{value:.{digits}f}'


def build_type_summary(rows):
    by_type = defaultdict(list)
    for row in rows:
        if row['policy'] not in POLICY_INFO:
            continue
        by_type[POLICY_INFO[row['policy']]['type']].append(row)
    out = []
    for type_name, items in by_type.items():
        out.append({
            'type': type_name,
            'count': len(items),
            'avg_rate': avg([r['avg_rate'] for r in items]),
            'avg_reward': avg([r['avg_reward'] for r in items]),
            'avg_zero': avg([r['zero_windows'] for r in items]),
            'reward_note': 'Contextual only' if type_name in {'Static baseline', 'Heuristic threshold control', 'Clustering-based control'} else 'Comparable within RL families',
        })
    order = ['Static baseline', 'Heuristic threshold control', 'Clustering-based control', 'RL-based action-value control', 'RL-based value-learning']
    return sorted(out, key=lambda x: order.index(x['type']) if x['type'] in order else 99)


def build_policy_summary(rows):
    by_pol = defaultdict(list)
    for row in rows:
        by_pol[row['policy']].append(row)
    out = []
    for pol, items in by_pol.items():
        info = POLICY_INFO[pol]
        out.append({
            'policy': pol,
            'label': info['label'],
            'type': info['type'],
            'avg_rate': avg([r['avg_rate'] for r in items]),
            'avg_reward': avg([r['avg_reward'] for r in items]),
            'avg_decisions': avg([r['decision_count'] for r in items]),
            'avg_zero': avg([r['zero_windows'] for r in items]),
            'color': info['color'],
            'is_adaptive': pol != 'fixed_rate',
        })
    order = ['fixed_rate', 'rule', 'kmeans', 'bandit', 'sarsa', 'q_learning']
    return sorted(out, key=lambda x: order.index(x['policy']) if x['policy'] in order else 99)


def type_cards_html(type_summary):
    blocks = []
    for item in type_summary:
        color = TYPE_COLORS.get(item['type'], '#334155')
        reward_label = 'Average reward' if item['avg_reward'] is not None else 'Reward interpretation'
        reward_value = fmt(item['avg_reward'], 4) if item['avg_reward'] is not None else item['reward_note']
        rate_label = 'Average configured rate' if item['type'] == 'Static baseline' else 'Average selected rate'
        blocks.append(
            f"<article class='card summary'><div class='eyebrow'>Type</div><h3><span class='swatch' style='background:{color}'></span>{item['type']}</h3><p class='caption'>Observed runs: {item['count']}</p><p><strong>{rate_label}:</strong> {fmt(item['avg_rate'],3)}</p><p><strong>{reward_label}:</strong> {reward_value}</p><p><strong>Average zero windows:</strong> {fmt(item['avg_zero'],2)}</p></article>"
        )
    return ''.join(blocks)


def policy_rows_html(policy_summary):
    rows = []
    for item in policy_summary:
        info = POLICY_INFO[item['policy']]
        reward_display = fmt(item['avg_reward'], 4) if item['avg_reward'] is not None else 'Contextual only'
        decision_display = fmt(item['avg_decisions'], 1) if item['is_adaptive'] else 'n/a'
        zero_display = fmt(item['avg_zero'], 2) if item['is_adaptive'] else 'n/a'
        rate_display = f"{fmt(item['avg_rate'],3)} (configured)" if not item['is_adaptive'] else fmt(item['avg_rate'],3)
        rows.append(
            f"<tr><td><span class='policy-badge'><span class='swatch' style='background:{item['color']}'></span>{item['label']}</span></td><td>{item['type']}</td><td>{info['goal']}</td><td>{info['signals']}</td><td>{info['behavior']}</td><td>{rate_display}</td><td>{reward_display}</td><td>{decision_display}</td><td>{zero_display}</td></tr>"
        )
    return ''.join(rows)


def avg_rate_chart(policy_summary):
    adaptive_items = [item for item in policy_summary if item['is_adaptive']]
    vals = [item['avg_rate'] or 0.0 for item in adaptive_items]
    maxv = max(vals) if vals else 1.0
    rows = []
    for item in adaptive_items:
        value = item['avg_rate'] or 0.0
        width = 100 * value / maxv if maxv else 0
        rows.append(
            f"<div class='bar-row'><div class='bar-label'><span class='swatch' style='background:{item['color']}'></span>{item['label']}</div><div class='bar-track'><div class='bar-fill' style='width:{width:.1f}%;background:{item['color']}'></div></div><div class='bar-value'>{fmt(value,3)}</div></div>"
        )
    return ''.join(rows)


def complexity_svg():
    items = [
        ('Fixed Rate', 'Static baseline', 1),
        ('Rule', 'Threshold logic', 2),
        ('K-Means', 'Cluster mapping', 3),
        ('Bandit', 'Immediate value learning', 4),
        ('SARSA', 'On-policy TD RL', 5),
        ('Q-Learning', 'Off-policy TD RL', 6),
    ]
    svg = ["<svg viewBox='0 0 900 210' role='img' aria-label='Project-specific adaptive tracing complexity ladder'>"]
    x = 20
    for label, subtitle, level in items:
        width = 130
        height = 140
        y = 30 + (6-level)*4
        color = POLICY_INFO.get(label.lower().replace('-', '_').replace(' ', '_'), {}).get('color', '#475569')
        if label == 'Fixed Rate':
            color = POLICY_INFO['fixed_rate']['color']
        elif label == 'Rule':
            color = POLICY_INFO['rule']['color']
        elif label == 'K-Means':
            color = POLICY_INFO['kmeans']['color']
        elif label == 'Bandit':
            color = POLICY_INFO['bandit']['color']
        elif label == 'SARSA':
            color = POLICY_INFO['sarsa']['color']
        elif label == 'Q-Learning':
            color = POLICY_INFO['q_learning']['color']
        svg.append(f"<rect x='{x}' y='{y}' width='{width}' height='{height}' rx='18' fill='{color}' opacity='0.92'></rect>")
        svg.append(f"<text x='{x+18}' y='{y+38}' fill='white' font-size='24' font-family='Georgia, serif'>{label}</text>")
        svg.append(f"<text x='{x+18}' y='{y+68}' fill='white' font-size='14' font-family='Georgia, serif'>{subtitle}</text>")
        svg.append(f"<text x='{x+18}' y='{y+108}' fill='white' font-size='13' font-family='Georgia, serif'>complexity level {level}</text>")
        x += 145
    svg.append("</svg>")
    return ''.join(svg)


def build_html(rows):
    type_summary = build_type_summary(rows)
    policy_summary = build_policy_summary(rows)
    adaptive_rows = [row for row in rows if row['is_adaptive']]
    baseline_rows = [row for row in rows if not row['is_adaptive']]
    baseline_rate = avg([row['avg_rate'] for row in baseline_rows])
    html = f"""<!DOCTYPE html>
<html lang='en'>
<head>
  <meta charset='UTF-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1.0' />
  <title>RQ3 Report - Adaptive Tracing Taxonomy and Behavioral Synthesis</title>
  <style>
    :root {{ --ink:#102a43; --muted:#5b6878; --line:#d7e3ec; --shadow:0 18px 42px rgba(15,23,42,.08); }}
    body {{ margin:0; font-family: Georgia, 'Times New Roman', serif; color:var(--ink); background:linear-gradient(180deg,#f8fbfd,#ffffff 26%); }}
    .page {{ max-width:1240px; margin:0 auto; padding:28px 18px 64px; }}
    .hero,.card {{ background:#fff; border:1px solid var(--line); border-radius:20px; box-shadow:var(--shadow); }}
    .hero {{ padding:28px; }}
    .grid {{ display:grid; grid-template-columns:repeat(12,1fr); gap:14px; margin-top:16px; }}
    .card {{ padding:16px; grid-column:span 12; }}
    .summary {{ grid-column:span 4; }}
    h1,h2,h3 {{ color:#102a43; line-height:1.2; }}
    h1 {{ margin:0 0 10px; font-size:2.6rem; }}
    h2 {{ margin:34px 0 12px; font-size:1.4rem; border-bottom:1px solid #e5e7eb; padding-bottom:8px; }}
    h3 {{ margin:0 0 8px; font-size:1.05rem; display:flex; align-items:center; gap:8px; }}
    p {{ line-height:1.68; }}
    .eyebrow {{ font-size:.8rem; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); margin-bottom:8px; }}
    .swatch {{ width:10px; height:10px; border-radius:999px; display:inline-block; }}
    .policy-badge {{ display:inline-flex; align-items:center; gap:8px; font-weight:600; }}
    .metric-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-top:12px; }}
    .metric-grid div {{ border:1px solid var(--line); border-radius:12px; background:#fbfdff; padding:10px 12px; }}
    .metric-grid span {{ display:block; font-size:.82rem; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; }}
    .metric-grid strong {{ display:block; margin-top:4px; }}
    table {{ width:100%; border-collapse:collapse; margin-top:14px; font-size:.94rem; }}
    th,td {{ padding:10px 12px; border-top:1px solid var(--line); text-align:left; vertical-align:top; }}
    thead th {{ background:#eff6fb; border-top:none; }}
    .bar-chart {{ display:grid; gap:10px; margin-top:12px; }}
    .bar-row {{ display:grid; grid-template-columns:180px 1fr 80px; gap:10px; align-items:center; }}
    .bar-track {{ height:16px; border-radius:999px; background:#e8eef5; overflow:hidden; }}
    .bar-fill {{ height:100%; border-radius:999px; }}
    .bar-value {{ text-align:right; color:var(--muted); font-variant-numeric:tabular-nums; }}
    .caption {{ color:var(--muted); font-size:.92rem; }}
    ul {{ line-height:1.7; }}
    @media (max-width: 950px) {{ .summary {{ grid-column:span 12; }} .metric-grid {{ grid-template-columns:1fr; }} .bar-row {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <div class='page'>
    <section class='hero'>
      <div class='eyebrow'>Research Question 3</div>
      <h1>RQ3 Report: Main Types of Adaptive Tracing and How They Differ</h1>
      <p><strong>RQ3:</strong> What are the main types of adaptive tracing, and how do they differ in goals, decision signals, and tracing behavior?</p>
      <p>This report answers RQ3 by synthesizing the methods implemented and evaluated in the project across all three applications. It does not introduce a new experiment matrix. Instead, it organizes the implemented controllers into a defensible taxonomy and explains how each type behaves in practice based on the completed RQ1 and RQ2 evidence.</p>
    </section>

    <section class='grid'>
      <article class='card summary'><div class='eyebrow'>Adaptive tracing types</div><h3>5 practical categories</h3><p class='caption'>Static baseline, heuristic threshold control, clustering-based control, RL action-value control, and RL value-learning control.</p></article>
      <article class='card summary'><div class='eyebrow'>Adaptive-controller evidence</div><h3>{len(adaptive_rows)} controller runs</h3><p class='caption'>Aggregated adaptive-policy evidence from the completed RQ1 and RQ2 results across all three applications.</p></article>
      <article class='card summary'><div class='eyebrow'>Baseline reference</div><h3>{len(baseline_rows)} fixed-rate runs</h3><p class='caption'>The non-adaptive baseline is kept separate. Its mean configured rate in the pooled evidence is {fmt(baseline_rate,3)}.</p></article>
    </section>

    <section>
      <h2>1. Taxonomy of Adaptive Tracing Types</h2>
      <div class='grid'>
        {type_cards_html(type_summary)}
      </div>
      <div class='card' style='margin-top:16px;'>
        <p>The project evidence supports a practical five-part taxonomy. <strong>Fixed-rate tracing</strong> is the non-adaptive baseline and is reported separately from adaptive controllers when evidence is counted. <strong>Rule-based adaptive tracing</strong> reacts to explicit thresholds. <strong>Clustering-based adaptive tracing</strong> maps similar runtime states to a rate using unsupervised grouping. <strong>Bandit-style adaptive tracing</strong> learns from the immediate payoff of actions without a full transition model. <strong>Value-learning RL methods</strong>, represented by Q-Learning and SARSA, learn the long-run usefulness of tracing actions under changing runtime conditions.</p>
      </div>
    </section>

    <section>
      <h2>2. Complexity and Decision-Making Ladder</h2>
      <div class='card'>
        {complexity_svg()}
        <p class='caption'>This is a project-specific conceptual ladder, not a measured experimental ranking. From left to right, the controllers become more adaptive and more model-driven, which generally increases configuration or learning complexity.</p>
      </div>
    </section>

    <section>
      <h2>3. Method-Level Comparison</h2>
      <div class='card'>
        <table>
          <thead>
            <tr>
              <th>Method</th>
              <th>Type</th>
              <th>Main goal</th>
              <th>Decision signals</th>
              <th>Observed tracing behavior</th>
              <th>Avg selected rate</th>
              <th>Avg reward</th>
              <th>Avg decision count</th>
              <th>Avg zero windows</th>
            </tr>
          </thead>
          <tbody>
            {policy_rows_html(policy_summary)}
          </tbody>
        </table>
      </div>
    </section>

    <section>
      <h2>4. Tracing Behavior in Practice</h2>
      <div class='grid'>
        <article class='card' style='grid-column:span 7;'>
          <div class='eyebrow'>Average selected tracing rate across RQ1 and RQ2 adaptive runs</div>
          <div class='bar-chart'>{avg_rate_chart(policy_summary)}</div>
          <p class='caption'>This chart summarizes how aggressively each adaptive method tends to sample once the completed controller runs are pooled together. The fixed-rate baseline is excluded because it does not make runtime selections.</p>
        </article>
        <article class='card' style='grid-column:span 5;'>
          <div class='eyebrow'>Interpretation</div>
          <ul>
            <li><strong>Fixed rate</strong> has no runtime adaptation at all.</li>
            <li><strong>Rule</strong> can be either conservative or aggressive depending on threshold logic; in the Petclinic evidence it became the most aggressive controller under faulted conditions.</li>
            <li><strong>K-Means</strong> behaves like a moderate, stable controller and often stays near a representative middle rate.</li>
            <li><strong>Bandit</strong> tends to be conservative and low-overhead in this project, but it can still react strongly when the immediate payoff is clear.</li>
            <li><strong>SARSA</strong> is the most exploratory RL method in the pooled project evidence.</li>
            <li><strong>Q-Learning</strong> tends to stay conservative until degradation becomes clearer, then adjusts with stronger long-run reward awareness.</li>
          </ul>
        </article>
      </div>
    </section>

    <section>
      <h2>5. What the Three Systems Contributed to RQ3</h2>
      <div class='grid'>
        <article class='card summary'><div class='eyebrow'>Train-Ticket</div><p>Showed the clearest and most stable distinction between RL value-learning and simpler baselines. It is the strongest evidence for Q-Learning as a practical adaptive tracing type.</p></article>
        <article class='card summary'><div class='eyebrow'>Timescale OpenTelemetry Demo</div><p>Showed that heuristic control can still win on final latency, which matters because it prevents an overly simplistic “RL always wins” taxonomy.</p></article>
        <article class='card summary'><div class='eyebrow'>Spring Petclinic Microservices</div><p>Showed that a simpler RL family member like Bandit can be the best choice when runtime signals are noisier and operational complexity matters.</p></article>
      </div>
    </section>

    <section>
      <h2>6. Answer to RQ3</h2>
      <div class='card'>
        <p>The main adaptive tracing types identified in this project are: <strong>static fixed-rate tracing</strong>, <strong>rule-based adaptive tracing</strong>, <strong>clustering-based adaptive tracing</strong>, <strong>bandit-style RL adaptive tracing</strong>, and <strong>value-learning RL adaptive tracing</strong>.</p>
        <p>They differ along three axes:</p>
        <p class='caption'>Reward values are compared only inside the RL families. For rule-based, clustering-based, and fixed-rate methods, reward is treated as controller-specific context rather than a directly comparable cross-family score.</p>
        <div class='metric-grid'>
          <div><span>Goals</span><strong>Some optimize low overhead, others optimize immediate payoff, and others optimize long-run reward.</strong></div>
          <div><span>Decision signals</span><strong>They range from no runtime signal at all to threshold logic, cluster assignments, and state-value updates from latency, error, and throughput.</strong></div>
          <div><span>Tracing behavior</span><strong>They differ in conservatism, stability, exploration, and willingness to change the sampling rate under degradation.</strong></div>
        </div>
        <p>In practical terms, RQ3 shows that adaptive tracing is not one technique. It is a family of control styles. The completed experiments demonstrate that these styles are meaningfully different both in how they make decisions and in how they behave on real microservice applications.</p>
      </div>
    </section>

    <section>
      <h2>7. Final Synthesis</h2>
      <div class='card'>
        <p>The strongest project-level interpretation is that adaptive tracing should be discussed as a taxonomy of control strategies rather than as a single binary choice. Static, heuristic, clustering-based, and RL-based methods all occupy different points in the design space. The completed RQ1 and RQ2 evidence shows that:</p>
        <ul>
          <li>RL-based value-learning methods are the most expressive and often the strongest when the system supports stable learning.</li>
          <li>Bandit-style control is a useful middle ground between simple heuristics and full value-learning RL.</li>
          <li>Rule-based control remains competitive when the runtime structure is simple and the system responds predictably to thresholds.</li>
          <li>Clustering-based control is useful when moderate, data-driven behavior is preferred over manual thresholds.</li>
          <li>Fixed-rate tracing remains an important baseline because it shows what is lost when runtime adaptation is absent.</li>
        </ul>
      </div>
    </section>
  </div>
</body>
</html>"""
    OUT.write_text(html, encoding='utf-8')
    print(OUT)


if __name__ == '__main__':
    build_html(load_runs())
