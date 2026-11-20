# XSkill 使用说明

[English](./README.md) | **中文**

**零第三方依赖、纯 Python 标准库实现的多 Agent 共享知识库与技能中枢（MCP 协议）。**

XSkill 让 Claude Code、Codex、Cursor、OpenCode、Gemini CLI 等多个 AI Agent 共用同一份 **Skill（可复用工作流）** 与 **Experience（情境化避坑规则）**，无需在每个工具里复制粘贴副本。

---

## 核心特性

- **零依赖**：纯 Python 3.10+ 标准库，clone 下来直接跑。
- **两级检索**：项目级（`projects/<项目名>/`，1.5 倍权重优先）+ 全局级（`global/`）自动合并去重。
- **双形态技能（无需软链）**：原生同时扫描单文件（`*.md`）和文件夹式标准 Agent Skill（`<name>/SKILL.md`），Linux / macOS / Windows 均无软链失效问题。
- **只读 MCP + 路径锁**：`xskill_mcp.py` 通过 stdio JSON-RPC 2.0 暴露 `xskill_search` 和 `xskill_read`，严格只读且锁定在 `XSKILL_ROOT` 目录内，防止多 Agent 误写或越权读库外文件。
- **支持双仓分离**：框架代码公开维护，个人知识库放在独立私有仓（如 `xskill-vault`），通过 `--root` 或 `XSKILL_ROOT` 环境变量动态挂载。

---

## 3 分钟快速上手

### 1. 克隆并自检

```bash
git clone https://github.com/zaki030220/xskill.git
cd xskill

# 体检：检查目录结构、frontmatter、索引一致性与检索自检
python3 scripts/xskill_doctor.py

# 跑单元测试（含 MCP 协议往返与路径锁安全测试）
python3 -m unittest discover -s tests -v
```

### 2. 命令行体验

```bash
# 用完整句子描述任务进行检索
python3 xskill_core.py search "论文里的数字和原始结果文件对不上，怎么逐数字核对"

# 增改条目后重建索引
python3 xskill_core.py index

# 查看当前库存统计
python3 xskill_core.py stats
```

---

## 挂载到各类 AI Agent（MCP 接入）

以下示例中的 `/path/to/xskill` 替换为你本机的框架路径；如果使用双仓分离，把 `--root /path/to/xskill-vault` 指向你的私有知识库目录（单仓使用则省略 `--root`）。

### Claude Code

```bash
claude mcp add xskill -s user -- python3 /path/to/xskill/xskill_mcp.py --root /path/to/xskill-vault
```

### Codex CLI（`~/.codex/config.toml`）

```toml
[mcp_servers.xskill]
command = "python3"
args = ["/path/to/xskill/xskill_mcp.py", "--root", "/path/to/xskill-vault"]
```

### Cursor / Gemini CLI（`mcp_config.json`）

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

### 建议给 Agent 加一条触发规则

在你的 `AGENTS.md` / `CLAUDE.md` 中加入：

```markdown
- 学术或技术任务开始前，先调用 `xskill_search` 检索共享知识库（必须使用完整句子描述任务，不要用两三个字的短关键词）。
- 命中后调用 `xskill_read` 读取完整条目作为参考，不替代专业判断。
```

---

## 双仓分离用法（推荐）

如果你想把框架升级与个人科研/工程资产彻底隔离：

1. **框架仓（本仓库）**：只保留代码、测试与精选通用 Skill，随时 `git pull` 获取引擎更新。
2. **私有知识库仓（如 `xskill-vault`）**：只存放你自己的 `global/`、`projects/` 和 `_index.json`。
3. **启动时指定根目录**（二选一）：
   - 命令行参数：`python3 /path/to/xskill/xskill_mcp.py --root /path/to/xskill-vault`
   - 环境变量：`export XSKILL_ROOT=/path/to/xskill-vault`

---

## 如何新增 Skill / Experience

### 选单文件还是文件夹？

- **单文件（`global/skills/<name>.md`）**：纯方法论、核查清单、写作/审稿规范，推荐默认用单文件。
- **文件夹式（`global/skills/<name>/SKILL.md`）**：当该技能附带 `scripts/`、`templates/`、`assets/` 等配套文件，或需要兼容原生文件夹式 Agent Skill 发现机制时使用。
- **项目级覆盖**：只对某个具体课题生效的规则，放到 `projects/<项目名>/skills/` 或 `projects/<项目名>/experiences/`，检索时会自动获得 **1.5 倍权重加成**。

### 标准 Frontmatter 模板

```markdown
---
type: skill
name: my-workflow
description: 用一句话完整说明适用场景与核心动作（检索打分的主要依据）
metadata:
  domain: academic
  tools: ["read_file", "terminal"]
  success_count: 1
  tags: ["workflow", "audit", "核查"]
  author: your-name
  created: 2026-11-20
  updated: 2026-11-20
---

## 核心步骤
...
```

新增或修改后，执行以下两条命令同步索引并体检：

```bash
python3 xskill_core.py index
python3 scripts/xskill_doctor.py
```

---

## 内置精选 Starter Skills（9 个）

| 名称 | 形态 | 领域 | 用途 |
|---|---|---|---|
| `anti-defensive-writing` | 文件夹 | 学术写作 | 消除论文、方案与返修信中的防御性措辞与自我削弱 |
| `paper-claim-audit` | 单文件 | 学术核查 | 无上下文逐数字比对论文与原始结果文件，抓四舍五入与配置漂移 |
| `citation-integrity-check` | 单文件 | 学术核查 | DOI/PubMed 双源核验、嵌合引用检测、撤稿核查与支持度判定 |
| `claim-safety-gates` | 单文件 | 学术纪律 | 不伪造、不过度承诺、全覆盖三道门与零臆造红线 |
| `review-rebuttal` | 单文件 | 审稿返修 | 原话保全、原子化分诊、策略五选一与承诺台账 |
| `figure-creation-standards` | 文件夹 | 科研绘图 | 期刊栏宽尺寸、色盲安全配色、矢量导出与诚实编码 |
| `figure-review-gate` | 单文件 | 科研绘图 | 渲染后 PDF 终检与视觉诚实检查清单 |
| `minimal-code-ladder` | 单文件 | 工程开发 | 写代码前按阶梯压掉过度设计，守住安全与校验硬边界 |
| `code-review-beyond-diff` | 单文件 | 工程审查 | 跳出 diff 看波及文件，按 must/should/nice 分级与债务台账 |

---

## 两条高频避坑提示

1. **检索必须用整句，不要用短词**：引擎基于 `name / description / tags` 的中英文分词做 Jaccard + 命中率打分。如果只搜两三个字（如 `"审稿"`），分母拉大且命中词太少，容易低于阈值返回空；改成 `"收到审稿意见需要逐条回复并建立承诺台账"` 即可精准命中。
2. **MCP 默认只读是有意设计**：防止多个并发 Agent 自动往共享库里写入噪声条目。需要沉淀新经验时，建议由人工确认后通过 `xskill_core.py` 或直接编辑 Markdown 文件入库，再运行 `index`。

## License

MIT
