#!/usr/bin/env python3
"""Parse markdown, text, outline, or source files into a richer deck-source model."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from common import (
    CodeBlock,
    SectionModel,
    build_parser,
    detect_text_format,
    extract_keywords,
    normalize_whitespace,
    sentences,
    short_title,
    split_paragraphs,
    strip_inline_markup,
    write_json,
)


def _new_section(title: str, order: int) -> SectionModel:
    return SectionModel(title=title or "核心内容", source_order=order)


def _flush_section(sections: list[SectionModel], current: SectionModel | None) -> SectionModel | None:
    if current and (current.title or current.bullets or current.paragraphs or current.code_blocks):
        sections.append(current)
    return None


def _parse_markdown(text: str) -> dict[str, Any]:
    title = ""
    subtitle = ""
    sections: list[SectionModel] = []
    current: SectionModel | None = None
    in_code = False
    code_language = ""
    code_lines: list[str] = []
    order = 0

    for raw_line in normalize_whitespace(text).splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_code and current:
                current.code_blocks.append(CodeBlock(language=code_language, lines=code_lines.copy()))
                code_lines.clear()
            in_code = not in_code
            code_language = stripped.strip("`").strip() if in_code else ""
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not stripped:
            continue
        if stripped.startswith("# "):
            title = strip_inline_markup(stripped[2:])
            continue
        if stripped.startswith("## "):
            current = _flush_section(sections, current)
            order += 1
            current = _new_section(strip_inline_markup(stripped[3:]), order)
            continue
        if stripped.startswith("### "):
            current = _flush_section(sections, current)
            order += 1
            current = _new_section(strip_inline_markup(stripped[4:]), order)
            continue
        if re.match(r"^[-*+]\s+", stripped):
            if not current:
                order += 1
                current = _new_section("核心内容", order)
            current.bullets.append(strip_inline_markup(re.sub(r"^[-*+]\s+", "", stripped)))
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            if not current:
                order += 1
                current = _new_section("数据整理", order)
            current.paragraphs.append(strip_inline_markup(stripped.replace("|", " ")))
            continue
        content = strip_inline_markup(stripped)
        if content.startswith(("汇报人", "主讲人", "Speaker")) and not subtitle:
            subtitle = content
        if not current:
            order += 1
            current = _new_section("概述", order)
        current.paragraphs.append(content)

    if in_code and current and code_lines:
        current.code_blocks.append(CodeBlock(language=code_language, lines=code_lines.copy()))
    _flush_section(sections, current)
    return {
        "title": title or "清华主题汇报",
        "subtitle": subtitle,
        "sections": [section_to_dict(section) for section in sections],
    }


def _parse_outline(text: str) -> dict[str, Any]:
    title = ""
    subtitle = ""
    sections: list[SectionModel] = []
    current: SectionModel | None = None
    order = 0
    lines = [line.strip() for line in normalize_whitespace(text).splitlines() if line.strip()]
    for idx, line in enumerate(lines):
        if idx == 0 and not re.match(r"^([-*+]|\d+[.)]|[一二三四五六七八九十]+[、.])", line):
            title = strip_inline_markup(line)
            continue
        if ("汇报人" in line or "主讲人" in line or "日期" in line) and not subtitle:
            subtitle = strip_inline_markup(line)
            continue
        if re.match(r"^(第[一二三四五六七八九十]+部分|[一二三四五六七八九十]+[、.]|\d+[、.)])", line):
            current = _flush_section(sections, current)
            order += 1
            current = _new_section(strip_inline_markup(line), order)
            continue
        if re.match(r"^[-*+]\s+|^\d+[.)]\s+", line):
            if not current:
                order += 1
                current = _new_section("核心内容", order)
            current.bullets.append(strip_inline_markup(re.sub(r"^([-*+]|\d+[.)])\s+", "", line)))
            continue
        if not current:
            order += 1
            current = _new_section("概述", order)
        current.paragraphs.append(strip_inline_markup(line))
    _flush_section(sections, current)
    return {
        "title": title or "清华主题汇报",
        "subtitle": subtitle,
        "sections": [section_to_dict(section) for section in sections],
    }


def _parse_plain_text(text: str) -> dict[str, Any]:
    title = "清华主题汇报"
    subtitle = ""
    sections: list[SectionModel] = []
    paragraphs = split_paragraphs(text)
    order = 0

    if paragraphs:
        first_lines = [line.strip() for line in paragraphs[0].splitlines() if line.strip()]
        if first_lines and len(first_lines[0]) <= 40:
            title = strip_inline_markup(first_lines[0])
            if len(first_lines) > 1 and ("汇报人" in first_lines[1] or "日期" in first_lines[1]):
                subtitle = strip_inline_markup(first_lines[1])
            paragraphs[0] = "\n".join(first_lines[1 if not subtitle else 2 :]).strip()

    current = _new_section("概述", 1)
    for para in paragraphs:
        if not para:
            continue
        lines = [strip_inline_markup(line) for line in para.splitlines() if line.strip()]
        header = lines[0] if lines else ""
        if re.match(r"^(第[一二三四五六七八九十]+部分|[一二三四五六七八九十]+[、.]|\d+[、.)])", header):
            _flush_section(sections, current)
            order += 1
            current = _new_section(header, order)
            current.paragraphs.extend(lines[1:])
            continue
        bullet_lines = [line for line in lines if re.match(r"^[-*+]\s+", line)]
        if bullet_lines:
            _flush_section(sections, current)
            order += 1
            title_candidate = header if not re.match(r"^[-*+]\s+", header) else f"主题 {order}"
            current = _new_section(title_candidate, order)
            current.bullets.extend(strip_inline_markup(re.sub(r"^[-*+]\s+", "", line)) for line in bullet_lines)
            current.paragraphs.extend(line for line in lines if line not in bullet_lines and line != header)
            continue
        current.paragraphs.extend(sentences(" ".join(lines)))
    _flush_section(sections, current)
    return {
        "title": title,
        "subtitle": subtitle,
        "sections": [section_to_dict(section) for section in sections],
    }


def section_to_dict(section: SectionModel) -> dict[str, Any]:
    return {
        "title": section.title,
        "bullets": section.bullets,
        "paragraphs": section.paragraphs,
        "code_blocks": [{"language": block.language, "lines": block.lines} for block in section.code_blocks],
        "hint": section.hint,
        "source_order": section.source_order,
    }


SOURCE_SUFFIX_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "jsx",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".go": "go",
    ".rs": "rust",
    ".sh": "bash",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
}


def _parse_source_file(text: str, path: Path) -> dict[str, Any]:
    language = SOURCE_SUFFIX_LANGUAGE.get(path.suffix.lower(), path.suffix.lstrip(".") or "text")
    title = path.stem.replace("_", " ").replace("-", " ").strip() or "技术源码解读"
    section = SectionModel(title=f"{path.name} 角色与逻辑", source_order=1)
    code_lines = text.splitlines()
    preview = [line.strip() for line in code_lines[:14] if line.strip()][:6]
    if preview:
        section.paragraphs.append("源码预览：" + " / ".join(preview[:3]))
    section.code_blocks.append(CodeBlock(language=language, lines=code_lines))
    return {
        "title": short_title(title, "技术源码解读", 36),
        "subtitle": path.name,
        "sections": [section_to_dict(section)],
        "source_kind": "code_file",
        "primary_language": language,
    }


def parse_input_text(text: str, source_format: str = "auto", source_path: str | None = None) -> dict[str, Any]:
    path = Path(source_path) if source_path else None
    if path and path.suffix.lower() in SOURCE_SUFFIX_LANGUAGE:
        payload = _parse_source_file(text, path)
        detected_format = "code_file"
    else:
        detected_format = detect_text_format(text) if source_format == "auto" else source_format
        if detected_format == "markdown":
            payload = _parse_markdown(text)
        elif detected_format == "outline":
            payload = _parse_outline(text)
        else:
            payload = _parse_plain_text(text)

    all_text = normalize_whitespace(text)
    speaker = ""
    date_text = ""
    for line in all_text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("汇报人", "主讲人", "Speaker")):
            speaker = stripped
        if "日期" in stripped or re.search(r"\d{4}[年/-]\d{1,2}([月/-]\d{1,2})?", stripped):
            date_text = stripped
    payload.update(
        {
            "source_text": all_text,
            "speaker": speaker,
            "date": date_text,
            "keywords": extract_keywords(all_text),
            "detected_structure": detected_format,
            "code_block_count": sum(len(section.get("code_blocks", [])) for section in payload["sections"]),
            "section_count": len(payload["sections"]),
            "source_name": path.name if path else "",
            "source_path": str(path) if path else "",
            "primary_language": payload.get("primary_language", ""),
            "source_kind": payload.get("source_kind", "document"),
        }
    )
    return payload


def parse_input_file(path: str | Path, source_format: str = "auto") -> dict[str, Any]:
    file_path = Path(path)
    return parse_input_text(file_path.read_text(encoding="utf-8"), source_format=source_format, source_path=str(file_path))


def main() -> None:
    parser = build_parser("Parse input content into a rich deck-source JSON model.")
    parser.add_argument("--input", required=True, help="Path to markdown, text, or outline input.")
    parser.add_argument("--format", choices=["auto", "markdown", "text", "outline"], default="auto")
    parser.add_argument("--output-json", required=True, help="Where to write the parsed JSON.")
    args = parser.parse_args()

    payload = parse_input_file(args.input, args.format)
    write_json(args.output_json, payload)


if __name__ == "__main__":
    main()
