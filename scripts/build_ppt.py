#!/usr/bin/env python3
"""Build a PPTX deck with a real rebuildable JS authoring source."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from apply_style import resolve_theme
from common import build_parser, read_json, write_json


SLIDES_HELPERS = Path("/Users/liuzichang/.codex/skills/slides/assets/pptxgenjs_helpers")


def _copy_authoring_bundle(output_js: str) -> tuple[Path, Path]:
    js_target = Path(output_js)
    js_target.parent.mkdir(parents=True, exist_ok=True)
    source_template = Path(__file__).with_name("build_ppt.js")
    shutil.copy2(source_template, js_target)
    helpers_target = js_target.parent / "helpers"
    if helpers_target.exists():
        shutil.rmtree(helpers_target)
    shutil.copytree(SLIDES_HELPERS, helpers_target)
    return js_target, helpers_target


def build_ppt(
    plan: dict[str, Any],
    assets: dict[str, Any],
    theme_tokens: dict[str, Any],
    output_pptx: str,
    output_js: str | None = None,
    visual_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    per_asset_theme = assets.get("theme_profile") or {}
    category_theme = theme_tokens.get("by_category", {}).get(plan["category"], {})
    resolved_theme = resolve_theme(
        plan["category"],
        per_asset_theme or category_theme,
    )
    output_path = Path(output_pptx)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    source_js_path = Path(output_js) if output_js else output_path.with_name("deck_source.js")
    source_js_path, helpers_path = _copy_authoring_bundle(str(source_js_path))
    payload_path = source_js_path.parent / "deck_payload.json"
    payload = {
        "plan": plan,
        "assets": assets,
        "visual_plan": visual_plan or {},
        "theme": resolved_theme,
        "output_pptx": str(output_path),
    }
    write_json(payload_path, payload)
    command = ["node", str(source_js_path), "--payload-json", str(payload_path), "--output-pptx", str(output_path)]
    env = os.environ.copy()
    skill_node_modules = str(Path(__file__).resolve().parents[1] / "node_modules")
    env["NODE_PATH"] = skill_node_modules + (os.pathsep + env["NODE_PATH"] if env.get("NODE_PATH") else "")
    result = subprocess.run(command, capture_output=True, text=True, check=False, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"deck_source.js failed: {result.stderr.strip() or result.stdout.strip()}")
    if not output_path.exists():
        raise RuntimeError(f"PPTX was not generated at {output_pptx}")
    return {
        "output_pptx": str(output_path),
        "output_js": str(source_js_path),
        "payload_json": str(payload_path),
        "helpers_dir": str(helpers_path),
        "slide_count": len(plan.get("slides", [])),
        "renderer": "pptxgenjs",
        "theme_profile_source": assets.get("theme_profile_source", "by_category"),
        "stdout": result.stdout.strip(),
    }


def main() -> None:
    parser = build_parser("Build a PPTX file from a plan and selected assets.")
    parser.add_argument("--plan-json", required=True)
    parser.add_argument("--assets-json", required=True)
    parser.add_argument("--theme", required=True)
    parser.add_argument("--visual-plan-json")
    parser.add_argument("--output-pptx", required=True)
    parser.add_argument("--output-js")
    parser.add_argument("--qa-json")
    args = parser.parse_args()

    summary = build_ppt(
        read_json(args.plan_json),
        read_json(args.assets_json),
        read_json(args.theme),
        args.output_pptx,
        output_js=args.output_js,
        visual_plan=read_json(args.visual_plan_json) if args.visual_plan_json else None,
    )
    if args.qa_json:
        write_json(args.qa_json, summary)


if __name__ == "__main__":
    main()
