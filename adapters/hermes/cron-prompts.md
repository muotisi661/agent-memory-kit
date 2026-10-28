# Hermes cron 提示词模板（4 个维护任务）

每个任务只干一件事，权限尽量单向（只读或只写）。**双向权限的任务最容易搞坏记忆库。**

注册方式：

```bash
hermes cron add --name "记忆同步" --cron "15 */2 * * *" --prompt "<见下>"
```

或者用 `cronjob_manage` 工具，`action=create`。

---

## 任务 A · 会话同步（只写）

频率：`15 */2 * * *`

```markdown
任务：把最近有价值的对话整理成记忆摘要

限制：
- 只使用 session_search、read_file、search_files、write_file
- 只允许新建文件，不要移动、删除、重命名任何已有文件
- 不要修改 memory/facts/、memory/user-profiles/、kernel/ 下的内容

## 🚫 保护白名单（绝对不能移动/删除）
- kernel/  memory/  archive/  skills/  index.md  changelog.md

步骤：
1. 浏览最近的对话会话
2. 跳过：简短问候、纯测试、没有结论的对话
3. 为每个有价值的会话写一份摘要到 memory/session-notes/YYYY-MM-DD-主题.md
   只记录：做了什么、为什么这么决定、留下了什么坑
   不要复制完整对话，不要写"用户问…我回答…"的流水账
4. 如果这次对话产生了新的"事实级"结论（不是过程），
   追加到 memory/facts/ 对应文件，没有对应文件就新建
5. 报告：处理了 N 个会话，写入 M 个文件
```

---

## 任务 B · 记忆体检（只读）

频率：`5 3 * * *`

```markdown
任务：记忆库体检，只报告不修改

限制：
- execute_code 不可用，用 terminal 代替
- 只使用 terminal、read_file、search_files
- 不要修改任何文件

步骤：
1. cd 到 agent-memory-kit 目录，运行：
   python scripts/amk.py lint --vault "<VAULT>"
   python scripts/amk.py stats --vault "<VAULT>"
2. 从 lint 输出里提取：错误数、警告数、L0 占用率
3. 如果占用率 > 85%，在报告里明确写"建议执行 amk.py promote"
4. 抽查索引：如果 vault 下有 .smart-env/multi/，抽一个 .ajson 检查 vec 是否为空
5. 报告 <300 字符：错误数 / 警告数 / L0 占用率 / 需要人工处理的事项
6. 报告写入 archive/reports/lint-YYYY-MM-DD.md，只保留最近 8 份
```

---

## 任务 C · 整理去重（读写，必须带白名单）

频率：`40 23 * * *`

```markdown
任务：合并高相似度文件、补全缺失标签

限制：
- execute_code 不可用，用 terminal
- 只使用 terminal、read_file、search_files、write_file

## 🚫 保护白名单（绝对不能移动/删除/重命名）
- kernel/           L0 内核
- memory/           记忆本体
- archive/          归档
- scripts/          脚本
- skills/           skill 目录
- index.md          主索引
- changelog.md      变更日志

## 允许的操作
1. 只处理 memory/ 之外的普通笔记目录
2. 文件相似度 > 80% 的文件对：合并到更完整的一份，删掉另一份
3. 对没有 tags 字段的文件补标签（不要动已有标签）
4. 合并后必须全文搜索旧文件名，更新所有 wikilink 引用

## 报告
写入 archive/reports/整理报告_YYYY-MM-DD.md，内容包括：
扫描文件数、发现的高相似对、合并了几对、删了几个、标签补充数
```

> ⚠️ 真实事故：整理任务把 `agent-memory/` 当成"待分类笔记"全部移进 `wiki/entities/`，
> 系统文档看起来完好，实际记忆已经读不到了。白名单是唯一可靠的防御。

---

## 任务 D · 占用率监控（只读）

频率：`0 9 * * *`

```markdown
任务：检查 L0 占用率并给出建议

限制：
- memory 工具在 cron 中不可用，不要调用
- 只使用 terminal、read_file
- 不要修改任何文件

步骤：
1. 从日志读占用率：
   grep "Memory at" ~/AppData/Local/hermes/logs/agent.log | tail -3
   提取 X/Y 格式的数字，算百分比
2. 如果日志里没有，直接算文件大小：
   read_file ~/AppData/Local/hermes/memories/MEMORY.md 与 USER.md，
   统计正文字符数（不含 frontmatter），上限 2200
3. 输出 <200 字符：
   - 占用率
   - <80% → "记忆占用正常"
   - 80-90% → "偏高，本周内建议执行 amk.py promote"
   - >90% → "紧急：下次交互式会话优先执行 amk.py promote"
4. 不要尝试自己执行迁移（无人监督环境下改记忆风险太高）
```

---

## 为什么定时任务不该自己迁移记忆

它在无人监督下运行，一旦判断失误（比如把"不要把密码写进记忆"这条安全约束下沉了），
代价是之后所有会话都少了这条保护，而且没人会发现。

**分工**：机器负责提醒，人（或交互式会话）负责决策。
