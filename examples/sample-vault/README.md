# 样例记忆库（脱敏）

一个完整的四层记忆库长什么样。所有人名、地址、端口都是编的。

```bash
# 直接体检
cd ../..
python scripts/amk.py lint --vault examples/sample-vault
python scripts/amk.py stats --vault examples/sample-vault
python scripts/amk.py boot --vault examples/sample-vault | head -40

# 试试下沉（copytree 到临时目录再跑，别改这个样例）
cp -r examples/sample-vault /tmp/sv
python scripts/amk.py promote --vault /tmp/sv --target 40 --dry-run
```

## 看点

| 文件 | 看什么 |
|---|---|
| `kernel/KERNEL.md` | L0 该有多短、指针长什么样 |
| `memory/facts/lancedb-踩坑.md` | 一个合格的事实+坑记录：症状、原因、解法、通用教训 |
| `memory/facts/system-config.md` | 易腐值怎么写（端口不写值，写"怎么实测"） |
| `memory/procedures/部署静态站.md` | 流程类记忆：步骤 + 故障对照表 |
| `memory/session-notes/2026-10-12-...md` | 决策记录要写"为什么"，不只写"选了什么" |

注意 `KERNEL.md` 里的 L0 只占 40% 左右 —— **不要塞满**。留的空间是给未来的高价值约束的。
