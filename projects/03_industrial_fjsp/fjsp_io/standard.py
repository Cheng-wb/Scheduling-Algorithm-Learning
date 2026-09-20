"""经典 OR-Library JSP 文本格式的读写。

格式（本模块实现的全部内容，没有别的花样）：

```text
第一行    nb_jobs nb_machines
之后每个订单一行：2 * nb_machines 个整数，成对出现 —— 机器号 加工时间
         机器号是 **0 基**（0 表示第一台机器）
         这一行里成对出现的**顺序**就是该订单的工艺路线
```

一个 2 订单 2 机器的例子：

```text
2 2
0 3 1 2
1 2 0 4
```

读作：订单 0 先在机器 0 上做 3 个时间单位，再到机器 1 上做 2 个；订单 1 先在机器 1
上做 2 个，再到机器 0 上做 4 个。每条工序**只在一台机器上**加工，因此解析出来的实例
里每道工序的 ``machine_times`` 恰好一项 —— 这正是经典 JSP 的定义。

**证据来源必须说清楚**：本解析器是用 ``tests/data/`` 下**手写的**同格式小文件
（``tiny2x2.jsp`` / ``tiny3x3.jsp``）验证的，**没有**用 OR-Library 原始的 FT / LA /
ABZ 文件验证过 —— 那些文件不在本仓库里，本模块也刻意不去下载它们。因此
「格式解析正确」这句话在本仓库成立的范围是：**与手写样例一致的写法**。
真实基准文件里常见的额外花样（前置的订单数/机器数注释行、行尾空白、科学计数法、
``+`` 号当分隔符）本模块不保证支持，遇到时抛 ``ValueError`` 而不是猜。

写回函数 ``format_standard_jsp`` 要求机器 id 恰好是 ``M0 … M{n-1}`` 且顺序一致 ——
否则「机器号 = 机器在列表里的位置」这条映射就不是双射，往返会静默换机器。
"""
from __future__ import annotations

from pathlib import Path

from fjsp_core.models import FJSPInstance, Job, Machine, Operation


class StandardFormatError(ValueError):
    """标准格式不合法。单独一个类型，便于测试断言与上层区分「格式错」和「约束错」。"""


def _tokens(line: str) -> list[str]:
    return line.replace("\t", " ").split()


def parse_standard_jsp(text: str, *, name: str = "standard") -> FJSPInstance:
    """解析经典 JSP 文本格式，返回 :class:`FJSPInstance`。"""
    lines: list[tuple[int, str]] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append((number, stripped))
    if not lines:
        raise StandardFormatError("空文件：标准格式至少要有头行")

    number, header = lines[0]
    parts = _tokens(header)
    if len(parts) < 2:
        raise StandardFormatError(f"第 {number} 行应为「订单数 机器数」，实际是 {header!r}")
    try:
        job_count, machine_count = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise StandardFormatError(
            f"第 {number} 行的订单数/机器数不是整数：{header!r}"
        ) from exc
    if job_count < 1 or machine_count < 1:
        raise StandardFormatError(f"第 {number} 行：订单数与机器数都必须 >= 1，实际 {job_count}/{machine_count}")

    body = lines[1:]
    if len(body) < job_count:
        raise StandardFormatError(
            f"头行声明 {job_count} 个订单，但后面只有 {len(body)} 行工序数据"
        )
    if len(body) > job_count:
        raise StandardFormatError(
            f"头行声明 {job_count} 个订单，但后面有 {len(body)} 行工序数据（多出来的部分不猜）"
        )

    machines = tuple(Machine(f"M{index}", f"Machine {index}") for index in range(machine_count))
    jobs: list[Job] = []
    operations: list[Operation] = []

    for job_index, (line_number, line) in enumerate(body):
        values = _tokens(line)
        expected = 2 * machine_count
        if len(values) != expected:
            raise StandardFormatError(
                f"第 {line_number} 行有 {len(values)} 个整数，应为 {expected} 个"
                f"（{machine_count} 台机器 × 机器号+工时）"
            )
        try:
            numbers = [int(value) for value in values]
        except ValueError as exc:
            raise StandardFormatError(f"第 {line_number} 行含非整数：{line!r}") from exc

        job_id = f"J{job_index}"
        operation_ids: list[str] = []
        for position in range(machine_count):
            machine_number = numbers[2 * position]
            minutes = numbers[2 * position + 1]
            if not 0 <= machine_number < machine_count:
                raise StandardFormatError(
                    f"第 {line_number} 行的机器号 {machine_number} 越界"
                    f"（本格式机器号 0 基，合法范围 0..{machine_count - 1}）"
                )
            if minutes <= 0:
                raise StandardFormatError(
                    f"第 {line_number} 行工序 {position} 的工时 {minutes} 不是正数"
                )
            operation_id = f"{job_id}_O{position}"
            operation_ids.append(operation_id)
            operations.append(
                Operation(
                    id=operation_id,
                    job_id=job_id,
                    position=position,
                    machine_times=((machines[machine_number].id, minutes),),
                )
            )
        jobs.append(Job(job_id, tuple(operation_ids)))

    return FJSPInstance(
        jobs=tuple(jobs),
        operations=tuple(operations),
        machines=machines,
        meta={
            "format": "or-library-jsp",
            "source": name,
            "job_count": job_count,
            "machine_count": machine_count,
            "machine_id_base": 0,
        },
    )


def load_standard_jsp(path: str | Path) -> FJSPInstance:
    """从文件读取标准格式实例。``name`` 记成文件路径，便于实验里回溯到磁盘证据。"""
    target = Path(path)
    return parse_standard_jsp(target.read_text(encoding="utf-8"), name=target.name)


def format_standard_jsp(instance: FJSPInstance) -> str:
    """把实例写回标准格式。

    只能写「每道工序恰好一台合格机器、且机器 id 恰好是 ``M0 … M{n-1}``」的实例：
    本格式用**机器号的整数位置**表示机器，若 id 与位置不是双射，写出去再读回来
    就会静默换一台机器 —— 那种「看似成功」的往返比报错危险得多。
    """
    expected = tuple(f"M{index}" for index in range(len(instance.machines)))
    actual = tuple(machine.id for machine in instance.machines)
    if actual != expected:
        raise StandardFormatError(
            f"机器 id 必须是 M0..M{len(instance.machines) - 1} 且顺序一致，实际是 {list(actual)}"
        )
    index_of = {machine_id: index for index, machine_id in enumerate(actual)}

    lines = [f"{len(instance.jobs)} {len(instance.machines)}"]
    for job in instance.jobs:
        pairs: list[str] = []
        for operation_id in job.operation_ids:
            operation = instance.operation(operation_id)
            if len(operation.machine_times) != 1:
                raise StandardFormatError(
                    f"工序 {operation.id!r} 有 {len(operation.machine_times)} 台合格机器；"
                    "标准 JSP 格式每道工序只能写一台"
                )
            machine_id, minutes = operation.machine_times[0]
            pairs.append(f"{index_of[machine_id]} {minutes}")
        lines.append(" ".join(pairs))
    return "\n".join(lines) + "\n"


def save_standard_jsp(instance: FJSPInstance, path: str | Path) -> None:
    """写出标准格式文件（``utf-8``，纯 ASCII 内容）。"""
    target = Path(path)
    if target.parent and not target.parent.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(format_standard_jsp(instance), encoding="utf-8")
