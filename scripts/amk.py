#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
amk.py — Agent Memory Kit 命令行工具

单文件、零第三方依赖、Python 3.9+。
命令：init / lint / boot / promote / stats / archive

设计原则：所有操作都是幂等的，任何会改动文件的操作都支持 --dry-run。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

# ---------------------------------------------------------------- 常量

DEFAULT_LIMIT = 2200          # L0 硬上限（字符）
DEFAULT_TARGET = 60           # promote 的目标占用率
MAX_LINE = 120                # L0 单行长度线
PROMOTE_LEN = 200             # 单条超过这个长度就该下沉

KERNEL_DIR = "kernel"
MEMORY_DIR = "memory"
L1_SUBDIRS = [
    "user-profiles",
    "facts",
    "procedures",
    "session-notes",
    "context-snapshots",
]

# 标准标签词表（lint 用来提醒，不强制失败）
CANON_TAGS = {
    "user", "profile", "config", "fact", "workflow", "procedure",
    "project", "decision", "pitfall", "archive", "reference", "system",
}

# 易腐值：出现这些就说明在记录会变的值
PERISHABLE_RE = re.compile(
    r"(端口|password|passwd|密码|token|api[_ ]?key|密钥|secret|"
    r"v\d+\.\d+\.\d+|localhost:\d+|127\.0\.0\.1:\d+|:\d{2,5}\b)",
    re.IGNORECASE,
)
# 保护类：包含这些的条目绝不自动下沉
PROTECT_RE = re.compile(
    r"(必须|禁止|绝不|绝对|不要|安全|红线|删除|rm |rm-|凭据|隐私|泄露)"
)
STEP_RE = re.compile(r"(^\s*\d+\.\s|^\s*[-*]\s|\n\s*\d+\.\s)", re.MULTILINE)
POINTER_RE = re.compile(r"(详见|见 |参见|部署在|位于)\s*[`\[]?([\w\-./]+\.md)")

C_RESET, C_RED, C_YEL, C_GRN, C_DIM, C_BOLD = (
    "\033[0m", "\033[31m", "\033[33m", "\033[32m", "\033[2m", "\033[1m"
)


def color(s: str, c: str, enabled: bool) -> str:
    return f"{c}{s}{C_RESET}" if enabled else s


def use_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


# ---------------------------------------------------------------- 文件读写

def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def write_text(p: Path, s: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8", newline="\n")


def md_files(root: Path, subdirs=None):
    """列出 root 下（可限定子目录）的所有 .md，跳过隐藏目录。"""
    bases = [root / d for d in subdirs] if subdirs else [root]
    out = []
    for b in bases:
        if not b.exists():
            continue
        for p in b.rglob("*.md"):
            parts = p.relative_to(root).parts
            if any(x.startswith(".") for x in parts):
                continue
            out.append(p)
    return sorted(out)


# ---------------------------------------------------------------- frontmatter

FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)


def split_frontmatter(text: str):
    """返回 (frontmatter字符串或None, 正文)。"""
    m = FM_RE.match(text)
    if not m:
        return None, text
    return m.group(1), text[m.end():]


def parse_tags(fm: str):
    """从 frontmatter 文本抽 tags（宽松解析）。返回 (tags列表, 问题列表)。"""
    problems = []
    tags = []
    lines = fm.splitlines()
    tag_key_lines = [i for i, l in enumerate(lines) if re.match(r"^tags\s*:", l)]
    if len(tag_key_lines) > 1:
        problems.append(f"重复的 tags 键（{len(tag_key_lines)} 个）")

    for idx in tag_key_lines:
        head = lines[idx]
        inline = head.split(":", 1)[1].strip()
        if inline:
            # 字符串形式：'["a","b"]' 或 "a, b"
            if inline.startswith("["):
                try:
                    tags += [str(t).strip() for t in json.loads(
                        inline.replace("'", '"'))]
                except Exception:
                    problems.append(f"tags 行不是合法数组：{inline[:40]}")
                    tags += [t.strip(" '\"[]") for t in inline.split(",") if t.strip()]
            else:
                problems.append("tags 用了单行字符串，建议改成 YAML 块数组")
                tags += [t.strip(" '\"[]") for t in inline.split(",") if t.strip()]
        else:
            # 块数组：向后读 - item
            j = idx + 1
            while j < len(lines) and re.match(r"^\s*-\s", lines[j]):
                item = lines[j].split("-", 1)[1].strip()
                if re.match(r"^[\w\-]+\s*:\s", item):
                    problems.append(f"标签里混进了键值对：{item[:40]}")
                    item = item.split(":", 1)[0]
                tags.append(item.strip(" '\""))
                j += 1

    clean = []
    for t in tags:
        t = t.strip()
        if not t:
            continue
        if t.startswith("#"):
            problems.append(f"标签带了 # 前缀：{t}")
            t = t.lstrip("#")
        if " " in t:
            problems.append(f"标签含空格：{t}")
        if not re.fullmatch(r"[a-z0-9\-_]+", t):
            problems.append(f"标签非小写英文：{t}")
        clean.append(t)
    return clean, problems


def fix_frontmatter(text: str):
    """修复常见 frontmatter 问题。返回 (新文本, 是否改动)。"""
    fm, body = split_frontmatter(text)
    if fm is None:
        return text, False
    tags, problems = parse_tags(fm)
    if not problems:
        return text, False
    # 标签里混进键值对的情况不自动修：拆错了会把 source_url 之类的字段丢掉，
    # 这类只能人工看（多半是 YAML 折行粘连）。
    if any("混进了键值对" in p for p in problems):
        return text, False

    # 丢掉所有旧的 tags 行（含块数组项），保留其它字段，再造一个干净的 tags 块
    out = []
    lines = fm.splitlines()
    i = 0
    while i < len(lines):
        if re.match(r"^tags\s*:", lines[i]):
            i += 1
            while i < len(lines) and re.match(r"^\s*-\s", lines[i]):
                i += 1
            continue
        out.append(lines[i])
        i += 1

    seen = []
    for t in tags:
        if t and t not in seen:
            seen.append(t)
    new_fm = "tags:\n" + "".join(f"  - {t}\n" for t in seen)
    others = "\n".join(out).strip()
    if others:
        new_fm += others + "\n"
    return f"---\n{new_fm}---\n{body}", True


# ---------------------------------------------------------------- init

KERNEL_TEMPLATE = """---
tags:
  - system
  - config
limit: 2200
---

# 内核记忆（L0）

<!--
每次会话无条件注入，硬上限 {limit} 字符。
只放三闸门全部通过的内容：跨会话必需 + 写错有实际损失 + 单行可表达（≤120 字符）。
超长的用 `amk.py promote` 下沉到 memory/，这里只留一行指针。
-->

## 身份锚点

<语言 / 角色 / 交互风格，2-4 行以内>

## 硬性约束

<违反会造成实际损失的事，一行一条>

## 环境关键路径

<知识库根目录、项目根目录、凭据在哪>

## 指针

<主题>：memory/facts/<文件>.md
"""

USER_TEMPLATE = """---
tags:
  - user
---

# 用户最小集（L0）

> 只放"不记住就会问错问题"的信息。完整画像在 memory/user-profiles/。

- 称呼：
- 语言：中文
- 沟通风格：
- 当前重点：
"""

INDEX_TEMPLATE = """---
tags:
  - system
  - reference
---

# 记忆库索引

## 结构

```
kernel/            L0 内核记忆（每次注入，≤{limit} 字符）
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

*创建: {today}*
*最后更新: {today}*
"""

CHANGELOG_TEMPLATE = """---
tags:
  - system
  - reference
---

# 变更日志

一行一条：日期 + 改了什么 + 为什么。

## {today}
- 初始化记忆库
"""


def cmd_init(args):
    vault = Path(args.vault).expanduser().resolve()
    limit = args.limit
    today = date.today().isoformat()
    created, skipped = [], []

    plan = {
        vault / KERNEL_DIR / "KERNEL.md": KERNEL_TEMPLATE.format(limit=limit),
        vault / KERNEL_DIR / "user.md": USER_TEMPLATE,
        vault / "index.md": INDEX_TEMPLATE.format(limit=limit, today=today),
        vault / "changelog.md": CHANGELOG_TEMPLATE.format(today=today),
        vault / "archive" / ".gitkeep": "",
    }
    for sub in L1_SUBDIRS:
        plan[vault / MEMORY_DIR / sub / ".gitkeep"] = ""

    for p, content in plan.items():
        if p.exists():
            skipped.append(p)
            continue
        write_text(p, content)
        created.append(p)

    print(f"{color('✔', C_GRN, use_color())} 记忆库：{vault}")
    print(f"  新建 {len(created)} 个文件，跳过已存在 {len(skipped)} 个")
    print(f"  L0 上限：{limit} 字符")
    print("\n下一步：")
    print(f"  1. 编辑 {vault/'kernel'/'KERNEL.md'} 填入内核记忆")
    print(f"  2. python scripts/amk.py lint --vault \"{vault}\"")
    print(f"  3. python scripts/amk.py boot --vault \"{vault}\"")
    return 0


# ---------------------------------------------------------------- lint

def collect_wikilinks(text: str):
    return re.findall(r"\[\[([^\]|#]+)", text)


def cmd_lint(args):
    vault = Path(args.vault).expanduser().resolve()
    if not vault.exists():
        print(f"vault 不存在：{vault}")
        return 2
    c = use_color()
    files = md_files(vault, [MEMORY_DIR, KERNEL_DIR])
    all_names = {p.stem.lower() for p in md_files(vault)}
    all_names |= {p.name.lower() for p in md_files(vault)}

    errors, warns, fixed, manual = [], [], [], []

    # 1) frontmatter / 标签
    for p in files:
        if p.name in (".gitkeep",):
            continue
        text = read_text(p)
        rel = p.relative_to(vault).as_posix()
        if p.stat().st_size < 120:
            warns.append(f"{rel}: 文件过短（{p.stat().st_size}B），可能是空壳")
        fm, body = split_frontmatter(text)
        if fm is None:
            errors.append(f"{rel}: 缺 frontmatter")
            continue
        tags, problems = parse_tags(fm)
        if not tags:
            warns.append(f"{rel}: 没有 tags")
        for pr in problems:
            tag = "重复" in pr or "不合法" in pr
            note = "（需人工修，--fix 不会动它）" if "混进了键值对" in pr else ""
            (errors if tag else warns).append(f"{rel}: {pr}{note}")
        odd = [t for t in tags if t not in CANON_TAGS]
        if odd:
            warns.append(f"{rel}: 非标准标签 {odd}（可用但要统一）")

        # 2) wikilink 死链
        for link in collect_wikilinks(body):
            key = link.strip().lower()
            if key and key not in all_names:
                warns.append(f"{rel}: 死链 [[{link}]]")

        # 3) 相对路径指针死链
        for m in re.finditer(r"`(memory/[\w\-./]+\.md)`", body):
            target = Path(m.group(1))
            if not (vault / target).exists():
                errors.append(f"{rel}: 指针失效 → {target.as_posix()}")

        # 4) 易腐值提醒
        if PERISHABLE_RE.search(body) and p.parent.name == "facts":
            if "verified" not in fm:
                warns.append(f"{rel}: 疑似含易腐值但没标 verified 日期")

        # 5) --fix
        if args.fix and problems:
            new_text, changed = fix_frontmatter(text)
            if changed:
                write_text(p, new_text)
                fixed.append(rel)
            elif any("混进了键值对" in x for x in problems):
                manual.append(rel)

    # 6) L0 占用率
    kernel = vault / KERNEL_DIR / "KERNEL.md"
    usage = 0
    if kernel.exists():
        fm, body = split_frontmatter(read_text(kernel))
        limit = args.limit
        if fm:
            m = re.search(r"^limit\s*:\s*(\d+)", fm, re.MULTILINE)
            if m:
                limit = int(m.group(1))
        # 只算实际注入的内容（正文 + 用户最小集），不算 frontmatter
        user = vault / KERNEL_DIR / "user.md"
        usage = len(body.strip())
        if user.exists():
            _, ub = split_frontmatter(read_text(user))
            usage += len(ub.strip())
        ratio = usage / limit * 100 if limit else 0
        line = f"L0 占用：{usage}/{limit} 字符（{ratio:.0f}%）"
        if ratio > 85:
            errors.append(line + " — 超过 85%，执行 amk.py promote")
        elif ratio > 70:
            warns.append(line + " — 偏高")
        else:
            print(color("  " + line, C_DIM, c))
    else:
        errors.append(f"缺 {KERNEL_DIR}/KERNEL.md")

    # 7) 空向量抽查（存在 .smart-env 时才查）
    se = vault / ".smart-env" / "multi"
    if se.exists():
        bad = 0
        sample = list(se.glob("*.ajson"))[:20]
        for f in sample:
            try:
                txt = read_text(f)
                vecs = re.findall(r'"vec":\[([^\]]*)\]', txt)
                if vecs and all(not v.strip() for v in vecs):
                    bad += 1
            except Exception:
                pass
        if bad:
            errors.append(f"索引异常：抽查 {len(sample)} 个文件有 {bad} 个向量为空（嵌入没跑起来）")

    # 报告
    print()
    for e in errors:
        print(color("  ✘ " + e, C_RED, c))
    for w in warns:
        print(color("  ! " + w, C_YEL, c))
    if fixed:
        print(color(f"  ✎ 已修复 frontmatter：{len(fixed)} 个文件", C_GRN, c))
    if manual:
        print(color(f"  ✋ 需要人工修（含键值对粘连）：{len(manual)} 个文件", C_YEL, c))

    n_ok = max(0, len(files) - len({e.split(':')[0] for e in errors}))
    print()
    summary = (f"扫描 {len(files)} 个文件 · 错误 {len(errors)} · 警告 {len(warns)}"
               f" · 修复 {len(fixed)}")
    print(color(summary, C_BOLD if (errors or warns) else C_GRN, c))
    if not errors and not warns:
        print(color("  记忆库健康 ✔", C_GRN, c))

    if args.quiet and not errors:
        return 0
    return 1 if errors else 0


# ---------------------------------------------------------------- boot

def file_hint(p: Path, vault: Path) -> str:
    """给索引清单生成一行摘要：标题 + frontmatter description 或首段。"""
    text = read_text(p)
    fm, body = split_frontmatter(text)
    desc = ""
    if fm:
        m = re.search(r"^description\s*:\s*(.+)$", fm, re.MULTILINE)
        if m:
            desc = m.group(1).strip().strip("\"'")
    if not desc:
        m = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        if m:
            desc = m.group(1).strip()
    if not desc:
        for line in body.splitlines():
            line = line.strip()
            if line and not line.startswith(("#", ">", "|", "-", "*")):
                desc = line[:60]
                break
    rel = p.relative_to(vault).as_posix()
    return f"- `{rel}` — {desc}" if desc else f"- `{rel}`"


def cmd_boot(args):
    vault = Path(args.vault).expanduser().resolve()
    c = use_color()
    kernel = vault / KERNEL_DIR / "KERNEL.md"
    user = vault / KERNEL_DIR / "user.md"
    if not kernel.exists():
        print(f"没找到 {kernel}，先跑 amk.py init", file=sys.stderr)
        return 2

    out = []
    out.append(f"<!-- agent-memory-kit boot v1 · vault: {vault.name} · "
               f"{datetime.now().strftime('%Y-%m-%d %H:%M')} -->")
    out.append("")

    _, kb = split_frontmatter(read_text(kernel))
    out += ["## 【记忆】内核（必须遵守）", "", kb.strip(), ""]

    if user.exists():
        _, ub = split_frontmatter(read_text(user))
        out += ["## 【记忆】用户最小集", "", ub.strip(), ""]

    # 索引清单
    entries = []
    for p in md_files(vault, [MEMORY_DIR]):
        if p.name in ("README.md", ".gitkeep"):
            continue
        entries.append(file_hint(p, vault))
    if entries:
        limit = args.max_index
        shown = entries[:limit]
        out += ["## 【记忆】知识库索引（按需读取，不自动注入）", ""]
        out += shown
        if len(entries) > limit:
            out.append(f"- …另有 {len(entries) - limit} 个文件，用 `amk.py stats` 或检索查看")
        out.append("")

    # 可选：检索提示（不自己跑向量，交给宿主）
    if args.query:
        out += ["## 【记忆】检索请求", "",
                f"关键词「{args.query}」。请执行：", "",
                f"```bash\nqmd query \"{args.query}\" --max-results 5\n```", ""]

    out += [
        "## 读取规则", "",
        "- 上面索引里的文件**不自动注入**，需要时用文件读取工具按路径打开。",
        "- 遇到 `X 详见 memory/xxx.md` 形式的指针，先读完再回答。",
        "- 关键词记不准时走语义检索（qmd / 本地向量库），已知路径就直接读文件。",
        "- 记忆与实测冲突时以实测为准。遇到易腐值（端口/凭据/版本）必须实测。",
        "- 没有值得记的新信息就不要写记忆 —— 噪音比缺失更有害。",
        "- 不要向用户播报「我已读取记忆」，除非记忆之间矛盾或明显过时。",
        "",
    ]
    text = "\n".join(out)
    if args.out:
        write_text(Path(args.out), text)
        print(f"{color('✔', C_GRN, c)} 上下文包已写入 {args.out}（{len(text)} 字符）")
    else:
        print(text)
    return 0


# ---------------------------------------------------------------- promote

SECTION_RE = re.compile(r"(?m)^(?=##\s)")
HEADER_RE = re.compile(r"^#\s+\S")


def split_entries(text: str):
    """把 L0 切成可独立评估的条目。

    返回 [(prefix, text)]：prefix 是这条之前的分隔符（保持原文结构）。
    先按 § 切成大块，块内再按 `##` 二级标题切成小节 —— 否则「身份/约束/路径」
    挤在一块，只要含一个保护词整块就被保护，等于没法维护。
    以单个 `#` 开头的文件头永远不参与下沉。
    """
    has_sep = re.search(r"(?m)^\s*§\s*$", text) is not None
    blocks = re.split(r"\n\s*§\s*\n", text) if has_sep else [text]
    entries = []
    for bi, block in enumerate(blocks):
        block = block.strip()
        if not block:
            continue
        parts = [x.strip() for x in SECTION_RE.split(block) if x.strip()]
        for pi, part in enumerate(parts):
            if not entries:
                prefix = ""
            elif pi == 0 and bi > 0:
                prefix = "\n\n§\n\n"
            else:
                prefix = "\n\n"
            entries.append((prefix, part))
    return entries


def score_entry(e: str):
    """分数越高越应该下沉。"""
    s = 0.0
    s += min(len(e) / PROMOTE_LEN, 1.0) * 40           # 长度
    if PERISHABLE_RE.search(e):
        s += 30                                        # 易腐值
    if STEP_RE.search(e):
        s += 20                                        # 是步骤
    if POINTER_RE.search(e) or re.search(r"memory/[\w\-./]+\.md", e):
        s += 10                                        # 已经是指针/含路径
    if len(e) > 400:
        s += 10
    return s


def slugify(e: str) -> str:
    """从条目生成文件名。类人可读、无路径符号、中文优先。"""
    first = e.splitlines()[0]
    first = re.sub(r"^#+\s*", "", first)
    first = re.sub(r"[`*_>\[\]()（）【】《》\"']", "", first)
    first = re.sub(r"^[\d.\-)\s]+", "", first)
    # 按标题分隔符切第一段（排除 Windows/Unix 路径里的冒号）
    m = re.search(r"[：。；;，,]|:(?![\\/])", first)
    if m and m.start() >= 4:
        first = first[: m.start()]
    first = first.strip()
    if len(first) > 20:
        tokens = first.split()
        if len(tokens) >= 2:
            first = " ".join(tokens[:2])
    first = re.sub(r"(部署在|位于|存放在|是在|的|在|是|为|和|与)$", "", first.strip())
    first = first.strip(" -—·:：")
    if len(first) < 2:
        first = "未命名条目"
    first = re.sub(r"[\\/:*?\"<>|]", "-", first)
    first = re.sub(r"\s+", "-", first)[:24].strip("-")
    return first or "未命名条目"


def unique_path(d: Path, slug: str) -> Path:
    p = d / f"{slug}.md"
    n = 2
    while p.exists():
        p = d / f"{slug}-{n}.md"
        n += 1
    return p


def cmd_promote(args):
    vault = Path(args.vault).expanduser().resolve()
    kernel = Path(args.kernel).expanduser().resolve() if args.kernel \
        else vault / KERNEL_DIR / "KERNEL.md"
    c = use_color()
    if not kernel.exists():
        print(f"没找到 {kernel}", file=sys.stderr)
        return 2

    raw = read_text(kernel)
    fm, body = split_frontmatter(raw)
    limit = args.limit
    if fm:
        m = re.search(r"^limit\s*:\s*(\d+)", fm, re.MULTILINE)
        if m:
            limit = int(m.group(1))

    entries = split_entries(body)          # [(prefix, text)]
    # L0 实际注入量 = 内核正文 + 用户最小集（和 lint 的算法保持一致）
    user_path = vault / KERNEL_DIR / "user.md"
    user_len = 0
    if user_path.exists():
        _, ub = split_frontmatter(read_text(user_path))
        user_len = len(ub.strip())
    total = sum(len(pf) + len(t) for pf, t in entries) + user_len
    ratio = total / limit * 100
    print(f"当前 L0：{total}/{limit} 字符（{ratio:.0f}%），{len(entries)} 个条目")

    if ratio <= args.target and not args.force:
        print(color(f"  ✔ 未超过目标 {args.target}%，无需下沉", C_GRN, c))
        return 0

    # 打分 + 保护过滤
    scored = []          # [(分数, 下标)]
    protect_long = []
    for idx, (pf, e) in enumerate(entries):
        if HEADER_RE.match(e):
            continue                                    # 文件头永不下沉
        if PROTECT_RE.search(e):
            if len(e) <= PROMOTE_LEN:
                continue                                # 短约束不下沉：那才是真正的红线
            protect_long.append(e)                      # 长且含保护词 → 交给人
            continue
        sc = score_entry(e)
        if sc > 0:
            scored.append((sc, idx))
    scored.sort(key=lambda x: -x[0])

    for e in protect_long:
        head = e.splitlines()[0][:40]
        print(color(f"  ! 含保护词但过长（{len(e)}字）：{head}… "
                    f"— 不自动下沉，请人工判断", C_YEL, c))

    budget = total
    plan = []
    for sc, idx in scored:
        if budget / limit * 100 <= args.target:
            break
        pf, e = entries[idx]
        slug = slugify(e)
        est = 40 + len(slug)        # 下沉后这一条会变成一行指针
        if len(e) <= est + 20:      # 沉下去不省空间，跳过
            continue
        plan.append((sc, idx, slug))
        budget -= (len(e) - est)

    if not plan:
        print(color("  ! 没有可下沉的条目（都受保护或下沉不省空间）", C_YEL, c))
        return 0

    facts = vault / MEMORY_DIR / "facts"
    facts.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    remaining = list(entries)
    moved = 0

    for sc, idx, slug in plan:
        pf, e = entries[idx]
        target = unique_path(facts, slug)
        pointer = f"{slug}：{target.relative_to(vault).as_posix()}"
        # 条目带 ## 小节标题时保留标题，否则指针会掉进上一节的正文里
        heading = re.match(r"^(#{2,3}\s+[^\n]+)\n", e)
        if heading:
            pointer = f"{heading.group(1)}\n\n{pointer}"
        print(f"  ↓ [{sc:.0f}分] {slug}  ({len(e)}字 → 指针)")
        # 试运行时也要替换，否则预估占用率算不对
        remaining[idx] = (pf, pointer)
        if args.dry_run:
            continue

        content = (
            f"---\n"
            f"tags:\n  - fact\n"
            f"migrated: {today}\n"
            f"verified: {today}\n"
            f"---\n\n"
            f"# {slug}\n\n"
            f"> 由 `amk.py promote` 从内核记忆下沉。原文保留如下，请人工复核分类与命名。\n\n"
            f"{e}\n\n"
            f"---\n\n"
            f"*下沉于 {today} · 原在 {kernel.name}*\n"
        )
        write_text(target, content)
        moved += 1

    new_body = "".join(pf + t for pf, t in remaining)

    if args.dry_run:
        est_total = len(new_body.strip()) + user_len
        print(f"\n[试运行] 将下沉 {len(plan)} 条，预计 {total} → {est_total} 字符"
              f"（{est_total/limit*100:.0f}%）")
        print("确认后去掉 --dry-run 执行")
        return 0

    header = f"---\n{fm}\n---\n" if fm else (f"---\ntags:\n  - system\nlimit: {limit}\n---\n")
    write_text(kernel, header + new_body.strip() + "\n")

    new_total = len(new_body.strip()) + user_len
    chlog = vault / "changelog.md"
    line = f"- L0 下沉 {moved} 条到 memory/facts/（{ratio:.0f}% → {new_total/limit*100:.0f}%）"
    if chlog.exists():
        t = read_text(chlog).rstrip() + "\n" + line + "\n"
    else:
        t = f"# 变更日志\n\n## {today}\n{line}\n"
    write_text(chlog, t)

    print(color(f"\n✔ 下沉 {moved} 条", C_GRN, c) +
          f"：{total} → {new_total} 字符（{new_total/limit*100:.0f}%）")
    if new_total / limit * 100 > args.target:
        print(color(f"  ! 仍高于目标 {args.target}%：剩余条目含保护词、是文件头、"
                    f"或下沉不省空间，需要人工判断", C_YEL, c))
    print("  请人工复核 memory/facts/ 下新生成的文件，按需要改分类和命名")
    return 0


# ---------------------------------------------------------------- stats

def cmd_stats(args):
    vault = Path(args.vault).expanduser().resolve()
    c = use_color()
    rows = []
    for sub in [KERNEL_DIR] + [f"{MEMORY_DIR}/{s}" for s in L1_SUBDIRS] + ["archive"]:
        p = vault / sub
        if not p.exists():
            rows.append((sub, 0, 0))
            continue
        fs = [f for f in p.rglob("*.md")]
        rows.append((sub, len(fs), sum(f.stat().st_size for f in fs)))

    print(f"记忆库：{vault}\n")
    print(f"{'目录':<32}{'文件':>6}{'字节':>10}")
    print("-" * 48)
    for name, n, size in rows:
        print(f"{name:<32}{n:>6}{size:>10}")

    kernel = vault / KERNEL_DIR / "KERNEL.md"
    if kernel.exists():
        fm, body = split_frontmatter(read_text(kernel))
        limit = DEFAULT_LIMIT
        if fm:
            m = re.search(r"^limit\s*:\s*(\d+)", fm, re.MULTILINE)
            if m:
                limit = int(m.group(1))
        usage = len(body.strip())
        user = vault / KERNEL_DIR / "user.md"
        if user.exists():
            _, ub = split_frontmatter(read_text(user))
            usage += len(ub.strip())
        ratio = usage / limit * 100
        bar_n = int(ratio / 5)
        bar = "█" * bar_n + "·" * (20 - bar_n)
        col = C_GRN if ratio <= 70 else (C_YEL if ratio <= 85 else C_RED)
        print()
        print(f"L0 占用 [{bar}] {usage}/{limit} = {color(f'{ratio:.0f}%', col, c)}")

    # 最近修改
    all_md = md_files(vault, [KERNEL_DIR, MEMORY_DIR])
    if all_md:
        recent = sorted(all_md, key=lambda f: f.stat().st_mtime, reverse=True)[:5]
        print("\n最近更新：")
        for f in recent:
            ts = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            print(f"  {ts}  {f.relative_to(vault).as_posix()}")
    return 0


# ---------------------------------------------------------------- archive

def cmd_archive(args):
    vault = Path(args.vault).expanduser().resolve()
    src = Path(args.file)
    if not src.is_absolute():
        src = vault / src
    if not src.exists():
        print(f"文件不存在：{src}", file=sys.stderr)
        return 2
    area = args.to or datetime.now().strftime("%Y-%m")
    dst = vault / "archive" / area / src.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst = dst.with_name(f"{src.stem}-{datetime.now():%H%M%S}{src.suffix}")
    shutil.move(str(src), str(dst))
    print(f"✔ {src.relative_to(vault).as_posix()} → {dst.relative_to(vault).as_posix()}")
    return 0


# ---------------------------------------------------------------- main

def build_parser():
    p = argparse.ArgumentParser(
        prog="amk",
        description="Agent Memory Kit — 四层本地记忆系统工具",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_vault(sp):
        sp.add_argument("--vault", required=True, help="记忆库根目录")

    sp = sub.add_parser("init", help="初始化四层目录结构")
    add_vault(sp)
    sp.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="L0 字符上限")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("lint", help="体检：frontmatter/标签/死链/空向量/L0 占用")
    add_vault(sp)
    sp.add_argument("--fix", action="store_true", help="安全修复 frontmatter")
    sp.add_argument("--quiet", action="store_true", help="只在有错误时输出")
    sp.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    sp.set_defaults(func=cmd_lint)

    sp = sub.add_parser("boot", help="生成会话启动上下文包")
    add_vault(sp)
    sp.add_argument("--query", help="附带一个检索关键词")
    sp.add_argument("--max-index", type=int, default=60, help="索引清单最多几条")
    sp.add_argument("--out", help="写入文件而不是打印")
    sp.set_defaults(func=cmd_boot)

    sp = sub.add_parser("promote", help="把过长的 L0 条目下沉到 L1")
    add_vault(sp)
    sp.add_argument("--kernel", help="L0 文件路径（默认 <vault>/kernel/KERNEL.md）")
    sp.add_argument("--target", type=int, default=DEFAULT_TARGET, help="目标占用率%%")
    sp.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--force", action="store_true", help="即使未超阈值也下沉")
    sp.set_defaults(func=cmd_promote)

    sp = sub.add_parser("stats", help="各层统计")
    add_vault(sp)
    sp.set_defaults(func=cmd_stats)

    sp = sub.add_parser("archive", help="把文件归档到 archive/YYYY-MM/")
    add_vault(sp)
    sp.add_argument("--file", required=True)
    sp.add_argument("--to", help="目标子目录，默认当年当月")
    sp.set_defaults(func=cmd_archive)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
