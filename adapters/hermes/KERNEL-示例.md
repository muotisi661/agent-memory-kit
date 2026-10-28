# MEMORY.md 示例（精简后的 L0）

> 这是 Hermes `memories/MEMORY.md` 迁移完成后大概的样子。
> 条目之间用 `§` 分隔（Hermes 的分隔符）。目标：占用率 60% 左右。

```text
用户：中文，Windows 11，独立开发者。沟通极简，期望直接行动不要多问。输出必须中文，去 AI 痕迹，一次成功不反复确认。
msys/git-bash 的 rm 直接永久删除，不进回收站。执行前必须确认路径。
不要把密码/token/API key 写进任何记忆文件或 git 仓库。
知识库：~/Obsidian Vault/
系统配置：memory/facts/system-config.md
GitHub 账号：memory/facts/github-account.md
§
代码注释用中文，文件名中英混合。改配置优先直接覆盖旧文件，不要并行保留两套。
§
本地模型只能跑 7B Q4（RTX 3060 12G）。国内网络下 ollama pull 会 SSL 失败，需手动下 GGUF 再 ollama create 导入。
§
历史迁移记录：memory/facts/memory-migration-2026-10.md
```

## 说明

- 前 3 条是**约束类** —— 说错就会造成实际损失，永远留在 L0
- 第 4-6 条是**路径/指针** —— 一行说得清，但指向的细节在 L1
- 后两条是**环境事实** —— 短、稳定、不记住就会重复踩坑
- 超过 200 字符的条目（配置详情、操作步骤、历史记录）已经全部下沉，
  在 L0 里只剩一行指针

对照自己的 MEMORY.md 检查：

- [ ] 有没有超过 200 字符的条目？→ 该下沉
- [ ] 有没有端口、密码、版本号的具体值？→ 改成"去哪查 + 怎么验"
- [ ] 每条都过了三闸门吗？只有不记住就会做错的才配留在 L0
- [ ] 占用率 < 70% 吗？→ `python scripts/amk.py stats --vault <vault>`
