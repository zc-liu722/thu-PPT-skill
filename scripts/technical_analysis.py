#!/usr/bin/env python3
"""Technical and research-aware content analysis for thu-ppt-generator."""

from __future__ import annotations

import ast
import re
from collections import Counter
from typing import Any

from common import count_words, extract_keywords, short_title, trim_sentence


PIPELINE_TERMS = {
    "training": ["train", "training", "optimizer", "loss", "epoch", "fit", "反向传播", "训练"],
    "evaluation": ["eval", "evaluate", "metric", "accuracy", "f1", "auc", "评估", "实验结果"],
    "inference": ["infer", "predict", "generate", "serve", "online", "推理", "预测"],
    "simulation": ["simulate", "loop", "step", "rollout", "episode", "仿真", "调度循环"],
    "data": ["dataset", "dataloader", "input", "feature", "token", "embedding", "数据", "样本"],
}

MEANINGLESS_NODE_LABELS = {
    "data",
    "code",
    "module",
    "system",
    "function",
    "class",
    "step",
    "node",
    "流程",
    "模块",
    "系统",
    "阶段",
}


def _safe_parse_python(source: str) -> ast.AST | None:
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def _node_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _node_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return _node_name(node.func)
    return ""


def analyze_python_code(source: str) -> dict[str, Any]:
    tree = _safe_parse_python(source)
    if tree is None:
        return {
            "language": "python",
            "parse_ok": False,
            "summary": trim_sentence(source[:180].replace("\n", " "), 22),
            "functions": [],
            "classes": [],
            "imports": [],
            "config_keys": [],
            "pipeline_stages": [],
            "artifacts": [],
            "relationships": [],
        }

    functions: list[dict[str, Any]] = []
    classes: list[dict[str, Any]] = []
    imports: list[str] = []
    assignments: list[str] = []
    calls: Counter[str] = Counter()
    pipeline_hits: Counter[str] = Counter()
    artifacts: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body_calls = sorted({_node_name(inner.func) for inner in ast.walk(node) if isinstance(inner, ast.Call) and _node_name(inner.func)})
            functions.append(
                {
                    "name": node.name,
                    "args": [arg.arg for arg in node.args.args],
                    "decorators": [_node_name(dec) for dec in node.decorator_list if _node_name(dec)],
                    "calls": body_calls[:8],
                    "doc": trim_sentence(ast.get_docstring(node) or "", 18),
                    "line": getattr(node, "lineno", 0),
                }
            )
        elif isinstance(node, ast.ClassDef):
            methods = [inner.name for inner in node.body if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef))]
            classes.append(
                {
                    "name": node.name,
                    "bases": [_node_name(base) for base in node.bases if _node_name(base)],
                    "methods": methods[:8],
                    "doc": trim_sentence(ast.get_docstring(node) or "", 18),
                    "line": getattr(node, "lineno", 0),
                }
            )
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments.append(target.id)
                    if target.id.lower().endswith(("path", "file", "dir", "output", "artifact")):
                        artifacts.add(target.id)
        elif isinstance(node, ast.Call):
            name = _node_name(node.func)
            if name:
                calls[name] += 1
                lowered = name.lower()
                for stage, tokens in PIPELINE_TERMS.items():
                    if any(token in lowered for token in tokens):
                        pipeline_hits[stage] += 1
                if any(token in lowered for token in ("save", "write", "dump", "export", "plot", "render")):
                    artifacts.add(name.split(".")[-1])

    relationships = []
    for item in functions[:8]:
        for callee in item["calls"][:4]:
            relationships.append({"source": item["name"], "target": callee.split(".")[-1], "type": "calls"})

    summary_bits = []
    if classes:
        summary_bits.append(f"{len(classes)} 个核心类")
    if functions:
        summary_bits.append(f"{len(functions)} 个主要函数")
    if pipeline_hits:
        summary_bits.append("包含 " + "、".join(stage for stage, _ in pipeline_hits.most_common(3)) + " 阶段")
    summary = "；".join(summary_bits) if summary_bits else "以脚本流程为主"

    return {
        "language": "python",
        "parse_ok": True,
        "summary": summary,
        "functions": functions[:12],
        "classes": classes[:8],
        "imports": sorted(dict.fromkeys(imports))[:16],
        "config_keys": sorted(dict.fromkeys(name for name in assignments if name.isupper() or "config" in name.lower()))[:12],
        "pipeline_stages": [stage for stage, _ in pipeline_hits.most_common()],
        "artifacts": sorted(artifacts)[:12],
        "relationships": relationships[:20],
    }


def analyze_code_block(block: dict[str, Any]) -> dict[str, Any]:
    source = "\n".join(block.get("lines", []))
    language = (block.get("language") or "").lower()
    if language in {"python", "py"}:
        return analyze_python_code(source)
    tokens = extract_keywords(source, top_n=12)
    return {
        "language": language or "text",
        "parse_ok": False,
        "summary": trim_sentence(source[:200].replace("\n", " "), 18),
        "functions": [],
        "classes": [],
        "imports": tokens[:6],
        "config_keys": [],
        "pipeline_stages": [stage for stage, terms in PIPELINE_TERMS.items() if any(term in source.lower() for term in terms)],
        "artifacts": [],
        "relationships": [],
    }


def _clean_point(text: str, limit: int = 22) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip(" -:：")
    return trim_sentence(cleaned, limit) if cleaned else ""


def _extract_research_signals(text: str) -> dict[str, list[str]]:
    sections = {
        "problem": [],
        "method": [],
        "results": [],
        "risks": [],
        "next_steps": [],
    }
    for sentence in re.split(r"(?<=[。！？!?;；.])\s+|\n+", text):
        item = sentence.strip()
        lowered = item.lower()
        if not item:
            continue
        if any(token in lowered for token in ["problem", "challenge", "背景", "动机", "问题"]):
            sections["problem"].append(_clean_point(item))
        if any(token in lowered for token in ["method", "approach", "algorithm", "方法", "机制", "设计"]):
            sections["method"].append(_clean_point(item))
        if any(token in lowered for token in ["result", "metric", "实验", "结果", "性能", "%"]):
            sections["results"].append(_clean_point(item))
        if any(token in lowered for token in ["risk", "limitation", "限制", "风险", "不足"]):
            sections["risks"].append(_clean_point(item))
        if any(token in lowered for token in ["next", "future", "下一步", "后续", "计划"]):
            sections["next_steps"].append(_clean_point(item))
    return {key: [item for item in values if item][:4] for key, values in sections.items()}


def _infer_pipeline_steps(sections: list[dict[str, Any]], code_analysis: list[dict[str, Any]]) -> list[str]:
    steps: Counter[str] = Counter()
    for section in sections:
        joined = " ".join(section.get("bullets", []) + section.get("paragraphs", []))
        lowered = joined.lower()
        for stage, tokens in PIPELINE_TERMS.items():
            if any(token in lowered for token in tokens):
                steps[stage] += 1
    for item in code_analysis:
        for stage in item.get("pipeline_stages", []):
            steps[stage] += 2
    ordered = [stage for stage, _ in steps.most_common()]
    if {"data", "training", "evaluation"} <= set(ordered):
        return ["data", "training", "evaluation"] + [stage for stage in ordered if stage not in {"data", "training", "evaluation"}]
    return ordered[:6]


def _file_role(parsed_input: dict[str, Any], code_analysis: list[dict[str, Any]]) -> dict[str, Any]:
    title = parsed_input.get("title", "")
    filename = parsed_input.get("source_name", "")
    roles = []
    lowered = f"{title} {filename}".lower()
    if any(token in lowered for token in ["train", "trainer", "训练"]):
        roles.append("training entrypoint")
    if any(token in lowered for token in ["infer", "predict", "serve", "推理"]):
        roles.append("inference or serving logic")
    if any(token in lowered for token in ["eval", "metric", "评估"]):
        roles.append("evaluation harness")
    if any(item.get("classes") for item in code_analysis):
        roles.append("class-oriented module")
    if any(item.get("functions") for item in code_analysis):
        roles.append("function-driven utility flow")
    return {
        "filename": filename,
        "title": title,
        "roles": roles[:4] or ["research or technical content source"],
    }


def _derive_data_flow(parsed_input: dict[str, Any], code_analysis: list[dict[str, Any]]) -> list[str]:
    candidates: list[str] = []
    for section in parsed_input.get("sections", []):
        lines = section.get("bullets", []) + section.get("paragraphs", [])
        for line in lines:
            if any(token in line.lower() for token in ["input", "output", "dataset", "feature", "token", "embedding", "数据", "结果"]):
                candidates.append(_clean_point(line, 14))
    for item in code_analysis:
        for stage in item.get("pipeline_stages", []):
            if stage == "data":
                candidates.append("输入数据经过加载与表征整理")
            elif stage == "training":
                candidates.append("训练阶段计算损失并更新参数")
            elif stage == "evaluation":
                candidates.append("评估阶段输出指标与可视化结果")
            elif stage == "inference":
                candidates.append("推理阶段生成预测或服务响应")
    deduped = []
    seen = set()
    for item in candidates:
        key = re.sub(r"\W+", "", item.lower())
        if item and key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped[:6]


def _extract_metrics(text: str) -> list[dict[str, str]]:
    metrics = []
    for label, value in re.findall(r"([A-Za-z\u4e00-\u9fff][A-Za-z0-9_\u4e00-\u9fff /-]{1,20})[^0-9]{0,8}(\d+(?:\.\d+)?%|\d+(?:\.\d+)?(?:ms|s|秒|轮|项|倍|GB|MB|k|K|M)?)", text):
        metrics.append({"label": short_title(label.strip(), "指标", 18), "value": value.strip()})
    deduped = []
    seen = set()
    for item in metrics:
        key = (item["label"], item["value"])
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped[:6]


def _meaningful_nodes(values: list[str]) -> list[str]:
    nodes = []
    seen = set()
    for value in values:
        cleaned = _clean_point(value, 8)
        key = re.sub(r"\W+", "", cleaned.lower())
        if not cleaned or key in seen or key in MEANINGLESS_NODE_LABELS or count_words(cleaned) > 8:
            continue
        seen.add(key)
        nodes.append(cleaned)
    return nodes[:8]


def analyze_technical_content(parsed_input: dict[str, Any]) -> dict[str, Any]:
    sections = parsed_input.get("sections", [])
    source_text = parsed_input.get("source_text", "")
    code_analysis = []
    for section in sections:
        for block in section.get("code_blocks", []):
            code_analysis.append(analyze_code_block(block))

    research = _extract_research_signals(source_text)
    pipeline_steps = _infer_pipeline_steps(sections, code_analysis)
    data_flow = _derive_data_flow(parsed_input, code_analysis)
    metrics = _extract_metrics(source_text)

    entities = []
    for item in code_analysis:
        entities.extend([fn["name"] for fn in item.get("functions", [])[:6]])
        entities.extend([cls["name"] for cls in item.get("classes", [])[:4]])
    entities = _meaningful_nodes(entities)

    relationship_nodes = _meaningful_nodes(
        [edge["source"] for item in code_analysis for edge in item.get("relationships", [])]
        + [edge["target"] for item in code_analysis for edge in item.get("relationships", [])]
        + data_flow
    )

    technicality = 0.0
    if sections:
        technicality += min(0.35, len(code_analysis) * 0.12)
        technicality += min(0.25, len(entities) * 0.03)
        technicality += min(0.2, len(pipeline_steps) * 0.04)
        technicality += 0.15 if metrics else 0.0
        technicality += 0.05 if research["results"] else 0.0

    return {
        "source_role": _file_role(parsed_input, code_analysis),
        "research_signals": research,
        "code_analysis": code_analysis,
        "major_entities": entities,
        "relationship_nodes": relationship_nodes,
        "pipeline_steps": pipeline_steps,
        "data_flow": data_flow,
        "metrics": metrics,
        "technicality": round(min(1.0, technicality), 2),
    }
