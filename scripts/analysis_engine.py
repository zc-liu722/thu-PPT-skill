#!/usr/bin/env python3
"""Narrative and technical analysis helpers for thu-ppt-generator."""

from __future__ import annotations

from typing import Any

from common import (
    TECH_KEYWORDS,
    count_words,
    detect_comparison,
    detect_metrics,
    detect_technical,
    detect_timeline,
    extract_keywords,
    short_title,
    trim_sentence,
)
from technical_analysis import analyze_technical_content


AUDIENCE_KEYWORDS = {
    "executive": ["战略", "价值", "落地", "路线图", "roi", "overview"],
    "technical": ["api", "架构", "module", "pipeline", "代码", "训练", "推理", "benchmark"],
    "academic": ["研究", "方法", "实验", "理论", "文献", "课程", "研讨"],
}

PURPOSE_KEYWORDS = {
    "proposal": ["方案", "计划", "建议", "roadmap", "proposal"],
    "research_review": ["研究", "实验", "方法", "论文", "benchmark"],
    "architecture_review": ["架构", "pipeline", "service", "code", "module"],
    "progress_report": ["进展", "阶段", "milestone", "复盘"],
}


def infer_audience(text: str) -> str:
    lowered = text.lower()
    scores = {name: sum(1 for item in keywords if item.lower() in lowered) for name, keywords in AUDIENCE_KEYWORDS.items()}
    winner = max(scores, key=scores.get) if scores else "academic"
    return winner if scores.get(winner, 0) else "academic"


def infer_purpose(text: str, technicality: float) -> str:
    lowered = text.lower()
    scores = {name: sum(1 for item in keywords if item.lower() in lowered) for name, keywords in PURPOSE_KEYWORDS.items()}
    winner = max(scores, key=scores.get) if scores else "research_review"
    if scores.get(winner, 0):
        return winner
    if technicality >= 0.55:
        return "architecture_review"
    return "research_review"


def infer_core_message(parsed_input: dict[str, Any], technical: dict[str, Any]) -> str:
    title = parsed_input.get("title", "").strip()
    if title and len(title) <= 28:
        return title
    research = technical.get("research_signals", {})
    for key in ("problem", "method", "results"):
        values = research.get(key) or []
        if values:
            return trim_sentence(values[0], 18)
    role = technical.get("source_role", {})
    roles = role.get("roles", [])
    if roles:
        return f"围绕 {role.get('filename') or '核心模块'} 的 {' / '.join(roles[:2])}"
    keywords = parsed_input.get("keywords") or extract_keywords(parsed_input.get("source_text", ""))
    if keywords:
        return "围绕 " + "、".join(keywords[:3]) + " 展开技术汇报"
    return "形成准确、可复现的技术汇报"


def summarize_section(section: dict[str, Any], technical: dict[str, Any]) -> dict[str, Any]:
    title = short_title(section.get("title", ""), "核心内容")
    bullets = [trim_sentence(item, 18) for item in section.get("bullets", []) if item.strip()]
    paragraphs = [trim_sentence(item, 22) for item in section.get("paragraphs", []) if item.strip()]
    text = " ".join([title] + bullets + paragraphs)
    hint = "content"
    if detect_timeline(text):
        hint = "timeline"
    elif detect_comparison(text):
        hint = "comparison"
    elif detect_metrics(text):
        hint = "metrics"
    elif detect_technical(text):
        hint = "technical"

    preserved_points = []
    preserved_points.extend(bullets[:4])
    preserved_points.extend(paragraphs[:4])
    if not preserved_points and section.get("code_blocks"):
        for item in technical.get("code_analysis", []):
            if item.get("summary"):
                preserved_points.append(item["summary"])
                break
    return {
        "title": title,
        "hint": hint,
        "summary_points": preserved_points[:5],
        "keywords": extract_keywords(text, top_n=10),
        "source_order": section.get("source_order", 0),
        "raw_bullets": section.get("bullets", []),
        "raw_paragraphs": section.get("paragraphs", []),
        "code_blocks": section.get("code_blocks", []),
        "text": text,
    }


def build_storyline(core_message: str, technical: dict[str, Any]) -> list[str]:
    beats = [trim_sentence(core_message, 16)]
    research = technical.get("research_signals", {})
    if research.get("problem"):
        beats.append(trim_sentence(research["problem"][0], 16))
    if research.get("method"):
        beats.append(trim_sentence(research["method"][0], 16))
    if research.get("results"):
        beats.append(trim_sentence(research["results"][0], 16))
    if technical.get("pipeline_steps"):
        beats.append("流程覆盖 " + " -> ".join(technical["pipeline_steps"][:4]))
    deduped = []
    seen = set()
    for item in beats:
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped[:5]


def analyze_document(parsed_input: dict[str, Any]) -> dict[str, Any]:
    source_text = parsed_input.get("source_text", "")
    technical = analyze_technical_content(parsed_input)
    audience = infer_audience(source_text)
    purpose = infer_purpose(source_text, technical.get("technicality", 0.0))
    core_message = infer_core_message(parsed_input, technical)
    section_summaries = [summarize_section(section, technical) for section in parsed_input.get("sections", [])]
    keywords = parsed_input.get("keywords") or extract_keywords(source_text)
    technical_ratio = technical.get("technicality", 0.0)
    if section_summaries:
        technical_sections = sum(1 for item in section_summaries if item["hint"] in {"technical", "metrics"} or item.get("code_blocks"))
        technical_ratio = round(min(1.0, max(technical_ratio, technical_sections / max(len(section_summaries), 1))), 2)

    return {
        "core_message": core_message,
        "audience": audience,
        "purpose": purpose,
        "keywords": keywords,
        "technical_ratio": technical_ratio,
        "storyline_beats": build_storyline(core_message, technical),
        "section_summaries": section_summaries,
        "technical_summary": technical,
        "deck_shape": {
            "is_code_heavy": parsed_input.get("code_block_count", 0) > 0 or technical_ratio >= 0.55,
            "has_results": bool(technical.get("metrics") or technical.get("research_signals", {}).get("results")),
            "has_pipeline": len(technical.get("pipeline_steps", [])) >= 2,
            "has_risks": bool(technical.get("research_signals", {}).get("risks")),
        },
        "evidence": {
            "code_block_count": parsed_input.get("code_block_count", 0),
            "major_entities": technical.get("major_entities", []),
            "pipeline_steps": technical.get("pipeline_steps", []),
            "metrics_count": len(technical.get("metrics", [])),
            "word_count": count_words(source_text),
            "tech_keyword_hits": sum(1 for token in TECH_KEYWORDS if token in source_text.lower()),
        },
    }
