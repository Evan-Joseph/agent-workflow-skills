#!/usr/bin/env python3
"""Scan canonical Skill folders and report inventory/health signals."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

import yaml


DEFAULT_ROOTS = [
    Path.home() / ".agents" / "skills",
]
DEFAULT_MAGPIE_LIBRARY = Path.home() / ".config" / "magpie" / "library.json"
IGNORED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    "node_modules",
    "skills-archive",
    "vendor",
}

STANDARD_FRONTMATTER_KEYS = {
    "name",
    "description",
    "allowed-tools",
    "license",
    "metadata",
}


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    try:
        fields = yaml.safe_load(text[4:end])
    except yaml.YAMLError:
        return {}
    return fields if isinstance(fields, dict) else {}


def local_refs(skill_dir: Path, text: str) -> list[str]:
    pattern = re.compile(r"(?<![A-Za-z0-9_./-])((?:references|scripts|assets)/[^\s`'\"),;:]+)")
    refs: list[str] = []
    for match in pattern.finditer(text):
        ref = match.group(1)
        if "](" in ref:
            ref = ref.split("](", 1)[0]
        ref = ref.rstrip("]`'\"),.;:")
        if "<" in ref or ">" in ref:
            continue
        if ref not in refs:
            refs.append(ref)
    return refs


def classify(name: str, desc: str) -> str:
    hay = f"{name} {desc}".lower()
    rules = [
        ("browser-automation", ["browser-routing", "playwright", "camoufox"]),
        ("social-platform", ["wechat", "napcat", "xiaohongshu", "linuxdo", "chat-history", "agent-reach", "微信"]),
        ("security-ctf", ["artex", "ctf", "security", "渗透", "漏洞"]),
        ("research", ["academic", "paper", "literature", "anysearch", "developer-resource", "论文", "文献", "调研"]),
        ("devops-runtime", ["cloudflare", "workers", "wrangler", "durable", "harness-governance", "mobile-device", "local-machine"]),
        ("office-files", ["pdf", "docx", "ppt", "word", "document-crafting", "document-parsing", "ip-materials"]),
        ("frontend-design", ["frontend", "ui", "ux", "mobbin", "awwwards", "web", "design", "前端", "设计"]),
        ("media-data", ["ffmpeg", "image", "video", "quarkpan", "音视频"]),
        ("writing", ["writing", "shuorenhua", "engineering-quality", "改写"]),
    ]
    for category, needles in rules:
        if any(n in hay for n in needles):
            return category
    return "other"


def load_openai_yaml(skill_dir: Path) -> dict:
    path = skill_dir / "agents" / "openai.yaml"
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return {"_error": "invalid YAML"}
    return data if isinstance(data, dict) else {}


def load_magpie_library_status(lib_path: Path) -> dict[str, list[str]]:
    if not lib_path.exists():
        return {}
    try:
        data = json.loads(lib_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    result: dict[str, list[str]] = {}
    for entry in data.get("skills", []):
        name = str(entry.get("name", ""))
        if name:
            result[name] = [str(a) for a in (entry.get("agents") or [])]
    return result


def openai_interface(openai_yaml: dict) -> dict:
    interface = openai_yaml.get("interface") if isinstance(openai_yaml, dict) else {}
    return interface if isinstance(interface, dict) else {}


def scan_skill(skill_dir: Path) -> dict:
    skill_file = skill_dir / "SKILL.md"
    text = skill_file.read_text(encoding="utf-8", errors="replace")
    fm = parse_frontmatter(text)
    name = str(fm.get("name", "") or "")
    desc = str(fm.get("description", "") or "")
    meta = fm.get("metadata") if isinstance(fm.get("metadata"), dict) else {}
    openai_yaml = load_openai_yaml(skill_dir)
    interface = openai_interface(openai_yaml)
    refs = local_refs(skill_dir, text)
    missing_refs = []
    for ref in refs:
        if any(ch in ref for ch in "*?[]"):
            if not list(skill_dir.glob(ref)):
                missing_refs.append(ref)
        elif not (skill_dir / ref).exists():
            missing_refs.append(ref)
    scripts = list((skill_dir / "scripts").glob("*")) if (skill_dir / "scripts").is_dir() else []
    references = list((skill_dir / "references").glob("*")) if (skill_dir / "references").is_dir() else []
    assets = list((skill_dir / "assets").glob("*")) if (skill_dir / "assets").is_dir() else []
    warnings: list[str] = []
    if not name:
        warnings.append("missing frontmatter name")
    if not desc or desc.startswith("[TODO"):
        warnings.append("missing description")
    if name and name != skill_dir.name:
        warnings.append(f"name/folder mismatch: {name} != {skill_dir.name}")
    if missing_refs:
        warnings.append("missing local refs: " + ", ".join(missing_refs[:5]))
    if "[TODO" in text or "TODO:" in text:
        warnings.append("contains template TODO")
    nonstandard_keys = sorted(set(fm) - STANDARD_FRONTMATTER_KEYS)
    if nonstandard_keys:
        warnings.append("nonstandard frontmatter keys: " + ", ".join(nonstandard_keys))
    return {
        "folder": skill_dir.name,
        "name": name,
        "description": desc,
        "short_description": str(meta.get("short-description") or interface.get("short_description") or ""),
        "frontmatter_keys": sorted(fm.keys()),
        "category": classify(name or skill_dir.name, desc),
        "has_openai_yaml": (skill_dir / "agents" / "openai.yaml").exists(),
        "display_name": str(interface.get("display_name") or ""),
        "scripts": len([p for p in scripts if p.is_file() or p.is_symlink()]),
        "references": len([p for p in references if p.is_file() or p.is_dir()]),
        "assets": len([p for p in assets if p.is_file() or p.is_dir()]),
        "missing_refs": missing_refs,
        "warnings": warnings,
    }


def scan_roots(roots: list[Path], magpie_skills: dict[str, list[str]] | None = None) -> dict:
    magpie_skills = magpie_skills or {}
    result = {
        "updated_at": "2026-11-11",
        "roots": [],
        "skills": [],
        "magpie_library_loaded": bool(magpie_skills),
    }
    for root in roots:
        root_record = {"root": str(root), "exists": root.exists(), "count": 0}
        if root.is_dir():
            skill_files = sorted(root.glob("*/SKILL.md"))
            for skill_file in skill_files:
                record = scan_skill(skill_file.parent)
                record["root"] = str(root)
                record["magpie_agents"] = magpie_skills.get(record.get("name", ""), [])
                record["active"] = True
                result["skills"].append(record)
            root_record["count"] = sum(1 for s in result["skills"] if s["root"] == str(root))
        result["roots"].append(root_record)
    return result


def render_markdown(data: dict) -> str:
    skills = data["skills"]
    lines = ["# Canonical Skill Map", ""]
    for root in data["roots"]:
        lines.append(f"- `{root['root']}`: {'exists' if root['exists'] else 'missing'}, `{root['count']}` canonical skills")
    lines.append("")
    by_category: dict[str, list[dict]] = {}
    for skill in skills:
        by_category.setdefault(skill["category"], []).append(skill)
    for category in sorted(by_category):
        group = by_category[category]
        lines.append(f"## {category} ({len(group)})")
        lines.append("")
        lines.append("| Skill | Active | Projected Agents | Resources | Warnings |")
        lines.append("|---|---|---|---|---|")
        for skill in sorted(group, key=lambda x: x["folder"]):
            resources = f"s{skill['scripts']}/r{skill['references']}/a{skill['assets']}"
            agents = ",".join(skill.get("magpie_agents") or []) or "native"
            warnings = "; ".join(skill["warnings"]) if skill["warnings"] else ""
            lines.append(
                f"| `{skill['folder']}` | yes | `{agents}` | {resources} | {warnings} |"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan canonical Skills.")
    parser.add_argument("--root", action="append", type=Path, help="Skill root to scan.")
    parser.add_argument("--library", type=Path, default=DEFAULT_MAGPIE_LIBRARY)
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    roots = args.root or DEFAULT_ROOTS
    lib_status = load_magpie_library_status(args.library)
    data = scan_roots(roots, lib_status)
    if args.format == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(data))


if __name__ == "__main__":
    main()
