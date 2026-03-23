---
name: thu-ppt-generator
description: Generate production-grade Tsinghua-style PPTX decks for technical, code-heavy, and research material using a rebuildable PptxGenJS source, technical-content analysis, editable diagrams, selective image generation, and the slides skill QA loop.
---

# Tsinghua PPT Generator

Use this skill when the user wants a complete `.pptx` deck in a restrained Tsinghua-inspired academic style and the source material is technical, research-heavy, code-driven, or mixed Chinese-English.

## What This Skill Now Does

- Parses markdown, outlines, prose, and source files.
- Uses technical analysis instead of shallow sentence compression.
- Extracts Python structure with AST when code is present: classes, functions, imports, call relationships, pipeline stages, config-like symbols, and artifacts.
- Plans real technical slide types such as:
  - `problem_background`
  - `codebase_file_role`
  - `data_representation`
  - `architecture_diagram`
  - `algorithm_mechanism`
  - `training_pipeline`
  - `execution_loop`
  - `evaluation_results`
  - `limitations_risks`
  - `conclusion_next_steps`
- Generates editable visuals with PowerPoint-native shapes first.
- Uses selective `imagegen` integration only when the user explicitly asks for AI-generated visuals and records every request in trace artifacts.
- Produces a real rebuildable authoring bundle:
  - `final_deck.pptx`
  - `deck_source.js`
  - `deck_payload.json`
  - copied `helpers/` bundle from the `slides` skill
- Runs real QA after build with the `slides` skill tooling:
  - `render_slides.py`
  - `slides_test.py`
  - `detect_font.py` when available

## Workflow

1. Install local Node dependencies with `npm install` in this skill directory if they are missing.
2. Run:

```bash
python3 scripts/run_pipeline.py --input <file> --output-dir <dir>
```

3. The pipeline will:
  - parse and classify the material
  - extract technical structure
  - build a slide plan and visual plan
  - optionally run selective image generation only if the user explicitly asked for AI visuals and `--enable-ai-images` is set
  - select Tsinghua asset-library support
  - render a rebuildable `deck_source.js`
  - build `final_deck.pptx`
  - render and QA the result

## Output Artifacts

- `final_deck.pptx`
- `deck_source.js`
- `deck_payload.json`
- `parsed_input.json`
- `classification.json`
- `slide_plan.json`
- `selected_assets.json`
- `visual_plan.json`
- `lint_report.json`
- `qa_report.json`
- `image_generation_trace.json`
- `rendered_slides/` and montage assets when rendering succeeds

## Rules

- Preserve factual meaning from source text and code. Do not ellipsize away technical logic.
- Prefer editable PowerPoint-native shapes over raster graphics.
- Never call `imagegen` by default. Use generated images only when the user explicitly asks for AI visuals.
- Keep the theme restrained, academic, and Tsinghua-like rather than generic corporate blue.
- If QA cannot reach acceptable quality, report blockers instead of claiming success.

## Validation

- Use the task-local `deck_source.js` as the rebuild entrypoint.
- Prefer `python3 -m unittest tests.test_core -v` for local validation.
- Run `python3 -m unittest tests.test_pipeline -v` when Node and `pptxgenjs` are available.
