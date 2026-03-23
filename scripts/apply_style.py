#!/usr/bin/env python3
"""Theme and font resolution for thu-ppt-generator."""

from __future__ import annotations

import platform
import subprocess
from functools import lru_cache
from typing import Any


BASE_STYLE = {
    "spacing": {
        "page_margin": 0.52,
        "content_gap": 0.24,
        "card_radius": 0.08,
    },
    "palette": {
        "primary": "7A0019",
        "accent": "B58A2A",
        "text": "1B1E23",
        "muted": "66707A",
        "surface": "F6F2ED",
        "surface_alt": "EDE3D6",
        "line": "D7C9B8",
        "soft_fill": "F3EEE7",
    },
}


CATEGORY_STYLE_OVERRIDES = {
    "general": {},
    "humanities": {
        "palette": {
            "primary": "6F2E2A",
            "accent": "A2752D",
            "surface": "F7F1E8",
            "surface_alt": "E9DCCB",
        }
    },
    "party_building": {
        "palette": {
            "primary": "9C1622",
            "accent": "C79A37",
            "surface": "FBF5F0",
            "surface_alt": "F3E1D3",
        }
    },
}


FONT_CHAINS = {
    "title_zh": ["Source Han Sans SC", "Noto Sans CJK SC", "PingFang SC", "Microsoft YaHei", "SimHei", "Arial Unicode MS"],
    "body_zh": ["Source Han Sans SC", "Noto Sans CJK SC", "PingFang SC", "Microsoft YaHei", "SimSun", "Arial Unicode MS"],
    "title_en": ["Aptos Display", "Calibri", "Arial", "Helvetica Neue"],
    "body_en": ["Aptos", "Calibri", "Arial", "Helvetica Neue"],
    "mono": ["Menlo", "Consolas", "Courier New", "DejaVu Sans Mono"],
}


@lru_cache(maxsize=1)
def installed_fonts() -> set[str]:
    names: set[str] = set()
    try:
        result = subprocess.run(
            ["fc-list", "--format", "%{family}\n"],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in (result.stdout or "").splitlines():
            for item in line.split(","):
                cleaned = item.strip()
                if cleaned:
                    names.add(cleaned)
    except FileNotFoundError:
        pass
    fallback_by_os = {
        "Darwin": {"PingFang SC", "Helvetica Neue", "Menlo"},
        "Windows": {"Microsoft YaHei", "Calibri", "Consolas"},
        "Linux": {"Noto Sans CJK SC", "DejaVu Sans", "DejaVu Sans Mono"},
    }
    names.update(fallback_by_os.get(platform.system(), set()))
    return names


def pick_font(candidates: list[str], fallback: str) -> str:
    available = installed_fonts()
    for name in candidates:
        if name in available:
            return name
    return fallback


def resolve_fonts() -> dict[str, Any]:
    return {
        "title_zh": pick_font(FONT_CHAINS["title_zh"], "Microsoft YaHei"),
        "body_zh": pick_font(FONT_CHAINS["body_zh"], "Microsoft YaHei"),
        "title_en": pick_font(FONT_CHAINS["title_en"], "Arial"),
        "body_en": pick_font(FONT_CHAINS["body_en"], "Arial"),
        "mono": pick_font(FONT_CHAINS["mono"], "Courier New"),
        "fallback_chain": FONT_CHAINS,
        "font_check_method": "fc-list" if installed_fonts() else "os-default-assumption",
    }


def resolve_theme(category: str, theme_profile: dict[str, Any]) -> dict[str, Any]:
    resolved = {
        "category": category,
        "palette": dict(BASE_STYLE["palette"]),
        "spacing": dict(BASE_STYLE["spacing"]),
        "fonts": resolve_fonts(),
    }
    resolved["palette"].update(CATEGORY_STYLE_OVERRIDES.get(category, {}).get("palette", {}))
    primary_colors = theme_profile.get("primary_colors", [])
    secondary_colors = theme_profile.get("secondary_colors", [])
    if primary_colors:
        resolved["palette"]["primary"] = primary_colors[0].lstrip("#")
    if len(primary_colors) > 1:
        resolved["palette"]["accent"] = primary_colors[1].lstrip("#")
    if secondary_colors:
        resolved["palette"]["muted"] = secondary_colors[0].lstrip("#")
    if len(secondary_colors) > 1:
        resolved["palette"]["line"] = secondary_colors[1].lstrip("#")
    return resolved
