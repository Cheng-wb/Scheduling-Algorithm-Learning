# M1 Week 1 周总结：调度问题语言与经典规则

> 笔记：[Day1](Week_1/Day1.md) · [Day2](Week_1/Day2.md) · [Day3](Week_1/Day3.md) · [Day4](Week_1/Day4.md) · [Day5](Week_1/Day5.md) · [Day6](Week_1/Day6.md) · [Day7](Week_1/Day7.md)

## 1. 本周目标与成果

本周建立了调度问题三字段表示法、统一输入模型、输入校验与 objective 模块，并实现 SPT、EDD、WSPT、单机 LPT 与并行机 LPT 基线。通过手算小实例对拍验证了规则顺序、时间推进、机器分配和关键指标，并整理了 release time、total tardiness 与 parallel LPT 的失效反例。

当前系统已经能够从结构化 `Instance` 生成基础 `Schedule`，并输出甘特图数据；候选解表示、独立解码器、邻域与独立 Schedule Validator 已在工程中就位。

## 2. 问题语言（α|β|γ）

| 问题 | 含义 |
|---|---|
| `1\|\|ΣCj` | 单机、无额外约束、最小化总完成时间 |
| `1\|\|Lmax` | 单机、最小化最大延迟 |
| `1\|\|ΣwjCj` | 单机、最小化加权总完成时间 |
| `P\|\|Cmax` | 同质并行机、最小化最大完工时间 |

`α` 描述机器环境（`1` / `P` / `Q` / `R`），`β` 描述约束（`rj`、`prec`、`pmtn` 等），`γ` 描述目标。

## 3. 数据模型

| 实体 | 核心字段 |
|---|---|
| `Job` | `id`, `operation_ids`, `release_time`, `due_date`, `weight` |
| `Operation` | `id`, `job_id`, `processing_time`, `eligible_machine_ids` |
| `Machine` | `id`, `name` |
| `Instance` | `jobs`, `operations`, `machines` |
| `ScheduledOperation` | `operation_id`, `machine_id`, `start_time`, `end_time` |
| `Schedule` | `operations` |

输入实体用 `@dataclass(frozen=True, slots=True)` + `tuple`，保证不可变，可被多个算法公平复用。输入与结果严格分离：`eligible_machine_ids` 是**允许范围**（约束），`machine_id` 是**实际决策**（结果）。

## 4. Objective

| 指标 | 公式 | 业务含义 |
|---|---|---|
| `Cmax` | `max_j C_j` | 所有任务何时全部完成 |
| `ΣCj` | `Σ_j C_j` | 整体完成速度 |
| `Lmax` | `max_j (C_j − d_j)` | 最严重的交期偏离（可为负） |
| `ΣTj` | `Σ_j max(0, C_j − d_j)` | 累计迟交程度（恒非负） |
| `ΣwjCj` | `Σ_j w_j C_j` | 高价值任务是否更早完成 |
| `ΣFj` | `Σ_j (C_j − r_j)` | 总流程时间 |

**不存在脱离 objective 的「最好排程」**。Rule 只负责产生 `Schedule`，Objective 只负责评价，两者分离才能让不同算法公平比较。

## 5. 规则

| 规则 | 排序键 / 决策 | 经典最优问题 | 结论 |
|---|---|---|---|
| SPT | `p` 升序 | `1\|\|ΣCj` | 最优 |
| EDD | `d` 升序（`None` 视为 +∞） | `1\|\|Lmax` | 最优 |
| WSPT | `p/w` 升序（`Fraction` 精确比较） | `1\|\|ΣwjCj` | 最优 |
| LPT | `p` 降序 | 单机对照 baseline | 不适用于 `ΣCj` |
| Parallel LPT | `p` 降序 + 选最小 `ready` 机器 | `P\|\|Cmax` | 启发式/近似 |

释放时间处理采用 **non-delay 列表调度**：维护可选集合 `{j | rj <= t}`，无可用任务时把 `t` 推进到最小 `rj`。

## 6. 最优性条件（必须与 α|β|γ 同记）

> 「SPT 最优」是错的，正确的是「**SPT 对 `1||ΣCj` 最优**」。

以上全部「最优」均附带条件：**无释放时间、无额外约束、正权重、不可抢占**。`β` 字段的一点变化即可让结论失效。

## 7. 失效反例

完整推导与可执行断言见 [counterexamples.md](../projects/01_scheduling_core/notes/counterexamples.md) 与 [test_week1_review.py](../projects/01_scheduling_core/tests/test_week1_review.py)。

| # | Problem | 规则结果 | 更优解 | 结论 |
|---|---|---|---|---|
| CE-01 | `1\|rj\|ΣCj` | non-delay SPT `ΣCj=201` | 故意空转 `ΣCj=104` | `rj` 破坏 SPT 最优性，NP-hard |
| CE-02 | `1\|\|ΣTj` | EDD `ΣTj=4` | `ΣTj=3` | 对 `Lmax` 最优推不出对 `ΣTj` 最优 |
| CE-03 | `P\|\|Cmax` | LPT `Cmax=7` | `Cmax=6` | LPT 是启发式，近似界 `4/3 − 1/(3m)` |
| CE-04 | `1\|\|ΣCj` | LPT `ΣCj=28` | SPT `ΣCj=20` | 单机 LPT 只能作对照 baseline |

## 8. 手算测试结果

`tests/test_month1.py::test_ten_hand_calculations` 用 10 个独立手算实例对拍，覆盖单机排序、释放空闲、缺失交期、平局、权重与并行机；expected 全部来自显式手算时间线，**非由被测算法生成**。

复跑命令：

```bash
cd projects/01_scheduling_core
python -m pytest -q
```

## 9. 接口约定（API Contract）

```python
load_json_instance(path) -> Instance
load_csv_instance(dir) -> Instance
save_json_instance(instance, path) -> None

validate_instance(instance) -> None            # Input Validator
validate_schedule(instance, schedule) -> None  # Schedule Validator（独立）
schedule_errors(instance, schedule) -> list[str]

spt(instance, *, machine_id=None) -> Schedule
edd(instance, *, machine_id=None) -> Schedule
wspt(instance, *, machine_id=None) -> Schedule
lpt(instance, *, machine_id=None) -> Schedule
parallel_lpt(instance) -> Schedule
parallel_makespan_lower_bound(instance) -> int

decode(instance, candidate) -> Schedule

makespan(instance, schedule) -> int
total_completion_time(instance, schedule) -> int
max_lateness(instance, schedule) -> int
total_tardiness(instance, schedule) -> int
weighted_completion_time(instance, schedule) -> float

to_gantt_rows(instance, schedule) -> list[dict]
write_gantt_csv(rows, path) -> None
```

**Gantt schema**：六字段 `machine_id, job_id, operation_id, start_time, end_time, duration`，其中 `duration = end_time − start_time`，按 `(machine_id, start_time, operation_id)` 排序。

## 10. 确定性契约

```text
Job 平局:     job.id 升序
Machine 平局: machine.id 升序

相同 Instance + 相同 Config  →  相同 Schedule
```

这是可复现实验与后续 Benchmark 公平比较的前提，任何重构都不应改变。

## 11. 已知局限与隐含假设

```text
单机规则：恰好一台机器（或显式 machine_id）、每 Job 恰好一道工序、不可抢占
EDD：     due_date=None 视为 +∞，排最后
WSPT：    要求 weight > 0
Parallel LPT：r=0、同质机器、全资格；要求每 Job 恰好一道工序
```

本周**没有**实现 MILP / CP-SAT、局部搜索 / SA、工业级约束（setup / calendar / worker）。这是分阶段推进：先把 `baseline + validator + objective + benchmark` 做可信，精确算法才有公平参照。

## 12. 遗留问题

| # | 问题 | 状态 |
|---|---|---|
| 1 | 候选解与 Schedule 如何分离？ | 已由 `solution.py` 的 `Candidate` 落地 |
| 2 | decoder 保证可行，还是 validator 发现错误？ | 两者独立：`decoder.py` 构造，`schedule_validation.py` 独立校验 |
| 3 | 有 `rj` 时静态 permutation 如何解码？ | `decode` 取 `max(machine_ready, predecessor_end, release)` |
| 4 | 并行机 permutation 是否足以表示选机？ | 不足，`Candidate` 需同时含 `order` 与 `assignments` |
| 5 | 邻域如何保证不制造非法解？ | `neighborhoods.py` 只产生新 Candidate，由 `validate_candidate` 把关 |
| 6 | 小规模枚举对拍 | `oracle.py` 独立穷举，已完成 5 个种子对拍 |
| 7 | 随机实例从哪来 | `scheduling_io/generator.py`（局部 RNG，不改全局随机状态） |

核心原则：**不能让 decoder 自己证明自己**——与「expected 不由被测函数生成」是同一个思想。

## 13. 待个人完成

闭卷推导 SPT / WSPT 的相邻交换证明，并重做 CE-01 与 CE-02 的手算，确认不看笔记也能写出完整时间线。
