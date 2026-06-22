#!/usr/bin/env python3
import json
from collections import Counter
from pathlib import Path

import generate_final_paper_report as base

ROOT = Path('/Users/dan')
OUT = ROOT / 'final_adaptive_tracing_paper_report.tex'
QUICKPIZZA_SYSTEM = 'Grafana QuickPizza'
QUICKPIZZA_RESULTS = ROOT / 'quickpizza' / 'experiment_results'
ALL_SYSTEMS = list(base.SYSTEMS.keys()) + [QUICKPIZZA_SYSTEM]


def esc(text: str) -> str:
    repl = {
        '\\': r'\textbackslash{}',
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\textasciicircum{}',
    }
    return ''.join(repl.get(ch, ch) for ch in str(text))


def fmt(value, digits=2):
    return base.fmt(value, digits)


def bar_chart(title, data, xlabel, color_map, width='0.95\\linewidth', height='4.6cm', symbolic=False):
    labels = [item[0] for item in data]
    coords = ' '.join(f'({{{esc(label)}}},{value})' for label, value in data)
    figure_env = 'figure*' if symbolic or len(labels) > 5 else 'figure'
    if symbolic:
        ytick = ','.join('{' + esc(label) + '}' for label in labels)
        axis = rf"""
\begin{{{figure_env}}}[t]
\centering
\begin{{tikzpicture}}
\begin{{axis}}[
    width={width},
    height={height},
    scale only axis,
    xbar,
    xmin=0,
    axis x line*=bottom,
    axis y line*=left,
    xlabel={{{esc(xlabel)}}},
    symbolic y coords={{{ytick}}},
    ytick=data,
    y dir=reverse,
    bar width=10pt,
    enlarge y limits=0.16,
    nodes near coords,
    nodes near coords align={{horizontal}},
    nodes near coords style={{font=\scriptsize}},
    every axis plot/.append style={{fill=tealrule, draw=tealrule}},
    tick label style={{font=\scriptsize}},
    yticklabel style={{font=\scriptsize, align=right, text width=2.5cm}},
    label style={{font=\scriptsize}},
]
\addplot coordinates {{{coords}}};
\end{{axis}}
\end{{tikzpicture}}
\caption{{{esc(title)}}}
\end{{{figure_env}}}
"""
    else:
        xtick = ','.join('{' + esc(label) + '}' for label in labels)
        axis = rf"""
\begin{{{figure_env}}}[t]
\centering
\begin{{tikzpicture}}
\begin{{axis}}[
    width={width},
    height={height},
    scale only axis,
    ybar,
    ymin=0,
    ylabel={{{esc(xlabel)}}},
    symbolic x coords={{{xtick}}},
    xtick=data,
    xticklabel style={{rotate=24,anchor=east,font=\scriptsize,align=right,text width=1.45cm}},
    nodes near coords,
    nodes near coords style={{font=\scriptsize}},
    every axis plot/.append style={{fill=navyblue, draw=navyblue}},
    enlarge x limits=0.12,
    tick label style={{font=\scriptsize}},
    label style={{font=\scriptsize}},
]
\addplot coordinates {{{coords}}};
\end{{axis}}
\end{{tikzpicture}}
\caption{{{esc(title)}}}
\end{{{figure_env}}}
"""
    return axis


def rows_with_newlines(lines):
    return '\n'.join(lines)


def pie_chart(title, slices, colors, radius=1.34):
    filtered = [(label, value) for label, value in slices if value > 0]
    pie_parts = ', '.join(f"{value}/{esc(label)}" for label, value in filtered)
    color_list = ','.join(colors[:len(filtered)])
    return rf"""
\begin{{figure}}[t]
\centering
\begin{{tikzpicture}}
\pie[
    radius={radius},
    text=legend,
    color={{{color_list}}},
    after number=
]
{{{pie_parts}}}
\end{{tikzpicture}}
\caption{{{esc(title)}}}
\end{{figure}}
"""


def longtable_summary(rows, kind='comparison'):
    out = []
    if kind == 'comparison':
        out.append(r"""\begin{table*}[t]
\centering
\small
\caption{Cross-system summary of controller-comparison winners.}
\begin{tabularx}{\textwidth}{p{2.5cm}p{1.2cm}p{2.0cm}p{1.2cm}p{1.8cm}p{1.1cm}p{2.2cm}p{1.1cm}}
\toprule
Application & Scenario & Lowest latency & Value & Highest QPS & Value & Contextual RL reward leader & Avg. reward \\
\midrule
""")
        for row in rows:
            out.append(
                f"{esc(row['system'])} & {esc(row['scenario'])} & {esc(base.POLICIES[row['latency_winner']['policy']]['label'])} & {fmt(row['latency_winner']['latency'],2)} ms & "
                f"{esc(base.POLICIES[row['qps_winner']['policy']]['label'])} & {fmt(row['qps_winner']['qps'],3)} & "
                f"{esc(base.POLICIES[row['reward_winner']['policy']]['label']) if row['reward_winner'] else 'n/a'} & {fmt(row['reward_winner']['avg_reward'],4) if row['reward_winner'] else 'n/a'} " + r"\\")
        out.append(r"""\bottomrule
\end{tabularx}
\end{table*}
""")
    else:
        out.append(r"""\begin{table*}[t]
\centering
\small
\caption{Cross-system summary of runtime-change winners.}
\begin{tabularx}{\textwidth}{p{2.4cm}p{1.6cm}p{1.8cm}p{1.2cm}p{1.8cm}p{1.0cm}p{2.1cm}p{1.0cm}p{1.0cm}}
\toprule
Application & Scenario & Latency winner & Value & QPS winner & Value & Contextual RL reward leader & Avg. reward & Zero windows \\
\midrule
""")
        for row in rows:
            out.append(
                f"{esc(row['system'])} & {esc(row['scenario'])} & {esc(base.POLICIES[row['latency_winner']['policy']]['label'])} & {fmt(row['latency_winner']['latency'],2)} ms & "
                f"{esc(base.POLICIES[row['qps_winner']['policy']]['label'])} & {fmt(row['qps_winner']['qps'],3)} & "
                f"{esc(base.POLICIES[row['reward_winner']['policy']]['label']) if row['reward_winner'] else 'n/a'} & {fmt(row['reward_winner']['avg_reward'],4) if row['reward_winner'] else 'n/a'} & {row['zero_windows']} " + r"\\")
        out.append(r"""\bottomrule
\end{tabularx}
\end{table*}
""")
    return '\n'.join(out)


def pick_winner(rows, key, reverse=False):
    return sorted(rows, key=lambda r: r[key], reverse=reverse)[0] if rows else None


def load_quickpizza_rq1_rows():
    rows = []
    for path in sorted(QUICKPIZZA_RESULTS.glob('*.json')):
        payload = json.loads(path.read_text())
        policy = payload.get('policy')
        if not policy:
            continue
        summary = payload.get('summary', {})
        status = payload.get('status', {})
        decisions = payload.get('decisions', {}).get('items', [])
        rows.append({
            'system': QUICKPIZZA_SYSTEM,
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


def load_quickpizza_rq2_rows():
    rows = []
    for path in sorted((QUICKPIZZA_RESULTS / 'rq2').glob('*.json')):
        payload = json.loads(path.read_text())
        summary = payload.get('summary', {})
        status = payload.get('status', {})
        decisions = payload.get('decisions', {}).get('items', [])
        rows.append({
            'system': QUICKPIZZA_SYSTEM,
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


def summarize_rq1(rows, systems):
    out = []
    for system in systems:
        sys_rows = [r for r in rows if r['system'] == system and r.get('kind') == 'policy']
        for scenario, label in base.RQ1_SCENARIOS:
            scoped = [r for r in sys_rows if r['scenario'] == scenario]
            if not scoped:
                continue
            out.append({
                'system': system,
                'scenario': label,
                'latency_winner': pick_winner(scoped, 'latency', reverse=False),
                'qps_winner': pick_winner(scoped, 'qps', reverse=True),
                'reward_winner': pick_winner(
                    [r for r in scoped if r['policy'] in {'q_learning', 'sarsa', 'bandit'} and r['avg_reward'] is not None],
                    'avg_reward',
                    reverse=True,
                ),
            })
    return out


def summarize_rq2(rows, systems):
    out = []
    for system in systems:
        sys_rows = [r for r in rows if r['system'] == system]
        for scenario, label in base.RQ2_SCENARIOS:
            scoped = [r for r in sys_rows if r['scenario'] == scenario]
            if not scoped:
                continue
            out.append({
                'system': system,
                'scenario': label,
                'latency_winner': pick_winner(scoped, 'latency', reverse=False),
                'qps_winner': pick_winner(scoped, 'qps', reverse=True),
                'reward_winner': pick_winner([r for r in scoped if r['avg_reward'] is not None], 'avg_reward', reverse=True),
                'zero_windows': sum(r['zero_windows'] for r in scoped),
            })
    return out


def build_tex():
    rq1_rows = base.load_rq1_rows()
    rq2_rows = base.load_rq2_rows()
    quickpizza = base.load_quickpizza_extension()
    qp_rq1_rows = load_quickpizza_rq1_rows()
    qp_rq2_rows = load_quickpizza_rq2_rows()
    rq1_rows_all = rq1_rows + qp_rq1_rows
    rq2_rows_all = rq2_rows + qp_rq2_rows
    rq1_policies = [r for r in rq1_rows_all if r['kind'] == 'policy']
    rq1_baselines = [r for r in rq1_rows if r['kind'] == 'baseline']
    rq1_summary_rows = summarize_rq1(rq1_rows_all, ALL_SYSTEMS)
    rq2_summary_rows = summarize_rq2(rq2_rows_all, ALL_SYSTEMS)

    rq1_latency_family = Counter(base.POLICIES[row['latency_winner']['policy']]['family'] for row in rq1_summary_rows)
    rq1_qps_family = Counter(base.POLICIES[row['qps_winner']['policy']]['family'] for row in rq1_summary_rows)
    rq1_policy_latency = Counter(row['latency_winner']['policy'] for row in rq1_summary_rows)
    rq1_policy_qps = Counter(row['qps_winner']['policy'] for row in rq1_summary_rows)

    rq2_policy_latency = Counter(row['latency_winner']['policy'] for row in rq2_summary_rows)
    rq2_policy_qps = Counter(row['qps_winner']['policy'] for row in rq2_summary_rows)
    rq2_reward_policy = Counter(
        row['reward_winner']['policy'] for row in rq2_summary_rows if row['reward_winner'] is not None
    )

    avg_rate_by_policy = []
    for pol in ['rule', 'kmeans', 'bandit', 'sarsa', 'q_learning']:
        vals = [row['avg_rate'] for row in rq1_policies + rq2_rows_all if row['policy'] == pol and row['avg_rate'] is not None]
        avg_rate_by_policy.append((base.POLICIES[pol]['label'], sum(vals) / len(vals)))

    rq1_quality = {
        sys: {
            'runs': len([r for r in rq1_policies if r['system'] == sys]),
            'avg_decisions': sum(r['decision_count'] for r in rq1_policies if r['system'] == sys) / len([r for r in rq1_policies if r['system'] == sys]),
            'zero_windows': sum(r['zero_windows'] for r in rq1_policies if r['system'] == sys),
        }
        for sys in ALL_SYSTEMS
    }
    rq2_quality = {
        sys: {
            'runs': len([r for r in rq2_rows_all if r['system'] == sys]),
            'avg_decisions': sum(r['decision_count'] for r in rq2_rows_all if r['system'] == sys) / len([r for r in rq2_rows_all if r['system'] == sys]),
            'zero_windows': sum(r['zero_windows'] for r in rq2_rows_all if r['system'] == sys),
        }
        for sys in ALL_SYSTEMS
    }
    quality_rows = '\n'.join(
        f"{esc(sys)} & {rq1_quality[sys]['runs']} & {fmt(rq1_quality[sys]['avg_decisions'],1)} & {rq1_quality[sys]['zero_windows']} & {rq2_quality[sys]['runs']} & {fmt(rq2_quality[sys]['avg_decisions'],1)} & {rq2_quality[sys]['zero_windows']} " + r"\\"
        for sys in ALL_SYSTEMS
    )
    rq1_avg_decision_chart = [(sys, rq1_quality[sys]['avg_decisions']) for sys in ALL_SYSTEMS]
    rq2_avg_decision_chart = [(sys, rq2_quality[sys]['avg_decisions']) for sys in ALL_SYSTEMS]
    rq2_zero_window_chart = [(sys, rq2_quality[sys]['zero_windows']) for sys in ALL_SYSTEMS]
    rq1_run_chart = [(f'{sys} RQ1', rq1_quality[sys]['runs']) for sys in ALL_SYSTEMS]
    rq2_run_chart = [(f'{sys} RQ2', rq2_quality[sys]['runs']) for sys in ALL_SYSTEMS]

    tex = rf"""\documentclass[10pt,twocolumn]{{article}}
\usepackage[margin=0.72in,columnsep=0.24in]{{geometry}}
\usepackage[T1]{{fontenc}}
\usepackage[utf8]{{inputenc}}
\usepackage{{lmodern}}
\usepackage{{microtype}}
\usepackage{{booktabs}}
\usepackage{{tabularx}}
\usepackage{{array}}
\usepackage{{multirow}}
\usepackage{{graphicx}}
\usepackage{{xcolor}}
\usepackage{{hyperref}}
\usepackage{{enumitem}}
\usepackage{{tikz}}
\usepackage{{pgfplots}}
\usepackage{{pgf-pie}}
\usepackage{{dblfloatfix}}
\usepackage{{balance}}
\usepackage{{placeins}}
\usepackage{{fancyhdr}}
\usepackage{{caption}}
\usepackage{{titlesec}}
\usepackage{{xurl}}
\pgfplotsset{{compat=1.18}}

\definecolor{{navyblue}}{{HTML}}{{12344D}}
\definecolor{{tealrule}}{{HTML}}{{0F766E}}
\definecolor{{orangeaccent}}{{HTML}}{{C2410C}}
\definecolor{{slategray}}{{HTML}}{{64748B}}
\definecolor{{greenaccent}}{{HTML}}{{15803D}}
\definecolor{{purpleaccent}}{{HTML}}{{7C3AED}}
\definecolor{{lightbluebg}}{{HTML}}{{EFF6FB}}
\captionsetup{{font=small,labelfont=bf,skip=4pt}}
\renewcommand{{\arraystretch}}{{1.08}}
\setlength{{\emergencystretch}}{{3em}}
\setlength{{\parindent}}{{1em}}
\setlength{{\parskip}}{{0.08em}}
\setlength{{\textfloatsep}}{{5pt plus 1pt minus 1pt}}
\setlength{{\floatsep}}{{5pt plus 1pt minus 1pt}}
\setlength{{\intextsep}}{{4pt plus 1pt minus 1pt}}
\setlength{{\dbltextfloatsep}}{{6pt plus 1pt minus 1pt}}
\setlength{{\dblfloatsep}}{{5pt plus 1pt minus 1pt}}
\widowpenalty=10000
\clubpenalty=10000
\titleformat{{\section}}{{\large\bfseries\color{{navyblue}}}}{{\thesection}}{{0.55em}}{{}}
\titleformat{{\subsection}}{{\normalsize\bfseries\color{{navyblue}}}}{{\thesubsection}}{{0.55em}}{{}}
\titlespacing*{{\section}}{{0pt}}{{1.2ex plus .4ex minus .2ex}}{{0.6ex}}
\titlespacing*{{\subsection}}{{0pt}}{{1.0ex plus .3ex minus .2ex}}{{0.4ex}}
\setlist{{nosep,leftmargin=1.2em}}
\raggedbottom

\hypersetup{{
  colorlinks=true,
  linkcolor=navyblue,
  urlcolor=navyblue,
  citecolor=navyblue,
  pdftitle={{Adaptive Tracing Across Four Microservice Systems}},
  pdfauthor={{Dan Bhattarai}}
}}

\pagestyle{{fancy}}
\fancyhf{{}}
\fancyhead[L]{{Adaptive Tracing Study}}
\fancyhead[R]{{\thepage}}
\setlength{{\headheight}}{{14pt}}

\title{{\textbf{{Adaptive Tracing Across Four Microservice Systems}}\\[0.2em]
\large Comparative Evaluation of Controller Families, Runtime-Change Behavior, and Taxonomy-Guided Interpretation}}
\author{{Dan Bhattarai}}
\date{{June 22, 2026}}

\begin{{document}}
\maketitle
\thispagestyle{{fancy}}

\begin{{abstract}}
This paper presents a comparative study of adaptive tracing across four microservice applications: Train-Ticket, the Timescale OpenTelemetry Demo, Spring Petclinic Microservices, and Grafana QuickPizza. The study has three analytical objectives: first, to compare reinforcement-learning and non-reinforcement-learning tracing controllers under matched operating conditions; second, to examine how reinforcement-learning controllers behave under targeted runtime changes such as latency spikes, error bursts, and throughput drops; and third, to synthesize the implemented methods into a practical taxonomy for engineering use. The cross-system results show that no controller dominates across all environments. Q-Learning is the strongest overall method on Train-Ticket, the rule-based baseline gives the best final latency on the Timescale application, Bandit is the strongest Petclinic policy on final runtime metrics, and the QuickPizza results show that the same controller families remain usable on a Grafana-centered observability stack. Under runtime-change scenarios, Bandit wins the most latency cases overall, while SARSA wins the most throughput cases. The main engineering conclusion is that controller quality is system-dependent, and adaptive tracing should be selected according to runtime stability, operational transparency requirements, and the quality of the feedback signals available for control.
\end{{abstract}}

\section{{Introduction}}
Distributed tracing is a core observability mechanism for microservice applications, but a fixed tracing configuration imposes a persistent tradeoff. Higher sampling improves diagnostic visibility at the cost of additional telemetry volume, while lower sampling reduces overhead but weakens failure analysis and performance diagnosis. Adaptive tracing addresses this tension by modifying the tracing rate at runtime in response to observed system behavior. The study is grounded in established distributed tracing literature and platforms, including Dapper \cite{{dapper}}, X-Trace \cite{{xtrace}}, Canopy \cite{{canopy}}, Pivot Tracing \cite{{pivot}}, OpenTelemetry \cite{{otel}}, Jaeger \cite{{jaeger}}, and Zipkin \cite{{zipkin}}, together with project readings on adaptive observability and RL-guided logging \cite{{als}}.

The practical question is not whether adaptation is useful in principle, but which form of adaptation is strongest under realistic operating conditions. This paper therefore treats adaptive tracing as a control problem and evaluates multiple controller families rather than a single adaptive algorithm. The resulting contribution combines a four-system comparison, a runtime-change study, and a method taxonomy grounded in implemented experiments rather than only conceptual classification.

\subsection{{Practical usefulness}}
This study is intended to support a practical decision that observability teams face in production systems: how to retain diagnostically useful traces without paying unnecessary telemetry cost under changing workload conditions. The value of the work is therefore not only that it compares algorithms, but that it translates the comparison into controller-selection guidance.

In practical terms, the paper helps answer three operational questions: when a simple transparent heuristic is sufficient, when reinforcement learning becomes worthwhile, and how much the answer depends on the runtime behavior of the application itself. That practical usefulness is central to the interpretation of the results.

\section{{Study Objectives and Scope}}
The paper is organized around three analytical objectives:
\begin{{enumerate}}[label=\textbf{{Objective \Alph*:}}, leftmargin=2.4cm]
  \item compare reinforcement-learning and non-reinforcement-learning adaptive tracing controllers under matched system conditions;
  \item evaluate how reinforcement-learning controllers behave under latency spikes, error bursts, and throughput drops; and
  \item derive a practical taxonomy of adaptive tracing strategies based on the completed experiments.
\end{{enumerate}}

The completed evidence base consists of {len(rq1_policies)} controller-comparison runs, {len(rq1_baselines)} fixed-rate baselines, and {len(rq2_rows_all)} runtime-change reinforcement-learning runs across the four applications. Grafana QuickPizza contributes {len(qp_rq1_rows)} controller-comparison runs and {len(qp_rq2_rows)} runtime-change runs within that total, alongside {len(quickpizza['baseline_rows'])} fixed-rate checks used as supporting context.

\section{{Experimental Systems}}
The four experimental applications were selected from established open-source microservice demo and benchmark projects: Train-Ticket \cite{{trainrepo}}, the OpenTelemetry Demo / Astronomy Shop \cite{{otelrepo,oteldemo}}, Spring Petclinic Microservices \cite{{petrepo,petsite}}, and Grafana QuickPizza \cite{{quickrepo}}. These project sources were used during system selection, deployment, instrumentation review, and experimental setup.
\begin{{table*}}[t]
\centering
\small
\caption{{Experimental systems used in the study and their role in the evidence base.}}
\begin{{tabularx}}{{\textwidth}}{{p{{2.4cm}}p{{2.1cm}}X X p{{1.8cm}}}}
\toprule
System & Domain & Technical role in the study & Observability / tracing context & Comparative winner \\
\midrule
Train-Ticket & Railway ticket booking benchmark & Largest and most stable application in the study; strongest evidence base & Python microservices with adaptive tracing controller and experiment runners & Q-Learning \\
Timescale OpenTelemetry Demo & Password-generation microservice application & Lightweight tracing-first microservice system with strong observability & OpenTelemetry Collector, Promscale, TimescaleDB, Jaeger, Grafana & Rule \\
Spring Petclinic Microservices & Spring Cloud business-domain microservice application & Most realistic business application, but also the noisiest result set & API gateway, service discovery, config server, Zipkin, Prometheus & Bandit \\
Grafana QuickPizza & Pizza recommendation microservice application & Grafana-maintained demo system used as the fourth comparative application in the study & Grafana local stack with Alloy, Prometheus, Tempo, Loki, Pyroscope, Grafana, and QuickPizza microservices & {esc(base.POLICIES[quickpizza['best_latency']['policy']]['label']) if quickpizza['best_latency'] else 'n/a'} \\
\bottomrule
\end{{tabularx}}
\end{{table*}}

\section{{Methodology}}
\subsection{{Adaptive tracing controllers}}
The study evaluates five adaptive controllers. Q-Learning and SARSA are value-learning reinforcement-learning methods. Bandit is a simpler action-value controller with weaker assumptions about longer-term dynamics. Rule is a threshold-based heuristic baseline. K-Means is a clustering-based baseline that maps recent runtime states to representative sampling rates. The common action space is a discrete set of tracing rates: 0.05, 0.10, 0.20, 0.50, and 0.80.

\subsection{{Measured outputs}}
The primary outputs are latency, throughput (QPS), error rate, and trace totals. For reinforcement-learning methods, average reward is also reported. Reward is useful for RL-internal interpretation, but it is not treated as a universally comparable system-quality score because reward design differs across the applications, especially in the Timescale system. Data quality is tracked through decision counts and zero-window counts, because sparse windows weaken the reliability of adaptive-control conclusions.

\subsection{{Study design}}
\begin{{table*}}[t]
\centering
\small
\caption{{Design structure by analytical objective.}}
\begin{{tabularx}}{{\textwidth}}{{p{{2.4cm}}p{{3.4cm}}p{{2.8cm}}X}}
\toprule
Objective & Compared methods & Scenario structure & Main outputs \\
\midrule
Comparative evaluation & Q-Learning, SARSA, Bandit, Rule, K-Means & Healthy and faulted per system across all four applications & Final latency, final QPS, error rate, contextual RL reward \\
Runtime-change analysis & Q-Learning, SARSA, Bandit & Healthy, latency spike, error burst, throughput drop across all four applications & Latency/QPS winners per scenario, average selected rate, data quality \\
Taxonomy synthesis & Taxonomy over implemented methods & Uses completed comparison and runtime-change evidence; no new experiment matrix & Method categories, decision signals, behavior patterns, operational implications \\
\bottomrule
\end{{tabularx}}
\end{{table*}}

\subsection{{Methodological caveats}}
\begin{{itemize}}
  \item Reward is reported as contextual reinforcement-learning evidence, not as a uniformly comparable cross-system winner metric.
  \item The applications are not symmetric in evidence quality. Train-Ticket is the strongest result set, Timescale is valid but has reward-design caveats, and Petclinic is complete but much sparser.
  \item Fault injection mechanisms differ by application because the systems expose different operational controls. The study therefore emphasizes within-system comparisons first and cross-system synthesis second.
  \item QuickPizza uses the same controller families and scenario structure as the other systems, but its observability stack and service topology are distinct, so its results should still be interpreted as a separate system rather than as a direct replica of any other environment.
\end{{itemize}}

\section{{Comparative Evaluation of Controller Families}}
The cross-system comparison shows that reinforcement-learning controllers are consistently competitive, but there is no universal winner across the four applications. Q-Learning is strongest on Train-Ticket, the rule-based baseline is strongest on Timescale final latency, Bandit is strongest on Petclinic final runtime metrics, and QuickPizza shows that the same controller families remain viable on a Grafana-centered stack. The evidence therefore supports a contingent rather than absolute view of controller quality.

{pie_chart('Comparison-stage latency winner family split', [('RL', rq1_latency_family.get('RL', 0)), ('Non-RL', rq1_latency_family.get('Non-RL', 0))], ['navyblue', 'slategray'])}

{bar_chart('Selected policy win counts in the comparison study', [('Bandit latency', rq1_policy_latency.get('bandit', 0)), ('Q-Learning latency', rq1_policy_latency.get('q_learning', 0)), ('Rule latency', rq1_policy_latency.get('rule', 0)), ('SARSA QPS', rq1_policy_qps.get('sarsa', 0)), ('Bandit QPS', rq1_policy_qps.get('bandit', 0))], 'Wins', base.POLICIES, width='0.95\\linewidth', height='4.6cm', symbolic=False)}

{longtable_summary(rq1_summary_rows, kind='comparison')}

\paragraph{{Interpretation.}} Train-Ticket provides the clearest evidence for Q-Learning because it combines strong faulted performance, strong contextual reward, and a mature decision horizon. Timescale shows that a transparent heuristic can still outperform reinforcement learning on final latency, which prevents an overgeneralized conclusion that learning-based control is always superior. Petclinic shows that a simpler reinforcement-learning family member, Bandit, can be preferable when the runtime signal is noisier and operational stability matters more than deeper value learning. QuickPizza extends that comparison onto a Grafana-centered stack and shows that the same controller families remain analyzable there as well.

\paragraph{{What these results mean.}} The main meaning of the controller-comparison results is that complexity alone does not guarantee better adaptive tracing. More sophisticated learning-based control can be highly effective, but its advantage depends on whether the application produces a stable enough feedback signal to support learning. When the signal is cleaner, deeper reinforcement learning can justify its additional complexity. When the signal is less stable, simpler methods may be more reliable and easier to operate.

For practitioners, this means that controller choice should be framed as an engineering-fit problem rather than an algorithm race. The correct question is not which controller won overall, but which controller is most appropriate for the operational characteristics of the target system. The inclusion of QuickPizza as a fourth system reinforces that core conclusion across a broader range of observability stacks.
\FloatBarrier

\section{{Controller Behavior Under Runtime Changes}}
Controller behavior under runtime change is not uniform. Across the sixteen system-scenario cases, Bandit wins the most latency cases ({rq2_policy_latency.get('bandit', 0)}), SARSA wins the most QPS cases ({rq2_policy_qps.get('sarsa', 0)}), and contextual reward leadership is split across all three reinforcement-learning policies. This indicates that different controllers react differently to degradation patterns rather than sharing a common adaptation profile.

{bar_chart('Latency wins under runtime-change scenarios', [('Bandit', rq2_policy_latency.get('bandit', 0)), ('Q-Learning', rq2_policy_latency.get('q_learning', 0)), ('SARSA', rq2_policy_latency.get('sarsa', 0))], 'Cases', base.POLICIES, width='0.94\\linewidth', height='4.2cm', symbolic=False)}

{pie_chart('Runtime-change QPS winner split', [('SARSA', rq2_policy_qps.get('sarsa', 0)), ('Q-Learning', rq2_policy_qps.get('q_learning', 0)), ('Bandit', rq2_policy_qps.get('bandit', 0))], ['tealrule', 'navyblue', 'orangeaccent'])}

{bar_chart('Average selected tracing rate across the full study', avg_rate_by_policy, 'Average tracing rate', base.POLICIES, width='0.94\\linewidth', height='4.4cm', symbolic=False)}

{longtable_summary(rq2_summary_rows, kind='runtime')}

\begin{{table}}[htbp]
\centering
\caption{{System-level data quality across the two experimental blocks.}}
\begin{{tabularx}}{{\linewidth}}{{p{{3.4cm}}cccccc}}
\toprule
System & Comparison runs & Comparison avg. decisions & Comparison zero windows & Runtime-change runs & Runtime-change avg. decisions & Runtime-change zero windows \\
\midrule
{quality_rows}
\bottomrule
\end{{tabularx}}
\end{{table}}

\paragraph{{Interpretation.}} Train-Ticket remains the strongest environment for learning-oriented policies because it supplies long decision horizons and stable traffic. Timescale exposes reward-design weakness most clearly; the latency-spike case shows that contextual reward can appear favorable even when latency becomes extreme, so runtime metrics must remain primary. Petclinic remains usable but sparse. Its results still contribute meaningfully, but the short decision horizon makes the claims there weaker than in Train-Ticket.

\paragraph{{What these results mean.}} The runtime-change results show that reinforcement-learning controllers do not share one common adaptation behavior. One method can be better at controlling latency, while another can preserve throughput more effectively under the same disturbance. This means that runtime-change behavior is itself a design criterion, not just a secondary observation.

For operations teams, the implication is direct: controller evaluation should include the kinds of disturbances that actually matter in deployment. A method that looks strong in a stable scenario may not be the right choice if the real concern is bursty slowdown, transient failures, or throughput instability.
\FloatBarrier

\section{{Cross-System Visual Synthesis}}
The aggregated patterns become clearer when the study is viewed at the system level rather than only at the policy winner level. A compact data-quality view is therefore useful for explaining why some controller outcomes are more credible or more stable than others.

{bar_chart('Runtime-change zero-window count by system', rq2_zero_window_chart, 'Zero windows', base.POLICIES, width='0.94\\linewidth', height='4.3cm', symbolic=False)}

\paragraph{{Interpretation.}} This system-level view shows why the report should not collapse into a single universal ranking. Train-Ticket supplies the cleanest decision structure, which is why its controller conclusions are the strongest. Timescale is compact but still stable enough to support clear conclusions. Petclinic and QuickPizza remain useful, but their zero-window profiles require more caution when interpreting small differences between methods.

\paragraph{{Why this matters.}} The visual synthesis adds a second layer to the results: not only which controller wins, but how trustworthy the decision process was in each environment. This is operationally important because adaptive tracing quality depends not only on the controller algorithm, but also on the stability and granularity of the feedback loop that drives it.
\FloatBarrier

\section{{Taxonomy and Design Guidance}}
Adaptive tracing is best understood as a family of control strategies rather than one technique. The completed project supports a five-part practical taxonomy: fixed-rate baseline, rule-based control, clustering-based control, bandit-style reinforcement-learning control, and value-learning reinforcement-learning control.

\begin{{table*}}[t]
\centering
\small
\caption{{Practical taxonomy of adaptive tracing strategies.}}
\begin{{tabularx}}{{\textwidth}}{{p{{1.7cm}}p{{2.0cm}}p{{2.2cm}}p{{2.8cm}}p{{1.3cm}}X}}
\toprule
Method & Type & Main goal & Decision signals & Operational overhead & Observed practical takeaway \\
\midrule
Fixed Rate & Static baseline & No runtime adaptation; constant configured rate & Configuration time only & None after startup & Reference point for what is lost without adaptation. \\
Rule & Heuristic threshold control & Change tracing when thresholds are crossed & Thresholds on latency, errors, counts, or similar runtime signals & Low & Strong when system behavior is predictable and operational transparency matters. \\
K-Means & Clustering-based control & Map similar runtime states to representative rates & Recent latency, throughput, and error features grouped into clusters & Moderate & Useful middle ground between static thresholds and full reinforcement learning. \\
Bandit & RL action-value control & Choose the rate with the best immediate observed payoff & Short-horizon reward from recent behavior & Moderate & Strong on noisy systems where low-overhead adaptation is valuable. \\
SARSA & RL value learning & Learn state-action values on-policy while exploring & State bins derived from runtime metrics plus current action & High & Most exploratory RL method in this project; useful when controlled exploration helps. \\
Q-Learning & RL value learning & Learn long-run state-action value off-policy & State bins derived from runtime metrics and delayed reward & High & Strongest option when enough decisions and stable feedback are available. \\
\bottomrule
\end{{tabularx}}
\end{{table*}}

\begin{{figure*}}[t]
\centering
\resizebox{{0.96\textwidth}}{{!}}{{%
\begin{{tikzpicture}}[x=0.92cm,y=0.92cm]
\foreach \x/\name/\desc/\clr in {{0/Fixed Rate/Baseline/purpleaccent!90, 2.6/Rule/Threshold/slategray!85, 5.2/K-Means/Cluster/greenaccent!85, 7.8/Bandit/Immediate Value/tealrule!85, 10.4/SARSA/On-policy RL/orangeaccent!90, 13.0/Q-Learning/Off-policy RL/navyblue!90}} {{
  \fill[\clr, rounded corners=6pt] (\x,0) rectangle +(2.2,2.0);
  \node[align=center,text=white,font=\bfseries\small] at (\x+1.1,1.35) {{\name}};
  \node[align=center,text=white,font=\small] at (\x+1.1,0.8) {{\desc}};
}}
\end{{tikzpicture}}
}}
\caption{{Project-specific conceptual ladder from fixed-rate baselines to value-learning reinforcement-learning controllers. This is not a measured ranking; it summarizes relative modeling and operational complexity.}}
\end{{figure*}}

\paragraph{{Why the synthesis matters.}} The completed experiments do not support a single universal controller. Instead, they support a taxonomy in which controller families differ in goals, decision signals, exploration behavior, and operational cost. This is the appropriate abstraction for making deployment decisions in practice.

\paragraph{{What these results mean.}} The taxonomy matters because it converts a long list of experimental observations into a clearer design model. Instead of treating adaptive tracing as a single technique, the paper shows that it should be understood as a family of strategies that trade off interpretability, responsiveness, data requirements, and operational cost in different ways.

This gives the results a practical meaning beyond benchmarking: it provides a vocabulary for selecting, justifying, and communicating adaptive tracing choices in real engineering settings.
\FloatBarrier

\section{{Discussion}}
\subsection{{What the project shows overall}}
The strongest project-level conclusion is that controller choice must be matched to the system. Q-Learning is strongest when the environment supplies rich and stable feedback, as in Train-Ticket. Rule-based control remains highly competitive when latency can be improved through transparent threshold logic, as in the Timescale system. Bandit becomes attractive when the system is operationally noisier, as in Petclinic.

Grafana QuickPizza adds a practical secondary conclusion: the controller-family comparison and runtime-change workflow remain usable on a fourth, Grafana-centered demo stack.

\subsection{{Operational guidance}}
\begin{{itemize}}
  \item Use \textbf{{Q-Learning}} when long decision horizons and stable telemetry make long-run value learning realistic.
  \item Use \textbf{{Bandit}} when quick, low-overhead adaptation is needed and the environment is noisy or sparse.
  \item Use \textbf{{Rule}} when transparency, predictability, and ease of explanation are more important than model sophistication.
  \item Use \textbf{{K-Means}} when a moderate data-driven controller is preferred over manual thresholds.
  \item Treat \textbf{{SARSA}} as the most exploratory reinforcement-learning option in this project, useful when controlled exploration is acceptable.
\end{{itemize}}

\subsection{{Reward should not dominate the final interpretation}}
Reward was necessary to drive the reinforcement-learning controllers, but it cannot be allowed to dominate the final report. The Timescale results demonstrate why: the reward signal can look favorable even when the runtime outcome is poor. For that reason, the final synthesis prioritizes latency, QPS, error rate, and data quality over reward in the main findings.

\subsection{{Practical usefulness for engineers and operators}}
\begin{{itemize}}
  \item If the system is stable and feedback is rich, Q-Learning is a credible choice because it can exploit longer decision horizons.
  \item If transparency and ease of explanation matter, Rule-based control remains attractive and can still win on important metrics.
  \item If the environment is noisy or sparse, Bandit offers a useful middle ground between adaptability and operational simplicity.
  \item If the goal is controller selection rather than algorithm advocacy, the study provides a practical basis for matching controller family to system behavior.
\end{{itemize}}

\subsection{{System-specific takeaways}}
Train-Ticket is the strongest setting for learning-oriented control because its traffic and decision horizon are stable enough to reward longer-term value learning. The Timescale application shows the opposite lesson: transparent heuristic control can still win on a meaningful top-line metric even when more sophisticated controllers are available. Petclinic demonstrates that noisy business-style microservice environments can favor simpler RL control such as Bandit over deeper value learning. QuickPizza broadens the study into a Grafana-centered observability stack and shows that the same overall controller taxonomy remains usable even when the surrounding telemetry platform differs substantially from the other applications.

Taken together, these four cases support a practical deployment rule: choose the controller family that fits the behavior of the system and the quality of the feedback loop, not the controller that looked best in a different environment. This is the central reason the paper treats adaptive tracing as a design-space problem rather than an algorithm race.

\section{{Threats to Validity and Limitations}}
\begin{{itemize}}
  \item \textbf{{Unequal evidence quality:}} Train-Ticket remains the strongest result set overall. Petclinic and QuickPizza are more sensitive to sparse or noisy decision windows than Train-Ticket.
  \item \textbf{{Reward comparability:}} reward functions differ across systems, so cross-system reward comparisons are contextual rather than absolute.
  \item \textbf{{Scenario heterogeneity:}} the exact fault or degradation mechanism differs by application because the systems expose different control surfaces.
  \item \textbf{{Different telemetry backends:}} the systems use different data paths and observability stacks, which is realistic but introduces methodological heterogeneity.
  \item \textbf{{Limited repetition:}} the study uses completed matrices rather than repeated statistical replications for every scenario-policy combination.
\end{{itemize}}

\section{{Conclusion}}
This project evaluated adaptive tracing across four microservice systems through a controller-comparison study, a runtime-change study, and a taxonomy synthesis. The combined evidence shows that reinforcement-learning-based adaptive tracing is consistently competitive but not universally dominant: Q-Learning leads Train-Ticket, Rule leads Timescale final latency, Bandit leads Petclinic final runtime metrics, and QuickPizza confirms that the same controller families remain viable on a Grafana-centered observability stack. The runtime-change analysis shows that controllers respond differently to degradation patterns rather than exhibiting one common adaptation profile. The taxonomy synthesis shows that adaptive tracing is best understood as a family of control strategies, not as a single technique.

The final engineering conclusion is direct: \textbf{{there is no single best adaptive tracing controller for all microservice systems}}. The appropriate choice depends on the stability of the runtime signal, the need for operational transparency, and the quality of the feedback available for learning.

The broader practical conclusion is equally important: the usefulness of adaptive tracing lies in giving teams a structured way to balance observability value against telemetry cost under realistic runtime conditions. The contribution of this paper is therefore both empirical and operational: it provides evidence, translates that evidence into controller-selection guidance, and validates that the same workflow can be applied across four distinct microservice environments.

\clearpage
\onecolumn
\section*{{References and Readings Consulted}}
\begin{{thebibliography}}{{99}}
\bibitem{{dapper}} Sigelman, B. H., Barroso, L. A., Burrows, M., Stephenson, P., Plakal, M., Beaver, D., Jaspan, S., and Shanbhag, C. \emph{{Dapper, a Large-Scale Distributed Systems Tracing Infrastructure}}. Google technical report, 2010.
\bibitem{{xtrace}} Fonseca, R., Porter, G., Katz, R. H., Shenker, S., and Stoica, I. \emph{{X-Trace: A Pervasive Network Tracing Framework}}. NSDI, 2007.
\bibitem{{canopy}} Kaldor, J., Mace, J., Bejda, M., Gao, E., Kuropatwa, W., O'Neill, J., Ong, K., Schaller, B., Shan, P., Viscomi, B., Venkataraman, V., Veeraraghavan, K., Werner, K., and Zhou, Y. \emph{{Canopy: An End-to-End Performance Tracing and Analysis System}}. SOSP, 2017.
\bibitem{{pivot}} Mace, J., Roelke, R., and Fonseca, R. \emph{{Pivot Tracing: Dynamic Causal Monitoring for Distributed Systems}}. SOSP, 2015.
\bibitem{{trainrepo}} FudanSELab. \emph{{Train Ticket: A Benchmark Microservice System}}. GitHub repository. \url{{https://github.com/FudanSELab/train-ticket}}. Consulted during deployment and architecture review. Accessed June 22, 2026.
\bibitem{{otelrepo}} OpenTelemetry Project. \emph{{OpenTelemetry Demo (Astronomy Shop)}}. GitHub repository. \url{{https://github.com/open-telemetry/opentelemetry-demo}}. Consulted during deployment, instrumentation, and scenario review. Accessed June 22, 2026.
\bibitem{{oteldemo}} OpenTelemetry Project. \emph{{OpenTelemetry Demo Documentation}}. \url{{https://opentelemetry.io/docs/demo/}}. Consulted during deployment and observability-stack review. Accessed June 22, 2026.
\bibitem{{petrepo}} Spring Petclinic Community. \emph{{Spring Petclinic Microservices}}. GitHub repository. \url{{https://github.com/spring-petclinic/spring-petclinic-microservices}}. Consulted during deployment and architecture review. Accessed June 22, 2026.
\bibitem{{petsite}} Spring Petclinic Community. \emph{{The Spring PetClinic Community}}. \url{{https://spring-petclinic.github.io/}}. Consulted during project background and system-context review. Accessed June 22, 2026.
\bibitem{{quickrepo}} Grafana Labs. \emph{{QuickPizza}}. GitHub repository. \url{{https://github.com/grafana/quickpizza}}. Consulted during deployment, observability-stack setup, and experiment integration. Accessed June 22, 2026.
\bibitem{{otel}} OpenTelemetry Project. \emph{{OpenTelemetry Documentation and Demo Materials}}. Online documentation consulted during instrumentation and architecture review. Accessed May 18, 2026.
\bibitem{{jaeger}} Jaeger Project. \emph{{Jaeger Documentation}}. Online documentation consulted during the tracing-tooling review. Accessed May 18, 2026.
\bibitem{{zipkin}} Zipkin Project. \emph{{Zipkin Documentation}}. Online documentation consulted for the Petclinic tracing backend. Accessed May 18, 2026.
\bibitem{{als}} \emph{{An Adaptive Logging System (ALS): Enhancing Software Logging with Reinforcement Learning Techniques}}. Supplemental project reading consulted during the literature review.
\end{{thebibliography}}
\subsection*{{Additional Readings Consulted}}
\begin{{itemize}}
  \item \emph{{An Adaptive Logging System (ALS): Enhancing Software Logging with Reinforcement Learning Techniques}}.
  \item Zhang et al., \emph{{NSDI 2023 paper consulted during the observability literature review}}.
  \item \emph{{review.pdf}} local survey reading consulted during the report framing stage.
  \item \emph{{ArXiv reading stored as https:arxiv.org:pdf:2509.13852.pdf}} consulted during the broader adaptive observability review.
\end{{itemize}}

\end{{document}}
"""
    OUT.write_text(tex, encoding='utf-8')
    print(OUT)


if __name__ == '__main__':
    build_tex()
