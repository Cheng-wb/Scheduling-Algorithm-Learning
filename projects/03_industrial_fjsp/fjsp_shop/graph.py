"""析取图（disjunctive graph）：把「排程」翻译成「图」，把 makespan 翻译成「最长路径」。

Week 1 Day 3 的理论交付物。三件事必须分清，混在一起就全乱了：

```text
定义   析取图本身 —— 工序是点，同一订单的前后工序是**合取弧**（必须定向），
       同一机器上的任意两道工序之间是**析取弧**（方向待定）。
       这是问题的完整表示，与任何具体排程无关。
构造   给定一个排程，把每条析取弧定向成「先做的那道指向后做的那道」，
       得到一个**全定向**的有向图。
结论   若该有向图无环，则从源点到汇点的最长路径长度等于该排程的 makespan。
```

第三条是定理，但它带一个前提：**排程必须是左移的**（每道工序都在其所有约束允许的
最早时刻开工）。若某道工序被人为推迟，图上的最长路径会严格小于 makespan —— 因为
「图上算出来的最早开工」比「实际开工」早，最长路径只反映约束，不反映人为空等。

本模块的做法是不猜也不掩盖：``analyze`` 把这类工序列进 ``slack``，
``check_critical_path`` 遇到它们直接报错并列出工序名。``jsp_cpsat`` 因此在返回前
做一次左移归一化（见 ``left_shift_schedule``），让它的解可以被同一套工具复核。

**为什么带释放时间也要正确？** 虚拟源点到每个订单第一道工序的弧权就是该订单的
释放时间，于是「源 → 首工序 → … → 末工序 → 汇」的弧权和是
``释放时间 + 沿途加工时间之和``，正好是把释放时间算进去的 makespan。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fjsp_core.models import FJSPInstance, Schedule, ScheduledOperation
from fjsp_core.objective import makespan as _makespan

#: 虚拟源点与汇点。它们不是工序，只是为了让「最长路径」有一条统一的起止。
SOURCE = "__source__"
SINK = "__sink__"

#: 四类弧。``weight`` 一律是「经过这条弧需要流逝的时间」。
ARC_SOURCE = "source"  # 源 → 订单首工序，权重 = 释放时间
ARC_JOB = "job"  # 同订单前后工序，权重 = 前道加工时间
ARC_MACHINE = "machine"  # 同机器相邻工序，权重 = 前道加工时间
ARC_SINK = "sink"  # 工序 → 汇，权重 = 该工序加工时间

ARC_KINDS = (ARC_SOURCE, ARC_JOB, ARC_MACHINE, ARC_SINK)

_NEG = -(10**15)


@dataclass(frozen=True, slots=True)
class Arc:
    """一条带权的弧。``kind`` 取值见模块级常量。"""

    tail: str
    head: str
    weight: int
    kind: str


@dataclass(frozen=True, slots=True)
class DisjunctiveGraph:
    """全定向后的析取图。``nodes`` 只含真实工序，虚拟点在 ``arcs`` 里出现。"""

    nodes: tuple[str, ...]
    arcs: tuple[Arc, ...]
    machine_order: tuple[tuple[str, tuple[str, ...]], ...]

    # --- 邻接（每次重建；图很小，不做缓存以免破坏 frozen 语义） ------------
    def successors(self, node: str) -> tuple[Arc, ...]:
        return tuple(arc for arc in self.arcs if arc.tail == node)

    def predecessors(self, node: str) -> tuple[Arc, ...]:
        return tuple(arc for arc in self.arcs if arc.head == node)

    def arc_between(self, tail: str, head: str) -> Arc | None:
        for arc in self.arcs:
            if arc.tail == tail and arc.head == head:
                return arc
        return None

    def sequence_on(self, machine_id: str) -> tuple[str, ...]:
        for candidate, sequence in self.machine_order:
            if candidate == machine_id:
                return sequence
        raise KeyError(machine_id)

    # --- 拓扑序与最长路径 --------------------------------------------------
    def topological_order(self) -> tuple[str, ...] | None:
        """Kahn 算法；有环时返回 ``None``（= 这个排程不可行）。

        队列按节点出现顺序出队，因此拓扑序与 ``arcs`` 的构造顺序都确定 ——
        换一次运行不会换一条最长路径。
        """
        order = [SOURCE, *self.nodes, SINK]
        index = {node: position for position, node in enumerate(order)}
        indegree = {node: 0 for node in order}
        for arc in self.arcs:
            indegree[arc.head] += 1
        ready = [node for node in order if indegree[node] == 0]
        produced: list[str] = []
        while ready:
            node = ready.pop(0)
            produced.append(node)
            for arc in self.successors(node):
                indegree[arc.head] -= 1
                if indegree[arc.head] == 0:
                    # 插回时保持「按节点顺序」的确定性
                    position = index[arc.head]
                    insert_at = len(ready)
                    for offset, other in enumerate(ready):
                        if index[other] > position:
                            insert_at = offset
                            break
                    ready.insert(insert_at, arc.head)
        return tuple(produced) if len(produced) == len(order) else None

    def has_cycle(self) -> bool:
        return self.topological_order() is None

    def longest_path(self) -> tuple[tuple[str, ...], int]:
        """返回 ``(源到汇的最长路径, 长度)``；有环时抛 ``ValueError``。"""
        order = self.topological_order()
        if order is None:
            raise ValueError("析取图有环：这个排程不可行（工艺路线与机器顺序互相矛盾）")
        distance = {node: _NEG for node in order}
        distance[SOURCE] = 0
        parent: dict[str, Arc] = {}
        for node in order:
            if distance[node] == _NEG:
                continue
            for arc in self.successors(node):
                candidate = distance[node] + arc.weight
                if candidate > distance[arc.head]:  # 严格大于：平局保留先出现的弧
                    distance[arc.head] = candidate
                    parent[arc.head] = arc
        if distance[SINK] == _NEG:  # pragma: no cover - 只有图被截断时才可能
            raise ValueError("汇点不可达：排程缺少工序")
        path = [SINK]
        while path[-1] != SOURCE:
            path.append(parent[path[-1]].tail)
        path.reverse()
        return tuple(path), distance[SINK]

    def earliest_starts(self) -> dict[str, int]:
        """每道工序的最早开工时刻（= 源点到它的最长路径长度）。"""
        order = self.topological_order()
        if order is None:  # pragma: no cover - 由 longest_path 先拦住
            raise ValueError("析取图有环")
        distance = {node: _NEG for node in order}
        distance[SOURCE] = 0
        for node in order:
            if distance[node] == _NEG:
                continue
            for arc in self.successors(node):
                if distance[node] + arc.weight > distance[arc.head]:
                    distance[arc.head] = distance[node] + arc.weight
        return {node: distance[node] for node in self.nodes}


@dataclass(frozen=True, slots=True)
class GraphAnalysis:
    """一次完整分析的结果。字段之间必须自洽，否则说明有 bug。"""

    graph: DisjunctiveGraph
    path: tuple[str, ...]  # 关键路径上的**工序**（不含源汇）
    path_length: int  # 沿路径独立重算的长度
    graph_length: int  # 图算法给出的最长路径长度
    makespan: int  # fjsp_core.objective 给出的 makespan
    blocks: tuple[tuple[str, ...], ...]  # 关键块
    slack: tuple[str, ...]  # 实际开工晚于最早开工的工序（非空则定理前提不成立）
    earliest_starts: dict[str, int]

    @property
    def is_left_shifted(self) -> bool:
        return not self.slack

    @property
    def matches_makespan(self) -> bool:
        return self.path_length == self.graph_length == self.makespan


def _duration(instance: FJSPInstance, operation_id: str, machine_id: str) -> int:
    duration = instance.operation(operation_id).time_on(machine_id)
    if duration is None:
        raise ValueError(
            f"排程把工序 {operation_id!r} 放在不合格的机器 {machine_id!r} 上；"
            "请先跑 validate_schedule 再建图"
        )
    return duration


def build_graph(instance: FJSPInstance, schedule: Schedule) -> DisjunctiveGraph:
    """把**已经验证过**的排程翻译成全定向的析取图。

    不重复做可行性检查（那是 ``validate_schedule`` 的职责），但会拒绝两种
    无法忠实表达的情形：

    * 排程缺工序 —— 定向不完整，图会少点；
    * 工序被放在 ``machine_times`` 之外的机器上 —— 加工时间无从取值。

    适用条件：工序不带 ``locked_start``。锁定开工时刻意味着「人为推迟」，
    图上算出来的最早开工必然小于它，最长路径定理的前提不成立，所以这里
    明确拒绝而不是给出一个会误导人的图（WIP 锁定是 Week 4 的内容）。
    """
    for operation in instance.operations:
        if operation.locked_start is not None:
            raise ValueError(
                f"工序 {operation.id!r} 带 locked_start：锁定的开工时刻可能与"
                "最早开工不一致，析取图的最长路径不再等于 makespan"
            )

    by_id = schedule.by_operation()
    missing = [op.id for op in instance.operations if op.id not in by_id]
    if missing:
        raise ValueError(f"排程缺少工序，无法定向：{missing[:5]}")

    arcs: list[Arc] = []
    for job in instance.jobs:
        first = by_id[job.operation_ids[0]]
        arcs.append(Arc(SOURCE, first.operation_id, job.release_time, ARC_SOURCE))
        for before, after in zip(job.operation_ids, job.operation_ids[1:]):
            weight = _duration(instance, before, by_id[before].machine_id)
            arcs.append(Arc(before, after, weight, ARC_JOB))

    machine_order: list[tuple[str, tuple[str, ...]]] = []
    for machine in instance.machines:
        timeline = sorted(
            (item for item in schedule.operations if item.machine_id == machine.id),
            key=lambda item: (item.start_time, item.operation_id),
        )
        for earlier, later in zip(timeline, timeline[1:]):
            weight = _duration(instance, earlier.operation_id, machine.id)
            arcs.append(Arc(earlier.operation_id, later.operation_id, weight, ARC_MACHINE))
        machine_order.append((machine.id, tuple(item.operation_id for item in timeline)))

    for operation in instance.operations:
        item = by_id[operation.id]
        arcs.append(
            Arc(operation.id, SINK, _duration(instance, operation.id, item.machine_id), ARC_SINK)
        )

    return DisjunctiveGraph(
        nodes=tuple(op.id for op in instance.operations),
        arcs=tuple(arcs),
        machine_order=tuple(machine_order),
    )


def critical_path(instance: FJSPInstance, schedule: Schedule) -> tuple[str, ...]:
    """关键路径上的工序（不含虚拟源汇）。"""
    path, _ = build_graph(instance, schedule).longest_path()
    return tuple(node for node in path if node not in (SOURCE, SINK))


def graph_makespan(instance: FJSPInstance, schedule: Schedule) -> int:
    """只用图算出来的 makespan（源到汇的最长路径长度）。"""
    _, length = build_graph(instance, schedule).longest_path()
    return length


def path_length(instance: FJSPInstance, schedule: Schedule, path: tuple[str, ...]) -> int:
    """沿给定路径**独立重算**长度：首工序所在订单的释放时间 + 沿途加工时间之和。

    这个函数不看图的弧，只看路径上的工序列表 —— 与图算法是两条计算路径，
    两者相等才说明最长路径确实是一条合法路径。
    """
    if not path:
        raise ValueError("空路径没有长度")
    by_id = schedule.by_operation()
    job_release = {job.id: job.release_time for job in instance.jobs}
    first = instance.operation(path[0])
    total = job_release[first.job_id]
    for operation_id in path:
        total += _duration(instance, operation_id, by_id[operation_id].machine_id)
    return total


def critical_blocks(
    instance: FJSPInstance, schedule: Schedule
) -> tuple[tuple[str, ...], ...]:
    """关键块：关键路径上**同一台机器且在该机器上相邻**的工序组成的极大段。

    判定用「在机器顺序里相邻」而不是「两点之间有机器弧」：两者在无环图里等价，
    但前者直接对应定义，读代码时不需要额外推理。
    """
    graph = build_graph(instance, schedule)
    path = critical_path(instance, schedule)
    machine_of = {item.operation_id: item.machine_id for item in schedule.operations}
    position: dict[tuple[str, str], int] = {}
    for machine_id, sequence in graph.machine_order:
        for index, operation_id in enumerate(sequence):
            position[(machine_id, operation_id)] = index

    blocks: list[tuple[str, ...]] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            blocks.append(tuple(current))
            current.clear()

    for operation_id in path:
        if not current:
            current.append(operation_id)
            continue
        previous = current[-1]
        same_machine = machine_of[previous] == machine_of[operation_id]
        adjacent = (
            same_machine
            and position[(machine_of[operation_id], operation_id)]
            == position[(machine_of[previous], previous)] + 1
        )
        if adjacent:
            current.append(operation_id)
        else:
            flush()
            current.append(operation_id)
    flush()
    return tuple(blocks)


def analyze(instance: FJSPInstance, schedule: Schedule) -> GraphAnalysis:
    """一次给出关键路径、关键块、最早开工与「非左移工序」清单。"""
    graph = build_graph(instance, schedule)
    full_path, graph_length = graph.longest_path()
    real_path = tuple(node for node in full_path if node not in (SOURCE, SINK))
    earliest = graph.earliest_starts()
    slack = tuple(
        sorted(
            item.operation_id
            for item in schedule.operations
            if item.start_time > earliest[item.operation_id]
        )
    )
    return GraphAnalysis(
        graph=graph,
        path=real_path,
        path_length=path_length(instance, schedule, real_path),
        graph_length=graph_length,
        makespan=_makespan(instance, schedule),
        blocks=critical_blocks(instance, schedule),
        slack=slack,
        earliest_starts=earliest,
    )


def check_critical_path(instance: FJSPInstance, schedule: Schedule) -> int:
    """核心断言：**关键路径长度 = 图最长路径长度 = makespan**。

    不等时抛 ``ValueError`` 并说明原因是「排程非左移」还是「两者真的不一致」——
    前者是建模前提问题，后者是代码 bug，两种情况必须能区分。
    """
    analysis = analyze(instance, schedule)
    if analysis.matches_makespan:
        return analysis.makespan
    if analysis.slack:
        raise ValueError(
            "排程不是左移的，最长路径定理不适用；以下工序被人为推迟："
            f"{list(analysis.slack)}"
        )
    raise ValueError(
        "关键路径长度与 makespan 不一致：路径重算 "
        f"{analysis.path_length}、图最长路径 {analysis.graph_length}、"
        f"makespan {analysis.makespan}"
    )


def critical_block_machines(
    instance: FJSPInstance, schedule: Schedule
) -> tuple[str, ...]:
    """关键块落在哪些机器上 —— 这些就是这张排程的**瓶颈机器**（按出现次数排序）。"""
    machine_of = {item.operation_id: item.machine_id for item in schedule.operations}
    counts: dict[str, int] = {}
    for block in critical_blocks(instance, schedule):
        for operation_id in block:
            machine_id = machine_of[operation_id]
            counts[machine_id] = counts.get(machine_id, 0) + 1
    return tuple(
        machine_id
        for machine_id, _ in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    )


def left_shift_schedule(instance: FJSPInstance, schedule: Schedule) -> Schedule:
    """把每道工序搬到它的最早开工时刻（左移归一化），机器选择不变。

    **为什么需要它？** 关键路径定理要求排程是左移的。CP-SAT 的最优解在
    makespan 意义下最优，但**允许**某些工序带无用空等（把一道工序右移不影响
    最大完工时间时，求解器没有理由把它拉回来）。左移不改变机器顺序、
    不增加 makespan，却让图上的最长路径重新等于 makespan。

    可行性为什么保得住：新开工 = 图上最早开工，它由三类弧同时约束住 ——
    源弧（释放时间）、合取弧（前后工序）、机器弧（同机器先后），所以左移后
    释放时间、工艺路线、机器互斥全部仍然满足。

    适用条件（缺一不可，否则抛 ``ValueError``）：
    没有日历、没有维护窗、没有次生资源、没有 ``locked_start``。
    前两者是「可用时间窗」，左移可能把工序推进不可用区间；资源是共享的，
    左移可能让两道工序抢同一个工人；锁定开工时刻按定义不许动。
    """
    if instance.calendars or any(m.calendar_id is not None for m in instance.machines):
        raise ValueError("实例带机器日历：左移可能把工序推进不可用区间")
    if instance.maintenances:
        raise ValueError("实例带计划维护窗：左移可能把工序推进维护区间")
    if instance.workers:
        raise ValueError("实例带次生资源：左移可能让两道工序抢同一个资源")
    if any(op.locked_start is not None for op in instance.operations):
        raise ValueError("实例带 locked_start：锁定开工时刻的工序不允许被移动")

    earliest = build_graph(instance, schedule).earliest_starts()
    by_id = schedule.by_operation()
    shifted: list[ScheduledOperation] = []
    for item in schedule.operations:
        start = earliest[item.operation_id]
        duration = _duration(instance, item.operation_id, by_id[item.operation_id].machine_id)
        shifted.append(
            ScheduledOperation(
                operation_id=item.operation_id,
                machine_id=item.machine_id,
                start_time=start,
                end_time=start + duration,
                worker_id=item.worker_id,
            )
        )
    return Schedule(tuple(shifted))


def graph_summary(instance: FJSPInstance, schedule: Schedule) -> dict[str, Any]:
    """给实验脚本用的一页摘要（都是可核对的原始数字）。"""
    analysis = analyze(instance, schedule)
    return {
        "makespan": analysis.makespan,
        "graph_makespan": analysis.graph_length,
        "path_length": analysis.path_length,
        "is_left_shifted": analysis.is_left_shifted,
        "matches_makespan": analysis.matches_makespan,
        "path": list(analysis.path),
        "blocks": [list(block) for block in analysis.blocks],
        "block_machines": list(critical_block_machines(instance, schedule)),
        "slack": list(analysis.slack),
    }
