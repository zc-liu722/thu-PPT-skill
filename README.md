# thu-ppt-generator

Production-grade Tsinghua-style PPT generator for technical, research, and code-heavy material.

## Architecture

The upgraded pipeline is intentionally split into concrete stages instead of a single summarization pass:

1. `parse_input.py`
   - Parses markdown, outline, prose, and source-code files.
   - Preserves code blocks and source metadata.

2. `technical_analysis.py`
   - Performs AST-backed Python analysis when code is present.
   - Extracts classes, functions, imports, call edges, config-like symbols, pipeline stages, artifacts, and data-flow hints.

3. `analysis_engine.py`
   - Merges narrative signals and technical signals into one deck-analysis IR.

4. `plan_slides.py`
   - Chooses deliberate technical slide types rather than generic cards-only layouts.

5. `visual_planner.py`
   - Produces editable diagram specs, metrics-card specs, comparison layouts, and selective imagegen requests.

6. `select_assets.py`
   - Selects Tsinghua library assets while preserving programmatic visuals as the primary expression.

7. `build_ppt.py` + `build_ppt.js`
   - Copies a real rebuild bundle into the output directory.
   - Generates `deck_source.js`, `deck_payload.json`, and copied `helpers/`.
   - Builds the final `.pptx` with PptxGenJS.

8. `qa_deck.py`
   - Reuses the mature `slides` skill workflow for rendering, overflow checks, font checks, and artifact capture.

## Workflow

```bash
python3 scripts/run_pipeline.py --input examples/technical_system.md --output-dir /tmp/thu-tech-deck
```

Expected outputs:

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
- `rendered_slides/` when rendering succeeds

## Technical deck types

The planner now supports:

- `cover`
- `agenda`
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
- `thank_you`

## Visual generation

Programmatic visuals are preferred and stay editable in PowerPoint:

- architecture diagrams
- process pipelines
- execution loops
- code-relationship views
- comparison layouts
- metrics cards

Selective image generation is wired through `imagegen_bridge.py`, but it is opt-in:

- default behavior: do not call `imagegen`
- only runs when the user explicitly asks for AI-generated visuals and the pipeline is started with `--enable-ai-images`
- requests are created only for slides that benefit from editorial support visuals
- all prompts and statuses are stored in `image_generation_trace.json`
- when `OPENAI_API_KEY` is set and the imagegen CLI is available, the pipeline can generate the supporting image automatically

## QA

The build now performs real post-build QA:

- slide rendering via `slides/scripts/render_slides.py`
- overflow detection via `slides/scripts/slides_test.py`
- font inspection via `slides/scripts/detect_font.py` when LibreOffice is available
- weak-slide and repeated-layout checks
- pending-image and missing-artifact reporting

## Tests

Run:

```bash
python3 -m unittest tests.test_core -v
python3 -m unittest tests.test_pipeline -v
```

## Notes

- The deck source is rebuildable from the generated `deck_source.js`.
- The theme uses dynamic installed-font detection instead of assuming one Windows-only font.
- The imagegen path is selective, traceable, and optional rather than mandatory.
