# Agent Memory Kit · 给智能体一套不会忘事的本地记忆系统

> 一个纯文件、无云端依赖的四层记忆方法，为 **Hermes desktop** 而写。
> A file-based, vendor-neutral memory system for long-running agents.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![No Cloud](https://img.shields.io/badge/cloud-none-brightgreen)]()
[![Target](https://img.shields.io/badge/target-Hermes%20desktop-blue)]()

---

## 为什么需要它

智能体的记忆一般死在三个地方：

1. **上下文窗口塞不下** — 会话一长就压掉早期内容，用户说过的话第二次还得再说一遍。
2. **内置 memory 被当垃圾桶** — 键值记忆只有 2KB 左右的硬预算，塞满后每天都要清理，清理就得做取舍，取舍做不好就丢关键信息。
3. **云端记忆服务会走** — 付费额度耗尽、API 改版、涨价、下线。哪天返回 402，你的"记忆"就归零了。

这套方法的答案是：**把记忆分层，全部落在你自己硬盘上的 Markdown 文件里。**

- 常驻的那一小块（2KB）只放"不知道就会做错事"的东西，每次会话无条件注入。
- 其余全部沉到文件系统，需要时精确读取。
- 关键词记不准时，用本地语义索引兜底。
- 云端彻底不需要。

在真实的日常使用中跑了四个月、跨会话 300+ 次：内置记忆占用从 95% 降到 28%，同时记忆总量增长了 10 倍。

---

## 四层模型

```
┌──────────────────────────────────────────────────────────────┐
│ L0  KERNEL 内核记忆          每次会话 100% 注入 · ≤2200 字符   │
│     身份锚点 / 硬性约束 / 环境关键路径 / 指针                  │
│     载体：Hermes 的 memories/MEMORY.md + USER.md + SOUL.md     │
└──────────────────────────┬───────────────────────────────────┘
                           │ 指针 ("X：memory/facts/x.md")
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ L1  VAULT 结构化知识库       按需读取 · 无上限                 │
│     Markdown + YAML frontmatter，按用途分目录                  │
│     user-profiles/ facts/ procedures/ session-notes/          │
└──────────────────────────┬───────────────────────────────────┘
                           │ 索引
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ L2  INDEX 语义索引           模糊召回 · 本地向量               │
│     qmd / Smart Connections / 任何本地 embedding               │
└──────────────────────────┬───────────────────────────────────┘
                           │ 归档
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ L3  ARCHIVE 原始归档         仅回溯 · 从不注入                 │
│     会话日志、cron 输出、历史快照                              │
└──────────────────────────────────────────────────────────────┘
```

关键不在"分四层"，而在**层间怎么流动**：

| 方向 | 触发条件 | 动作 |
|---|---|---|
| 上升 L1→L0 | 跨会话必需 **且** 写错会造成实际损失 **且** 单行能写完（≤120 字符） | 写成一行内核条目 |
| 下沉 L0→L1 | L0 占用 >85% **或** 条目 >200 字符 **或** 含具体配置值/步骤 | 拆到 L1 文件，L0 只留路径指针 |
| 丢弃 | 易腐值 / 一次性状态 / 可从代码推导 / 任务进度 | 不写进任何层 |
| 召回 | 遇到指针 **或** 关键词记不准 | 读 L1 精确路径，读不到再走 L2 |

> 上升那三条必须同时成立，缺一条就不配进 L0 —— 这就是后文反复提到的**三闸门**。

完整规则见 [docs/03-promotion-demotion.md](docs/03-promotion-demotion.md) —— **这一篇是整套方法的核心，别跳过。**

---

## 5 分钟上手

```bash
git clone https://github.com/muotisi661/agent-memory-kit.git
cd agent-memory-kit

# 1. 在你的知识库里初始化四层结构
python scripts/amk.py init --vault "D:/Obsidian Vault/memory-root"

# 2. 体检
python scripts/amk.py lint --vault "D:/Obsidian Vault/memory-root"

# 3. 生成会话启动上下文包
python scripts/amk.py boot --vault "D:/Obsidian Vault/memory-root"
```

`init` 之后：

```
memory-root/
├── kernel/
│   ├── KERNEL.md            # L0：内核记忆（硬上限 2200 字符）
│   └── user.md              # L0：用户最小集
├── memory/
│   ├── user-profiles/       # L1：完整画像
│   ├── facts/               # L1：事实、配置、踩坑
│   ├── procedures/          # L1：可复用流程
│   ├── session-notes/       # L1：会话摘要
│   └── context-snapshots/   # L1：项目状态快照
├── archive/                 # L3：原始归档
├── index.md                 # 总索引
└── changelog.md             # 变更日志
```

然后把记忆协议贴进 Hermes 的 `SOUL.md`，详见 [docs/07-adapters.md](docs/07-adapters.md)。
现成的片段：**[adapters/hermes/SOUL-记忆协议.md](adapters/hermes/SOUL-记忆协议.md)**

---

## CLI

单文件、零第三方依赖、Python 3.9+。

| 命令 | 作用 |
|---|---|
| `amk.py init --vault PATH` | 初始化四层结构 + 模板（幂等，不覆盖已有文件） |
| `amk.py lint --vault PATH` | 体检：frontmatter、标签、死链、空壳、空向量、L0 占用率；`--fix` 安全修 frontmatter |
| `amk.py boot --vault PATH` | 生成可直接注入的上下文包（L0 全文 + 索引清单） |
| `amk.py promote --vault PATH` | 把过长的 L0 条目下沉到 L1，替换成指针（`--dry-run` 预览） |
| `amk.py stats --vault PATH` | 各层文件数 / 字符数 / 占用率 / 最近更新 |
| `amk.py archive --vault PATH --file F` | 一次性内容归档到 `archive/YYYY-MM/` |

```bash
# 典型的维护节奏
amk.py lint --vault "$VAULT"          # 每周
amk.py promote --vault "$VAULT"       # L0 到 85% 时
amk.py boot --vault "$VAULT" --query "上次那个部署脚本放哪了"
```

`promote` 的安全设计：

- 含「必须/禁止/安全/密码/删除」等**保护词且不超过 200 字**的条目**绝不下沉**
- 保护词但超长的条目 → 只警告，交给人判断
- 支持 `--dry-run`，先看计划再动手
- 下沉前自动记录 `changelog.md`

---

## 这套方法解决过的真实问题

详见 [docs/06-antipatterns.md](docs/06-antipatterns.md)，每条都是踩出来的：

1. **"文档写了架构" ≠ "系统在跑"** — 技能/文档描述得再完整，也必须实测路径下真有文件。
2. **自动整理任务会吃掉记忆目录** — 任何"自动归类/去重"的定时任务都必须配白名单，否则它会把 `memory/` 当普通笔记挪走。
3. **索引"成功"但向量是空的** — 嵌入配置错了也返回成功，`vec: []` 是假成功，必须抽查维度。
4. **易腐值写死就废** — 端口、密码、版本号三个月后全错，而且会被后续会话当真。
5. **L0 当垃圾桶 → 满了 → 什么都记不住** — 硬预算会逼你做取舍，所以取舍规则必须提前定，而不是满了再想。
6. **云端记忆 402** — 本地可迁移性不是洁癖，是备份方案。

---

## 和别的方案比

| | 内置键值记忆 | 云端记忆服务 | 向量数据库 | **本方案** |
|---|---|---|---|---|
| 容量 | ~2KB | 服务商定 | 大 | L0 2.2KB + L1 无限 |
| 成本 | 免费 | 按量付费 | 自建/托管 | 免费 |
| 隐私 | 本地 | 上传 | 看部署 | 全本地 |
| 可读可改 | 否 | 否 | 否 | **纯 Markdown，可 diff** |
| 换模型/换工具 | 被绑定 | 被绑定 | 部分 | **文件跟着你走** |
| 人肉可维护 | 否 | 否 | 否 | **Obsidian 直接打开** |

它不是替代向量库，而是把向量库降级成**可选的召回兜底**：
90% 的记忆访问是"我知道它在哪，去读那个文件"，只有剩下 10% 才需要模糊搜索。

---

## 它不做什么

- **不提供记忆服务**。没有数据库、没有守护进程、没有 API。就是一个目录加一个 CLI。
- **不做自动总结**。什么时候记、记什么，由智能体按 `docs/02` 的协议判断。自动总结会往记忆里灌噪音。
- **不绑定 Hermes**。L0 放哪各家不同（Hermes 用 `MEMORY.md`，Claude Code 用 `CLAUDE.md`），但 L1/L2/L3 通用。

---

## 目录

```
docs/       方法论：架构、写入协议、升降级、启动协议、维护、反模式、接入、迁移
scripts/    amk.py 单文件 CLI
adapters/   Hermes desktop 接入片段：SOUL 协议、cron 提示词、L0 示例
examples/   脱敏样例 vault，可直接 lint 跑通
```

建议阅读顺序：`README` → `docs/01` → `docs/03` → `docs/02` → `docs/07` → 其余按需。

## License

MIT。方法随便用。唯一需要按自己习惯调的是升降级阈值（`docs/03` 文末有推荐值）。
