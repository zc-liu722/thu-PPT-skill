#!/usr/bin/env python3
"""Built-deck QA using the mature slides skill workflow."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from common import write_json


SLIDES_SKILL_ROOT = Path("/Users/liuzichang/.codex/skills/slides")
RENDER_SCRIPT = SLIDES_SKILL_ROOT / "scripts" / "render_slides.py"
MONTAGE_SCRIPT = SLIDES_SKILL_ROOT / "scripts" / "create_montage.py"
OVERFLOW_SCRIPT = SLIDES_SKILL_ROOT / "scripts" / "slides_test.py"
FONT_SCRIPT = SLIDES_SKILL_ROOT / "scripts" / "detect_font.py"


def _run(args: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _weak_slide_finding(plan: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    robust_visual_types = {"agenda", "data_representation", "architecture_diagram", "algorithm_mechanism", "training_pipeline", "execution_loop", "evaluation_results", "cover", "thank_you"}
    for index, slide in enumerate(plan.get("slides", []), start=1):
        body = [item for item in slide.get("body", []) if item.strip()]
        if slide.get("slide_type") not in robust_visual_types and len(body) <= 1:
            findings.append({"slide_index": index, "severity": "warning", "code": "weak_slide", "message": "Slide likely lacks enough support to feel complete."})
    return findings


def qa_deck(pptx_path: str, output_dir: str, plan: dict[str, Any], visual_plan: dict[str, Any]) -> dict[str, Any]:
    out_dir = Path(output_dir)
    render_dir = out_dir / "rendered_slides"
    render_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"checks": {}, "findings": [], "artifacts": {}}

    if RENDER_SCRIPT.exists():
        code, stdout, stderr = _run([sys.executable, str(RENDER_SCRIPT), pptx_path, "--output_dir", str(render_dir)])
        report["checks"]["render"] = {"ok": code == 0, "stdout": stdout, "stderr": stderr}
        report["artifacts"]["render_dir"] = str(render_dir)
        if code == 0 and MONTAGE_SCRIPT.exists():
            montage_path = out_dir / "rendered_montage.png"
            m_code, m_stdout, m_stderr = _run([sys.executable, str(MONTAGE_SCRIPT), "--input_dir", str(render_dir), "--output_file", str(montage_path)])
            report["checks"]["montage"] = {"ok": m_code == 0, "stdout": m_stdout, "stderr": m_stderr}
            if montage_path.exists():
                report["artifacts"]["montage"] = str(montage_path)

    if OVERFLOW_SCRIPT.exists():
        code, stdout, stderr = _run([sys.executable, str(OVERFLOW_SCRIPT), pptx_path])
        overflow_ok = code == 0 and "No overflow detected" in stdout
        report["checks"]["overflow"] = {"ok": overflow_ok, "stdout": stdout, "stderr": stderr}
        if not overflow_ok:
            report["findings"].append({"slide_index": 0, "severity": "warning", "code": "overflow", "message": stdout or stderr or "Overflow checker reported an issue."})

    if FONT_SCRIPT.exists() and shutil.which("soffice"):
        font_json = out_dir / "font_report.json"
        code, stdout, stderr = _run([sys.executable, str(FONT_SCRIPT), pptx_path, "--json"])
        payload = {}
        if stdout:
            try:
                payload = json.loads(stdout)
                write_json(font_json, payload)
                report["artifacts"]["font_report"] = str(font_json)
            except json.JSONDecodeError:
                payload = {"raw_stdout": stdout}
        missing = payload.get("font_missing_overall", []) if isinstance(payload, dict) else []
        substituted = payload.get("font_substituted_overall", []) if isinstance(payload, dict) else []
        report["checks"]["fonts"] = {"ok": code == 0 and not missing, "stdout": stdout[:4000], "stderr": stderr[:2000]}
        if missing:
            report["findings"].append({"slide_index": 0, "severity": "warning", "code": "missing_fonts", "message": "Renderer reports missing fonts: " + ", ".join(missing[:5])})
        if substituted:
            report["findings"].append({"slide_index": 0, "severity": "warning", "code": "font_substitution", "message": "Renderer substituted fonts: " + ", ".join(substituted[:5])})

    report["findings"].extend(_weak_slide_finding(plan))
    repeated = 0
    previous = None
    for slide in plan.get("slides", []):
        family = slide.get("layout_family")
        repeated = repeated + 1 if family == previous else 1
        previous = family
        if repeated >= 3:
            report["findings"].append({"slide_index": 0, "severity": "warning", "code": "repeated_layout", "message": "Rendered deck still repeats one layout family too often."})
            break

    missing_images = []
    for item in visual_plan.get("slides", []):
        request = item.get("image_request")
        if request and request.get("requested") and request.get("status") != "generated":
            missing_images.append(item["slide_index"])
    if missing_images:
        report["findings"].append({"slide_index": missing_images[0], "severity": "warning", "code": "image_requests_pending", "message": "Some optional imagegen requests were left as traces only, not rendered assets."})

    score = 100
    score -= sum(10 for item in report["findings"] if item["severity"] == "fatal")
    for item in report["findings"]:
        if item["severity"] != "warning":
            continue
        if item["code"] in {"overflow", "missing_fonts", "font_substitution"} and any(
            token in item["message"] for token in ["ModuleNotFoundError", "No such file or directory", "Failed to produce PDF"]
        ):
            score -= 1
        else:
            score -= 4
    report["score"] = max(0, score)
    report["status"] = "pass" if score >= 80 and not any(item["severity"] == "fatal" for item in report["findings"]) else "needs_attention"
    return report
