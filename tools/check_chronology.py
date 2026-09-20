"""检查学习笔记里的「前瞻引用」（forward reference），保证笔记严格按时间顺序。

## 规则

**每天的学习内容必须严格按时间顺序。** `Week_W/DayD.md` 可以自由引用本周的
Day 1..D 与第 1..W 周（以及已完成的更早月份），但**不能**出现对 Day D+k、
Week W+k 或后续月份的引用——否则读者必须跳着看才能理解当前内容。
`weekN.md` 只能引用第 1..N 周。

唯一豁免：月度总纲计划 ``Month_XX/README.md`` 与月度报告 ``MONTH*REPORT.md``
（前者本就要铺开整月，后者写于月末）。

## 为什么要区分「向后」与「向前」

`Week 1 Day 4 第 5 节`（在第 2 周的笔记里）是**向后**引用，完全合法；
裸的 `Day 4 第 5 节` 在第 2 周里则有歧义，按违规处理。同理 `M1 Day 5`、
`M2 Week 1 Day 7` 指向已完成月份，合法。机器编号形如 `M1`/`M2`/`M3`
（Flow Shop 举例）不是月份引用，必须放过——这正是本工具最容易误伤的地方，
所以月份引用一律要求带中文语境词。

## 用法

    python tools/check_chronology.py                       # 全部三个月
    python tools/check_chronology.py Month_03_工业排程与柔性车间   # 某个月
    python tools/check_chronology.py 某文件.md              # 某个文件
    python tools/check_chronology.py --fences              # 连代码块内一起检查

默认**跳过 ``` 代码块**（那里大多是脚本输出的粘贴，且 `M1 → M2 → M3` 这类
机器编号极多）。但粘贴块里也可能有真正的指向，所以隔一段时间应加 `--fences`
跑一次——三处真实的粘贴输出前瞻引用就是这样找出来的。

有命中时把详情写入 `_forward_refs_report[_fences].txt`（UTF-8，因为中文在
GBK 控制台会崩），控制台只打印 ASCII 摘要。**没有命中就不留文件。**
退出码 0 表示干净。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

MONTHS = {
    "Month_01_基础系统与框架设计": 1,
    "Month_02_精确算法与参数学习": 2,
    "Month_03_工业排程与柔性车间": 3,
}

# 月份引用必须带中文语境，否则会误伤机器编号（例：M1 → M2 → M3 是 Flow Shop 举例）。
# 注意**不**把 `的` 收进语境词：`M2 的空闲` / `M2 的负载` 说的是机器 M2，
# 这是最常见的误报来源。真正的月份引用通常会带「会/学习/实现/精确」这类动词或领域词。
MONTH_CTX = re.compile(
    r"第\s*([2-9])\s*月"
    r"|M([2-9])\s*(会|中|里|阶段|学习|实现|精确|元启发式|分解|强化|再|才|去做|去处理|引入)"
    r"|Month\s*([2-9])"
)
PHRASE = re.compile(
    r"下周|下一天|下一周|后续月份|以后会|将在.{0,12}(实现|介绍|学习|讲|讨论)"
)

SKIP_NAMES = {"README.md"}


def scan_file(path: Path, month: int, include_fences: bool = False) -> list[tuple[int, str, str]]:
    text = path.read_text(encoding="utf-8")
    posix = path.as_posix()
    m = re.search(r"Week_(\d+)/Day(\d+)", posix)
    week = int(m.group(1)) if m else 0
    day = int(m.group(2)) if m else 0
    wm = re.search(r"week(\d+)\.md$", path.name)
    summary_week = int(wm.group(1)) if wm else 0

    # 先标出「反向锚点」的跨度，例如 "Week 1 Day 4 第 5 节" / "M1 Day 5" / "M2 Week 1 Day 7"。
    # 这些是**向后**引用，完全合法，但朴素的 Day 正则会把它们当成当周的前瞻引用。
    # 两种形式：
    #   A) 带月份前缀：M1 Day 5 / Month 2 Week 1 Day 7 —— 月份早于当月即向后
    #   B) 带周前缀：  Week 1 Day 4 / Week_1/Day1.md —— 周次早于本文件所在周即向后
    ANCHOR_MONTH = re.compile(
        r"(?:M|Month\s+)(\d+)\s+(?:Week\s*(\d+)\s+)?Day\s*(\d+)"
    )
    ANCHOR_WEEK = re.compile(r"Week\s*(\d+)\s+Day\s*(\d+)|Week_(\d+)/Day(\d+)")

    hits: list[tuple[int, str, str]] = []
    fenced = False
    for index, line in enumerate(text.split("\n"), 1):
        if line.startswith("```"):
            fenced = not fenced
            if not include_fences:
                continue
        if fenced and not include_fences:
            continue

        # 计算本行里属于「向后引用」的字符区间，后面从 Day 检查里排除
        excluded: list[tuple[int, int]] = []
        current_week = summary_week or week
        for anchor in ANCHOR_MONTH.finditer(line):
            anchor_month = int(anchor.group(1))
            if anchor_month < month:
                excluded.append(anchor.span())
        for anchor in ANCHOR_WEEK.finditer(line):
            anchor_week = int(anchor.group(1) or anchor.group(3) or 0)
            if anchor_week and current_week and anchor_week < current_week:
                excluded.append(anchor.span())

        def is_backward(span: tuple[int, int]) -> bool:
            return any(a <= span[0] and span[1] <= b for a, b in excluded)

        for found in re.finditer(r"Day\s*(\d+)|第\s*(\d+)\s*天", line):
            if is_backward(found.span()):
                continue
            ref = int(found.group(1) or found.group(2))
            if day and ref > day:
                hits.append((index, f"Day{ref}", line.strip()))
        for found in re.finditer(r"Week\s*(\d+)|第\s*(\d+)\s*周", line):
            ref = int(found.group(1) or found.group(2))
            current = summary_week or week
            if current and ref > current:
                hits.append((index, f"Week{ref}", line.strip()))
        found = MONTH_CTX.search(line)
        if found:
            ref = int(found.group(1) or found.group(2) or found.group(4) or 0)
            if ref and ref > month:
                hits.append((index, f"Month{ref}", line.strip()))
        if PHRASE.search(line):
            hits.append((index, "PHRASE", line.strip()))
    return hits


def main() -> None:
    args = sys.argv[1:]
    include_fences = "--fences" in args
    targets = [a for a in args if a != "--fences"]
    roots = [Path(t) for t in targets] if targets else [Path(n) for n in MONTHS]
    report = Path("_forward_refs_report.txt")
    if include_fences:
        report = Path("_forward_refs_report_fences.txt")

    lines: list[str] = []
    total = 0
    for root in roots:
        if root.is_file():
            month = next((v for k, v in MONTHS.items() if k in root.as_posix()), 0)
            files = [root]
        else:
            month = MONTHS.get(root.name, 0)
            files = sorted(root.rglob("*.md"))
        for path in files:
            if path.name in SKIP_NAMES or "MONTH" in path.name.upper():
                continue
            if not month:
                month = next(
                    (v for k, v in MONTHS.items() if k in path.as_posix()), 0
                )
            hits = scan_file(path, month, include_fences=include_fences)
            if hits:
                total += len(hits)
                lines.append(f"--- {path.as_posix()} ({len(hits)}) ---")
                for line_number, kind, line in hits:
                    lines.append(f"  L{line_number} [{kind}] {line[:150]}")
    # 报告写文件（UTF-8），控制台只打印 ASCII —— 中文在 GBK 控制台会崩。
    # 干净时不留下任何文件，避免污染工作区。
    scope = "including fenced blocks" if include_fences else "prose only"
    if total:
        report.write_text("\n".join(lines) + f"\n\nTOTAL: {total}\n", encoding="utf-8")
        print(f"forward references = {total} ({scope}); details -> {report.resolve()}")
    else:
        report.unlink(missing_ok=True)
        print(f"forward references = 0 ({scope}); nothing to report")
    raise SystemExit(1 if total else 0)


if __name__ == "__main__":
    main()
