#!/usr/bin/env python3
"""xskill_doctor.py — Generic health check for an XSkill knowledge base.

Verifies directory layout, frontmatter validity, name consistency,
_index.json freshness, and end-to-end search behavior.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from xskill_core import XSkillManager, default_xskill_root  # noqa: E402


def run_doctor(root: Path) -> int:
    fails = 0
    warns = 0

    def ok(label: str, detail: str = "") -> None:
        print(f"[OK]   {label}" + (f" — {detail}" if detail else ""))

    def warn(label: str, detail: str = "") -> None:
        nonlocal warns
        warns += 1
        print(f"[WARN] {label}" + (f" — {detail}" if detail else ""))

    def fail(label: str, detail: str = "") -> None:
        nonlocal fails
        fails += 1
        print(f"[FAIL] {label}" + (f" — {detail}" if detail else ""))

    if not root.exists():
        fail("root exists", f"{root} not found")
        return 1
    ok("root exists", str(root))

    for rel in ("global/skills", "global/experiences"):
        if (root / rel).is_dir():
            ok(f"dir {rel}")
        else:
            fail(f"dir {rel}", "missing")

    mgr = XSkillManager(xskill_root=root)
    entries = mgr.list_entries()
    all_items = list(entries["global"])
    for p_items in entries["projects"].values():
        all_items.extend(p_items)

    # Validate frontmatter & name consistency
    expected_names = set()
    for item in all_items:
        p = Path(item["path"])
        name = item.get("name", "")
        expected = p.parent.name if p.name == "SKILL.md" else p.stem
        if not name:
            fail("frontmatter name", f"{p} missing name")
        elif name != expected:
            fail("name consistency", f"{p} has name={name!r}, expected {expected!r}")
        if not item.get("description"):
            warn("frontmatter description", f"{p} has empty description")
        if item.get("type") not in ("skill", "experience"):
            fail("frontmatter type", f"{p} invalid type={item.get('type')!r}")
        expected_names.add(name)

    ok("entries validated", f"{len(all_items)} entries checked")

    # Check _index.json freshness
    index_path = root / "_index.json"
    if not index_path.is_file():
        warn("_index.json", "missing; run `python3 xskill_core.py index`")
    else:
        try:
            idx = json.loads(index_path.read_text(encoding="utf-8"))
            indexed_names = set(idx.get("global", {}).keys())
            for p_map in idx.get("projects", {}).values():
                indexed_names.update(p_map.keys())
            if indexed_names == expected_names:
                ok("_index.json sync", f"{len(indexed_names)} entries in sync")
            else:
                missing = sorted(expected_names - indexed_names)
                extra = sorted(indexed_names - expected_names)
                fail("_index.json sync", f"drift detected (missing={missing}, extra={extra})")
        except Exception as e:  # noqa: BLE001
            fail("_index.json parse", repr(e))

    # End-to-end search smoke test
    if all_items:
        sample = all_items[0]
        res = mgr.search(f"{sample['name']} {sample.get('description', '')}")
        hit_names = [h["name"] for h in res["skills"] + res["experiences"]]
        if sample["name"] in hit_names:
            ok("search smoke test", f"matched {sample['name']!r}")
        else:
            fail("search smoke test", f"expected {sample['name']!r}, got {hit_names}")
    else:
        warn("search smoke test", "no entries to test")

    print(f"\nSummary: {fails} failed, {warns} warnings")
    return 1 if fails else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check XSkill knowledge base health.")
    parser.add_argument("--root", default=None, help="Knowledge base root (overrides XSKILL_ROOT)")
    ns = parser.parse_args(argv)
    root = Path(ns.root).expanduser().resolve() if ns.root else default_xskill_root()
    return run_doctor(root)


if __name__ == "__main__":
    raise SystemExit(main())
