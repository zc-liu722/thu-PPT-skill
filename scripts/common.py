#!/usr/bin/env python3
"""Shared helpers for the production-grade thu-ppt-generator pipeline."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ASSET_ROOT_DEFAULT = Path("/Users/liuzichang/Downloads/thu_PPT/thu_ppt_assets")
MANIFEST_DEFAULT = ASSET_ROOT_DEFAULT / "manifests" / "manifest.json"
LAYOUT_INDEX_DEFAULT = ASSET_ROOT_DEFAULT / "manifests" / "layout_index.json"
THEME_DEFAULT = ASSET_ROOT_DEFAULT / "manifests" / "theme_tokens.json"

CATEGORY_SET = {"general", "humanities", "party_building"}
LAYOUT_FAMILIES = {
    "cover",
    "agenda",
    "section_divider",
    "hero",
    "cards",
    "comparison",
    "timeline",
    "process",
    "architecture",
    "metrics",
    "mixed_media",
    "conclusion",
    "closing",
    "appendix",
}

TECH_KEYWORDS = {
    "api",
    "sdk",
    "service",
    "module",
    "pipeline",
    "workflow",
    "request",
    "response",
    "queue",
    "database",
    "cache",
    "deploy",
    "runtime",
    "architecture",
    "system",
    "code",
    "repo",
    "python",
    "javascript",
    "typescript",
    "function",
    "class",
    "model",
    "agent",
    "worker",
    "frontend",
    "backend",
}

STOPWORDS = {
    "the",
    "and",
    "with",
    "that",
    "this",
    "from",
    "into",
    "about",
    "我们",
    "进行",
    "内容",
    "工作",
    "项目",
    "研究",
    "一个",
    "以及",
    "通过",
    "为了",
    "可以",
}


@dataclass
class CodeBlock:
    language: str
    lines: list[str]


@dataclass
class SectionModel:
    title: str
    bullets: list[str] = field(default_factory=list)
    paragraphs: list[str] = field(default_factory=list)
    code_blocks: list[CodeBlock] = field(default_factory=list)
    hint: str = "content"
    source_order: int = 0

    def text_blob(self) -> str:
        code_text = " ".join(" ".join(block.lines) for block in self.code_blocks)
        return " ".join([self.title] + self.bullets + self.paragraphs + [code_text]).strip()


def build_parser(description: str) -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description=description)


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def load_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def normalize_whitespace(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def detect_text_format(text: str) -> str:
    stripped = text.strip()
    if re.search(r"^\s{0,3}#{1,6}\s+", stripped, flags=re.MULTILINE):
        return "markdown"
    if "```" in stripped:
        return "markdown"
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    outline_hits = sum(
        1
        for line in lines
        if re.match(r"^([-*+]|\d+[.)]|[一二三四五六七八九十]+[、.]|第[一二三四五六七八九十]+部分)", line)
    )
    if lines and outline_hits >= max(2, len(lines) // 4):
        return "outline"
    return "text"


def split_paragraphs(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"\n\s*\n", normalize_whitespace(text)) if item.strip()]


def strip_inline_markup(text: str) -> str:
    stripped = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    stripped = re.sub(r"\*(.*?)\*", r"\1", stripped)
    stripped = re.sub(r"`(.*?)`", r"\1", stripped)
    stripped = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", stripped)
    return stripped.strip()


def slugify(text: str) -> str:
    normalized = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", text.strip().lower())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "deck"


def sentences(text: str) -> list[str]:
    text = normalize_whitespace(text)
    if not text:
        return []
    parts = re.split(r"(?<=[。！？!?;；.])\s+|\n+", text)
    return [part.strip(" -") for part in parts if part.strip(" -")]


def count_cjk_chars(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def count_words(text: str) -> int:
    latin = re.findall(r"[A-Za-z0-9_./:-]+", text)
    cjk = count_cjk_chars(text)
    return len(latin) + math.ceil(cjk / 2)


def bullet_density(text: str) -> float:
    return count_words(text) + count_cjk_chars(text) / 10


def extract_keywords(text: str, top_n: int = 16) -> list[str]:
    words = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    counter = Counter(word for word in words if word not in STOPWORDS)
    return [word for word, _ in counter.most_common(top_n)]


def short_title(text: str, fallback: str, limit: int = 28) -> str:
    candidate = strip_inline_markup(text).strip("：: ")
    if not candidate:
        return fallback
    return candidate if len(candidate) <= limit else candidate[: limit - 1].rstrip() + "…"


def trim_sentence(text: str, max_words: int = 20) -> str:
    if count_words(text) <= max_words:
        return text.strip("，,;；。 ")
    parts = re.split(r"[，,;；。]", text)
    compact = ""
    for part in parts:
        piece = part.strip()
        if not piece:
            continue
        merged = f"{compact}，{piece}".strip("，")
        if compact and count_words(merged) > max_words:
            break
        compact = merged or piece
    compact = compact or text
    tokens = compact.split()
    if len(tokens) > max_words:
        compact = " ".join(tokens[:max_words])
    return compact.strip("，,;；。 ") + ("…" if compact != text else "")


def compress_points(items: list[str], max_items: int = 4, max_words: int = 16) -> list[str]:
    seen: set[str] = set()
    compact: list[str] = []
    for item in items:
        cleaned = trim_sentence(strip_inline_markup(item), max_words=max_words)
        key = re.sub(r"\W+", "", cleaned.lower())
        if not cleaned or key in seen:
            continue
        seen.add(key)
        compact.append(cleaned)
        if len(compact) >= max_items:
            break
    return compact


def ensure_category(value: str) -> str:
    return value if value in CATEGORY_SET else "general"


def derive_available_categories(manifest: dict[str, Any], theme_tokens: dict[str, Any]) -> list[str]:
    categories = set(manifest.get("categories", []))
    categories.update(theme_tokens.get("by_category", {}).keys())
    for asset in manifest.get("assets", []):
        category = asset.get("category")
        if category in CATEGORY_SET:
            categories.add(category)
    return sorted(cat for cat in categories if cat in CATEGORY_SET)


def load_asset_library(assets_root: str | Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    root = Path(assets_root)
    manifest = read_json(root / "manifests" / "manifest.json")
    layout_index = read_json(root / "manifests" / "layout_index.json")
    theme_tokens = read_json(root / "manifests" / "theme_tokens.json")
    return manifest, layout_index, theme_tokens


def get_deck_metadata(manifest: dict[str, Any], deck_id: str) -> dict[str, Any]:
    for asset in manifest.get("assets", []):
        if asset.get("asset_id") == deck_id:
            metadata_path = asset.get("metadata_path")
            if metadata_path and Path(metadata_path).exists():
                return read_json(metadata_path)
    return {}


def score_deck_for_layouts(deck_id: str, layouts: list[dict[str, Any]], preferred_types: list[str]) -> float:
    score = 0.0
    for layout in layouts:
        if layout.get("asset_id") != deck_id:
            continue
        family = layout.get("layout_type")
        confidence = float(layout.get("confidence", 0.4))
        if family in preferred_types:
            score += 2.5 * confidence
        elif family in {"cover", "content", "two_column", "section_divider", "agenda"}:
            score += 0.8 * confidence
    return score


def asset_keywords(asset: dict[str, Any]) -> list[str]:
    path = asset.get("output_path") or asset.get("template_path") or asset.get("source_path") or ""
    words = re.findall(r"[A-Za-z]+|[\u4e00-\u9fff]{2,}", Path(path).stem.lower())
    extras = [asset.get("role", ""), asset.get("category", ""), asset.get("asset_type", "")]
    return [word for word in words + extras if word]


def semantic_overlap_score(subject_terms: list[str], target_terms: list[str]) -> float:
    if not subject_terms or not target_terms:
        return 0.0
    subject = Counter(subject_terms)
    target = Counter(target_terms)
    overlap = sum(min(subject[key], target[key]) for key in subject if key in target)
    coverage = overlap / max(len(subject_terms), 1)
    return coverage


def detect_comparison(text: str) -> bool:
    return bool(re.search(r"(对比|比较|优劣|before|after|vs\.?|versus|trade[- ]?off)", text, re.IGNORECASE))


def detect_timeline(text: str) -> bool:
    return bool(
        re.search(
            r"(时间线|历程|里程碑|timeline|history|阶段一|阶段二|阶段三|\b20\d{2}\b|\d+月|\d+周)",
            text,
            re.IGNORECASE,
        )
    )


def detect_metrics(text: str) -> bool:
    return bool(re.search(r"(\d+%|\d+\.\d+%|提升|下降|增长|时延|耗时|准确率|ROI|KPI|指标|million|ms|秒)", text, re.IGNORECASE))


def detect_technical(text: str) -> bool:
    lowered = text.lower()
    if "```" in text or "->" in text or "=>" in text:
        return True
    return any(keyword in lowered for keyword in TECH_KEYWORDS)


def classify_body_pattern(title: str, bullets: list[str], paragraphs: list[str], code_blocks: list[dict[str, Any]] | None = None) -> str:
    blob = " ".join([title] + bullets + paragraphs + [" ".join(block.get("lines", [])) for block in (code_blocks or [])])
    if detect_comparison(blob):
        return "comparison"
    if detect_timeline(blob):
        return "timeline"
    if detect_metrics(blob):
        return "metrics"
    if detect_technical(blob):
        if re.search(r"(架构|system|architecture|module|service|组件|依赖)", blob, re.IGNORECASE):
            return "architecture"
        if re.search(r"(流程|pipeline|workflow|request|response|处理|阶段)", blob, re.IGNORECASE):
            return "process"
    return "content"


def estimate_slide_budget(total_words: int, section_count: int, technical_ratio: float = 0.0) -> int:
    base = 5 + round(total_words / 180)
    base += 1 if section_count >= 4 else 0
    base += 1 if technical_ratio >= 0.35 else 0
    return min(12, max(6, base))


def split_bullets_for_budget(bullets: list[str], max_items: int = 4, max_density: float = 34.0) -> list[list[str]]:
    if not bullets:
        return [[]]
    groups: list[list[str]] = []
    current: list[str] = []
    density = 0.0
    for bullet in bullets:
        weight = bullet_density(bullet)
        if current and (len(current) >= max_items or density + weight > max_density):
            groups.append(current)
            current = []
            density = 0.0
        current.append(bullet)
        density += weight
    if current:
        groups.append(current)
    return groups


def score_sentence(sentence: str, keywords: list[str]) -> float:
    lowered = sentence.lower()
    keyword_hits = sum(1 for keyword in keywords if keyword and keyword.lower() in lowered)
    numeric_bonus = 1.5 if detect_metrics(sentence) else 0.0
    technical_bonus = 1.2 if detect_technical(sentence) else 0.0
    length_penalty = max(count_words(sentence) - 22, 0) * 0.03
    return keyword_hits + numeric_bonus + technical_bonus - length_penalty


def top_sentences(text: str, keywords: list[str], limit: int = 4) -> list[str]:
    ranked = sorted(sentences(text), key=lambda item: score_sentence(item, keywords), reverse=True)
    return compress_points(ranked, max_items=limit)


def pick_first(items: list[dict[str, Any]], role: str, categories: list[str]) -> dict[str, Any] | None:
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        if item.get("asset_type") != "media" or item.get("role") != role:
            continue
        by_category[item.get("category", "")].append(item)
    for category in categories:
        candidates = [asset for asset in by_category.get(category, []) if Path(asset.get("output_path", "")).exists()]
        if candidates:
            return sorted(
                candidates,
                key=lambda asset: (-float(asset.get("role_confidence", 0.0)), -float(asset.get("confidence", 0.0))),
            )[0]
    return None


def markdown_report_from_lint(lint_report: dict[str, Any]) -> str:
    lines = [
        "# PPT Quality Report",
        "",
        f"- deck score: {lint_report.get('deck_score', 0)} / 100",
        f"- fatal issues: {lint_report.get('fatal_count', 0)}",
        f"- warning issues: {lint_report.get('warning_count', 0)}",
        f"- improvements applied: {len(lint_report.get('applied_fixes', []))}",
        "",
    ]
    if lint_report.get("findings"):
        lines.append("## Findings")
        lines.append("")
        for finding in lint_report["findings"]:
            lines.append(
                f"- slide {finding.get('slide_index')}: [{finding.get('severity')}] {finding.get('code')} - {finding.get('message')}"
            )
        lines.append("")
    if lint_report.get("applied_fixes"):
        lines.append("## Applied Improvements")
        lines.append("")
        for fix in lint_report["applied_fixes"]:
            lines.append(f"- {fix}")
        lines.append("")
    if lint_report.get("deck_summary"):
        lines.append("## Deck Summary")
        lines.append("")
        lines.append(lint_report["deck_summary"])
        lines.append("")
    return "\n".join(lines)
