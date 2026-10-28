# 09 · 分支：本地知识库选 Obsidian

前面八篇讲的是方法，存储层用什么都能跑。这一篇讲**具体落地到 Obsidian** 的完整操作流程 —— 什么时候该选它、装什么、怎么接、以及 Obsidian 特有的六个坑。

## 先决策：要不要上 Obsidian

| | 纯目录 | **Obsidian** |
|---|---|---|
| 智能体读写 | ✅ | ✅ |
| 人能浏览/编辑 | 要开编辑器 | ✅ 图形界面 + 图谱 |
| 手机上看记忆 | ❌ | ✅（配合同步） |
| 双向链接/反链 | 手搓 | ✅ 自动 |
| 额外依赖 | 零 | Obsidian + 2 个插件 + 端口 |
| 故障面 | 小 | 多（插件、端口、索引、同步冲突） |

**结论**：只要你需要"人也看这些记忆"，就选 Obsidian；如果只是智能体自己用，纯目录更省事，L1 层逻辑完全一样。

---

## 一、库怎么放（唯一需要想清楚的结构问题）

### ❌ 别把记忆库直接建在 vault 根

```bash
amk.py init --vault "D:/Obsidian Vault"      # 不推荐
```

`init` 会写 `index.md` 和 `changelog.md` —— 和知识库自己的主索引撞名，而且 `kernel/` `memory/` 混在一堆笔记里，人一眼看不出边界。

### ✅ 建在 vault 下的独立子目录

```bash
amk.py init --vault "D:/Obsidian Vault/memory-root"
```

```
D:/Obsidian Vault/                 ← Obsidian 库根
├── .obsidian/                     ← 配置与插件（不要提交，不要被智能体动）
│   ├── app.json
│   ├── community-plugins.json
│   └── plugins/
│       ├── obsidian-local-rest-api/
│       └── smart-connections/
├── .smart-env/                    ← Smart Connections 的向量索引（不同步、不提交）
├── .trash/                        ← Obsidian 的回收站
├── 日记/ 项目/ 笔记/               ← 你自己的人类知识库
└── memory-root/                   ← ⭐ 四层记忆库（智能体的地盘）
    ├── kernel/
    │   ├── KERNEL.md
    │   └── user.md
    ├── memory/
    │   ├── user-profiles/
    │   ├── facts/
    │   ├── procedures/
    │   ├── session-notes/
    │   └── context-snapshots/
    ├── archive/
    ├── index.md
    └── changelog.md
```

**边界规则**（写进 SOUL 或 AGENTS 提示词）：

- 智能体默认**只读写 `memory-root/`**，不碰人类笔记目录
- `.obsidian/`、`.smart-env/`、`.trash/` 永不进入整理任务的处理范围
- `memory-root/` 永不被"自动整理/去重"任务移动

### gitignore

```gitignore
.obsidian/workspace.json      # 窗口布局，各端不同
.smart-env/                   # 向量索引，各端重建
.trash/
*.lock
```

其余都可以进 git —— 记忆库能被 diff、能回滚，是这套方法的一半价值。

---

## 二、初始化命令

```bash
cd ~/agent-memory-kit

# 1. 建结构
python scripts/amk.py init --vault "D:/Obsidian Vault/memory-root"

# 2. 填 L0（用编辑器或 Obsidian 打开）
#    kernel/KERNEL.md  —— 身份锚点 / 硬性约束 / 关键路径 / 指针

# 3. 体检
python scripts/amk.py lint --vault "D:/Obsidian Vault/memory-root"
```

然后在 Obsidian 里 `打开文件夹作为库` → 选 `D:/Obsidian Vault`（**选 vault 根，不是 memory-root**）。
记忆库会作为普通文件夹出现在左侧文件树里，能直接点开编辑 —— 这正是要的效果。

---

## 三、装两个插件（必须）+ 三个可选

### 1. Local REST API —— 让 Hermes 能读写 vault

**作用**：暴露 HTTP/MCP 接口，智能体不用 shell 就能读写 vault。

安装（社区市场搜 `Local REST API`，或手动）：

```bash
cd "D:/Obsidian Vault/.obsidian/plugins"
mkdir -p obsidian-local-rest-api && cd obsidian-local-rest-api
curl -sL -o main.js     "https://github.com/coddingtonbear/obsidian-local-rest-api/releases/latest/download/main.js"
curl -sL -o manifest.json "https://github.com/coddingtonbear/obsidian-local-rest-api/releases/latest/download/manifest.json"
curl -sL -o styles.css  "https://github.com/coddingtonbear/obsidian-local-rest-api/releases/latest/download/styles.css"
```

启用后：设置 → Local REST API → 复制 **API Key**。

**验证**（这一步不能省，见坑 3）：

```bash
# 端口：27123 HTTP / 27124 HTTPS，插件设置里可改
curl -s -H "Authorization: Bearer <API_KEY>" http://127.0.0.1:27123/vault/ | head -c 200
# 200 且有 JSON = 通；000 = Obsidian 没开或插件没启用
```

接进 Hermes：

```bash
hermes mcp add obsidian --url http://127.0.0.1:27123/mcp \
  --header "Authorization: Bearer <API_KEY>"
hermes mcp test obsidian
```

> API Key 是易腐值：**不要写进记忆文件**，写"在 Obsidian 设置 → Local REST API 里，用 curl 验证"。

### 2. Smart Connections —— Obsidian 内的语义检索（L2）

**作用**：在 Obsidian 里直接看到"与当前笔记语义相关的笔记"，是 L2 的图形化版本。

配置本地嵌入（不花钱、不上传）：

1. 装 Ollama，拉嵌入模型：`ollama pull nomic-embed-text`（约 274MB，国内可能 SSL 失败，见坑 6）
2. **关键**：Smart Connections 有两个配置文件，`smart_env.json` 覆盖 `data.json`：

```jsonc
// D:/Obsidian Vault/.smart-env/smart_env.json    ← 权威，必须改这个
{
  "smart_sources": {
    "embed_model": {
      "adapter": "ollama",
      "ollama": { "model": "nomic-embed-text", "base_url": "http://localhost:11434" }
    }
  },
  "embedding_models": { "default_model_key": "ollama#nomic-embed-text" }
}
```

3. 重启 Obsidian → Smart Environment 设置里 Reset data → 等重新索引

### 3~5. 可选插件

| 插件 | 用途 | ⚠️ 注意 |
|---|---|---|
| Dataview | 用查询统计记忆库（如"列出所有 pitfall 标签"） | 只读，安全 |
| Templater | 新建记忆文件时套模板 | 模板别写死 today 之外的变量 |
| Linter | 自动格式化 frontmatter | **会重排 tags**，必须关掉 tags 排序，否则每次都和记忆规范打架 |

---

## 四、L2 索引：两条路选一条

### A. qmd（推荐）—— 命令行/ MCP，混合检索

```bash
cd "D:/Obsidian Vault"
qmd collection add vault --pattern "**/*.md"     # 一次
qmd update                                       # 增量重建（新增/改动）
qmd embed                                         # 生成向量（CPU 密集，放后台）
qmd query "嵌入模型 配置 端口"                     # 使用
```

实测对比（同一台机器、同一份 215 文件的知识库）：

| | qmd | Smart Connections |
|---|---|---|
| 检索质量 | BM25 + 向量混合，命中更稳 | 纯向量 |
| 智能体能调用 | ✅ CLI + MCP | ❌（只能在 Obsidian UI 里用） |
| 需要额外服务 | 无 | Ollama |
| 索引位置 | `~/.cache/qmd/index.sqlite` | `<vault>/.smart-env/` |

**结论**：智能体用 qmd，人用 Smart Connections，两个可以同时装 —— 它们各建各的索引，互不干扰。

### B. 只查不建：先用 `search_files`

Hermes 自带 `search_files`（ripgrep）。记忆库只有几百个文件时，精确关键词搜索比向量检索更快更准：

```bash
rg -n "相变片|温度" "D:/Obsidian Vault/memory-root/memory/"
```

**向量检索的定位是"记不清关键词时的兜底"**，不是默认路径。别为了"看起来智能"给每个查询都套一层向量。

---

## 五、Obsidian 特有的六个坑

### 坑 1 · 重命名文件会悄悄打断指针

Obsidian 重命名文件时，会自动更新 `[[wikilink]]`，但**不会**更新 L0 里的裸路径指针：

```
未处理前，kernel/KERNEL.md 里是：
  系统配置：memory/facts/system-config.md

你在 Obsidian 里把文件改名成 系统配置.md 之后：
  → wikilink 自动更新了
  → 上面这一行指针还指着旧路径 → 断了
```

**处理**：重命名后立刻体检

```bash
python scripts/amk.py lint --vault "D:/Obsidian Vault/memory-root"
# 输出：kernel/KERNEL.md: 指针失效 → memory/facts/system-config.md
```

`lint` 对裸路径指针和 wikilink 都做死链检查，这是它比 `rg` 值钱的地方。

### 坑 2 · Linter / 格式化插件会重排 frontmatter

Obsidian 的 Linter 插件（以及某些模板插件）会：

- 把 `tags` 块数组压成单行字符串 → Obsidian 标红、智能体的规范检查失败
- 重排字段顺序
- 顺手把 `verified` 日期改成今天（有的配置会）

**处理**：

```bash
python scripts/amk.py lint --vault "$VAULT" --fix   # 安全修复 tags 格式
```

并在 Linter 配置里关掉：`Sort YAML keys`、`Format tags in body`、`Format tags in YAML`。

### 坑 3 · 端口通了 ≠ 接口能用；索引建了 ≠ 向量有内容

实测案例（本机真实数据）：

```
qmd status
  Total:    215 files indexed
  Vectors:  0 embedded
  Pending:  214 need embedding
```

文件全在索引里，**向量数是 0** —— 搜索仍然"能返回结果"（走纯关键词），你会以为一切正常。直到某天需要语义召回时才发现它一直是空的。

**验证方法**：

```bash
qmd status | grep -E "Vectors|Pending"        # Pending 应该是 0
qmd query "一个只有语义相关、字面不匹配的查询"   # 能命中才算通
```

Smart Connections 同理，抽查 `.smart-env/multi/*.ajson` 里的 `vec` 是否非空、维度是否为 768。

### 坑 4 · Obsidian 的删除进回收站，智能体的删除是永久的

| 操作方 | 删除行为 |
|---|---|
| 你在 Obsidian 里删 | 进 `.trash/`，可恢复 |
| 智能体用 `rm` | **永久删除**（git-bash/MSYS 下不进回收站） |

**处理**：智能体侧删除前必须 `ls` 确认路径，且优先用 `amk.py archive`（移到 `archive/YYYY-MM/`）而不是删。

### 坑 5 · 自动整理任务会吃掉 memory-root

这是本 kit `docs/06` 里最贵的一条教训，在 Obsidian 场景下更容易踩：vault 里本来就有一堆笔记，一个"帮你分类去重"的定时任务看不出 `memory-root/` 和普通笔记的区别，会把记忆文件搬进 `wiki/entities/` 之类的目录。

症状：目录结构完好，文件不见了。

**处理**：任何整理类提示词顶部写死白名单：

```markdown
## 🚫 保护白名单（绝对不能移动/删除/重命名）
- memory-root/     记忆本体
- .obsidian/       Obsidian 配置
- .smart-env/      向量索引
- archive/
```

再加一层保险：vault 进 git，出事 `git checkout`。

### 坑 6 · 国内网络的两个卡点

| 卡点 | 症状 | 解法 |
|---|---|---|
| `ollama pull` | SSL 证书验证失败（registry.ollama.ai 被干扰） | 手动从 HuggingFace 下 GGUF → `ollama create` 导入；或配代理 `HTTPS_PROXY=http://127.0.0.1:7890` |
| `better-sqlite3` | `NODE_MODULE_VERSION 137 vs 147` | Node 升级后原生模块失效，`npm rebuild better-sqlite3` |

第二条是 qmd 最常见的罢工原因，症状看起来像 qmd 坏了，实际上是 Node 版本变了：

```bash
cd "$(npm root -g)/@tobilu/qmd" && npm rebuild better-sqlite3
```

---

## 六、人和智能体同时改一个库的协作规则

写进 SOUL 或项目 AGENTS 提示词：

```markdown
## Obsidian 协作规则

- 记忆库路径：D:/Obsidian Vault/memory-root/
- 只用 read_file / write_file / search_files 读写；不要动 .obsidian/、.smart-env/
- 用户可能同时在 Obsidian 里编辑同一个文件：写之前先读一遍，不要凭记忆覆盖
- 新建记忆文件用 `YYYY-MM-DD-主题.md`（session-notes）或 `主题.md`（facts）
- 改名/删除后必须跑 lint，检查指针与 wikilink
- 不要用 Obsidian 自身的"整理/重命名"能力代替 amk.py 的归档
```

**冲突处理**：如果用户在 Obsidian 里改过而你手上有旧版本 —— **以磁盘上的当前内容为准**，重新读取后再改，绝不 `write_file` 覆盖未读过的文件。

（Hermes 的 `write_file` 本身就有这个保护：文件被外部改动过会拒绝写入并要求重读。别绕过它。）

---

## 七、多端同步

| 方案 | 适合 | 注意 |
|---|---|---|
| **git** | 有技术背景、要版本历史 | `.obsidian/workspace.json`、`.smart-env/` 加进 gitignore |
| **Syncthing** | 多设备、免服务器 | 排除 `.smart-env/`（各端各自建索引） |
| **Obsidian Sync** | 官方、省心 | 付费；同步 `.obsidian/` 有时会带坏配置 |
| **iCloud / OneDrive** | 顺手 | ⚠️ 同步盘 + 编辑器同时写 = 冲突副本；不建议放自动运行的记忆库 |

**冲突副本识别**：文件名出现 `xxx (conflicted copy).md` 或 `xxx.sync-conflict-*.md` —— 这类文件不要直接删，先 `diff` 一下，可能包含用户的真改动，合并后归档。

---

## 八、验收清单

```bash
VAULT="D:/Obsidian Vault/memory-root"

python scripts/amk.py lint  --vault "$VAULT"     # 0 错误
python scripts/amk.py stats --vault "$VAULT"     # L0 占用 < 70%
qmd status | grep Vectors                        # 向量数 > 0（用了 qmd 的话）
```

- [ ] Obsidian 能打开 vault，`memory-root/` 出现在文件树里
- [ ] `curl -H "Authorization: Bearer <KEY>" http://127.0.0.1:27123/vault/` 返回 200
- [ ] `hermes mcp test obsidian` 通过
- [ ] 在 Obsidian 里新建一条笔记，智能体能 `search_files` 搜到
- [ ] 智能体写一条记忆，Obsidian 里立即可见（无需重启）
- [ ] 重命名一个记忆文件后，`lint` 能报出断掉的指针
- [ ] 开一个新 Hermes 会话，它能说出记忆库结构（而不是编造）

最后一条是真验收，前面都是形式检查。
