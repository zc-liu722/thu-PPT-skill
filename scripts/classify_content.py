#!/usr/bin/env python3
"""Classify content domain, audience, and presentation intent."""

from __future__ import annotations

from typing import Any

from analysis_engine import analyze_document
from common import build_parser, derive_available_categories, ensure_category, read_json, write_json


CATEGORY_KEYWORDS = {
    "party_building": [
        "党建",
        "党课",
        "党员",
        "党支部",
        "思政",
        "红色",
        "团课",
        "理论学习",
        "组织建设",
        "先锋",
        "政治引领",
        "支部",
        "党性",
    ],
    "humanities": [
        "人文",
        "文学",
        "历史",
        "哲学",
        "文化",
        "艺术",
        "思想史",
        "文本",
        "讲座",
        "经典",
        "社会思想",
        "叙事",
        "文明",
    ],
    "general": [
        "研究",
        "项目",
        "实验",
        "指标",
        "方案",
        "计划",
        "科技",
        "报告",
        "阶段进展",
        "分析",
        "系统",
        "平台",
        "工程",
    ],
}

TECHNICAL_TEMPLATE_COLOR_HINTS = {
    "912C8D",
    "7561D6",
    "7A0019",
}


def _score_category(text: str) -> dict[str, float]:
    lowered = text.lower()
    scores: dict[str, float] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = 0.0
        for keyword in keywords:
            if keyword.lower() in lowered:
                score += 1.0
        scores[category] = score
    return scores


def _technical_template_bonus(manifest: dict[str, Any], theme_tokens: dict[str, Any], category: str, analysis: dict[str, Any]) -> float:
    if category != "general":
        return 0.0
    technical_ratio = float(analysis.get("technical_ratio", 0.0) or 0.0)
    deck_shape = analysis.get("deck_shape", {}) or {}
    is_code_heavy = bool(deck_shape.get("is_code_heavy"))
    has_pipeline = bool(deck_shape.get("has_pipeline"))
    has_results = bool(deck_shape.get("has_results"))
    technical_summary = analysis.get("technical_summary", {}) or {}
    entities = technical_summary.get("major_entities", []) or []
    metrics = technical_summary.get("metrics", []) or []

    if technical_ratio < 0.3 and not is_code_heavy and not has_pipeline:
        return 0.0

    per_asset = {
        item.get("asset_id"): item
        for item in theme_tokens.get("per_asset", [])
        if item.get("asset_id")
    }
    best_bonus = 0.0
    for asset in manifest.get("assets", []):
        if asset.get("asset_type") != "deck" or asset.get("category") != "general":
            continue
        asset_theme = per_asset.get(asset.get("asset_id"), {})
        primary_colors = [str(color).upper().lstrip("#") for color in asset_theme.get("primary_colors", [])]
        if not primary_colors:
            continue
        if not any(color in TECHNICAL_TEMPLATE_COLOR_HINTS for color in primary_colors[:2]):
            continue
        bonus = 0.12
        bonus += min(0.18, technical_ratio * 0.3)
        if is_code_heavy:
            bonus += 0.16
        if has_pipeline:
            bonus += 0.08
        if has_results:
            bonus += 0.04
        if entities:
            bonus += 0.04
        if metrics:
            bonus += 0.03
        best_bonus = max(best_bonus, bonus)
    return round(best_bonus, 3)


def classify_content(
    parsed_input: dict[str, Any],
    manifest: dict[str, Any],
    theme_tokens: dict[str, Any],
    forced_category: str | None = None,
) -> dict[str, Any]:
    analysis = analyze_document(parsed_input)
    available_categories = derive_available_categories(manifest, theme_tokens)
    text = parsed_input.get("source_text", "")
    keyword_scores = _score_category(text + " " + " ".join(parsed_input.get("keywords", [])))
    theme_bonus = {
        category: len(theme_tokens.get("by_category", {}).get(category, {}).get("reusable_visual_notes", [])) * 0.1
        for category in available_categories
    }
    technical_template_bonus = {
        category: _technical_template_bonus(manifest, theme_tokens, category, analysis)
        for category in available_categories
    }
    merged_scores = {
        category: keyword_scores.get(category, 0.0) + theme_bonus.get(category, 0.0) + technical_template_bonus.get(category, 0.0)
        for category in available_categories
    }
    inferred_category = max(merged_scores, key=merged_scores.get) if merged_scores else "general"
    if merged_scores.get(inferred_category, 0.0) <= 0:
        inferred_category = "general"
    if forced_category and forced_category != "auto":
        inferred_category = ensure_category(forced_category)

    presentation_type = analysis["purpose"]
    audience = analysis["audience"]
    technical_depth = min(1.0, max(0.0, analysis["technical_ratio"]))
    recommended_mix = {
        "text": round(max(0.35, 0.62 - technical_depth * 0.15), 2),
        "visual": round(min(0.65, 0.38 + technical_depth * 0.15), 2),
    }
    tone = {
        "general": "restrained academic",
        "humanities": "reflective and elegant",
        "party_building": "formal and mission-oriented",
    }[inferred_category]
    confidence = 0.62 + min(0.28, merged_scores.get(inferred_category, 0.0) * 0.05)

    return {
        "presentation_type": presentation_type,
        "category": inferred_category,
        "confidence": round(min(confidence, 0.95), 2),
        "tone": tone,
        "audience": audience,
        "core_message": analysis["core_message"],
        "storyline_beats": analysis["storyline_beats"],
        "technical_depth": round(technical_depth, 2),
        "recommended_mix": recommended_mix,
        "signals": {
            "keyword_scores": keyword_scores,
            "theme_bonus": theme_bonus,
            "technical_template_bonus": technical_template_bonus,
            "available_categories": available_categories,
            "technical_ratio": analysis["technical_ratio"],
            "deck_shape": analysis.get("deck_shape", {}),
            "technical_summary": analysis.get("technical_summary", {}),
        },
        "analysis": analysis,
    }


def main() -> None:
    parser = build_parser("Classify parsed content into Tsinghua presentation categories.")
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--theme", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--category", default="auto", choices=["auto", "general", "humanities", "party_building"])
    args = parser.parse_args()

    payload = classify_content(
        read_json(args.input_json),
        read_json(args.manifest),
        read_json(args.theme),
        args.category,
    )
    write_json(args.output_json, payload)


if __name__ == "__main__":
    main()
