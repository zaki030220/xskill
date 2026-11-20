#!/usr/bin/env python3
"""
xskill_core.py — Zero-dependency two-tier shared knowledge engine for AI agents.

Provides a shared global + project-level repository of reusable Skills (workflows)
and Experiences (contextual decision rules), supporting both single-file entries
(`*.md`) and folder-based Agent Skills (`<name>/SKILL.md`) without symlinks.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent

TOP_K_SKILLS = 3
TOP_K_EXPERIENCES = 5
JACCARD_THRESHOLD = 0.06

SIMILARITY_WARN = 0.50
SIMILARITY_MERGE = 0.70


def default_xskill_root() -> Path:
    """Resolve the XSkill root directory via XSKILL_ROOT env var or script directory."""
    env_root = os.environ.get("XSKILL_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()
    return SCRIPT_DIR


class XSkillManager:
    """Two-tier (global + project) knowledge base manager for Skills and Experiences."""

    def __init__(self, xskill_root: str | Path | None = None, project: str | None = None):
        self.root = Path(xskill_root).expanduser().resolve() if xskill_root else default_xskill_root()
        self.project = project
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        for d in (
            self.root / "global" / "skills",
            self.root / "global" / "experiences",
        ):
            d.mkdir(parents=True, exist_ok=True)
        if self.project:
            for d in (
                self.root / "projects" / self.project / "skills",
                self.root / "projects" / self.project / "experiences",
            ):
                d.mkdir(parents=True, exist_ok=True)

    def set_project(self, project: str | None) -> None:
        self.project = project
        self._ensure_dirs()

    # ── Entry Discovery (supports both *.md and <dir>/SKILL.md) ───────

    def _iter_entry_files(self, directory: Path) -> List[Path]:
        """Yield markdown entry files in `directory`, deduplicating resolved paths."""
        if not directory.exists():
            return []

        files: List[Path] = []
        seen_resolved: set[Path] = set()

        # 1. Folder-based standard Agent Skills: <directory>/<name>/SKILL.md
        for child in sorted(directory.iterdir()):
            if child.is_dir() and not child.name.startswith("_") and not child.name.startswith("."):
                skill_md = child / "SKILL.md"
                if skill_md.is_file():
                    resolved = skill_md.resolve()
                    if resolved not in seen_resolved:
                        seen_resolved.add(resolved)
                        files.append(skill_md)

        # 2. Single-file entries: <directory>/*.md (skips symlinks pointing to already-seen SKILL.md)
        for md_file in sorted(directory.glob("*.md")):
            if md_file.name.startswith("_"):
                continue
            if not md_file.is_file():
                continue
            resolved = md_file.resolve()
            if resolved not in seen_resolved:
                seen_resolved.add(resolved)
                files.append(md_file)

        return files

    # ── Search ────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        project: str | None = None,
        k_skills: int = TOP_K_SKILLS,
        k_experiences: int = TOP_K_EXPERIENCES,
    ) -> Dict[str, List[Dict]]:
        """Two-tier search: project-level first (1.5x boost) -> global -> merge & rank."""
        proj = project if project is not None else self.project

        all_skills: List[Dict] = []
        all_exps: List[Dict] = []

        if proj:
            proj_skills = self._search_in_dir(query, self.root / "projects" / proj / "skills", "skill")
            proj_exps = self._search_in_dir(query, self.root / "projects" / proj / "experiences", "experience")
            for item in proj_skills:
                item["score"] = round(item["score"] * 1.5, 4)
                item["source"] = "project"
            for item in proj_exps:
                item["score"] = round(item["score"] * 1.5, 4)
                item["source"] = "project"
            all_skills.extend(proj_skills)
            all_exps.extend(proj_exps)

        if proj != "__project_only__":
            global_skills = self._search_in_dir(query, self.root / "global" / "skills", "skill")
            global_exps = self._search_in_dir(query, self.root / "global" / "experiences", "experience")
            for item in global_skills:
                item["source"] = "global"
            for item in global_exps:
                item["source"] = "global"
            all_skills.extend(global_skills)
            all_exps.extend(global_exps)

        return {
            "skills": self._merge_and_rank(all_skills, k_skills),
            "experiences": self._merge_and_rank(all_exps, k_experiences),
        }

    def _search_in_dir(self, query: str, directory: Path, mem_type: str) -> List[Dict]:
        query_kw = self._extract_keywords(query)
        if not query_kw:
            return []

        results: List[Dict] = []
        for md_file in self._iter_entry_files(directory):
            try:
                info = self._read_entry(md_file)
                if info is None or info.get("type") != mem_type:
                    continue

                search_text = f"{info.get('name', '')} {info.get('description', '')}"
                tags = info.get("metadata", {}).get("tags", [])
                if isinstance(tags, list):
                    search_text += " " + " ".join(str(t) for t in tags)
                elif isinstance(tags, str):
                    search_text += " " + tags

                file_kw = self._extract_keywords(search_text)
                jaccard = self._jaccard_similarity(query_kw, file_kw)
                hit_ratio = len(query_kw & file_kw) / max(1, len(query_kw))
                score = max(jaccard, hit_ratio * 0.85)

                if score >= JACCARD_THRESHOLD:
                    sc = int(info.get("metadata", {}).get("success_count", 1))
                    score *= min(1.0 + sc * 0.05, 1.5)
                    results.append(
                        {
                            "name": info.get("name"),
                            "description": info.get("description"),
                            "type": mem_type,
                            "score": round(score, 4),
                            "source": "global",
                            "path": str(md_file),
                            "success_count": sc,
                            "metadata": info.get("metadata", {}),
                        }
                    )
            except Exception:
                continue

        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def _merge_and_rank(self, items: List[Dict], top_k: int) -> List[Dict]:
        seen: Dict[str, Dict] = {}
        for item in items:
            name = item["name"]
            if name not in seen or item["score"] > seen[name]["score"]:
                seen[name] = item
        merged = sorted(seen.values(), key=lambda x: x["score"], reverse=True)
        return merged[:top_k]

    # ── Read & List ───────────────────────────────────────────────────

    def _read_entry(self, file_path: Path) -> Optional[Dict]:
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            return None

        fm = self._extract_frontmatter(content)
        if fm is None:
            return None

        body_match = re.match(r"^---\s*\n.*?\n---\s*\n(.*)", content, re.DOTALL)
        fm["body"] = body_match.group(1).strip() if body_match else ""
        return fm

    def read_entry(self, name: str, mem_type: str | None = None, project: str | None = None) -> Optional[Dict]:
        search_bases: List[Path] = []
        proj = project or self.project
        if proj:
            search_bases.append(self.root / "projects" / proj)
        search_bases.append(self.root / "global")

        subs = ["skills", "experiences"]
        if mem_type == "skill":
            subs = ["skills"]
        elif mem_type == "experience":
            subs = ["experiences"]

        for base in search_bases:
            for sub in subs:
                for candidate in (base / sub / name / "SKILL.md", base / sub / f"{name}.md"):
                    if candidate.is_file():
                        info = self._read_entry(candidate)
                        if info:
                            info["path"] = str(candidate)
                            return info
        return None

    def list_entries(self, mem_type: str | None = None) -> Dict:
        result: Dict = {"global": [], "projects": {}}

        for sub in ("skills", "experiences"):
            gdir = self.root / "global" / sub
            for md_file in self._iter_entry_files(gdir):
                info = self._read_entry(md_file)
                if info and (mem_type is None or info.get("type") == mem_type):
                    info["path"] = str(md_file)
                    result["global"].append(info)

        proj_root = self.root / "projects"
        if proj_root.exists():
            for proj_dir in sorted(proj_root.iterdir()):
                if not proj_dir.is_dir() or proj_dir.name.startswith("."):
                    continue
                proj_entries = []
                for sub in ("skills", "experiences"):
                    sdir = proj_dir / sub
                    for md_file in self._iter_entry_files(sdir):
                        info = self._read_entry(md_file)
                        if info and (mem_type is None or info.get("type") == mem_type):
                            info["path"] = str(md_file)
                            proj_entries.append(info)
                if proj_entries:
                    result["projects"][proj_dir.name] = proj_entries

        return result

    # ── Create & Update ───────────────────────────────────────────────

    def create_skill(
        self,
        name: str,
        description: str,
        domain: str,
        tools: List[str],
        content: str,
        project: str | None = None,
        tags: List[str] | None = None,
        author: str = "user",
        folder: bool = False,
    ) -> str:
        proj = project or self.project
        target_dir = (self.root / "projects" / proj / "skills") if proj else (self.root / "global" / "skills")
        target_dir.mkdir(parents=True, exist_ok=True)

        if folder:
            skill_dir = target_dir / name
            skill_dir.mkdir(parents=True, exist_ok=True)
            file_path = skill_dir / "SKILL.md"
        else:
            file_path = target_dir / f"{name}.md"

        if file_path.exists():
            return str(file_path)

        today = datetime.now().strftime("%Y-%m-%d")
        frontmatter = (
            "---\n"
            "type: skill\n"
            f"name: {name}\n"
            f"description: {description}\n"
            "metadata:\n"
            f"  domain: {domain}\n"
            f"  tools: {json.dumps(tools, ensure_ascii=False)}\n"
            "  success_count: 1\n"
            f"  tags: {json.dumps(tags or [], ensure_ascii=False)}\n"
            f"  author: {author}\n"
            f"  created: {today}\n"
            f"  updated: {today}\n"
            "---\n\n"
        )
        file_path.write_text(frontmatter + content, encoding="utf-8")
        return str(file_path)

    def create_experience(
        self,
        name: str,
        description: str,
        context: str,
        content: str,
        related_skills: List[str] | None = None,
        project: str | None = None,
        tags: List[str] | None = None,
        confidence: str = "high",
        author: str = "user",
    ) -> str:
        proj = project or self.project
        target_dir = (
            (self.root / "projects" / proj / "experiences") if proj else (self.root / "global" / "experiences")
        )
        target_dir.mkdir(parents=True, exist_ok=True)

        file_path = target_dir / f"{name}.md"
        if file_path.exists():
            return str(file_path)

        today = datetime.now().strftime("%Y-%m-%d")
        related_str = json.dumps([f"[[{s}]]" for s in (related_skills or [])], ensure_ascii=False)
        frontmatter = (
            "---\n"
            "type: experience\n"
            f"name: {name}\n"
            f"description: {description}\n"
            "metadata:\n"
            f"  context: {context}\n"
            f"  related_skills: {related_str}\n"
            f"  confidence: {confidence}\n"
            f"  tags: {json.dumps(tags or [], ensure_ascii=False)}\n"
            f"  author: {author}\n"
            f"  created: {today}\n"
            "---\n\n"
        )
        file_path.write_text(frontmatter + content, encoding="utf-8")
        return str(file_path)

    def increment_success(self, name: str, mem_type: str | None = None, project: str | None = None) -> bool:
        entry = self.read_entry(name, mem_type, project)
        if entry is None:
            return False

        file_path = Path(entry["path"])
        content = file_path.read_text(encoding="utf-8")

        new_content, count = re.subn(
            r"success_count:\s*(\d+)",
            lambda m: f"success_count: {int(m.group(1)) + 1}",
            content,
            count=1,
        )
        if count == 0:
            new_content, meta_count = re.subn(
                r"(?m)^metadata:\s*$",
                "metadata:\n  success_count: 2",
                content,
                count=1,
            )
            if meta_count == 0:
                new_content = re.sub(r"^---\s*\n", "---\nmetadata:\n  success_count: 2\n", content, count=1)

        new_content = re.sub(
            r"updated:\s*\d{4}-\d{2}-\d{2}",
            f"updated: {datetime.now().strftime('%Y-%m-%d')}",
            new_content,
            count=1,
        )
        file_path.write_text(new_content, encoding="utf-8")
        return True

    # ── Frontmatter & Tokenization ────────────────────────────────────

    def _extract_frontmatter(self, content: str) -> Optional[Dict]:
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if not match:
            return None

        fm_text = match.group(1)
        fm: Dict = {}
        current_key = None
        current_value: List[str] = []

        for line in fm_text.split("\n"):
            if ":" in line and not line.startswith(" ") and not line.startswith("\t"):
                if current_key:
                    fm[current_key] = "\n".join(current_value).strip()
                key, value = line.split(":", 1)
                current_key = key.strip()
                current_value = [value.strip()]
            elif current_key:
                current_value.append(line.strip())

        if current_key:
            fm[current_key] = "\n".join(current_value).strip()

        if "metadata" in fm and isinstance(fm["metadata"], str):
            metadata: Dict = {}
            for line in fm["metadata"].split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip()
                    if value.startswith("[") and value.endswith("]"):
                        try:
                            parsed = json.loads(value)
                            value = parsed if isinstance(parsed, list) else value
                        except json.JSONDecodeError:
                            inner = value[1:-1]
                            value = [v.strip().strip('"').strip("'") for v in inner.split(",") if v.strip()]
                    elif value.isdigit():
                        value = int(value)
                    metadata[key] = value
            fm["metadata"] = metadata

        return fm

    def _extract_keywords(self, text: str) -> set:
        text = text.lower()
        english_words = set(re.findall(r"[a-z]{2,}", text))

        extra_from_hyphen = set()
        for w in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)+", text):
            for part in w.replace("-", " ").replace("_", " ").split():
                if len(part) > 2:
                    extra_from_hyphen.add(part)

        chinese_chars = re.findall(r"[\u4e00-\u9fff]+", text)
        chinese_ngrams = set()
        for chunk in chinese_chars:
            for i in range(len(chunk) - 1):
                chinese_ngrams.add(chunk[i : i + 2])
            for i in range(len(chunk) - 2):
                chinese_ngrams.add(chunk[i : i + 3])

        clean = re.sub(r"[^\w\s-]", " ", text)
        words = set(clean.split())
        all_keywords = english_words | extra_from_hyphen | chinese_ngrams | words

        stopwords = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
            "been", "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "can", "this",
            "that", "these", "those", "i", "you", "he", "she", "it", "we", "they",
            "的", "是", "在", "了", "和", "不", "也", "都", "就", "要", "有", "会",
            "能", "可以", "需要", "应该", "这个", "那个", "一个",
        }

        keywords = {w for w in all_keywords if len(w) > 2 and w not in stopwords}
        for chunk in chinese_chars:
            for i in range(len(chunk) - 1):
                bigram = chunk[i : i + 2]
                if bigram not in stopwords:
                    keywords.add(bigram)
        return keywords

    def _jaccard_similarity(self, set1: set, set2: set) -> float:
        if not set1 or not set2:
            return 0.0
        union = len(set1 | set2)
        return len(set1 & set2) / union if union > 0 else 0.0

    # ── Index & Stats ─────────────────────────────────────────────────

    def build_index(self) -> Dict:
        all_entries = self.list_entries()
        index: Dict = {"global": {}, "projects": {}}

        for entry in sorted(all_entries.get("global", []), key=lambda e: e.get("name", "")):
            index["global"][entry["name"]] = {
                "type": entry.get("type"),
                "description": entry.get("description"),
                "success_count": entry.get("metadata", {}).get("success_count", 1),
            }

        for proj_name, entries in sorted(all_entries.get("projects", {}).items()):
            index["projects"][proj_name] = {}
            for entry in sorted(entries, key=lambda e: e.get("name", "")):
                index["projects"][proj_name][entry["name"]] = {
                    "type": entry.get("type"),
                    "description": entry.get("description"),
                    "success_count": entry.get("metadata", {}).get("success_count", 1),
                }

        index_path = self.root / "_index.json"
        index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return index

    def stats(self) -> Dict:
        entries = self.list_entries()
        global_counts = {"skill": 0, "experience": 0}
        for e in entries["global"]:
            t = e.get("type")
            if t in global_counts:
                global_counts[t] += 1

        proj_counts = {}
        for proj, ents in entries["projects"].items():
            sc = {"skill": 0, "experience": 0}
            for e in ents:
                t = e.get("type")
                if t in sc:
                    sc[t] += 1
            proj_counts[proj] = sc

        return {
            "root": str(self.root),
            "global": global_counts,
            "projects": proj_counts,
            "total_skills": global_counts["skill"] + sum(p["skill"] for p in proj_counts.values()),
            "total_experiences": global_counts["experience"] + sum(p["experience"] for p in proj_counts.values()),
        }


# ── Programmatic Convenience API ──────────────────────────────────────

def quick_search(
    query: str,
    project: str | None = None,
    k_skills: int = TOP_K_SKILLS,
    k_experiences: int = TOP_K_EXPERIENCES,
    xskill_root: str | Path | None = None,
) -> Dict[str, List[Dict]]:
    mgr = XSkillManager(xskill_root=xskill_root, project=project)
    return mgr.search(query, k_skills=k_skills, k_experiences=k_experiences)


def increment_success(
    name: str,
    mem_type: str | None = None,
    project: str | None = None,
    xskill_root: str | Path | None = None,
) -> bool:
    mgr = XSkillManager(xskill_root=xskill_root, project=project)
    ok = mgr.increment_success(name, mem_type=mem_type, project=project)
    if ok:
        mgr.build_index()
    return ok


def quick_add_skill(
    name: str,
    description: str,
    domain: str,
    tools: List[str],
    content: str,
    project: str | None = None,
    author: str = "user",
    folder: bool = False,
    xskill_root: str | Path | None = None,
) -> str:
    mgr = XSkillManager(xskill_root=xskill_root, project=project)
    path = mgr.create_skill(name, description, domain, tools, content, project=project, author=author, folder=folder)
    mgr.build_index()
    return path


def quick_add_experience(
    name: str,
    description: str,
    context: str,
    content: str,
    related: List[str] | None = None,
    project: str | None = None,
    confidence: str = "high",
    author: str = "user",
    xskill_root: str | Path | None = None,
) -> str:
    mgr = XSkillManager(xskill_root=xskill_root, project=project)
    path = mgr.create_experience(
        name, description, context, content, related, project=project, confidence=confidence, author=author
    )
    mgr.build_index()
    return path


def _cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="XSkill CLI")
    parser.add_argument("--root", default=None, help="Knowledge base root (overrides XSKILL_ROOT)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_search = sub.add_parser("search", help="Search skills and experiences")
    p_search.add_argument("query", help="Full-sentence task description")
    p_search.add_argument("--project", default=None)
    p_search.add_argument("--k-skills", type=int, default=TOP_K_SKILLS)
    p_search.add_argument("--k-experiences", type=int, default=TOP_K_EXPERIENCES)

    sub.add_parser("index", help="Rebuild _index.json")
    sub.add_parser("stats", help="Print knowledge base stats")

    ns = parser.parse_args()
    mgr = XSkillManager(xskill_root=ns.root)

    if ns.cmd == "search":
        res = mgr.search(ns.query, project=ns.project, k_skills=ns.k_skills, k_experiences=ns.k_experiences)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif ns.cmd == "index":
        idx = mgr.build_index()
        print(f"Index rebuilt: {len(idx['global'])} global, {len(idx['projects'])} project(s)")
    elif ns.cmd == "stats":
        print(json.dumps(mgr.stats(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
