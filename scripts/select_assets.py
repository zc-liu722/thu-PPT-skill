#!/usr/bin/env python3
"""Asset selection for the upgraded thu-ppt-generator."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from common import (
    asset_keywords,
    build_parser,
    derive_available_categories,
    extract_keywords,
    get_deck_metadata,
    pick_first,
    read_json,
    score_deck_for_layouts,
    semantic_overlap_score,
    write_json,
)


def _group_assets(manifest: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for asset in manifest.get("assets", []):
        grouped[asset.get("category", "unknown")].append(asset)
    return grouped


def _select_template(manifest: dict[str, Any], layout_index: dict[str, Any], requested_category: str) -> dict[str, Any]:
    decks = [asset for asset in manifest.get("assets", []) if asset.get("asset_type") == "deck"]
    candidates = [deck for deck in decks if deck.get("category") == requested_category] or [
        deck for deck in decks if deck.get("category") == "general"
    ]
    preferred_layouts = ["cover", "content", "two_column", "agenda", "section_divider"]
    return sorted(
        candidates,
        key=lambda deck: (
            -score_deck_for_layouts(deck["asset_id"], layout_index.get("layouts", []), preferred_layouts),
            -float(deck.get("confidence", 0.0)),
            -int(deck.get("slide_count", 0)),
        ),
    )[0]


def _technical_template_priority(
    deck: dict[str, Any],
    classification: dict[str, Any],
    theme_tokens: dict[str, Any],
) -> float:
    if deck.get("category") != "general":
        return 0.0
    audience = classification.get("audience", "")
    technical_depth = float(classification.get("technical_depth", 0.0) or 0.0)
    deck_shape = (classification.get("signals") or {}).get("deck_shape", {}) or {}
    is_technical = audience == "technical" or technical_depth >= 0.35 or deck_shape.get("has_pipeline") or deck_shape.get("is_code_heavy")
    if not is_technical:
        return 0.0
    per_asset = {
        item.get("asset_id"): item
        for item in theme_tokens.get("per_asset", [])
        if item.get("asset_id")
    }
    asset_theme = per_asset.get(deck.get("asset_id"), {})
    primary_colors = [str(color).upper().lstrip("#") for color in asset_theme.get("primary_colors", [])]
    if not primary_colors:
        return 0.0
    if primary_colors[0] == "912C8D":
        return 1.0
    if "912C8D" in primary_colors[:2] or "7561D6" in primary_colors[:2]:
        return 0.7
    return 0.0


def _score_media_for_slide(asset: dict[str, Any], slide: dict[str, Any], requested_category: str) -> float:
    path = asset.get("output_path", "")
    if not path or not Path(path).exists():
        return -1.0
    role = asset.get("role", "")
    category = asset.get("category", "")
    slide_terms = extract_keywords(" ".join([slide.get("title", ""), slide.get("key_message", "")] + slide.get("body", [])), top_n=12)
    score = semantic_overlap_score(slide_terms + [slide.get("slide_type", "")], asset_keywords(asset))
    if category == requested_category:
        score += 0.35
    elif category == "shared":
        score += 0.2
    if role == "illustration" and slide.get("slide_type") in {"cover", "problem_background"}:
        score += 0.25
    if slide.get("slide_type") in {
        "architecture_diagram",
        "data_representation",
        "algorithm_mechanism",
        "training_pipeline",
        "execution_loop",
        "evaluation_results",
    }:
        score -= 0.45
    return score


def select_assets(
    manifest: dict[str, Any],
    layout_index: dict[str, Any],
    theme_tokens: dict[str, Any],
    classification: dict[str, Any],
    plan: dict[str, Any],
    visual_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    available_categories = derive_available_categories(manifest, theme_tokens)
    requested_category = classification["category"] if classification["category"] in available_categories else "general"
    grouped = _group_assets(manifest)
    selected_deck = _select_template(manifest, layout_index, requested_category)
    if requested_category == "general":
        decks = [asset for asset in manifest.get("assets", []) if asset.get("asset_type") == "deck" and asset.get("category") == requested_category]
        selected_deck = sorted(
            decks,
            key=lambda deck: (
                -_technical_template_priority(deck, classification, theme_tokens),
                -score_deck_for_layouts(deck["asset_id"], layout_index.get("layouts", []), ["cover", "content", "two_column", "agenda", "section_divider"]),
                -float(deck.get("confidence", 0.0)),
                -int(deck.get("slide_count", 0)),
            ),
        )[0]
    deck_metadata = get_deck_metadata(manifest, selected_deck["asset_id"])
    per_asset_theme = next(
        (item for item in theme_tokens.get("per_asset", []) if item.get("asset_id") == selected_deck["asset_id"]),
        {},
    )

    media_assets = [asset for asset in manifest.get("assets", []) if asset.get("asset_type") == "media"]
    fallback_order = [requested_category, "shared", "general", "humanities", "party_building", "ambiguous"]
    background = pick_first(media_assets, "background", fallback_order)
    logo = pick_first(media_assets, "logo", fallback_order)
    illustrations = [asset for asset in media_assets if asset.get("role") == "illustration"]

    slide_assets = []
    used_ids: set[str] = set()
    visual_index = {item["slide_index"]: item for item in (visual_plan or {}).get("slides", [])}
    for index, slide in enumerate(plan.get("slides", []), start=1):
        visual_entry = visual_index.get(index, {})
        visual = visual_entry.get("visual", {})
        illustration = None
        visual_mode = "programmatic" if visual.get("strategy") == "programmatic" else "layout"
        rationale = "Prefer editable native shapes and diagrams."
        generated = visual_entry.get("image_request") or {}
        if generated.get("status") == "generated" and generated.get("output_path") and Path(generated["output_path"]).exists():
            illustration = {"output_path": generated["output_path"]}
            visual_mode = "hybrid"
            rationale = "Selective imagegen output was generated for this slide and kept traceable."
        if slide.get("slide_type") in {"cover", "problem_background"} and not visual_entry.get("image_request"):
            candidates = sorted(illustrations, key=lambda asset: _score_media_for_slide(asset, slide, requested_category), reverse=True)
            for candidate in candidates:
                if candidate["asset_id"] in used_ids:
                    continue
                if _score_media_for_slide(candidate, slide, requested_category) <= 0.18:
                    break
                illustration = candidate
                used_ids.add(candidate["asset_id"])
                visual_mode = "hybrid"
                rationale = "Add one supporting illustration without replacing the deck's editable structure."
                break
        slide_assets.append(
            {
                "slide_index": index,
                "slide_type": slide["slide_type"],
                "background_path": background.get("output_path") if background else None,
                "logo_path": logo.get("output_path") if logo else None,
                "illustration_path": illustration.get("output_path") if illustration else None,
                "visual_mode": visual_mode,
                "rationale": rationale,
            }
        )

    return {
        "category": requested_category,
        "available_categories": available_categories,
        "selected_template": {
            "asset_id": selected_deck["asset_id"],
            "template_path": selected_deck.get("template_path"),
            "thumbnail_path": selected_deck.get("thumbnail_path"),
            "metadata": deck_metadata,
        },
        "theme_profile": per_asset_theme or theme_tokens.get("by_category", {}).get(requested_category, {}),
        "theme_profile_source": "per_asset" if per_asset_theme else "by_category",
        "global_assets": {
            "background_path": background.get("output_path") if background else None,
            "logo_path": logo.get("output_path") if logo else None,
        },
        "slide_assets": slide_assets,
        "visual_support": visual_plan or {},
        "inventory_summary": {category: len(items) for category, items in grouped.items() if category in available_categories or category == "shared"},
    }


def main() -> None:
    parser = build_parser("Select semantically matched Tsinghua PPT assets.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--layout-index", required=True)
    parser.add_argument("--theme", required=True)
    parser.add_argument("--classification-json", required=True)
    parser.add_argument("--plan-json", required=True)
    parser.add_argument("--visual-plan-json")
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    payload = select_assets(
        read_json(args.manifest),
        read_json(args.layout_index),
        read_json(args.theme),
        read_json(args.classification_json),
        read_json(args.plan_json),
        read_json(args.visual_plan_json) if args.visual_plan_json else None,
    )
    write_json(args.output_json, payload)


if __name__ == "__main__":
    main()
