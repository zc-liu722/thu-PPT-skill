#!/usr/bin/env python3
"""End-to-end production pipeline for thu-ppt-generator."""

from __future__ import annotations

from pathlib import Path

from build_ppt import build_ppt
from classify_content import classify_content
from common import ASSET_ROOT_DEFAULT, build_parser, load_asset_library, markdown_report_from_lint, write_json, write_text
from imagegen_bridge import run_image_generation
from lint_ppt import lint_plan
from parse_input import parse_input_file
from plan_slides import plan_slides
from qa_deck import qa_deck
from select_assets import select_assets
from visual_planner import generate_visual_plan, write_image_trace


def run_pipeline(
    *,
    input_path: str,
    output_dir: str,
    assets_root: str,
    title: str | None = None,
    author: str | None = None,
    date_text: str | None = None,
    category: str = "auto",
    enable_ai_images: bool = False,
    keep_intermediate: bool = True,
) -> dict:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest, layout_index, theme_tokens = load_asset_library(assets_root)

    parsed = parse_input_file(input_path)
    if title:
        parsed["title"] = title
    if author:
        parsed["speaker"] = f"汇报人：{author}" if "汇报人" not in author else author
    if date_text:
        parsed["date"] = date_text

    classification = classify_content(parsed, manifest, theme_tokens, category)
    plan = plan_slides(parsed, classification)
    plan["author"] = author or parsed.get("speaker", "")
    plan["date"] = date_text or parsed.get("date", "")

    visual_plan = generate_visual_plan(plan, classification, enable_ai_images=enable_ai_images)
    image_trace = {"requests": []}
    if enable_ai_images:
        image_trace = run_image_generation(visual_plan, out_dir)
        trace_index = {item["slide_index"]: item for item in image_trace.get("requests", [])}
        for entry in visual_plan.get("slides", []):
            if entry["slide_index"] in trace_index:
                entry["image_request"] = trace_index[entry["slide_index"]]
        visual_plan["image_requests"] = image_trace.get("requests", [])
    selected_assets = select_assets(manifest, layout_index, theme_tokens, classification, plan, visual_plan)
    lint_report, plan = lint_plan(plan, selected_assets, visual_plan)

    pptx_path = out_dir / "final_deck.pptx"
    source_js_path = out_dir / "deck_source.js"
    build_summary = build_ppt(plan, selected_assets, theme_tokens, str(pptx_path), output_js=str(source_js_path), visual_plan=visual_plan)
    qa_report = qa_deck(str(pptx_path), str(out_dir), plan, visual_plan)

    parsed_path = out_dir / "parsed_input.json"
    classification_path = out_dir / "classification.json"
    plan_path = out_dir / "slide_plan.json"
    assets_path = out_dir / "selected_assets.json"
    visual_plan_path = out_dir / "visual_plan.json"
    lint_path = out_dir / "lint_report.json"
    qa_path = out_dir / "qa_report.json"
    lint_md_path = out_dir / "lint_report.md"
    qa_md_path = out_dir / "qa_report.md"
    image_trace_path = out_dir / "image_generation_trace.json"

    write_json(parsed_path, parsed)
    write_json(classification_path, classification)
    write_json(plan_path, plan)
    write_json(assets_path, selected_assets)
    write_json(visual_plan_path, visual_plan)
    write_json(lint_path, lint_report)
    write_json(qa_path, qa_report)
    write_json(image_trace_path, image_trace)
    write_text(lint_md_path, markdown_report_from_lint(lint_report))
    write_text(qa_md_path, markdown_report_from_lint({"findings": qa_report["findings"], "deck_score": qa_report["score"], "deck_summary": qa_report["status"], "warning_count": sum(1 for item in qa_report["findings"] if item["severity"] == "warning"), "fatal_count": sum(1 for item in qa_report["findings"] if item["severity"] == "fatal"), "applied_fixes": []}))

    return {
        "output_pptx": str(pptx_path),
        "output_js": str(source_js_path),
        "category": classification["category"],
        "selected_template": selected_assets["selected_template"]["asset_id"],
        "slide_count": build_summary["slide_count"],
        "warnings": lint_report["warning_count"] + sum(1 for item in qa_report["findings"] if item["severity"] == "warning"),
        "fatals": lint_report["fatal_count"] + sum(1 for item in qa_report["findings"] if item["severity"] == "fatal"),
        "deck_score": min(lint_report["deck_score"], qa_report["score"]),
        "core_message": classification["core_message"],
        "qa_status": qa_report["status"],
        "ai_images_enabled": enable_ai_images,
        "keep_intermediate": keep_intermediate,
    }


def main() -> None:
    parser = build_parser("Run the complete upgraded thu-ppt-generator pipeline.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--assets-root", default=str(ASSET_ROOT_DEFAULT))
    parser.add_argument("--title")
    parser.add_argument("--author")
    parser.add_argument("--date")
    parser.add_argument("--category", choices=["auto", "general", "humanities", "party_building"], default="auto")
    parser.add_argument("--enable-ai-images", action="store_true")
    parser.add_argument("--keep-intermediate", action="store_true")
    args = parser.parse_args()

    result = run_pipeline(
        input_path=args.input,
        output_dir=args.output_dir,
        assets_root=args.assets_root,
        title=args.title,
        author=args.author,
        date_text=args.date,
        category=args.category,
        enable_ai_images=args.enable_ai_images,
        keep_intermediate=args.keep_intermediate,
    )
    print(f"category={result['category']}")
    print(f"template={result['selected_template']}")
    print(f"slide_count={result['slide_count']}")
    print(f"deck_score={result['deck_score']}")
    print(f"qa_status={result['qa_status']}")
    print(f"ai_images_enabled={result['ai_images_enabled']}")
    print(f"output={result['output_pptx']}")


if __name__ == "__main__":
    main()
