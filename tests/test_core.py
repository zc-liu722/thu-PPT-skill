import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from classify_content import classify_content
from common import load_asset_library
from lint_ppt import lint_plan
from parse_input import parse_input_file, parse_input_text
from plan_slides import plan_slides
from select_assets import select_assets
from technical_analysis import analyze_python_code
from visual_planner import generate_visual_plan


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.layout_index, cls.theme_tokens = load_asset_library("/Users/liuzichang/Downloads/thu_PPT/thu_ppt_assets")

    def test_parse_markdown_captures_code_blocks(self):
        text = "# 标题\n\n## 架构\n```python\nprint('hello')\n```\n- 要点一\n"
        parsed = parse_input_text(text, "markdown")
        self.assertEqual(parsed["detected_structure"], "markdown")
        self.assertEqual(parsed["code_block_count"], 1)
        self.assertEqual(parsed["sections"][0]["code_blocks"][0]["language"], "python")

    def test_parse_python_file_marks_code_source(self):
        parsed = parse_input_file(ROOT / "scripts" / "analysis_engine.py")
        self.assertEqual(parsed["source_kind"], "code_file")
        self.assertEqual(parsed["primary_language"], "python")
        self.assertEqual(parsed["code_block_count"], 1)

    def test_python_analysis_extracts_structure(self):
        result = analyze_python_code(
            "import os\n\nclass Trainer:\n    def fit(self, data):\n        return run_eval(data)\n\ndef run_eval(data):\n    return data\n"
        )
        self.assertTrue(result["parse_ok"])
        self.assertEqual(result["classes"][0]["name"], "Trainer")
        self.assertTrue(any(fn["name"] == "run_eval" for fn in result["functions"]))

    def test_classify_humanities(self):
        parsed = parse_input_text("人文讲座\n- 历史与文化\n- 文学经典\n- 思想史讨论\n", "outline")
        result = classify_content(parsed, self.manifest, self.theme_tokens)
        self.assertEqual(result["category"], "humanities")
        self.assertIn(result["audience"], {"academic", "technical"})

    def test_plan_creates_technical_deck_shapes(self):
        parsed = parse_input_text((ROOT / "examples" / "technical_system.md").read_text(encoding="utf-8"), "markdown")
        classification = classify_content(parsed, self.manifest, self.theme_tokens)
        plan = plan_slides(parsed, classification)
        slide_types = [slide["slide_type"] for slide in plan["slides"]]
        self.assertIn("agenda", slide_types)
        self.assertTrue(any(slide_type in {"architecture_diagram", "training_pipeline", "execution_loop", "algorithm_mechanism"} for slide_type in slide_types))

    def test_visual_plan_prefers_programmatic_diagrams(self):
        parsed = parse_input_text((ROOT / "examples" / "technical_system.md").read_text(encoding="utf-8"), "markdown")
        classification = classify_content(parsed, self.manifest, self.theme_tokens)
        plan = plan_slides(parsed, classification)
        visual_plan = generate_visual_plan(plan, classification)
        diagram_entries = [item for item in visual_plan["slides"] if item["slide_type"] in {"architecture_diagram", "training_pipeline", "execution_loop", "algorithm_mechanism"}]
        self.assertTrue(diagram_entries)
        self.assertTrue(all(item["visual"]["strategy"] == "programmatic" for item in diagram_entries))
        self.assertEqual(visual_plan["image_requests"], [])

    def test_visual_plan_only_requests_ai_images_when_enabled(self):
        parsed = parse_input_text((ROOT / "examples" / "technical_system.md").read_text(encoding="utf-8"), "markdown")
        classification = classify_content(parsed, self.manifest, self.theme_tokens)
        classification["technical_depth"] = 0.95
        plan = plan_slides(parsed, classification)
        disabled = generate_visual_plan(plan, classification, enable_ai_images=False)
        enabled = generate_visual_plan(plan, classification, enable_ai_images=True)
        self.assertEqual(disabled["image_requests"], [])
        self.assertGreaterEqual(len(enabled["image_requests"]), 1)

    def test_select_assets_keeps_diagrams_programmatic(self):
        parsed = parse_input_text((ROOT / "examples" / "technical_system.md").read_text(encoding="utf-8"), "markdown")
        classification = classify_content(parsed, self.manifest, self.theme_tokens)
        plan = plan_slides(parsed, classification)
        visual_plan = generate_visual_plan(plan, classification)
        assets = select_assets(self.manifest, self.layout_index, self.theme_tokens, classification, plan, visual_plan)
        diagram_assets = [item for item, slide in zip(assets["slide_assets"], plan["slides"]) if slide["slide_type"] in {"architecture_diagram", "training_pipeline", "execution_loop", "algorithm_mechanism"}]
        self.assertTrue(diagram_assets)
        self.assertTrue(all(item["visual_mode"] == "programmatic" for item in diagram_assets))

    def test_lint_flags_truncated_and_repeated_layouts(self):
        plan = {
            "slides": [
                {"slide_type": "cover", "title": "标题", "body": [], "layout_family": "cover"},
                {"slide_type": "problem_background", "title": "问题", "body": ["第一点…", "第二点"], "layout_family": "cards"},
                {"slide_type": "algorithm_mechanism", "title": "机制", "body": ["A", "B"], "layout_family": "cards"},
                {"slide_type": "evaluation_results", "title": "结果", "body": ["C", "D"], "layout_family": "cards"},
                {"slide_type": "thank_you", "title": "谢谢", "body": [], "layout_family": "closing"},
            ]
        }
        visual_plan = {"slides": [{"slide_index": 3, "visual": {"nodes": ["模块", "真实节点"]}}]}
        report, _ = lint_plan(plan, {"slide_assets": []}, visual_plan)
        codes = {item["code"] for item in report["findings"]}
        self.assertIn("truncated_text", codes)
        self.assertIn("repeated_layout", codes)
        self.assertIn("weak_diagram_labels", codes)


if __name__ == "__main__":
    unittest.main()
