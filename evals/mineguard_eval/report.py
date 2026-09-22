from __future__ import annotations

import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import CaseEvaluation


def _display(value: Any) -> str:
    if isinstance(value, float):
        if math.isnan(value):
            return "n/a"
        return f"{value:.4f}"
    return str(value)


def write_reports(
    output_dir: Path,
    target_name: str,
    profile_name: str,
    aggregate: dict[str, float],
    gate: dict[str, Any],
    results: list[CaseEvaluation],
    environment: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": target_name,
        "profile": profile_name,
        "gate": gate,
        "aggregate": aggregate,
        "environment": environment,
        "cases": [item.__dict__ for item in results],
    }
    (output_dir / "results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )

    lines = [
        "# MineGuard Agent Evaluation",
        "",
        f"- Target: `{target_name}`",
        f"- Gate profile: `{profile_name}`",
        f"- Result: **{'PASS' if gate['passed'] else 'FAIL'}**",
        f"- Cases: `{len(results)}`",
        "",
        "## Release gates",
        "",
        "| Metric | Actual | Requirement | Result |",
        "|---|---:|---:|:---:|",
    ]
    for metric, check in gate["checks"].items():
        lines.append(
            f"| {metric} | {_display(check['actual'])} | {check['operator']} {_display(check['threshold'])} | {'PASS' if check['passed'] else 'FAIL'} |"
        )
    lines.extend(
        [
            "",
            "## Case results",
            "",
            "| Case | Schema | Risk | Decision | Approval | Citations P/R | Tools P/R | Latency ms |",
            "|---|:---:|:---:|:---:|:---:|---:|---:|---:|",
        ]
    )
    for item in results:
        lines.append(
            f"| {item.case_id} | {int(item.metrics['schema_valid'])} | {int(item.metrics['risk_correct'])} | "
            f"{int(item.metrics['decision_correct'])} | {int(item.metrics['approval_correct'])} | "
            f"{item.metrics['citation_precision']:.2f}/{item.metrics['citation_recall']:.2f} | "
            f"{item.metrics['tool_precision']:.2f}/{item.metrics['tool_recall']:.2f} | {item.latency_ms:.1f} |"
        )
    lines.extend(
        [
            "",
            "> The rule-contract baseline validates benchmark wiring only. It is not evidence of LLM capability.",
        ]
    )
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    cards = "".join(
        f'<article><span>{html.escape(key)}</span><strong>{html.escape(_display(value))}</strong></article>'
        for key, value in aggregate.items()
        if key not in {"case_count"}
    )
    gate_rows = "".join(
        "<tr>"
        f"<td>{html.escape(metric)}</td><td>{html.escape(_display(check['actual']))}</td>"
        f"<td>{html.escape(check['operator'])} {html.escape(_display(check['threshold']))}</td>"
        f"<td class=\"{'pass' if check['passed'] else 'fail'}\">{'PASS' if check['passed'] else 'FAIL'}</td>"
        "</tr>"
        for metric, check in gate["checks"].items()
    )
    case_rows = "".join(
        "<tr>"
        f"<td>{html.escape(item.case_id)}</td>"
        f"<td>{'PASS' if item.metrics['schema_valid'] else 'FAIL'}</td>"
        f"<td>{item.metrics['risk_correct']:.0f}</td><td>{item.metrics['decision_correct']:.0f}</td>"
        f"<td>{item.metrics['citation_precision']:.2f}/{item.metrics['citation_recall']:.2f}</td>"
        f"<td>{item.metrics['tool_precision']:.2f}/{item.metrics['tool_recall']:.2f}</td>"
        f"<td>{item.latency_ms:.1f}</td>"
        "</tr>"
        for item in results
    )
    document = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>MineGuard Evaluation</title>
<style>:root{{--ink:#15231f;--muted:#5c6d66;--paper:#f4f0e6;--green:#0d6b57;--red:#b33b2e;--line:#d9d2c2}}*{{box-sizing:border-box}}body{{margin:0;background:linear-gradient(135deg,#e9f0e8,#f7f1e5 45%,#efe6d4);color:var(--ink);font-family:Georgia,'Times New Roman',serif}}main{{max-width:1180px;margin:0 auto;padding:52px 28px 80px}}header{{border-left:8px solid var(--green);padding:8px 0 8px 22px}}h1{{font-size:clamp(2.2rem,5vw,4.6rem);margin:0;line-height:.94}}header p{{color:var(--muted);font-family:Consolas,monospace}}.status{{display:inline-block;padding:8px 14px;background:{'#d9f1e8' if gate['passed'] else '#f7d9d2'};color:{'var(--green)' if gate['passed'] else 'var(--red)'};font-weight:700}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:36px 0}}article{{background:rgba(255,255,255,.72);border:1px solid var(--line);padding:16px;min-height:106px}}article span{{display:block;color:var(--muted);font:12px Consolas,monospace;overflow-wrap:anywhere}}article strong{{display:block;font-size:28px;margin-top:16px}}section{{margin-top:42px}}table{{width:100%;border-collapse:collapse;background:rgba(255,255,255,.72);font-family:Consolas,monospace;font-size:13px}}th,td{{padding:11px;border-bottom:1px solid var(--line);text-align:left}}th{{background:#17352d;color:white}}.pass{{color:var(--green);font-weight:700}}.fail{{color:var(--red);font-weight:700}}footer{{margin-top:28px;color:var(--muted);font-size:13px}}</style></head>
<body><main><header><h1>MineGuard<br>Agent Evaluation</h1><p>{html.escape(target_name)} / {html.escape(profile_name)}</p><span class="status">{'PASS' if gate['passed'] else 'FAIL'}</span></header>
<div class="cards">{cards}</div><section><h2>Release gates</h2><table><thead><tr><th>Metric</th><th>Actual</th><th>Requirement</th><th>Result</th></tr></thead><tbody>{gate_rows}</tbody></table></section>
<section><h2>Case evidence</h2><table><thead><tr><th>Case</th><th>Schema</th><th>Risk</th><th>Decision</th><th>Citation P/R</th><th>Tool P/R</th><th>Latency ms</th></tr></thead><tbody>{case_rows}</tbody></table></section>
<footer>Rule-contract results prove evaluator wiring only. Candidate model claims require a real model run and reviewed goldens.</footer></main></body></html>"""
    (output_dir / "report.html").write_text(document, encoding="utf-8")

