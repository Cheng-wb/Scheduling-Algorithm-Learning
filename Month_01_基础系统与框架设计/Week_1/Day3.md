# Day 3：输入解析、字段校验与独立 Objective 模块

> 所属：第 1 月 · 第 1 周 · 第 3 天
> 主题：把「外部数据」变成「可信输入」，把「排程结果」变成「统一指标」

---

## 1. 今日学习目标

1. 理解调度系统里的**数据流边界**：原始数据、领域模型、校验、求解、结果、评估，各自在哪一层、谁该干什么。
2. 会写一个 **JSON Parser**，把外部 JSON 转成昨天定义好的不可变 `Instance`。
3. 会写一个 **Input Validator**，用 fail-fast 的方式检查输入的字段、唯一性、引用完整性、双向一致性。
4. 会写一个**独立的 Objective 模块**，从 `Schedule` 统一算出 `makespan / ΣCj / tardiness / ΣwjCj / flow time`。

---

## 2. 数据流边界：四层职责

昨天只建了「领域模型」（Job / Operation / Machine / Instance）。今天要把它前后的两层补上：

```text
Raw Data (JSON/CSV)
      │  Parser（读、结构、类型转换）
      ▼
Domain Model (Instance)
      │  Input Validator（字段/唯一性/引用/一致性）
      ▼
可信的 Instance
      │  Solver（算法，今天还没有）
      ▼
Schedule（排程结果）
      │  Objective Evaluator（统一指标）
      ▼
数字（makespan、ΣCj、…）
```

关键的一句话：**每层只做一件事，层与层之间通过不可变对象传递**。

- Parser 只负责「把外部数据读进来、转成领域对象」，**不判断对错**。
- Input Validator 只负责「判断 Instance 本身是否合法」，**不求解**。
- Objective Evaluator 只负责「给定一个 Schedule 算出指标」，**不关心这个 Schedule 是怎么来的**。

---

## 3. 为什么 Parser 和 Validator 要分开

很多人会写一个函数，一边读 JSON、一边判断「这个 job 引用的 machine 不存在，报错」。这样写的问题：

1. **职责纠缠**：读文件、转类型、查引用，全混在一起，改一处就要重看全部。
2. **来源耦合**：校验逻辑本该对所有输入来源通用（JSON、CSV、数据库），但解析逻辑是「来源专属」的。
3. **测试困难**：想测「重复 ID 会被拒绝」，却被迫先写一个文件再读进来。

正确做法：

```text
load_json_instance(path)          # 只负责 JSON 来源
        │ 返回 Instance（可能不合法）
        ▼
validate_instance(instance)       # 与来源无关，只判断语义
        │ 合法就什么都不做，不合法就 raise
        ▼
可信的 Instance
```

Parser 的产物可以「先不合法」，交给 Validator 统一把关。这样 CSV、JSON 甚至未来的数据库导入，最终都走同一个 `validate_instance`。

---

## 4. JSON 输入格式

今天只约定一种输入格式（JSON）。参考文档里的 CSV 只要求理解「Parser 是来源专属、Validator 是来源通用」这个思想，不实现万能 CSV parser。

```json
{
  "machines": [
    {"id": "M1", "name": "Machine 1"},
    {"id": "M2", "name": "Machine 2"}
  ],
  "jobs": [
    {"id": "J1", "operation_ids": ["O1", "O2"], "release_time": 0, "due_date": 10, "weight": 2.0},
    {"id": "J2", "operation_ids": ["O3"], "release_time": 0, "due_date": 8, "weight": 1.0}
  ],
  "operations": [
    {"id": "O1", "job_id": "J1", "processing_time": 3, "eligible_machine_ids": ["M1", "M2"]},
    {"id": "O2", "job_id": "J1", "processing_time": 2, "eligible_machine_ids": ["M2"]},
    {"id": "O3", "job_id": "J2", "processing_time": 4, "eligible_machine_ids": ["M1"]}
  ]
}
```

几个约定：

- `release_time` 缺省为 `0`。
- `weight` 缺省为 `1.0`。
- `due_date` 缺省为 `null`，表示「无交期」。

---

## 5. Parser 第一版

对应文件 `scheduling_io/parser.py`：

```python
def load_json_instance(path: str | Path) -> Instance:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return _parse_instance(data)
```

`_parse_instance` 只做三件事：

1. 从 `data["machines"]` / `data["jobs"]` / `data["operations"]` 里逐条取字段。
2. 用 `tuple(...)` 把列表转成不可变的 tuple（对应昨天 `Operation.eligible_machine_ids` 是 tuple 的约定）。
3. 用 `item.get("release_time", 0)`、`item.get("weight", 1.0)` 补默认值。

注意 Parser **不调用** `validate_instance`——它老老实实返回一个「可能不合法」的 Instance。

---

## 6. 输入校验的四个层级

Validator 按「从局部到全局」分四层，逐层收紧：

| 层级 | 检查内容 | 例子 |
|------|----------|------|
| 字段级 | 单个字段是否在合法范围 | `processing_time > 0`、`release_time >= 0` |
| 唯一性 | 同类 ID 是否重复 | 两个 Job 都叫 `J1` |
| 引用完整性 | ID 是否指向存在的对象 | `eligible_machine_ids` 里出现不存在的 `M99` |
| 关系一致性 | 两个方向的关系是否对得上 | `op.job_id` 说它属于 J1，但 J1 的 `operation_ids` 里没有它 |

这四层的顺序不是随意排的：先查字段（最快、最便宜），再查唯一性，再查引用，最后查「两个集合之间的双向关系」。反过来也没问题，但「从局部到全局」读起来更顺。

---

## 7. Validation Error 设计：fail-fast

校验失败时，我们用一个专门的异常：

```python
class InstanceValidationError(ValueError):
    """输入实例不合法时抛出。"""
```

约定两点：

1. **继承 `ValueError`**：语义上它就是「值不对」，调用方可以用 `except ValueError` 兜住。
2. **fail-fast**：`validate_instance` 遇到**第一个**错误就 `raise`，不做「收集所有错误再一次性报告」。对 Month 1 的规模来说，第一个错误就足以让数据提供者回去修，收集全部错误反而让函数签名变复杂。

`validate_instance(instance)` 返回 `None`——合法就不说话，不合法就抛异常。

---

## 8. 13 条校验规则

`validate_instance` 依次检查：

**唯一性（3 条）**

1. machine id 不重复
2. job id 不重复
3. operation id 不重复

**字段级（4 条）**

4. `processing_time > 0`
5. `release_time >= 0`
6. `weight > 0`
7. `due_date is None` 或 `>= 0`

**引用完整性（4 条）**

8. `Operation.job_id` 指向的 Job 存在
9. `eligible_machine_ids` 非空
10. `eligible_machine_ids` 里的每个 machine 都存在
11. `Job.operation_ids` 里的每个 operation 都存在

**关系一致性（2 条）**

12. 正向：`operation.job_id == job.id`（Job 列出某工序，那道工序必须回指它）
13. 反向：`operation.id in job.operation_ids`（Operation 声称属于某 Job，那个 Job 的列表里必须有它）

第 12、13 条要成对出现，只查一边会漏掉「A 指向 B，但 B 不认 A」的坏数据。

---

## 9. 核心代码：`_check_unique`

```python
def _check_unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise InstanceValidationError(f"duplicate {label} ids")
```

`len(list) != len(set(list))` 是判断「有没有重复」的惯用写法，`set` 会去重，两者长度不等就说明有重复。

---

## 10. 最小 Schedule 表示

Objective 需要一个「排程结果」作为输入。今天先定义它的**最小数据结构**，不引入可行性判断：

```python
@dataclass(frozen=True, slots=True)
class ScheduledOperation:
    operation_id: str
    machine_id: str
    start_time: int
    end_time: int

@dataclass(frozen=True, slots=True)
class Schedule:
    operations: tuple[ScheduledOperation, ...]
```

对应文件 `scheduling_core/schedule.py`。

注意：这里**没有** `processing_time`，因为 `end_time - start_time` 就是它的加工时长，存两份反而会不一致。这里的 `machine_id` 是「被分配到的机器」，和 `Operation.eligible_machine_ids`（可选机器集合）是两个概念。

---

## 11. Objective 模块为什么必须独立

如果每个算法自己算指标，会出现三类问题：

1. **算法之间不可比**：A 算法算 `makespan` 时把最后一个 job 当分母，B 算法把第一个 job 当分母，两个数字放一起毫无意义。
2. **指标定义漂移**：同一个「总完工时间」，今天在求解器里写成 `sum(...)`，明天在 benchmark 里又写成另一套。
3. **改动面过大**：改一次指标定义，要翻所有算法文件。

独立 Objective 模块的约束是：**所有算法统一输出 `Schedule`，所有指标统一由 Objective 从 `Schedule` 计算**。这样「指标怎么算」只存在一个地方，所有比较都在同一把尺子下进行。

---

## 12. 六个 Objective

所有 Objective 都先算「每个 Job 的完工时间 Cj」，再在其上汇总。

### 12.1 `job_completion_times`

```python
def job_completion_times(instance, schedule) -> dict[str, int]:
    # 每个 Job 的完工时间 = 该 Job 所有工序中最大的 end_time
```

一个 Job 可能有多道工序（如 J1 有 O1、O2），它的完工时间是**最后完成的那道工序**的 `end_time`，所以取 `max`。

### 12.2 `makespan`（Cmax）

```text
Cmax = max_j Cj
```

最后一个 Job 完成的时间，衡量「整体完工」。

### 12.3 `total_completion_time`（ΣCj）

```text
ΣCj = Σ_j Cj
```

所有 Job 完工时间之和。

### 12.4 `total_tardiness`（ΣTj）

```text
Tj = max(0, Cj - dj)
ΣTj = Σ_j Tj
```

只有超过交期才算迟交；`dj = None` 的 Job **不参与**求和。

### 12.5 `weighted_completion_time`（ΣwjCj）

```text
ΣwjCj = Σ_j wj · Cj
```

权重越大的 Job，晚完工的代价越大。

### 12.6 `total_flow_time`（ΣFj）

```text
Fj = Cj - rj
ΣFj = Σ_j Fj
```

流动时间 = 完工时间减去到达时间，衡量「这个 Job 在系统里待了多久」。当所有 `rj = 0` 时，`Fj = Cj`，`ΣFj = ΣCj`。

---

## 13. 手算示例

用第 4 节的 JSON，手工排一个简单可行排程：

```text
O1 放 M1：0-3
O2 放 M2：3-5   （J1 的第二道，等 O1 完成）
O3 放 M1：3-7   （等 O1 释放 M1）
```

| Job | 工序 | 最后完成时间 Cj | dj | wj | Tj = max(0, Cj-dj) |
|-----|------|----------------|----|----|--------------------|
| J1  | O1、O2 | 5 | 10 | 2.0 | 0 |
| J2  | O3 | 7 | 8 | 1.0 | 0 |

| 指标 | 计算 | 结果 |
|------|------|------|
| Cmax | max(5, 7) | 7 |
| ΣCj | 5 + 7 | 12 |
| ΣTj | 0 + 0 | 0 |
| ΣwjCj | 2.0×5 + 1.0×7 | 17.0 |

参考文档还给了两个更小的对拍案例（第 19 节：makespan=5、ΣCj=8、ΣTj=0、ΣwjCj=11；第 26 节练习 2：Cmax=8、ΣCj=19、ΣTj=1、ΣwjCj=40），这些都写进了 `tests/test_objective.py` 作单元测试。

---

## 14. Input Validator 与 Schedule Validator 的区别

今天只做了前者，一定要分清楚：

| | Input Validator（今天） | Schedule Validator（以后） |
|---|---|---|
| 检查对象 | `Instance`（问题本身） | `Schedule`（某个排程） |
| 回答问题 | 这个问题定义得对不对？ | 这个排程可不可行？ |
| 典型检查 | ID 唯一、引用存在 | 机器不重叠、工序顺序不颠倒、`start+加工=end` |
| 何时调用 | 求解前一次 | 每次产生排程后 |

一句话：**Input Validator 保证「题目没错」，Schedule Validator 保证「答案没错」**。后者是后续周的重点，今天不实现。

---

## 15. 职责边界总表

| 模块 | 输入 | 输出 | 职责 |
|------|------|------|------|
| `parser.py` | JSON 文件 | `Instance` | 读、结构、类型转换 |
| `validation.py` | `Instance` | `None` / raise | 合法性判断 |
| `models.py` | — | 领域对象 | 不可变数据模型 |
| `schedule.py` | — | `Schedule` | 排程结果表示 |
| `objective.py` | `Instance` + `Schedule` | 数字 | 指标计算 |

---

## 16. 今日练习

1. **练习 1**：手写一段 JSON，故意让 `eligible_machine_ids` 引用一个不存在的机器，运行 `validate_instance`，确认它抛 `InstanceValidationError`。
2. **练习 2**：把第 13 节的排程改成把 O2 放到 M1 上（和 O1 重叠），观察 Objective 是否还能算出数字。想清楚：为什么 Objective 不拦这个错误？（因为它不负责可行性，那是 Schedule Validator 的事。）
3. **练习 3**：给 J2 去掉 `due_date`（设成 `null`），重新算 `total_tardiness`，确认 J2 不再参与。
4. **练习 4**：自己构造一个两工序 Job，验证 `job_completion_times` 取的是「较晚完成的那道工序」。

---

## 17. 验收清单

- [ ] `parser.py` 能从 JSON 读出 2 机器 / 2 作业 / 3 工序的 Instance。
- [ ] `validation.py` 对 13 条规则各自有负例测试，且合法实例能通过。
- [ ] `objective.py` 的 6 个函数都用手算值对拍过。
- [ ] `python -m pytest -q` 全部通过。
- [ ] `python -m examples.m1w1d3_pipeline` 能打印出 7 / 12 / 0 / 17.0。

---

## 18. 复盘题

1. 为什么 `load_json_instance` 不直接调用 `validate_instance`？分开的好处是什么？
2. 「正向一致」和「反向一致」各漏掉哪一种坏数据？为什么两条都要查？
3. 如果以后要支持 CSV 输入，哪些代码要新写、哪些代码能复用？
4. 为什么 `ScheduledOperation` 里没有 `processing_time` 字段？

---

## 19. 一句话总结

今天把「不可变的数据模型」向前接到「外部数据」、向后接到「统一指标」：**Parser 读进来，Validator 把关，Objective 评出去**——一条可信的数据流水线。
