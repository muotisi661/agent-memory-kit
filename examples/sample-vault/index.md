---
tags:
  - system
  - reference
---

# 记忆库索引

## 结构

```
kernel/            L0 内核记忆（每次注入，≤2200 字符）
memory/
├── user-profiles/   完整用户画像
├── facts/           事实、配置、踩坑
├── procedures/      可复用流程
├── session-notes/   会话摘要
└── context-snapshots/ 项目状态
archive/           L3 原始归档
```

## 规则速查

| 场景 | 动作 |
|---|---|
| 跨会话必需 + 写错有损失 + 一行能写完 | 进 kernel/ |
| 其余有价值的 | 写 memory/ 对应目录，kernel 留一行指针 |
| 端口/密码/版本号 | 只记「去哪查 + 怎么验」 |
| 任务进度/一次性状态 | 不写，靠会话归档 |

详见 docs/02-write-protocol.md 与 docs/03-promotion-demotion.md。

---

*创建: 2026-10-28*
*最后更新: 2026-10-28*
