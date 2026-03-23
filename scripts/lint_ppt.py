#!/usr/bin/env python3
"""Plan-level linting before PPT build."""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from common import build_parser, count_words, markdown_report_from_lint, read_json, write_json, write_text


def _meaningless_label(text: str) -> bool:
    normalized = re.sub(r"[\W_]+", "", text.lower())
    return normalized in {"module", "function", "class", "step", "node", "模块", "函数", "阶段"}


def lint_plan(plan: dict[str, Any], assets: dict[str, Any], visual_plan: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    fixed = deepcopy(plan)
    findings: list[dict[str, Any]] = []
    applied_fixes: list[str] = []
    slides = fixed.get("slides", [])
    seen_layouts = []

    for index, slide in enumerate(slides, start=1):
        body = [item for item in slide.get("body", []) if item.strip()]
        words = sum(count_words(item) for item in body)
        if slide.get("slide_type") not in {"cover", "agenda", "thank_you"} and not body:
            findings.append({"slide_index": index, "severity": "warning", "code": "empty_slide", "message": "Slide body is empty and likely too weak to present."})
        if words > 85:
            findings.append({"slide_index": index, "severity": "warning", "code": "dense_content", "message": "Slide content is too dense for stable technical communication."})
        if any("…" in item for item in body):
            findings.append({"slide_index": index, "severity": "warning", "code": "truncated_text", "message": "Ellipsized text risks factual loss; keep technical phrasing intact."})
        seen_layouts.append(slide.get("layout_family"))

    for start in range(len(seen_layouts) - 2):
        triplet = seen_layouts[start : start + 3]
        if len(set(triplet)) == 1 and triplet[0] not in {"agenda", "closing"}:
            findings.append({"slide_index": start + 1, "severity": "warning", "code": "repeated_layout", "message": "Three consecutive slides reuse the same layout family."})
            break

    if slides and slides[0].get("slide_type") != "cover":
        findings.append({"slide_index": 1, "severity": "fatal", "code": "missing_cover", "message": "Deck must start with a cover slide."})
    if slides and slides[-1].get("slide_type") != "thank_you":
        findings.append({"slide_index": len(slides), "severity": "fatal", "code": "missing_closing", "message": "Deck must end with a thank-you slide."})

    visual_index = {item["slide_index"]: item for item in (visual_plan or {}).get("slides", [])}
    for index, slide in enumerate(slides, start=1):
        visual = visual_index.get(index, {}).get("visual", {})
        for label in visual.get("nodes", [])[:8]:
            if _meaningless_label(label):
                findings.append({"slide_index": index, "severity": "warning", "code": "weak_diagram_labels", "message": "Generated diagram labels are too generic to teach the audience anything."})
                break

    score = 100 - sum(12 for item in findings if item["severity"] == "fatal") - sum(5 for item in findings if item["severity"] == "warning")
    report = {
        "findings": findings,
        "issues": findings,
        "fatal_count": sum(1 for item in findings if item["severity"] == "fatal"),
        "warning_count": sum(1 for item in findings if item["severity"] == "warning"),
        "applied_fixes": applied_fixes,
        "deck_score": max(0, score),
        "deck_summary": "Plan checked for truncation, weak slides, repeated layouts, and low-value diagram labels.",
    }
    return report, fixed


def main() -> None:
    parser = build_parser("Lint a slide plan before building the deck.")
    parser.add_argument("--plan-json", required=True)
    parser.add_argument("--assets-json", required=True)
    parser.add_argument("--visual-plan-json")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--auto-fix-json", required=True)
    args = parser.parse_args()

    report, fixed_plan = lint_plan(
        read_json(args.plan_json),
        read_json(args.assets_json),
        read_json(args.visual_plan_json) if args.visual_plan_json else None,
    )
    write_json(args.output_json, report)
    write_json(args.auto_fix_json, fixed_plan)
    write_text(Path(args.output_json).with_suffix(".md"), markdown_report_from_lint(report))


if __name__ == "__main__":
    main()
