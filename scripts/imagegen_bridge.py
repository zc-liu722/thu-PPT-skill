#!/usr/bin/env python3
"""Selective image generation bridge for editorial support visuals."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any


IMAGEGEN_SCRIPT = Path("/Users/liuzichang/.codex/skills/imagegen/scripts/image_gen.py")


def run_image_generation(visual_plan: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    output_root = Path(output_dir) / "generated_images"
    output_root.mkdir(parents=True, exist_ok=True)
    requests = []
    for item in visual_plan.get("image_requests", []):
        request = dict(item)
        request["output_path"] = ""
        if not request.get("eligible"):
            request["status"] = "skipped"
            request["skip_reason"] = "OPENAI_API_KEY missing or imagegen CLI unavailable"
            requests.append(request)
            continue
        out_path = output_root / f"slide-{request['slide_index']}.png"
        command = [
            os.environ.get("PYTHON", "python3"),
            str(IMAGEGEN_SCRIPT),
            "generate",
            "--prompt",
            request["prompt"],
            "--out",
            str(out_path),
            "--use-case",
            "stylized-concept",
            "--style",
            "restrained editorial technical illustration",
            "--composition",
            "balanced academic composition with clean negative space",
            "--lighting",
            "soft editorial lighting",
            "--palette",
            "Tsinghua crimson, muted gold, ivory, graphite",
            "--constraints",
            "keep it academically restrained and semantically relevant",
            "--negative",
            "purple neon, tacky sci-fi, clutter, stock photo look",
            "--augment",
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        request["command"] = command
        request["status"] = "generated" if result.returncode == 0 and out_path.exists() else "failed"
        request["stdout"] = result.stdout[-2000:]
        request["stderr"] = result.stderr[-2000:]
        request["output_path"] = str(out_path) if out_path.exists() else ""
        requests.append(request)
    return {"requests": requests}
