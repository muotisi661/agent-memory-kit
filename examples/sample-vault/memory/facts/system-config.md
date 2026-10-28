---
tags:
  - config
  - fact
date: 2026-09-10
verified: 2026-10-14
---

# 系统与工具配置

## 机器

- Windows 11 + WSL2，日常在 git-bash 里操作
- Ryzen 5 7600 / RTX 3060 12G / 32G DDR5
- 本地能跑的最大模型：7B Q4（再大就掉出显存）

## 工具链

- 编辑器：VS Code，终端用 Windows Terminal
- 知识库：Obsidian，库在 `D:/Obsidian Vault/`
- 语义检索：qmd（`qmd query`），索引在 vault 根目录 `.qmd/`
- 版本控制：git + GitHub（账号在 `memory/facts/github-account.md`）

## 代理

- 端口见代理客户端当前配置，实测：`curl -x http://127.0.0.1:7890 -sI https://github.com`
- 不要凭记忆写端口号 —— 换过三次了

## 踩过的坑

- **MSYS 的 `rm` 不进回收站**，直接永久删除。删之前必须 `ls` 确认路径。
- `python3` 在这个环境不存在，只有 `python`。
- MSYS 输出的 `/d/...` 路径不能被 Python `open()` 直接读，先 `cygpath -w` 转换。
- 写临时文件别用 `/tmp`（会被解析成 `\tmp`），用项目下的 `tmp/` 目录。

## 相关文件

- [[老李]]
- `memory/facts/lancedb-踩坑.md`

---

*创建: 2026-09-10 · 最后更新: 2026-10-14*
