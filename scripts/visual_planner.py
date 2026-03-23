#!/usr/bin/env python3
"""Visual planning for technical and research decks."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from common import trim_sentence, write_json


IMAGEGEN_SKILL_ROOT = Path("/Users/liuzichang/.codex/skills/imagegen")
IMAGEGEN_SCRIPT = IMAGEGEN_SKILL_ROOT / "scripts" / "image_gen.py"


def _diagram(slide_type: str, title: str, nodes: list[str], body: list[str]) -> dict[str, Any]:
    return {
        "visual_kind": slide_type,
        "strategy": "programmatic",
        "editable": True,
        "title": title,
        "nodes": nodes[:8],
        "annotations": body[:4],
    }


def _comparison_visual(slide: dict[str, Any]) -> dict[str, Any]:
    body = slide.get("body", [])
    return {
        "visual_kind": "comparison_cards",
        "strategy": "programmatic",
        "editable": True,
        "columns": [
            {"label": "当前 / baseline", "items": body[::2][:3]},
            {"label": "目标 / improved", "items": body[1::2][:3] or body[:3]},
        ],
    }


def _metrics_visual(slide: dict[str, Any], technical: dict[str, Any]) -> dict[str, Any]:
    cards = technical.get("metrics", [])[:4]
    if not cards:
        cards = [{"label": f"要点 {index + 1}", "value": trim_sentence(item, 6)} for index, item in enumerate(slide.get("body", [])[:4])]
    return {
        "visual_kind": "metrics_cards",
        "strategy": "programmatic",
        "editable": True,
        "cards": cards,
    }


def _code_structure_visual(technical: dict[str, Any]) -> dict[str, Any]:
    code_items = technical.get("code_analysis", [])
    relationships = [edge for item in code_items for edge in item.get("relationships", [])]
    return {
        "visual_kind": "code_relationship",
        "strategy": "programmatic",
        "editable": True,
        "nodes": technical.get("major_entities", [])[:8],
        "edges": relationships[:12],
    }


def _pipeline_visual(technical: dict[str, Any]) -> dict[str, Any]:
    steps = technical.get("pipeline_steps", [])[:6]
    labels = {
        "data": "数据准备",
        "training": "训练",
        "evaluation": "评估",
        "inference": "推理",
        "simulation": "执行循环",
    }
    return {
        "visual_kind": "pipeline",
        "strategy": "programmatic",
        "editable": True,
        "steps": [{"name": labels.get(step, step.title()), "code": step} for step in steps],
    }


def _should_request_image(slide: dict[str, Any], classification: dict[str, Any], enable_ai_images: bool) -> bool:
    if not enable_ai_images:
        return False
    if slide.get("slide_type") not in {"cover", "problem_background"}:
        return False
    if classification.get("technical_depth", 0.0) >= 0.8 and slide.get("slide_type") == "cover":
        return True
    return slide.get("slide_type") == "problem_background" and classification.get("audience") != "technical"


def _image_request(slide: dict[str, Any], classification: dict[str, Any]) -> dict[str, Any]:
    use_case = "stylized-concept" if slide.get("slide_type") == "cover" else "infographic-diagram"
    prompt = "\n".join(
        [
            f"Use case: {use_case}",
            "Asset type: academic technical presentation support visual",
            f"Primary request: {slide.get('title')}",
            "Style/medium: restrained editorial technical illustration",
            "Composition/framing: clean central subject with generous negative space and academic polish",
            "Lighting/mood: calm, precise, research-oriented",
            f"Color palette: restrained Tsinghua-inspired crimson, ivory, graphite, muted gold",
            f"Constraints: support the meaning of '{slide.get('key_message', slide.get('title'))}'; no watermark; no random UI chrome; no exaggerated sci-fi glow",
            "Avoid: clutter, stock-photo vibe, purple neon, cartoon excess",
        ]
    )
    return {
        "requested": True,
        "eligible": bool(os.environ.get("OPENAI_API_KEY")) and IMAGEGEN_SCRIPT.exists(),
        "skill_root": str(IMAGEGEN_SKILL_ROOT),
        "script_path": str(IMAGEGEN_SCRIPT),
        "prompt": prompt,
        "status": "pending",
        "rationale": f"Slide {slide.get('slide_type')} benefits from one selective editorial visual.",
    }


def generate_visual_plan(plan: dict[str, Any], classification: dict[str, Any], enable_ai_images: bool = False) -> dict[str, Any]:
    technical = classification.get("analysis", {}).get("technical_summary", {})
    visual_slides = []
    image_requests = []
    for index, slide in enumerate(plan.get("slides", []), start=1):
        slide_type = slide.get("slide_type")
        if slide_type in {"architecture_diagram", "data_representation", "algorithm_mechanism"}:
            visual = _diagram(slide_type, slide["title"], technical.get("relationship_nodes", []) or technical.get("major_entities", []), slide.get("body", []))
        elif slide_type in {"training_pipeline", "execution_loop"}:
            visual = _pipeline_visual(technical)
        elif slide_type == "codebase_file_role":
            visual = _code_structure_visual(technical)
        elif slide_type == "evaluation_results":
            visual = _metrics_visual(slide, technical)
        elif slide_type == "comparison":
            visual = _comparison_visual(slide)
        elif slide_type == "agenda":
            visual = {"visual_kind": "agenda_rail", "strategy": "programmatic", "editable": True, "items": slide.get("body", [])}
        else:
            visual = {"visual_kind": "text_support", "strategy": "layout", "editable": True}

        image = _image_request(slide, classification) if _should_request_image(slide, classification, enable_ai_images) else None
        visual_slides.append({"slide_index": index, "slide_type": slide_type, "visual": visual, "image_request": image})
        if image:
            image_requests.append({"slide_index": index, "slide_type": slide_type, **image})

    return {
        "deck_visual_strategy": "prefer editable PowerPoint-native diagrams; request imagegen only for selective opener/supporting visuals",
        "ai_images_enabled": enable_ai_images,
        "slides": visual_slides,
        "image_requests": image_requests,
    }


def write_image_trace(path: str | Path, visual_plan: dict[str, Any]) -> None:
    write_json(path, {"requests": visual_plan.get("image_requests", [])})
