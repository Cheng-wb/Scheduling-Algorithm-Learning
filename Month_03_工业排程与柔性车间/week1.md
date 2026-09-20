# M3 Week 1 周总结：流水车间与作业车间的基础

> 笔记：[Day1](Week_1/Day1.md) · [Day2](Week_1/Day2.md) · [Day3](Week_1/Day3.md) · [Day4](Week_1/Day4.md) · [Day5](Week_1/Day5.md) · [Day6](Week_1/Day6.md) · [Day7](Week_1/Day7.md)

## 1. 本周目标与成果

本周把「排程」从一张订单表推进到**可求解、可验证、可呈现**的三层：构造规则层（`flow_johnson`、`flow_neh`、`jsp_priority` — 非延迟列表调度 + 五条优先级规则）、精确求解层（`jsp_cpsat`）、表示与呈现层（析取图、甘特行、机器负载汇总）。

四个方法全部注册进 `fjsp_shop.registry`，可被 `configs/month3.json` 直接调用；每一个返回的排程都通过 `fjsp_core.schedule_validation.validate_schedule` 与 `fjsp_core.result.validate_result` 的独立检查。

七个可运行脚本对应七天：流线规则手算、基线对拍、析取图与关键路径、CP-SAT 建模、枚举对拍、标准格式与甘特/瓶颈、复盘核对。实验驱动 `fjsp_experiments/week1_gantt.py` 把四个实例的甘特 CSV 与汇总写进 `artifacts/month3_w1/`。

**没有下载 OR-Library 的 FT/LA/ABZ 实例**：标准格式解析器只用 `tests/data/` 下手写的三个小文件验证，验证强度如实写在文档里。

## 2. 核心概念

| 概念 | 一句话定义 | 读它回答的问题 |
|---|---|---|
| 流水车间 `Fm \| prmu \| Cmax` | 每道工序的机器固定，所有订单走同一条机器顺序 | 这条产线最短能跑多快 |
| Johnson 规则 | 两边贪心：先排工时小于等于对角线的，再倒序排另一侧 | `F2 \|\| Cmax` 的最优顺序 |
| NEH | 总工时降序，逐个插到最靠前的最优位置 | `m >= 3` 时的插入式启发式 |
| 作业车间 `Jm \| Cmax` | 每道工序的机器由订单自己决定，可以任意交叉 | 通用车间怎么排 |
| 非延迟列表调度 | 只要有可开工的工序就立刻开机，不故意留空 | 快速拿到一个可行解 |
| 优先级规则 | `mwr` / `mopnr` / `spt` / `lpt` / `fifo`，决定列表里谁先 | 换规则能差多少 |
| 析取图 | 源点 + 汇点 + 合取弧（工序先后）+ 析取弧（机器先后） | 排程在图上的等价物 |
| 关键路径 | 从源点到汇点的最长路径 | makespan 的来源 |
| 关键块 | 关键路径上同一台机器上连续的一段 | 改排程的着手点 |
| 下界 `LB` | `max(最大机器负载, 最大订单总工时)` | 目标值离最优还有多远 |

**「最长路径 = makespan」是定理，但有前提**：排程必须是**左移**的（每道工序取最早可行开工时刻）。被人工推迟过的排程上两者不等，此时 `check_critical_path` 抛 `ValueError`，而不是算一个错的长度出来。

## 3. 四个方法与适用条件

| 方法 | 什么时候精确 | 什么时候只是启发式 | 什么时候拒绝 | 有下界吗 |
|---|---|---|---|---|
| `flow_johnson` | `F2 \|\| Cmax`（2 台机器） | `m >= 3`（瓶颈机对上的 Johnson） | 非流水车间实例 | 否 |
| `flow_neh` | 从不（无最优性定理） | 所有 `Fm \| prmu \| Cmax` | 非流水车间实例 | 否 |
| `jsp_priority` | 从不 | 经典作业车间（一工序一机器） | 需要额外约束的实例 | 否 |
| `jsp_cpsat` | 预算内搜完并证明时 | 预算内只找到可行解时 | 模型不合法时 | 目标是 makespan 时才有 |

**启发式一律 `best_bound = None`**（不是目标值）。`FAILED` 表示「不适用」，与「结果更差」是两回事 —— 前者三列全是 `-`，后者有数字。

## 4. 接口约定（API Contract）

```python
# fjsp_shop/registry.py
available() -> list[str]          # 当前已导入模块注册的方法名（内容随导入范围变化）
load_week_modules() -> list[str]  # 逐个导入仓库里的各模块，返回导入失败的名字

# 统一入口：solve(instance, spec) -> ShopResult
# spec 里带 objective / time_limit / seed；heuristic 忽略 time_limit
flow_johnson(instance, spec) -> ShopResult
flow_neh(instance, spec) -> ShopResult
jsp_priority(instance, spec) -> ShopResult   # spec["priority"] 取 PRIORITY_RULES 之一
jsp_cpsat(instance, spec) -> ShopResult

# fjsp_shop/graph.py —— 析取图
build_graph(instance, schedule) -> DisjunctiveGraph
DisjunctiveGraph.nodes / .arcs / .machine_order          # nodes 只含真实工序
DisjunctiveGraph.topological_order() -> tuple[str, ...] | None   # None = 有环 = 排程不可行
DisjunctiveGraph.earliest_starts() -> dict[str, int]     # 节点 -> 最早开工（含源点与汇点）
critical_path(instance, schedule) -> tuple[str, ...]     # 关键路径上的工序（不含源汇）
path_length(instance, schedule, path) -> int             # 沿给定路径独立重算
critical_blocks(instance, schedule) -> tuple[tuple[str, ...], ...]
left_shift_schedule(instance, schedule) -> Schedule      # 归一化到左移
analyze(instance, schedule) -> GraphAnalysis             # path / blocks / slack / is_left_shifted
check_critical_path(instance, schedule) -> int           # 非左移排程抛 ValueError，返回 makespan
graph_summary(instance, schedule) -> dict[str, Any]      # 可打印的汇总

# fjsp_shop/gantt.py —— 展示模型
GANTT_FIELDS = ("machine_id", "job_id", "operation_id", "start_time", "end_time", "duration")
to_gantt_rows(instance, schedule) -> list[dict]      # 按 (machine_id, start_time, operation_id) 排序
write_gantt_csv(rows, path) / render_ascii_gantt(instance, schedule, width=..)
machine_load_summary(instance, schedule) -> list[dict]

# fjsp_io/standard.py —— 标准格式
load_standard_jsp(path) -> FJSPInstance        # 解析失败抛 StandardFormatError
format_standard_jsp(instance) -> str           # 机器 id 必须是 M0..M{n-1}，否则抛错
```

**命名派生规则**：`Operation.machine_times` 是 `[(machine_id, duration), ...]`，方法必须按它判断机器资格，不能用「第 i 道工序上第 i 台机器」这类隐含假设。

## 5. 关键数值证据

四个实例（`generate_instance`，`flexibility=1`，方法用 `makespan`）：

| 实例 | 规模 | `flow_johnson` | `flow_neh` | `jsp_priority` | `jsp_cpsat` | 最优 |
|---|---|---:|---:|---:|---:|---:|
| `flow_5x3` | 5 订单 × 3 机器 | 78 | 70 | 78 | **69**（OPTIMAL） | 69 |
| `flow_8x4` | 8 × 4 | 151 | 127 | 162 | **126**（OPTIMAL） | 126 |
| `jsp_6x4` | 6 × 4 | FAILED | FAILED | 71 | **67**（OPTIMAL） | 67 |
| `jsp_8x5` | 8 × 5 | FAILED | FAILED | 86 | **84**（OPTIMAL） | 84 |

（`jsp_priority` 一列报的是默认规则 `mwr` 的值；换规则的结果见下面 Day 5 那段。）

小实例上手算与枚举（**Day 1 / Day 3 / Day 5** 分别算过）：

| 实例 | 手算 / 枚举 | 方法给出的值 | 说明 |
|---|---|---|---|
| `tiny2x2`（手写 `.jsp`） | 枚举 4 个机器顺序 → 13 / 15 / 15 / 12 | Johnson 12（精确） | 2×2 上枚举与 Johnson 一致 |
| 三机器流水车间 | 枚举最优 10 | Johnson 11，NEH 10 | `m = 3` 时 Johnson 不再是精确解 |
| `tiny3x3` | 关键路径长度 7（两条并列） | CP-SAT 7 | 三条独立路径（手算 / 图 / 求解器）同一个数 |
| `jsp_6x4` | `LB = max(67, …) = 67` | CP-SAT 67 = LB | 目标值等于下界即证明最优，不需要求解器自证 |

`jsp_cpsat` 的预算实验（Day 4）：同一实例上 `time_limit=1s` → `FEASIBLE` 57（界 42，`gap` 0.263），`time_limit=10s` → `OPTIMAL` 56。**状态是「这次运行」的属性，不是方法的天性。**

## 6. 手算与独立复核

本周每条结论都配了一条**与实现无关**的复核路径：

```text
算法结论    -> 枚举器（machine order -> longest path，独立实现，不 import fjsp_shop）
图论结论    -> 手算弧数与关键路径（3n - k = 24，路径长度 7）
求解器结论  -> 目标值 == 下界 LB 时，不用求解器自证也能判定最优
排程结论    -> validate_schedule（机器不重叠 / 工序先后 / 机器资格 / 释放时间）
呈现结论    -> 甘特 CSV 写盘后读回，六列与排序键逐项比对
格式结论    -> format_standard_jsp 往返写回，与手写原文比对
```

枚举器（`examples/m3w1d5_baseline_vs_enumeration.py`，不 import `fjsp_shop`）的规模上限 `ENUMERATION_LIMIT = 200_000`：`tiny2x2` 是 `2!² = 4` 个组合，`jsp_6x4` 是 `6!⁴ = 331776` 超限，所以只在小实例上做对拍。**超限时明确拒绝，不降级成抽样。**

下界 `max(最大机器负载, 最大订单总工时)` 是 Day 4 示例脚本里的 `jsp_lower_bounds`：它只对「一工序一机器」的实例成立，遇到 `flexibility > 1` 的实例直接抛 `ValueError`，不返回一个会失效的数。

Day 5 的 32 行「方法 × 实例」对照表里，`flow_neh` 在两个流水车间实例上都只差 1，`jsp_priority` 在两个作业车间实例上差 4 与 2；`lpt` 在每个实例上都落在偏差那一档。**没有一条规则在四个实例上都最好**，所以只报观察，不据此调参。

## 7. 测试证据

`tests/test_week1.py`（51 个用例）与共享地基 `tests/test_foundation.py`（40 个）一起跑，91 个全绿：

```bash
cd projects/03_industrial_fjsp
python -m pytest -q tests/test_week1.py tests/test_foundation.py
# 91 passed in 1.07s
```

测试里的期望值一律**手算或用独立实现得到**（`tiny2x2` 的四个组合值、`tiny3x3` 的关键路径、`jsp_6x4` 的下界），不来自被测函数。整仓库的测试总数会随仓库内容变化，不作为核对判据。

## 8. 确定性契约

```text
相同实例 + 相同 spec  ->  相同排程与相同目标值（启发式与 CP-SAT 都一样）
CP-SAT：num_search_workers = 1，random_seed 由 spec["seed"] 固定
优先级规则：五条规则的顺序由 PRIORITY_RULES 固定，不依赖字典序
耗时：每行读数都会变（jsp_cpsat 在 0.007 ~ 0.049 秒之间浮动）—— 属观测值，不是规格值
析取图：Kahn 队列按 [源点, *工序, 汇点] 的出现顺序出队，拓扑序确定 —— 换一次运行不会换一条最长路径
```

## 9. 已知局限

```text
标准格式：只用 tests/data/ 下手写的三个小文件验证过；没有用 OR-Library 原始文件验证（也没有下载）
标准格式的信息量：只有「机器号 工时」对 —— 释放时间、交期、权重、可选机器全都不在格式里
Johnson：m >= 3 时退化为启发式，detail 里写清 applicability，不冒充精确解
下界：只对「一工序一机器」的实例成立（jsp_lower_bounds 遇到多台合格机器会抛 ValueError）
枚举器：ENUMERATION_LIMIT = 200_000，超过直接拒绝
甘特：是展示模型，job_id / duration 是可反推的冗余字段；ASCII 渲染只为读图，不参与任何计算
瓶颈机器：它的忙时是 makespan 的下界；只有在该机器全程不停时两者才相等
```

## 10. 遗留问题

| # | 问题 | 状态 |
|---|---|---|
| 1 | 三机器流水车间差 1 的那一步，能不能有更好的构造？ | 本周只如实记录差值，不做改进（改进需要另一套算法） |
| 2 | 关键块怎么用来改排程？ | 本周只做提取与展示，不做交换/邻域搜索 |
| 3 | 目标不是 makespan 时怎么报界？ | 本周一律 `best_bound = None`，`bound_kind` 写 `not_reported_for_this_objective` |
| 4 | 释放时间怎么进析取图？ | 作为源点出弧的权重；`earliest_starts` 与 `job.release_time` 取较大值 |
| 5 | `gap` 在没有界时填什么？ | `None`，绝不填 0 |
| 6 | 标准格式之外的信息从哪来？ | 不在本周范围：那是需要另一套实例描述的建模问题 |
| 7 | 瓶颈之外还有别的呈现吗？ | 不在本周范围：甘特与负载汇总已足够回答本周的问题 |

## 11. 待个人完成

闭卷重做两件事：一是 `flow_5x3` 上 `flow_johnson` 与 `flow_neh` 的手算对照（78 与 70 差在哪几道工序的先后上），二是 `tiny3x3` 的关键路径手推（两条长度为 7 的并列路径，逐弧加起来等于 7）。两件事都不看笔记写出来，才算把本周的两条主线（构造规则、图论表示）收进自己的手里。
