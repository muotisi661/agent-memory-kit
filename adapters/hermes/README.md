# Hermes 接入片段

把下面的内容挑需要的部分贴进你的 Hermes 配置。

| 文件 | 贴到哪 | 作用 |
|---|---|---|
| `SOUL-记忆协议.md` | `~/AppData/Local/hermes/SOUL.md` 末尾 | 让智能体知道怎么用记忆 |
| `cron-prompts.md` | 各 cron job 的 prompt | 维护任务（4 个职责） |
| `KERNEL-示例.md` | 参考 `~/AppData/Local/hermes/memories/MEMORY.md` | 精简后的 L0 长什么样 |

先读 `../../docs/07-adapters.md`，那里讲了完整的接入顺序和注意事项（尤其是 MEMORY.md 迁移一定要先在临时副本上试）。
