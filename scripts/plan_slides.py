#!/usr/bin/env python3
"""Plan technical and research-aware slide sequences."""

from __future__ import annotations

from typing import Any

from analysis_engine import analyze_document
from common import build_parser, count_words, read_json, short_title, trim_sentence, write_json


def _make_slide(
    slide_type: str,
    title: str,
    body: list[str],
    key_message: str,
    layout_family: str,
    narrative_role: str,
    source_sections: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "slide_type": slide_type,
        "title": title,
        "body": [item for item in body if item][:5],
        "key_message": key_message,
        "layout_family": layout_family,
        "narrative_role": narrative_role,
        "source_sections": source_sections or [],
        "density_score": sum(count_words(item) for item in body if item),
    }


def _agenda_items(slides: list[dict[str, Any]]) -> list[str]:
    return [short_title(slide["title"], f"主题 {index + 1}", 24) for index, slide in enumerate(slides) if slide["slide_type"] not in {"cover", "thank_you"}][:6]


def _section_titles(parsed_input: dict[str, Any]) -> list[str]:
    return [short_title(section.get("title", ""), "内容", 20) for section in parsed_input.get("sections", []) if section.get("title")]


def _build_technical_story(parsed_input: dict[str, Any], classification: dict[str, Any]) -> list[dict[str, Any]]:
    analysis = classification["analysis"]
    technical = analysis["technical_summary"]
    research = technical.get("research_signals", {})
    source_role = technical.get("source_role", {})
    section_names = _section_titles(parsed_input)
    major_entities = technical.get("major_entities", [])
    pipeline_steps = technical.get("pipeline_steps", [])
    data_flow = technical.get("data_flow", [])
    metrics = technical.get("metrics", [])

    slides = []
    if research.get("problem") or section_names:
        slides.append(
            _make_slide(
                "problem_background",
                "问题背景与研究目标",
                research.get("problem") or [f"内容来源覆盖：{'、'.join(section_names[:4])}"],
                trim_sentence((research.get("problem") or [classification["core_message"]])[0], 16),
                "hero",
                "context",
                section_names[:3],
            )
        )

    slides.append(
        _make_slide(
            "codebase_file_role",
            "代码角色与文件职责",
            [f"{source_role.get('filename') or parsed_input.get('source_name') or '输入材料'}：{role}" for role in source_role.get("roles", [])[:4]]
            or ["识别核心入口、关键类与主要函数责任边界"],
            "先说明这份代码或材料在整体系统中的位置",
            "comparison",
            "analysis",
            section_names[:3],
        )
    )

    if data_flow:
        slides.append(
            _make_slide(
                "data_representation",
                "数据与输入表示",
                data_flow[:4],
                data_flow[0],
                "architecture",
                "analysis",
                section_names[:3],
            )
        )

    if major_entities:
        slides.append(
            _make_slide(
                "architecture_diagram",
                "系统结构与模块关系",
                [f"核心实体：{'、'.join(major_entities[:5])}"] + research.get("method", [])[:3],
                "解释模块之间如何协同完成主链路",
                "architecture",
                "analysis",
                section_names[:4],
            )
        )

    method_points = research.get("method", [])
    if method_points or technical.get("code_analysis"):
        summary = []
        for item in technical.get("code_analysis", [])[:2]:
            if item.get("summary"):
                summary.append(item["summary"])
        slides.append(
            _make_slide(
                "algorithm_mechanism",
                "关键机制与算法桥接",
                method_points[:3] + summary[:2] or ["从输入、状态更新到输出，说明算法桥接逻辑"],
                (method_points or summary or ["说明关键机制"])[0],
                "process",
                "analysis",
                section_names[:4],
            )
        )

    if "training" in pipeline_steps:
        slides.append(
            _make_slide(
                "training_pipeline",
                "训练流程",
                [step for step in pipeline_steps[:5]] or ["data", "training", "evaluation"],
                "展示训练链路、关键环节与中间产物",
                "process",
                "analysis",
                section_names[:4],
            )
        )
    elif pipeline_steps:
        slides.append(
            _make_slide(
                "execution_loop",
                "执行循环与运行流程",
                pipeline_steps[:5],
                "把系统按运行时步骤讲清楚",
                "process",
                "analysis",
                section_names[:4],
            )
        )

    if metrics or research.get("results"):
        body = [f"{item['label']}：{item['value']}" for item in metrics[:4]] + research.get("results", [])[:2]
        slides.append(
            _make_slide(
                "evaluation_results",
                "评估结果与证据",
                body[:5],
                body[0] if body else "用指标或实验结果支撑结论",
                "metrics",
                "evidence",
                section_names[:4],
            )
        )

    slides.append(
        _make_slide(
            "limitations_risks",
            "局限性与风险",
            research.get("risks", [])[:4] or ["仍需补充鲁棒性验证、边界条件和工程化约束说明"],
            (research.get("risks") or ["明确当前方案边界"])[0],
            "cards",
            "risk",
            section_names[:3],
        )
    )
    return slides


def _build_research_story(parsed_input: dict[str, Any], classification: dict[str, Any]) -> list[dict[str, Any]]:
    analysis = classification["analysis"]
    technical = analysis["technical_summary"]
    research = technical.get("research_signals", {})
    section_names = _section_titles(parsed_input)
    slides = []
    slides.append(
        _make_slide(
            "problem_background",
            "研究背景与问题定义",
            research.get("problem", [])[:4] or analysis.get("storyline_beats", [])[1:3],
            classification["core_message"],
            "hero",
            "context",
            section_names[:3],
        )
    )
    if research.get("method"):
        slides.append(
            _make_slide(
                "algorithm_mechanism",
                "方法路径与核心机制",
                research.get("method", [])[:4],
                research["method"][0],
                "process",
                "analysis",
                section_names[:4],
            )
        )
    if technical.get("metrics") or research.get("results"):
        body = [f"{item['label']}：{item['value']}" for item in technical.get("metrics", [])[:4]] + research.get("results", [])[:2]
        slides.append(
            _make_slide(
                "evaluation_results",
                "结果与讨论",
                body[:5],
                body[0] if body else "用结果支撑结论",
                "metrics",
                "evidence",
                section_names[:4],
            )
        )
    slides.append(
        _make_slide(
            "limitations_risks",
            "限制与后续工作",
            research.get("risks", [])[:3] + research.get("next_steps", [])[:2],
            "把限制讲清楚，比过度包装更重要",
            "cards",
            "risk",
            section_names[:3],
        )
    )
    return slides


def plan_slides(parsed_input: dict[str, Any], classification: dict[str, Any]) -> dict[str, Any]:
    title = parsed_input.get("title") or "清华技术汇报"
    analysis = classification.get("analysis") or analyze_document(parsed_input)
    is_technical = analysis.get("deck_shape", {}).get("is_code_heavy") or classification.get("technical_depth", 0.0) >= 0.55

    story = _build_technical_story(parsed_input, classification) if is_technical else _build_research_story(parsed_input, classification)
    slides = [
        _make_slide(
            "cover",
            title,
            [parsed_input.get("subtitle") or parsed_input.get("speaker") or classification["core_message"]],
            classification["core_message"],
            "cover",
            "opening",
        ),
        _make_slide(
            "agenda",
            "汇报结构",
            _agenda_items(story),
            "先建立问题、机制、证据、边界四层结构",
            "agenda",
            "orientation",
        ),
    ]
    slides.extend(story)
    next_steps = analysis.get("technical_summary", {}).get("research_signals", {}).get("next_steps", [])[:3]
    closing_body = analysis.get("storyline_beats", [])[:3] + next_steps
    slides.append(
        _make_slide(
            "conclusion_next_steps",
            "结论与下一步",
            closing_body[:4] or [classification["core_message"], "继续补强实验、可视化与工程验证"],
            classification["core_message"],
            "conclusion",
            "closing",
        )
    )
    slides.append(
        _make_slide(
            "thank_you",
            "谢谢",
            [parsed_input.get("speaker") or "", parsed_input.get("date") or ""],
            "欢迎交流",
            "closing",
            "closing",
        )
    )

    return {
        "title": title,
        "category": classification["category"],
        "audience": classification["audience"],
        "presentation_type": classification["presentation_type"],
        "author": parsed_input.get("speaker", ""),
        "date": parsed_input.get("date", ""),
        "slide_count_target": len(slides),
        "story_model": "technical_deck" if is_technical else "research_deck",
        "slides": slides,
    }


def main() -> None:
    parser = build_parser("Plan slides for a Tsinghua-style technical or research deck.")
    parser.add_argument("--parsed-json", required=True)
    parser.add_argument("--classification-json", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    payload = plan_slides(read_json(args.parsed_json), read_json(args.classification_json))
    write_json(args.output_json, payload)


if __name__ == "__main__":
    main()
