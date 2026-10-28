# 07 · 接入 Hermes desktop

本 kit 的第一等目标是 **Hermes desktop**：四层结构直接映射到 Hermes 已有的注入机制，不需要改它一行代码。

## Hermes 的注入机制（L0 的落点）

```
Windows:  %LOCALAPPDATA%\hermes\            (git-bash: ~/AppData/Local/hermes/)
Linux:    ~/.local/share/hermes/
├── SOUL.md              ← 人格与行为规范，每轮加载
├── memories/
│   ├── MEMORY.md        ← L0 主文件（条目用 § 分隔）
│   └── USER.md          ← L0 用户最小集
├── skills/              ← 程序性记忆，按需加载
├── cron/                ← 定时任务（jobs.json + output/）
└── config.yaml
```

对应关系：

| 层 | Hermes 里的位置 |
|---|---|
| **L0 内核** | `memories/MEMORY.md` + `memories/USER.md`（自动注入，有字符预算） |
| **L0 行为规则** | `SOUL.md`（人格、交互风格、工具原则） |
| **L1 知识库** | Obsidian vault 或任意目录，靠 `read_file` / MCP 读 |
| **L2 语义索引** | `qmd`（CLI 或 MCP server） |
| **L3 归档** | `cron/output/`、会话历史、`archive/` |
| **程序性记忆** | `skills/` —— 只在该类任务出现时加载 |

**关键区别**：Hermes 的 MEMORY.md 有硬字符预算（默认 2200），这正是本 kit 三闸门规则的现实来源。预算是约束，也是保护 —— 它逼你在写入前就想清楚。

---

## 第一步：把 L0 装进 Hermes

### 1. 初始化知识库

```bash
python scripts/amk.py init --vault "$HOME/Obsidian Vault/memory-root"
```

Hermes 用户通常把 vault 指向 Obsidian 库里的一个子目录，这样人能看、智能体也能读。

### 2. 迁移 MEMORY.md

Hermes 的 MEMORY.md 条目用 `§` 分隔，`amk.py promote` 直接认得。

**先备份，再在临时副本上试**：

```bash
cp "$HOME/AppData/Local/hermes/memories/MEMORY.md" /tmp/MEMORY.backup.md

# 试运行：看它打算怎么拆（不动原文件）
python scripts/amk.py promote \
  --vault "$VAULT" \
  --kernel /tmp/MEMORY.backup.md \
  --target 60 --dry-run

# 确认后执行
python scripts/amk.py promote \
  --vault "$VAULT" \
  --kernel /tmp/MEMORY.backup.md \
  --target 60
```

它会生成 `memory/facts/*.md`，并把 `MEMORY.backup.md` 改写成精简版。然后：

1. 人工过一遍生成的 facts 文件（自动切分不懂语义，命名和分类要人调）
2. 把精简后的内容贴回 `memories/MEMORY.md`
3. 新会话确认正常后，备份移进 `archive/`

**保留在 L0 的清单（不要下沉）**：

- 语言 / 风格 / 交互约束（说错就破坏长期体验）
- 安全红线（`rm` 不进回收站、不写密码）
- 关键路径（vault 在哪、配置在哪）
- 唯一标识（GitHub 账号、仓库名）
- 硬性工具行为（某个配置只能用什么方式改）

### 3. 把记忆协议写进 SOUL.md

这一段决定整套系统能不能跑起来 —— **没有它，L0 里的指针就是死文字**。

```markdown
## 记忆协议

- 会话开始：`memories/MEMORY.md` 与 `memories/USER.md` 已自动注入，无条件遵守。
- 遇到「X 详见 memory/xxx.md」这类指针：先用 read_file 打开对应路径，读完再回答。
- 指针指向的文件不存在：不要猜内容，用 search_files 找，找到后**修好指针**。
- 关键词记不准：走 qmd `qmd query "<关键词>" --max-results 5`；
  已知路径就直接读文件，别浪费一次检索。
- 写入前先判断：三个月后还有用吗？会腐坏吗？过三闸门吗？
- 易腐值（端口/密码/版本号）只记「去哪查 + 怎么验」，**不记值**。
- 记忆与实测冲突时以实测为准，改掉旧值并标注 verified 日期。
- 没有值得记的新信息就不要写 —— 噪音比缺失更有害。
- 不要向用户播报"我已读取记忆"，除非记忆之间矛盾或明显过时。
```

直接把这整段追加到 `SOUL.md` 末尾即可。完整版见
[adapters/hermes/SOUL-记忆协议.md](../adapters/hermes/SOUL-记忆协议.md)。

---

## 第二步：把方法论装成 skill

Hermes 的 skill 是**按需加载**的程序性记忆，正好放"怎么维护记忆"这类流程，不占 L0 预算。

```bash
# 把 docs 收进一个 skill
mkdir -p ~/AppData/Local/hermes/skills/memory/agent-memory-kit
cp docs/*.md ~/AppData/Local/hermes/skills/memory/agent-memory-kit/
cp README.md ~/AppData/Local/hermes/skills/memory/agent-memory-kit/SKILL.md
```

`SKILL.md` 的 frontmatter 要写清触发条件，让 Hermes 只在相关任务时加载：

```yaml
---
name: agent-memory-kit
description: "四层本地记忆系统的维护与迁移：写入协议、L0 升降级、体检、索引修复"
version: 1.0.0
metadata:
  hermes:
    tags: [memory, obsidian, qmd, maintenance]
---
```

之后说"整理一下记忆库"，Hermes 会自己加载这套流程，而不是每次临场发挥。

---

## 第三步：注册维护任务（Hermes cron）

四个职责，对应四个 cron job。用 `hermes cron add` 或 `cronjob_manage` 工具注册：

| 任务 | 频率 | 职责 | 权限 |
|---|---|---|---|
| 会话同步 | `15 */2 * * *` | 有价值的对话 → `memory/session-notes/` | 只写 |
| 记忆体检 | `5 3 * * *` | `amk.py lint` + 索引检查 | 只读 |
| 整理去重 | `40 23 * * *` | 合并重复、补标签 | 读写（带白名单） |
| 占用率监控 | `0 9 * * *` | 报告 L0 占用，超阈值提醒 | 只读 |

**提示词模板在 [adapters/hermes/cron-prompts.md](../adapters/hermes/cron-prompts.md)**，直接抄。

### ⚠️ 白名单是硬要求

整理类任务必须在提示词顶部写死：

```markdown
## 🚫 保护白名单（绝对不能移动/删除/重命名）
- memory/          记忆本体
- kernel/          L0 内核
- archive/         归档
- skills/          skill 目录
- index.md         主索引
- changelog.md     变更日志
```

真实事故：整理任务把记忆目录当成"待分类笔记"，全部移到 `wiki/entities/`。系统文档看起来完好，实际数据已被搬走，会话读不到任何内容。**白名单是唯一可靠的防御。**

### Cron 环境的能力限制

定时任务里的工具集和交互式会话不同，写提示词时留个心眼：

- `execute_code` 在 cron 中通常不可用 → 用 `terminal` 代替
- `memory` 工具在 cron 中通常不可用 → 占用率从日志读：
  ```bash
  grep "Memory at" ~/AppData/Local/hermes/logs/agent.log | tail -3
  ```
- 单向任务（只读 / 只写）比双向任务安全得多，尽量拆开
- 长任务（如 `qmd embed`）放后台，别让 cron 卡在超时上

---

## 第四步：L2 索引（qmd）

```bash
# 建索引（一次）
cd "$VAULT"
qmd collection add memory --pattern "memory/**/*.md"

# 更新
qmd update && qmd embed

# 查询
qmd query "相变片 温度 结论" --max-results 5
```

`qmd embed` 是 CPU 密集操作，几百个文件可能要几分钟。放后台，别放进高频 cron。

### 接成 MCP（可选）

```bash
qmd mcp                              # stdio 传输
hermes mcp add qmd --command "qmd mcp"
hermes mcp test qmd
```

Obsidian 也可以挂（需要 Local REST API 插件）：

```bash
hermes mcp add obsidian --url http://localhost:27123/mcp
```

**不必为了记忆系统专门搭 MCP**。Hermes 本来就能 `read_file` / `search_files`，直接用更快。

---

## 第五步：验证

```bash
python scripts/amk.py lint  --vault "$VAULT"
python scripts/amk.py stats --vault "$VAULT"
python scripts/amk.py boot  --vault "$VAULT" | head -30
```

然后在 Hermes desktop 里开一个新会话，问：

> 我的记忆库里都记了什么？说一下结构。

合格的回答会：说出 `memory/` 下的目录结构、指出 L0 在哪、**不编造**具体文件内容（除非它真的读了）。

最后一条才是真验收 —— 前面全是形式检查。

---

## 附录：其他智能体（仅供参考）

方法本身不绑定 Hermes，L1/L2/L3 在任何客户端都一样，只有 L0 的落点不同：

| 客户端 | L0 放哪 | 备注 |
|---|---|---|
| Claude Code | `CLAUDE.md`（用户级 / 项目级） | 支持 `@import`，适合引 L1 摘要 |
| Codex CLI | `AGENTS.md`（`~/.codex/` + 项目根） | 用 shell 工具读 L1 |
| Cursor | `.cursor/rules/*.mdc`（`alwaysApply: true`） | 别把 L1 也设成 alwaysApply |
| 其他 | system prompt 最前面 | 用 `amk.py boot` 生成的上下文包 |

`amk.py boot` 输出的是纯 Markdown 上下文包，塞给哪个客户端都能用：

```bash
python scripts/amk.py boot --vault ~/my-vault --out context.md
```
