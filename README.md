# XSkill

**English** | [中文](./README_CN.md)

**Zero-dependency, two-tier shared knowledge & skill hub for multi-agent workflows — exposed over standard MCP.**

XSkill lets multiple AI coding & research agents (Claude Code, Codex, Cursor, OpenCode, Gemini CLI, etc.) share a single source of truth for **Skills** (reusable workflows) and **Experiences** (contextual decision rules) without duplicating files across tools.

## Highlights

- **Zero third-party dependencies**: pure Python 3.10+ standard library.
- **Two-tier retrieval**: `projects/<project>/` (1.5x priority boost) + `global/` fallback.
- **Dual skill formats (no symlinks required)**: natively discovers both single-file entries (`*.md`) and folder-based standard Agent Skills (`<name>/SKILL.md`), safe on Linux, macOS, and Windows.
- **Read-only MCP Server with path lock**: `xskill_mcp.py` exposes `xskill_search` and `xskill_read` over stdio JSON-RPC 2.0, preventing unintended writes or directory traversal outside `XSKILL_ROOT`.
- **Dual-repo ready**: keep the framework public (`xskill`) while pointing `XSKILL_ROOT` or `--root` to your private knowledge vault (`xskill-vault`).

---

## Repository Layout

```text
xskill/
├── xskill_core.py          # Search, index, and CRUD engine
├── xskill_mcp.py           # Read-only stdio MCP server
├── scripts/
│   └── xskill_doctor.py    # Knowledge base health check
├── global/
│   ├── skills/             # Bundled starter skills (*.md and <name>/SKILL.md)
│   └── experiences/        # Contextual decision rules & lessons learned
├── projects/               # Project-scoped overrides (projects/<name>/{skills,experiences})
├── tests/
│   └── test_xskill.py      # Core & MCP test suite
└── _index.json             # Generated index
```

---

## Bundled Starter Skills (Academic & Engineering)

| Skill | Format | Domain | Purpose |
|---|---|---|---|
| `anti-defensive-writing` | Folder | Academic | Eliminate defensive hedging in papers, protocols, and rebuttals |
| `paper-claim-audit` | Single | Academic | Context-free number-by-number audit between manuscript and raw outputs |
| `citation-integrity-check` | Single | Academic | Dual-source DOI/metadata verification, chimera & retraction checks |
| `claim-safety-gates` | Single | Academic | Three hard gates (no fabrication, no unapproved promises, full coverage) |
| `review-rebuttal` | Single | Academic | Structured peer-review triage, evidence binding, and commitment ledger |
| `figure-creation-standards` | Folder | Academic | Journal dimensions, colorblind-safe palettes, vector export, honest encoding |
| `figure-review-gate` | Single | Academic | Post-render PDF figure QA and visual honesty checklist |
| `minimal-code-ladder` | Single | Engineering | Anti-over-engineering ladder with non-negotiable safety boundaries |
| `code-review-beyond-diff` | Single | Engineering | Impact-first code review beyond changed lines + shortcut debt ledger |

---

## Quick Start

### 1. Run Health Check & Tests

```bash
python3 scripts/xskill_doctor.py
python3 -m unittest discover -s tests -v
```

### 2. CLI Usage

```bash
# Search with a full-sentence task description
python3 xskill_core.py search "论文里的数字和原始结果文件对不上，怎么逐数字核对"

# Rebuild _index.json after adding or editing entries
python3 xskill_core.py index

# Inspect counts
python3 xskill_core.py stats
```

> **Tip on querying**: Always pass a **full-sentence task description** rather than 2–3 short keywords. The engine uses Jaccard + keyword hit-ratio scoring; overly short queries may fall below the relevance threshold.

### 3. Dual-Repo Setup (Public Framework + Private Vault)

Keep this repo as your framework, and store your private `global/` and `projects/` entries in a separate private repository (e.g. `xskill-vault`). Point XSkill at your vault via `--root` or `XSKILL_ROOT`:

```bash
export XSKILL_ROOT=/path/to/xskill-vault
python3 xskill_mcp.py
# or explicitly:
python3 xskill_mcp.py --root /path/to/xskill-vault
```

---

## MCP Integration

Point any MCP-compatible client to `xskill_mcp.py` (optionally passing `--root /path/to/your/vault`).

### Claude Code

```bash
claude mcp add xskill -s user -- python3 /path/to/xskill/xskill_mcp.py --root /path/to/xskill-vault
```

### Codex CLI (`~/.codex/config.toml`)

```toml
[mcp_servers.xskill]
command = "python3"
args = ["/path/to/xskill/xskill_mcp.py", "--root", "/path/to/xskill-vault"]
```

### Cursor / Gemini CLI (`mcp_config.json`)

```json
{
  "mcpServers": {
    "xskill": {
      "command": "python3",
      "args": ["/path/to/xskill/xskill_mcp.py", "--root", "/path/to/xskill-vault"]
    }
  }
}
```

### OpenCode

```bash
opencode mcp add xskill --global -- python3 /path/to/xskill/xskill_mcp.py --root /path/to/xskill-vault
```

---

## Writing a New Entry

Every Skill or Experience uses a lightweight YAML frontmatter block:

```markdown
---
type: skill
name: my-workflow
description: One-sentence description used for retrieval matching.
metadata:
  domain: academic
  tools: ["read_file", "terminal"]
  success_count: 1
  tags: ["workflow", "audit"]
  author: your-name
  created: 2026-11-20
  updated: 2026-11-20
---

## Steps
...
```

Place it at `global/skills/my-workflow.md` (or `global/skills/my-workflow/SKILL.md` for folder-based skills with bundled scripts/assets), then run `python3 xskill_core.py index`.

## License

MIT
