# Day 2：调度核心数据模型与不可变输入设计

> 当日主题：设计 `Job`、`Operation`、`Machine`、`Instance` 数据结构与不可变输入模型
> 当日产出：`scheduling_core` 数据模型 + 小实例 + 单元测试
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 把 Day 1 学到的调度领域概念映射成代码中的领域对象。
2. 区分：业务实体、输入参数、决策变量、求解结果。
3. 设计最小但可扩展的 `Job`、`Operation`、`Machine`、`Instance`。
4. 理解为什么调度输入应尽量设计为「不可变对象」。
5. 使用 Python type hints、`dataclass(frozen=True)` 实现不可变领域模型。
6. 建立清晰的 ID 引用关系，而不是在对象中制造循环嵌套。
7. 为后续的解析、校验、objective 模块准备好干净的接口。

今天的重点不是「写得多」，而是把**调度问题的输入边界设计正确**。

---

## 2. 为什么 Day 2 要先设计数据模型

调度项目后续所有模块都会依赖输入模型：

```text
业务数据 → Instance → 规则/精确/启发式算法 → Schedule → Validator → Objective → Benchmark
```

如果最底层数据模型混乱，后面很容易出现：

- 同一个字段在不同模块里含义不同；
- 算法偷偷修改输入数据；
- Job、Operation、Machine 之间形成复杂引用；
- 无法稳定序列化；
- 测试难写；
- Benchmark 无法复现；
- 后期新增 setup、calendar、worker、tool 时大面积重构。

因此 Month 1 的核心不是急着写复杂算法，而是先建立一个长期可扩展的 `scheduling_core`。

---

## 3. 先划清四类对象

### 3.1 输入实体

描述「问题是什么」：`Job`、`Operation`、`Machine`、`Instance`。这些对象应该尽量不可变。

### 3.2 决策变量

描述「怎么排」：`operation → machine`、`operation → start_time`、`operation → sequence_position`。它们**不属于输入模型**。

### 3.3 排程结果

例如：

```python
ScheduledOperation(operation_id="O1", machine_id="M1", start_time=0, end_time=5)
```

这是后续的 `Schedule` / `Solution` 层，今天不要把它塞进 `Operation` 本身。

错误示例：

```python
@dataclass
class Operation:
    id: str
    processing_time: int
    start_time: int | None = None
    machine_id: str | None = None
```

为什么不好？因为 `Operation = 输入`，而 `start_time / machine_id = 求解结果`。一旦混在一起，算法就容易直接修改输入对象。

### 3.4 派生指标

例如 `Completion Time`、`Makespan`、`Tardiness`、`Weighted Completion Time`，应该由独立 objective 模块计算。

---

## 4. 建议的最小目录结构

```text
projects/
└── 01_scheduling_core/
    ├── scheduling_core/
    │   ├── __init__.py
    │   └── models.py
    └── tests/
        └── test_models.py
```

今天只建 `models.py`，不要急着创建 `parser.py`、`objective.py`、`validator.py`、`rules.py`。

---

## 5. ID 设计：调度模型中非常重要的一层

调度系统里实体会越来越多：Job、Operation、Machine、Worker、Tool、Calendar、Route、Order、Batch…

最简单可靠的关联方式是：**稳定 ID + 显式引用**。

Operation 中保存 `job_id = "J1"`、`eligible_machine_ids = ("M1", "M2")`，而不是直接保存完整对象 `job: Job`、`machines: list[Machine]`。

后者虽然「面向对象味道更浓」，但会带来循环引用、序列化困难、深拷贝困难、hash 困难、测试对象构造复杂、数据版本控制困难。

工程上推荐：

```text
实体本身轻量化
关系使用 ID
Instance 负责聚合
```

---

## 6. Machine 数据模型

最小字段：`id` + `name`。

```python
@dataclass(frozen=True)
class Machine:
    id: str
    name: str
```

| 字段 | 含义 |
|---|---|
| `id` | 唯一机器标识 |
| `name` | 人类可读名称 |

工业排程里机器还可能有 `available_from / calendar / maintenance / qualification / capacity / machine_group / setup_state` 等，但这些属于后续的工业约束。当前目标是**先建立一个能支持经典调度问题的最小模型**，不要过度设计。

---

## 7. Operation 数据模型

最小版本：

```python
@dataclass(frozen=True)
class Operation:
    id: str
    job_id: str
    processing_time: int
    eligible_machine_ids: tuple[str, ...]
```

| 字段 | 含义 |
|---|---|
| `id` | 工序唯一 ID |
| `job_id` | 所属 Job |
| `processing_time` | 加工时间 |
| `eligible_machine_ids` | 可加工机器集合 |

### 为什么使用 tuple 而不是 list

如果目标是不可变模型，`eligible_machine_ids: tuple[str, ...]` 优于 `list[str]`，因为 list 可被 `op.eligible_machine_ids.append("M99")` 修改，而 tuple 不允许。这对于可复现实验非常重要。

---

## 8. Job 数据模型

```python
@dataclass(frozen=True)
class Job:
    id: str
    operation_ids: tuple[str, ...]
    release_time: int = 0
    due_date: int | None = None
    weight: float = 1.0
```

| 字段 | 数学常见符号 | 含义 |
|---|---|---|
| `id` | j | Job 唯一标识 |
| `operation_ids` | — | 工序顺序 |
| `release_time` | rj | 最早可开始时间 |
| `due_date` | dj | 交期 |
| `weight` | wj | 权重 / 优先级 |

### 为什么 operation_ids 是有序 tuple

对于 `J1: O1 → O2 → O3`，顺序本身代表 precedence，所以 `operation_ids=("O1", "O2", "O3")`，不能用 `set`（会丢失顺序）。

---

## 9. Instance：整个调度问题的输入容器

```python
@dataclass(frozen=True)
class Instance:
    jobs: tuple[Job, ...]
    operations: tuple[Operation, ...]
    machines: tuple[Machine, ...]
```

算法入口未来可以统一成 `def solve(instance: Instance) -> Schedule`，让 SPT、EDD、LPT、Local Search、SA、MILP、CP-SAT、RL 都围绕同一个输入模型工作。

---

## 10. 完整最小实现

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Machine:
    id: str
    name: str


@dataclass(frozen=True)
class Operation:
    id: str
    job_id: str
    processing_time: int
    eligible_machine_ids: tuple[str, ...]


@dataclass(frozen=True)
class Job:
    id: str
    operation_ids: tuple[str, ...]
    release_time: int = 0
    due_date: int | None = None
    weight: float = 1.0


@dataclass(frozen=True)
class Instance:
    jobs: tuple[Job, ...]
    operations: tuple[Operation, ...]
    machines: tuple[Machine, ...]
```

---

## 11. 构造第一个小实例

```text
机器：M1、M2

作业：
J1:
  O1, p=3, 可在 M1/M2 加工
  O2, p=2, 只能在 M2 加工

J2:
  O3, p=4, 只能在 M1 加工
```

```python
m1 = Machine(id="M1", name="Machine 1")
m2 = Machine(id="M2", name="Machine 2")

o1 = Operation(id="O1", job_id="J1", processing_time=3, eligible_machine_ids=("M1", "M2"))
o2 = Operation(id="O2", job_id="J1", processing_time=2, eligible_machine_ids=("M2",))
o3 = Operation(id="O3", job_id="J2", processing_time=4, eligible_machine_ids=("M1",))

j1 = Job(id="J1", operation_ids=("O1", "O2"), release_time=0, due_date=8)
j2 = Job(id="J2", operation_ids=("O3",), release_time=1, due_date=7)

instance = Instance(jobs=(j1, j2), operations=(o1, o2, o3), machines=(m1, m2))
```

---

## 12. 用图理解这个 Instance

```text
Instance
├── Machines: M1, M2
├── Jobs
│   ├── J1: O1 → O2
│   └── J2: O3
└── Operations
    ├── O1: p=3, eligible={M1,M2}
    ├── O2: p=2, eligible={M2}
    └── O3: p=4, eligible={M1}
```

---

## 13. 为什么输入对象要不可变

假设算法写成 `instance.jobs[0].due_date = 999`。如果允许这么做，会导致：

- 第一次运行和第二次运行结果可能不同；
- 多算法对比失去公平性；
- 单元测试互相污染；
- 缓存和 hash 变得危险；
- 调试困难。

理想情况是「Instance 输入后不可被算法修改」，因此用 `@dataclass(frozen=True)` 配合 `tuple` 代替 `list`。

---

## 14. 注意：frozen=True 不等于「深度不可变」

```python
@dataclass(frozen=True)
class BadInstance:
    jobs: list[Job]
```

虽然 `bad.jobs = []` 不允许，但 `bad.jobs.append(...)` 仍然可能发生。因此真正不可变的数据模型要同时避免可变容器，优先使用 `tuple`（Month 1 先优先 tuple 即可，frozenset、MappingProxyType 以后需要再用）。

---

## 15. 输入模型中不要保存什么

以下字段不要加入输入模型：

```text
start_time / end_time / assigned_machine / sequence_position
completion_time / tardiness / objective_value
```

因为它们属于 `Solution / Schedule / Evaluation`，而不是 `Instance`。记住：**Problem Data ≠ Decision ≠ Result**。

---

## 16. ID 唯一性

今天虽然重点是模型结构，但你要知道这些必须被检查：

```text
Machine.id 唯一、Job.id 唯一、Operation.id 唯一
```

例如 `Machine(id="M1", ...)` 出现两次就是不合法的输入。系统性的校验会放到后续的校验器模块，今天先写少量模型级测试。

---

## 17. processing_time 的语义

当前阶段默认：`processing_time > 0`、单位统一、确定性加工时间。

`3` 到底表示 3 秒 / 3 分钟 / 3 小时，必须由 Instance 约定统一。最危险的输入之一就是「部分数据用分钟、部分数据用小时」。工业项目建议统一转成一个时间单位（如 minute）。Month 1 暂不需要专门建 `TimeUnit` 类型，但一定要在文档里写清楚。

---

## 18. due_date 为 None 的含义

```python
due_date=None
```

表示「该 Job 没有明确交期」，**不是** `due_date = 0`。这两个语义完全不同。EDD 规则需要明确「没有 due_date 的 Job 如何排序」（例如放在最后），这个策略应写在规则模块，而不是偷偷写在数据模型里。

---

## 19. weight 的含义

```python
weight: float = 1.0
```

通常表示业务优先级、延期成本、订单价值、服务等级。在调度目标中常见 `Σ wj·Cj` 或 `Σ wj·Tj`。今天只保留字段，不计算目标。

---

## 20. Release Time 的含义

`release_time` 即 `rj`，表示 Job 最早什么时候可以进入调度系统。例如 `J1 release_time=0`、`J2 release_time=10`，那么即使机器空闲，J2 也不能在 t < 10 时开始。规则基线阶段会正式处理 release time。

---

## 21. Job 和 Operation 的关系设计

推荐：

```text
Job --operation_ids--> Operation
Operation --job_id--> Job
```

这是一种轻量的双向可验证关系：`j1.operation_ids == ("O1","O2")` 同时 `o1.job_id == "J1"`、`o2.job_id == "J1"`。后续 validator 应检查两边是否一致。

---

## 22. Machine 和 Operation 的关系设计

`eligible_machine_ids=("M1","M2")` 表示 O1 可以选择 M1 或 M2。

- 经典 Job Shop：`eligible_machine_ids` 通常只有一个元素；
- Flexible Job Shop：`eligible_machine_ids` 可能有多个。

这个设计使同一个模型可以自然支持 JSP 与 FJSP。

---

## 23. 一个重要建模问题：加工时间是否依赖机器

当前版本 `processing_time: int` 隐含假设「同一个 Operation 在所有可选机器上加工时间相同」。但 FJSP 常见「O1 在 M1 上需要 3、在 M2 上需要 5」。未来可以升级为 `processing_times: tuple[tuple[str,int],...]` 或 `dict[str,int]`，但当前先不扩展——目标是学习基础框架，而不是一次设计完整工业模型。

---

## 24. 什么时候才应该扩展模型

遵循「**新字段必须来自明确业务需求或算法需求**」，而不是「以后可能有用，所以现在先加」。未来真正需要 setup / calendar / worker / tool / batch / qualification 时再添加对应结构，避免「大而全但没人敢改」的领域模型。

---

## 25. 今天应该写的测试

建立 `tests/test_models.py`，至少覆盖：

- 可以正常创建 Machine / Operation / Job / Instance；
- 对象不可重新赋值（`FrozenInstanceError`）；
- tuple 不应被 append。

---

## 26. 不要在模型里做太多「聪明逻辑」

不推荐在 `Job` 里写 `compute_tardiness()`、`select_machine()`、`optimize()` 等方法。领域输入对象应保持轻量、明确、稳定、容易测试；算法逻辑放在独立模块。

---

## 27. 推荐的职责边界

| 模块 | 职责 |
|---|---|
| `models.py` | 数据结构 |
| `parser.py` | 外部文件 → 模型 |
| `validation.py` | 检查输入合法性 |
| `objective.py` | 计算目标 |
| `rules.py` | SPT/EDD/WSPT/LPT |
| `schedule.py` | 排程结果结构 |
| `validator.py` | 检查 Schedule 是否可行 |

今天只做 `models.py`。

---

## 28. 辅助属性

今天可以加、但不必多：`Instance.num_jobs`、`num_machines` 这类纯派生、无副作用的 `@property` 问题不大，但不要滥用。

---

## 29. 今日练习 1：单机调度实例

构造 `M1`；`J1: p=3, due=8`、`J2: p=1, due=4`、`J3: p=5, due=12`，每个 Job 单工序（`J1→O1`、`J2→O2`、`J3→O3`）。要求创建 1 个 Machine、3 个 Operation、3 个 Job、完整 Instance，并打印所有 Job ID。

---

## 30. 今日练习 2：两台机器

```text
M1, M2
J1: O1 p=3 {M1}; O2 p=2 {M2}
J2: O3 p=4 {M1, M2}
```

思考：这个模型更接近 JSP 还是 FJSP？答案：含有可选机器，因此已经具有 FJSP 的特征。

---

## 31. 今日练习 3：找出模型设计错误

```python
@dataclass
class Operation:
    id: str
    machine: Machine
    start_time: int
    end_time: int
```

至少指出 3 个问题。参考答案：(1) 输入与结果混合；(2) Operation 直接嵌 Machine，耦合过深；(3) 对象可变；(4) 无 `job_id`；(5) 无法表达多可选机器；(6) `end_time` 是求解结果，不应输入。

---

## 32. 今日练习 4：不可变性分析

```python
@dataclass(frozen=True)
class Instance:
    jobs: list[Job]
```

是不是严格不可变？答案：不是。`frozen=True` 只禁止属性重新绑定，但 `jobs` 这个 list 自身仍可修改。改成 `tuple[Job, ...]` 更合理。

---

## 33. 今日练习 5：做一次「字段归属判断」

| 字段 | 所属 |
|---|---|
| `processing_time` | Operation 输入 |
| `due_date` | Job 输入 |
| `machine_id`（可选机器） | Operation 输入 |
| `assigned_machine_id` | Schedule 输出 |
| `start_time` | Schedule 输出 |
| `completion_time` | 派生结果 |
| `weight` | Job 输入 |
| `objective_value` | Evaluation 输出 |

如果这一题能快速做对，说明你开始建立清晰的建模边界。

---

## 34. 建议今天的代码风格

坚持：`from __future__ import annotations`、type hints、清晰命名、不可变输入、小函数、pytest。工程规范（ruff / black / mypy / pre-commit）今天不一定全部配置完成，但代码风格从现在就统一。

---

## 35. 一个更完整的 models.py 示例

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Machine:
    id: str
    name: str


@dataclass(frozen=True, slots=True)
class Operation:
    id: str
    job_id: str
    processing_time: int
    eligible_machine_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Job:
    id: str
    operation_ids: tuple[str, ...]
    release_time: int = 0
    due_date: int | None = None
    weight: float = 1.0


@dataclass(frozen=True, slots=True)
class Instance:
    jobs: tuple[Job, ...]
    operations: tuple[Operation, ...]
    machines: tuple[Machine, ...]
```

`slots=True` 不是必须，但可以减少误加属性，并让模型更明确。

---

## 36. 为什么今天暂时不使用 Pydantic

Pydantic 很适合 API 输入、JSON 校验、配置模型，但今天的目标是理解纯粹的领域模型。如果一开始全部依赖 Pydantic，很容易把「领域设计」和「外部输入校验」混在一起。先写纯 dataclass 领域模型，再在需要时引入外部输入校验。

---

## 37. 建议 3～4 小时学习安排

1. **复习 Day 1（20 分钟）**：能回答什么是 Job / Operation / Machine / release time / due date / processing time。
2. **领域模型设计（45 分钟）**：自己先画出 Job / Operation / Machine / Instance 的字段、类型、默认值、关系，不要先看代码答案。
3. **实现 models.py（45～60 分钟）**：`frozen=True`、`tuple`、type hints。
4. **构造小实例（30 分钟）**：至少 1 个单机实例 + 1 个双机实例，手动画出对象关系。
5. **测试（30～40 分钟）**：至少 5 个测试（Machine/Operation/Job/Instance 创建 + 不可变性）。
6. **复盘（20 分钟）**：为什么输入和 Schedule 必须分离？为什么用 ID？为什么 tuple 比 list 更适合输入模型？哪些字段未来可能扩展？

---

## 38. 今日验收标准

**理论**：能解释 Job/Operation/Machine/Instance 各自职责；输入数据与排程结果的区别；为什么避免循环对象引用；为什么调度输入应不可变；为什么 `frozen=True` 不能保证深度不可变。

**代码**：已实现 Machine/Operation/Job/Instance，全部有 type hints，输入对象 frozen，集合用 tuple，`Job→operation_ids`、`Operation→job_id`、`Operation→eligible_machine_ids`。

**测试**：至少 5 个 pytest 测试且能 `pytest` 通过。

---

## 39. 今日最终产出

```text
projects/01_scheduling_core/
├── scheduling_core/
│   ├── __init__.py
│   └── models.py
└── tests/
    └── test_models.py
```

笔记记录：数据模型设计原则、四个核心实体、不可变设计、ID 关系设计、小实例、遇到的问题。

---

## 40. Day 2 不应该做的事情

为了保持学习节奏，今天不要提前深入：JSON/CSV Parser、复杂字段校验、Objective、SPT/EDD/LPT、Gantt、Local Search、MILP、CP-SAT。今天真正要完成的是：**建立一个稳定、清晰、不可变、可扩展的调度问题输入模型。**

---

## 41. 今日复盘题

不看笔记回答：

1. 为什么 `Operation` 不应该包含 `start_time`？
2. 为什么 `Job.operation_ids` 应该是 tuple 而不是 set？
3. 为什么不推荐 `Operation.machine: Machine`？
4. `frozen=True` 能否阻止 list append？
5. `release_time` 和 `due_date` 分别表示什么？
6. `eligible_machine_ids` 有多个值时对应哪类调度问题特征？
7. 为什么 Instance 应成为算法统一输入？
8. 输入模型、Schedule、Objective 三者的职责分别是什么？

---

## 42. 今日一句话总结

> **Day 2 的核心不是写四个 dataclass，而是学会把「调度问题本身」与「算法决策和结果」彻底分离，并建立不可变、可验证、可扩展的统一输入接口。**
