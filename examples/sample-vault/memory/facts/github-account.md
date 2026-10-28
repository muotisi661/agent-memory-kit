---
tags:
  - fact
  - config
date: 2026-09-15
verified: 2026-10-14
---

# GitHub 账号与仓库

## 账号

- 用户名：`example-user`
- 邮箱：`example@example.com`（git commit 用）
- 认证方式：SSH key（`~/.ssh/id_ed25519`），不用密码

## 常用仓库

| 仓库 | 用途 | 备注 |
|---|---|---|
| `example-user/notes` | 主知识库的公开镜像 | 私有库在本地，不推 |
| `example-user/site` | 静态站 | GitHub Pages，子路径部署 |

## 验证凭据是否可用

不要凭记忆判断"我应该能推"。实测：

```bash
ssh -T git@github.com          # 应返回 Hi <username>!
git -C <repo> push --dry-run   # 检查权限
```

## 提交规范

- commit message 用中文，一句话说清"改了什么"
- 不提交 `.env`、凭据、vault 的 `.smart-env/`

## 相关文件

- [[system-config]]

---

*创建: 2026-09-15 · 最后更新: 2026-10-14*
