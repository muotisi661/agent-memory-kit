# 08 · 迁移：从现有记忆搬进来

三种起点：只有一个 system prompt / 有一套内置 memory / 有一个云端记忆服务。三种都能搬。

---

## 起点 A：只有系统提示里的几段话

最简单。手工搬，10 分钟。

```bash
python scripts/amk.py init --vault ~/my-vault
```

然后逐条过一遍你现有的系统提示，按三闸门分类：

| 现有内容 | 去向 |
|---|---|
| 身份、语言、风格、禁止事项 | 留在 L0（`kernel/KERNEL.md`） |
| 具体配置、端口、路径、步骤 | 移到 `memory/facts/` 或 `memory/procedures/`，L0 留一行指针 |
| 已过时的 | 删掉 |
| 端口/密码/版本号 | 改成"去哪查 + 怎么验" |

---

## 起点 B：Hermes 内置 MEMORY.md（§ 分隔条目）

用 `amk.py promote` 自动做，它认得 `§` 分隔符。

```bash
# 1. 先看它打算怎么拆（不动文件）
python scripts/amk.py promote --vault ~/my-vault \
    --kernel ~/AppData/Local/hermes/memories/MEMORY.md --dry-run

# 2. 确认后执行
python scripts/amk.py promote --vault ~/my-vault \
    --kernel ~/AppData/Local/hermes/memories/MEMORY.md
```

它会：

- 把超过阈值的条目写成 `memory/facts/<slug>.md`（保留完整原文）
- 在原位置替换成一行指针
- 打印前后占用率

**执行后必须人工过一遍生成的 facts 文件** —— 自动切分不知道语义，可能把两条不相关的内容并进一个文件。命名和分类要人调。

### 批量迁移流程（实测从 95% 降到 28%）

```python
# 1. 识别可迁移条目
#    特征：含"详见/配置/工具/规范/模型/提供方/端口"等关键词，或长度 >150 字符
# 2. 每条建一个 memory/facts/<topic>.md，内容含原条目全文 + frontmatter
# 3. 原条目 replace 成一行指针
# 4. 处理完统一跑 lint + 索引更新
```

**保留原则**：

- ✅ 必须留在 L0：安全红线、关键路径、唯一标识（账号、仓库名）、硬性偏好
- ❌ 下沉：详细步骤、配置值清单、工具用法、历史记录

---

## 起点 C：云端记忆服务（API / MCP）

**先导出，再迁移，最后才敢停服务。**

```
1. 用多个关键词组合查询，把结果全部落地成文件
   queries = ["用户偏好 配置 工作流", "工具 API 安装", "项目 决策", "历史 结论"]
   → 每条结果写成 memory/facts/import-<日期>-<序号>.md
2. 去重：同义条目标记，人工合并
3. 分类到 user-profiles / facts / procedures / session-notes
4. 挑出过三闸门的进 L0
5. 验证：lint 通过 + 抽查 5 条能读到
6. ✅ 确认本地可用之后，再考虑停用云端
```

**迁移触发信号**（出现任一，当天就搬）：

- `402 Payment Required` — 额度耗尽
- 服务商发涨价/下线公告
- 连续 3 天检索失败
- 数据无法导出（这是最该走的理由）

---

## 起点 D：从一堆散乱的笔记开始

很多人的问题是"笔记太多太乱"，不是"没有记忆"。

```bash
# 1. 先搞清楚有什么
find ~/notes -name "*.md" | wc -l
find ~/notes -name "*.md" -newermt "-90 days" | wc -l   # 最近活跃的

# 2. 只迁移"会被反复用到"的
#    判断标准：过去 3 个月你打开过 2 次以上
```

**不要全量迁移。** 一堆一年没看的笔记搬进记忆库，只会让检索变脏。先搬：
- 配置/环境（一定会再用）
- 踩坑记录（省时间最多）
- 可复用流程（copy-paste 就能用）
- 决策理由（想不起来会重复试错）

其余的留在原地，需要时 `rg` 搜一下就行。

---

## 迁移后验证清单

```bash
python scripts/amk.py lint --vault ~/my-vault
python scripts/amk.py stats --vault ~/my-vault
python scripts/amk.py boot --vault ~/my-vault | head -40
```

- [ ] L0 占用率 ≤ 70%
- [ ] 每个指针指向的文件都存在
- [ ] `facts/` 下没有明显重复（同一主题 ≤1 个文件）
- [ ] 所有文件有合规 frontmatter（`tags` 单个键、数组格式）
- [ ] 索引抽查：向量非空、维度正确
- [ ] **新会话能靠记忆答出"我在做什么项目"** ← 最终验收

最后一条才是真验收。前面都是形式检查。

---

## 迁移期间的双写

如果旧系统还在用，不要一次切断：

```
第 1 周：两边都写（旧系统为主，新系统只读验证）
第 2 周：新系统为主，旧系统只读
第 3 周：确认新系统覆盖了所有高频场景 → 停旧系统
```

**别急着删旧数据。** 归档成 `archive/legacy-<系统名>-<日期>/`，半年后没人回头找再删。
