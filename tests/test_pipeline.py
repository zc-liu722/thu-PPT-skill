import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from common import read_json


NODE_AVAILABLE = shutil.which("node") is not None
PPTXGENJS_INSTALLED = (ROOT / "node_modules" / "pptxgenjs").exists()


@unittest.skipUnless(NODE_AVAILABLE and PPTXGENJS_INSTALLED, "node and local pptxgenjs are required for integration tests")
class PipelineTests(unittest.TestCase):
    def test_end_to_end_general(self):
        from run_pipeline import run_pipeline

        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_pipeline(
                input_path=str(ROOT / "examples" / "long_research_report.md"),
                output_dir=tmpdir,
                assets_root="/Users/liuzichang/Downloads/thu_PPT/thu_ppt_assets",
            )
            self.assertTrue(Path(result["output_pptx"]).exists())
            self.assertTrue(Path(result["output_js"]).exists())
            self.assertEqual(result["category"], "general")
            self.assertTrue((Path(tmpdir) / "visual_plan.json").exists())
            self.assertTrue((Path(tmpdir) / "qa_report.json").exists())
            self.assertFalse(result["ai_images_enabled"])
            plan = read_json(Path(tmpdir) / "slide_plan.json")
            self.assertEqual(plan["slides"][0]["slide_type"], "cover")
            self.assertEqual(plan["slides"][-1]["slide_type"], "thank_you")

    def test_end_to_end_technical(self):
        from run_pipeline import run_pipeline

        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_pipeline(
                input_path=str(ROOT / "examples" / "technical_system.md"),
                output_dir=tmpdir,
                assets_root="/Users/liuzichang/Downloads/thu_PPT/thu_ppt_assets",
            )
            self.assertTrue(Path(result["output_pptx"]).exists())
            self.assertTrue(Path(tmpdir, "deck_payload.json").exists())
            plan = read_json(Path(tmpdir) / "slide_plan.json")
            slide_types = [slide["slide_type"] for slide in plan["slides"]]
            self.assertTrue(any(slide_type in {"architecture_diagram", "training_pipeline", "execution_loop", "algorithm_mechanism"} for slide_type in slide_types))
            lint = read_json(Path(tmpdir) / "lint_report.json")
            self.assertEqual(lint["fatal_count"], 0)
            image_trace = read_json(Path(tmpdir) / "image_generation_trace.json")
            self.assertIn("requests", image_trace)
            self.assertEqual(image_trace["requests"], [])


if __name__ == "__main__":
    unittest.main()
