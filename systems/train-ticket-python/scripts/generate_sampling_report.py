#!/usr/bin/env python3
import argparse
import html
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"

SCENARIO_NOTES = {
    "healthy": {
        "title": "Healthy Condition",
        "description": (
            "Baseline operating condition with low injected faults "
            "(ORDER_DELAY_MS=50, ORDER_ERROR_RATE=0.01, TRAVEL_DELAY_MS=30, TRAVEL_ERROR_RATE=0.0)."
        ),
    },
    "faulted": {
        "title": "Faulted Condition",
        "description": (
            "Stress condition with higher injected latency and error pressure "
            "(ORDER_DELAY_MS=200, ORDER_ERROR_RATE=0.08, TRAVEL_DELAY_MS=120, TRAVEL_ERROR_RATE=0.03)."
        ),
    },
}


def load_result(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fmt(value: float, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def summarize_entry(data: dict) -> dict:
    status = data["status"]
    summary = data["summary"]
    decisions = data.get("decisions", {})
    items = decisions.get("items", [])

    if "avg_reward" in summary:
        avg_reward = summary["avg_reward"]
        avg_rate = summary["avg_rate"]
        min_rate = summary["min_rate"]
        max_rate = summary["max_rate"]
        decision_count = summary["decision_count"]
    elif items:
        rewards = [item["reward"] for item in items if item.get("reward") is not None]
        rates = [item["chosen_rate"] for item in items]
        avg_reward = (sum(rewards) / len(rewards)) if rewards else None
        avg_rate = sum(rates) / len(rates)
        min_rate = min(rates)
        max_rate = max(rates)
        decision_count = len(items)
    else:
        avg_reward = None
        avg_rate = status.get("chosen_rate")
        min_rate = status.get("chosen_rate")
        max_rate = status.get("chosen_rate")
        decision_count = 0

    return {
        "policy": data["policy"],
        "scenario": data.get("scenario", "unknown"),
        "reward_mode": data["reward_mode"],
        "avg_reward": avg_reward,
        "avg_rate": avg_rate,
        "min_rate": min_rate,
        "max_rate": max_rate,
        "final_latency_ms": status["avg_latency_ms"],
        "final_qps": status["qps"],
        "final_error_rate": status["error_rate"],
        "decision_count": decision_count,
        "state": status.get("state"),
        "action_idx": status.get("action_idx"),
    }


def scenario_observation(entries: list[dict], scenario: str) -> str:
    ordered = sorted(entries, key=lambda item: item["avg_reward"] if item["avg_reward"] is not None else float("-inf"), reverse=True)
    best = ordered[0]
    if scenario == "healthy":
        return (
            f"In the healthy batch, `{best['policy']}` achieved the highest average reward "
            f"({fmt(best['avg_reward'])}). Across the methods, sampling stayed relatively low, "
            "which is consistent with a stable system where extra traces are mostly overhead."
        )
    return (
        f"In the faulted batch, `{best['policy']}` achieved the highest average reward "
        f"({fmt(best['avg_reward'])}). The injected delays lowered throughput and increased "
        "latency, so the comparison reflects how each method behaves under degraded performance."
    )


def limitations_text(entries_by_scenario: dict[str, list[dict]]) -> str:
    all_entries = [entry for entries in entries_by_scenario.values() for entry in entries]
    all_zero_error = all(entry["final_error_rate"] == 0.0 for entry in all_entries)
    if all_zero_error:
        return (
            "Across these batches, the final measured order-service error rate remained 0.0. "
            "The faulted scenario therefore mainly reflects latency and throughput degradation "
            "rather than persistent request failures. A later batch with stronger error-inducing "
            "conditions would help evaluate how the policies respond to explicit failures."
        )
    return (
        "These results cover both healthy and faulted conditions, but additional batches would still "
        "help confirm whether the same ranking holds across longer runs."
    )


def markdown_table(entries: list[dict]) -> list[str]:
    lines = [
        "| Method | Avg Reward | Avg Rate | Min Rate | Max Rate | Final Latency (ms) | Final QPS | Final Error Rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for entry in sorted(entries, key=lambda item: item["avg_reward"] if item["avg_reward"] is not None else float("-inf"), reverse=True):
        lines.append(
            f"| {entry['policy']} | {fmt(entry['avg_reward'])} | {fmt(entry['avg_rate'])} | "
            f"{fmt(entry['min_rate'], 2)} | {fmt(entry['max_rate'], 2)} | "
            f"{fmt(entry['final_latency_ms'], 2)} | {fmt(entry['final_qps'], 2)} | "
            f"{fmt(entry['final_error_rate'], 4)} |"
        )
    return lines


def build_markdown(entries_by_scenario: dict[str, list[dict]]) -> str:
    lines = [
        "# Adaptive Tracing Method Comparison Report",
        "",
        "## Overview",
        "",
        "This report summarizes the adaptive tracing experiments performed on the Train-Ticket Python testbed. "
        "The goal was to compare RL-based and non-RL adaptive tracing methods under the same workload pattern.",
        "",
        "The methods can include RL-based strategies such as `q_learning`, `sarsa`, and `bandit`, "
        "as well as non-RL baselines such as `rule` and `kmeans`. "
        "Runs collect metrics from the sampling agent status and summary endpoints.",
        "",
        "## Method",
        "",
        "The evaluation used the same adaptive tracing testbed, the same workload generation process, "
        "and the same runtime metrics (error rate, average latency, QPS, and sampling behavior). "
        "Two operating scenarios were tested:",
        "",
    ]
    for scenario in ("healthy", "faulted"):
        if scenario in entries_by_scenario:
            lines.append(f"- `{SCENARIO_NOTES[scenario]['title']}`: {SCENARIO_NOTES[scenario]['description']}")
    lines.extend(["", "## Results", ""])

    for scenario in ("healthy", "faulted"):
        entries = entries_by_scenario.get(scenario)
        if not entries:
            continue
        lines.append(f"### {SCENARIO_NOTES[scenario]['title']}")
        lines.append("")
        lines.append(scenario_observation(entries, scenario))
        lines.append("")
        lines.extend(markdown_table(entries))
        lines.append("")

    lines.extend(
        [
            "## Interpretation",
            "",
            "Under healthy conditions, the methods generally reduced tracing activity, which is the expected behavior when the system is stable and extra traces provide limited benefit.",
            "",
            "Under the faulted condition, the methods responded differently as latency increased and throughput dropped. "
            "This creates a useful basis for comparing how each method balances observability value against tracing cost.",
            "",
            "At this stage, the strongest comparison signal is average reward together with average sampling rate. "
            "A method with higher reward and a controlled sampling rate is preferable because it suggests better adaptation without unnecessary overhead.",
            "",
            "## Limitations",
            "",
            limitations_text(entries_by_scenario),
            "",
            "## Conclusion",
            "",
            "The implementation and experiment pipeline are now complete enough for comparative evaluation. "
            "These results provide a side-by-side view of adaptive tracing behavior and can be extended with additional fault scenarios, more baselines, or longer runs in the next phase.",
            "",
        ]
    )
    return "\n".join(lines)


def build_html(md_text: str) -> str:
    paragraphs = []
    in_list = False
    in_table = False
    table_lines: list[str] = []

    def flush_table() -> None:
        nonlocal in_table, table_lines
        if not table_lines:
            return
        header = table_lines[0].strip("|").split("|")
        rows = [line.strip("|").split("|") for line in table_lines[2:]]
        paragraphs.append("<table>")
        paragraphs.append("<thead><tr>" + "".join(f"<th>{html.escape(cell.strip())}</th>" for cell in header) + "</tr></thead>")
        paragraphs.append("<tbody>")
        for row in rows:
            paragraphs.append("<tr>" + "".join(f"<td>{html.escape(cell.strip())}</td>" for cell in row) + "</tr>")
        paragraphs.append("</tbody></table>")
        table_lines = []
        in_table = False

    for raw_line in md_text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("|"):
            if in_list:
                paragraphs.append("</ul>")
                in_list = False
            in_table = True
            table_lines.append(line)
            continue
        if in_table:
            flush_table()
        if not line:
            if in_list:
                paragraphs.append("</ul>")
                in_list = False
            continue
        if line.startswith("# "):
            paragraphs.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            paragraphs.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            paragraphs.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("- "):
            if not in_list:
                paragraphs.append("<ul>")
                in_list = True
            paragraphs.append(f"<li>{html.escape(line[2:])}</li>")
        else:
            paragraphs.append(f"<p>{html.escape(line)}</p>")

    if in_table:
        flush_table()
    if in_list:
        paragraphs.append("</ul>")

    body = "\n".join(paragraphs)
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Adaptive Sampling RL Evaluation Report</title>
  <style>
    body {{
      font-family: Helvetica, Arial, sans-serif;
      margin: 40px;
      color: #222;
      line-height: 1.45;
    }}
    h1, h2, h3 {{
      color: #0f2f44;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      margin: 16px 0 28px;
      font-size: 13px;
    }}
    th, td {{
      border: 1px solid #c9d4dc;
      padding: 8px 10px;
      text-align: left;
    }}
    th {{
      background: #eef4f7;
    }}
    p, li {{
      font-size: 14px;
    }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""


def write_pdf_from_html(html_path: Path, pdf_path: Path) -> bool:
    try:
        with pdf_path.open("wb") as handle:
            subprocess.run(
                ["cupsfilter", "-m", "application/pdf", str(html_path)],
                check=True,
                stdout=handle,
                stderr=subprocess.PIPE,
            )
        return True
    except subprocess.CalledProcessError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a concise sampling comparison report.")
    parser.add_argument("files", nargs="+", help="experiment result JSON files")
    parser.add_argument("--basename", default="sampling_evaluation_report", help="base name for output files")
    args = parser.parse_args()

    REPORTS_DIR.mkdir(exist_ok=True)

    grouped: dict[str, list[dict]] = {}
    for file_name in args.files:
        data = load_result(Path(file_name))
        entry = summarize_entry(data)
        grouped.setdefault(entry["scenario"], []).append(entry)

    md_text = build_markdown(grouped)
    html_text = build_html(md_text)

    md_path = REPORTS_DIR / f"{args.basename}.md"
    html_path = REPORTS_DIR / f"{args.basename}.html"
    pdf_path = REPORTS_DIR / f"{args.basename}.pdf"

    md_path.write_text(md_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")
    pdf_ok = write_pdf_from_html(html_path, pdf_path)

    print(md_path)
    print(html_path)
    if pdf_ok:
        print(pdf_path)
    else:
        print("PDF generation failed; Markdown and HTML were created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
