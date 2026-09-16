# Day 1：统一搜索接口与 Random Search

> 当日主题：先建立可比较的搜索实验，再讨论智能策略
> 当日产出：**统一搜索契约**（`SearchConfig` / `SearchResult` / `solve`）+ **Random Search 基线** + 实验脚本
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 写出统一入口 `solve(instance, config, initial=None) -> SearchResult`，并说明三个参数各自的角色。
2. 说出 `SearchConfig` 的七个字段与默认值，并知道哪些取值会在构造时被直接拒绝。
3. 说出 `SearchResult` 的七个字段，并区分 `objective`（历史最好值）与 `trace[-1].current`（最后走到的值）。
4. 精确定义「一次评价」，并解释为什么它比「迭代 100 次」是更公平的预算单位。
5. 说出所有算法共用的默认初始解从哪来（LPT 优先级 + 贪心指派），以及为什么不能各用各的初始解。
6. 手算一段 Random Search 的逐评价记账，写出 proposed / current / best 三列并解释 `best` 为什么单调不增。
7. 解释 `budget=1` 为什么必然只能返回初始解，以及「重复的同一个候选照样计数」为什么是必要设计。

---

## 2. 为什么第 1 天要先固定「搜索契约」

Week 1 有规则（SPT/EDD/WSPT/LPT），Week 2 有表示（`Candidate`）、解码（`decode`）、邻域（`neighbors`）和验证（`validate_schedule`）。把它们堆在一起，就能写搜索算法了——但**先写算法、后定接口**是算法工程里最贵的错误：

> **如果每个算法各自记账，实验结果之间就没有任何可比性。**

「运行了多少轮」不是一个可比较的单位：

```text
First Improvement 的一「轮」：找到第 1 个改善就停，可能只评价 1 个候选
Best Improvement  的一「轮」：必须扫完整个邻域，可能评价几百个候选
模拟退火          的一「轮」：固定评价 1 个候选
```

于是「三轮」在三种算法里代表的算力相差两个数量级。今天要做的事情只有一件：**把「跑了几轮」换成「评价了多少次」**，并把这套记账写进代码里，而不是写进实验报告里。

今天定义的 **search contract（搜索契约）** 有四条：

| # | 契约 | 违反后果 |
|---|---|---|
| 1 | 统一入口 `solve(instance, config, initial=None) -> SearchResult` | 调用方式各异，无法批量跑实验 |
| 2 | 统一预算单位：一次评价 = 完整 decode + 独立 validate + objective | 「轮数」不可比，快慢无法解释 |
| 3 | 统一返回结构：历史最好解的 Candidate / Schedule / 目标值 | 有的算法返回最后解，有的返回最好解 |
| 4 | 统一目标集合：所有目标**最小化**，只允许 `OBJECTIVES` 里的名字 | 有人最大化、有人最小化，方向错乱 |

一条重要的**理论结论**要现在就记住：

> **搜索算法返回的是「历史最好解」，不是「最后走到的解」。**

允许走坏的算法（SA、Multi-start）如果返回最后解，等价于随机乱走；只返回历史最好解，才能保证「搜索过程再乱，最终质量不下降」。

---

## 3. 统一入口：`solve(instance, config, initial=None) -> SearchResult`

对应文件 [search.py](../../projects/01_scheduling_core/scheduling_algorithms/search.py)。

```python
def solve(instance, config, initial=None) -> SearchResult: ...
```

三个参数各司其职：

| 参数 | 角色 | 谁决定 |
|---|---|---|
| `instance` | 问题输入，全程不可变 | 用户 / 生成器 |
| `config` | 算法名、目标名、预算、种子与参数 | 实验设计者 |
| `initial` | 可选的初始候选解；省略时用统一默认初始解 | 想对拍固定起点的实验 |

`initial=None` 时，代码走的是：

```python
current = initial if initial is not None else initial_candidate(instance)
```

`initial_candidate` 做两件事：**按 `p` 降序（LPT）排优先级**，再**为每道工序贪心选一台最早可完工的机器**。它是 Week 1 的 LPT 思路，被所有算法共享。

**为什么所有算法必须共用同一个初始解？** 否则「A 算法比 B 算法好」可能只是「A 的起点比 B 好」。共享起点之后，差异只能来自搜索策略，这才叫公平比较。需要研究起点影响时，用 `initial=` 显式传入，把「起点」变成一个受控变量。

整个流程：

```text
Instance
   ↓  initial=None
initial_candidate(instance)            # LPT 优先级 + 贪心指派
   ↓
Candidate ──decode──> Schedule ──validate_schedule──> 可信排程 ──objective──> 数值
   ↓                                                                    ↑
算法分支（lpt / random / first / best / multistart / sa）─ 提议新 Candidate ─┘
   ↓
SearchResult(candidate, schedule, objective, evaluations, status, elapsed_seconds, trace)
```

注意最后一步：`SearchResult` 里同时带着 `candidate`（决策）与 `schedule`（结果），所以调用者既能拿到「怎么排」，也能拿到「排成什么时间」。

---

## 4. `SearchConfig` / `SearchResult` / `ALGORITHMS` / `OBJECTIVES`

### 4.1 三个常量

```python
ALGORITHMS = ("lpt", "random", "first", "best", "multistart", "sa")
OBJECTIVES = {"makespan": ..., "total_tardiness": ..., "weighted_completion_time": ...}
```

- `ALGORITHMS` 是本月全部可选算法的白名单，顺序固定，便于实验脚本按序遍历。
- `OBJECTIVES` 是**可被搜索优化**的三个目标。注意它只是 Week 1 目标库的**子集**：`total_completion_time`、`max_lateness`、`total_flow_time` 能算，但不在这里——因为搜索接口只公开这三个。
- **所有目标都是最小化。** 想让某个指标变大，必须自己写成取负的目标函数并显式登记，不能在算法里偷偷改符号。

### 4.2 `SearchConfig`

| 字段 | 默认值 | 作用 |
|---|---|---|
| `algorithm` | `"sa"` | 选哪个算法，取值必须在 `ALGORITHMS` 里 |
| `objective` | `"makespan"` | 最小化哪个目标，取值必须在 `OBJECTIVES` 里 |
| `budget` | `200` | **评价次数上限**（不是轮数） |
| `seed` | `0` | 算法自己的随机种子（与实例种子无关） |
| `temperature` | `10.0` | SA 初始温度 |
| `cooling` | `0.98` | SA 每步降温系数 |
| `restart_interval` | `40` | Multi-start 每段最多消耗多少次评价 |

字段是 `frozen=True, slots=True` 的 dataclass——配置一旦建好就不能被中途改写，避免「算法跑着跑着改了预算」这类无法复现的事故。

`__post_init__` 里做了四道校验（**实验观察**：这些都会抛 `ValueError`）：

```text
algorithm 不在 ALGORITHMS，或 objective 不在 OBJECTIVES  -> "unknown algorithm/objective"
budget 不是 int（type(budget) is not int）或 budget < 1    -> "budget/restart_interval must be positive"
restart_interval < 1                                      -> 同上
temperature 非有限或 <= 0，或 cooling 不在 (0, 1]          -> "invalid annealing parameters"
```

这里有一个容易忽略的细节：`type(self.budget) is not int` 用的是 `type(...) is` 而不是 `isinstance(...)`。**`True` 是 `int` 的子类**，用 `isinstance` 会让 `budget=True` 通过校验，于是预算变成 1 却不报错。用 `type(...) is not int` 把布尔值挡在门外。

### 4.3 `SearchResult`

| 字段 | 类型 | 含义 |
|---|---|---|
| `candidate` | `Candidate` | 历史最好解对应的候选（决策） |
| `schedule` | `Schedule` | 该候选解码后的排程（结果） |
| `objective` | `float` | 该排程的目标值，等于 `trace[-1].best` |
| `evaluations` | `int` | 实际评价次数，等于 `len(trace)`，且 `<= budget` |
| `status` | `str` | 停止原因，见下表 |
| `elapsed_seconds` | `float` | 墙钟秒数，**不可复现**，只作成本参考 |
| `trace` | `tuple[TracePoint, ...]` | 逐评价记录 |

`status` 的取值与含义：

| 值 | 谁会产生 | 含义 |
|---|---|---|
| `BASELINE` | `lpt` | 只跑初始解，不搜索 |
| `BUDGET` | 全部算法 | 预算用完（默认值，也可能表示「扫描被预算打断」） |
| `LOCAL_OPTIMUM` | `first` / `best` | 完整扫描过邻域且无严格改善 |

两条**实现观察**（不是理论结论，是这份代码的选择）：

1. `multistart` **永远不会**返回 `LOCAL_OPTIMUM`。它的判断顺序是「先看要不要重启，再看有没有不动」，而 `not moved` 恰好是触发重启的条件之一，所以那个「不动就停」的分支对它不可达。
2. `multistart` / `random` / `sa` 一定**用满**预算；`first` / `best` 可能提前停（找到局部最优），也可能用满（一直没走完一轮干净扫描）。

`trace` 的元素是 `TracePoint`：

| 字段 | 含义 |
|---|---|
| `evaluation` | 第几次评价（从 1 开始，1 就是初始化） |
| `proposed` | 本次提议候选的目标值 |
| `current` | 本次记录时刻的当前值（接受后是新值，拒绝后不变） |
| `best` | 到本次为止的历史最小值 |
| `accepted` | 是否被接受 |
| `temperature` | SA 当时的温度；其他算法为 `None` |

---

## 5. 手算 / 示例：一次评价怎么记账

### 5.1 抽象示例（stub 原例）

假设初始值 30，接下来三次提议依次是 35、28、31：

| `evaluation` | `proposed` | `current` | `best` | `accepted` | 解释 |
|---:|---:|---:|---:|---|---|
| 1 | 30 | 30 | 30 | `True` | 初始化，第 1 次评价 |
| 2 | 35 | 30 | 30 | `False` | 更差 → 拒绝，`current` 与 `best` 都不动 |
| 3 | 28 | 28 | 28 | `True` | 严格改善 → 接受，两个值一起降 |
| 4 | 31 | 28 | 28 | `False` | 更差 → 拒绝 |

于是 `proposed` 序列是 35、28、31，`best` 序列是 30、28、28。三条要点：

1. **`best` 单调不增**——这是可写的断言，也是测试里真正在查的性质。
2. **`current` 可以回升**（SA 里必然发生），`best` 不会。
3. **被拒绝的候选照样占一次评价**：第 2、4 次都是真实成本，不能从统计里删掉。只统计「成功的提议」会让「提议得多但准头差」的算法看起来免费。

### 5.2 真实实例：4 工序单机

先用第 7 节的实验实例做一遍算术，确认「一次评价 = 一次完整解码 + 目标计算」。

| Job | `pj` | `rj` | `dj` | `wj` |
|---|---:|---:|---:|---:|
| J0 | 9 | 0 | 3 | 1 |
| J1 | 7 | 0 | 6 | 1 |
| J2 | 5 | 0 | 12 | 1 |
| J3 | 3 | 0 | 20 | 1 |

目标 `total_tardiness`（ΣTj）。单机、无释放时间，所以顺序即时间表。

```text
第 1 次评价：初始解 initial_candidate（LPT：p 降序，平局按 op.id）
  优先级 O0(9) -> O1(7) -> O2(5) -> O3(3)
  C = [9, 16, 21, 24]
  T = [9-3, 16-6, 21-12, 24-20] = [6, 10, 9, 4]
  ΣTj = 6 + 10 + 9 + 4 = 29
  → TracePoint(1, proposed=29, current=29, best=29, accepted=True)
```

```text
第 2 次评价：随机重排得到一个更好的优先级
  优先级 O1(7) -> O2(5) -> O3(3) -> O0(9)
  C = [7, 12, 15, 24]
  T = [7-6, 12-12, 15-20, 24-3] = [1, 0, 0(负数截为 0), 21]
  ΣTj = 1 + 0 + 0 + 21 = 22
  → 22 < 29，严格改善，接受：current 与 best 一起变成 22
```

对比表：

| 解 | 优先级顺序 | `C` | `ΣTj` |
|---|---|---|---|
| 初始解（LPT） | O0,O1,O2,O3 | 9, 16, 21, 24 | 29 |
| 第 2 次评价提议 | O1,O2,O3,O0 | 7, 12, 15, 24 | **22** |

注意第三次之后的所有提议（28、22、27、32、25、22、23、32）都**没有**进入 `best`：22 与当时的 `current` 相等，属于「不严格改善」，随机搜索不接受等值候选。这正是第 7 节里 `accepted=False` 的那 8 行。

---

## 6. 实现：`search.py`

### 6.1 初始化就是第 1 次评价

```python
current = initial if initial is not None else initial_candidate(instance)
current_schedule = decode(instance, current)
validate_schedule(instance, current_schedule)
value = float(objective(instance, current_schedule))
best, best_schedule, best_value = current, current_schedule, value
trace = [TracePoint(1, value, value, value, True, None)]
```

四件事在同一个地方发生：解码、**独立验证**、算目标、记账。注意 `validate_schedule` 是 Week 2 那个独立验证器——它不认识 `decoder` 的内部状态，所以任何算法产出的排程都要过这一关，搜索过程本身也不能例外。

`trace` 的长度就是预算账本：

```python
while len(trace) < config.budget:
    ...
    record(candidate, schedule, score, accepted, temp)
```

**为什么用 `len(trace)` 而不是单独的计数器？** 因为两者一旦分开就可能不一致（忘记加、加了两次）。让「记录」和「计数」是同一个动作，这类 bug 在结构上就不可能出现。

### 6.2 `evaluate` 与 `record`

```python
def evaluate(candidate: Candidate) -> tuple[Schedule, float]:
    schedule = decode(instance, candidate)
    validate_schedule(instance, schedule)
    return schedule, float(objective(instance, schedule))

def record(candidate, schedule, score, accepted, temp=None) -> None:
    nonlocal best, best_schedule, best_value
    if score < best_value:
        best, best_schedule, best_value = candidate, schedule, score
    trace.append(TracePoint(len(trace) + 1, score, value, best_value, accepted, temp))
```

两个要点：

1. **`evaluate` 就是「一次评价」的完整定义**：解码 + 独立验证 + 目标。任何绕过它的快捷计算都会让预算失去意义。
2. **`best` 的更新写在 `record` 里**，与 `accepted` 无关——即使某个候选被拒绝，只要它比历史最好还好（在 Best Improvement 的扫描阶段会出现），`best` 也必须更新。否则搜到的好解会因为「当时没接受」而丢失。

`record` 里读的 `value` 是外层作用域的当前值，调用时机决定了写进 `trace` 的 `current` 是「接受之后」的值，这正好与第 5 节的表格一致。

### 6.3 Random Search 的提议方式

```python
def random_candidate() -> Candidate:
    order = list(current.order)
    rng.shuffle(order)
    return Candidate(
        tuple(order),
        tuple(rng.choice(op.eligible_machine_ids) for op in instance.operations),
    )
```

两步：**打乱优先级** + **为每道工序独立随机选一台合格机器**。两条实现约束：

- `rng = Random(config.seed)` 是**局部 RNG**，不碰 Python 全局随机状态。同一个 `seed` 一定得到同一串提议，与实例种子、运行次数都无关。
- 抽样的对象是**编码（`Candidate`）**，不是排程。Week 2 已经知道编码有冗余，所以 Random Search **不等于**「在所有可行时间表上均匀抽样」——这是一个**理论边界**，不是 bug。

接受准则只有一句：

```python
accepted = score < value        # random 分支
```

只接受**严格改善**。等值候选一概拒绝，避免在平台上原地游走。注意这里用的是 `current`（可能已经被前一次接受抬高或压低），不是 `best`。

`lpt` 分支最简单：什么都不循环，`status = "BASELINE"`，于是 `evaluations == 1`。**LPT 基线只花 1 次评价，不人为把预算填满**——把它的 `evaluations` 填成 200 会让「每次评价的平均收益」这类指标彻底失真。

---

## 7. 实验：`m1w3d1_random`

对应脚本 [m1w3d1_random.py](../../projects/01_scheduling_core/examples/m1w3d1_random.py)，在项目目录下运行：

```bash
python examples/m1w3d1_random.py
```

脚本打印搜索契约、默认初始解、`budget=1` 的边界、一段 `random` 的逐评价轨迹，以及「重复候选照样计数」的极端例子。实际输出（节选）：

```text
== 1. 搜索契约 ==
  solve(instance, config, initial=None) -> SearchResult
  ALGORITHMS = ('lpt', 'random', 'first', 'best', 'multistart', 'sa')
  OBJECTIVES = ('makespan', 'total_tardiness', 'weighted_completion_time')
  SearchConfig 字段与默认值：
    algorithm          = 'sa'
    objective          = 'makespan'
    budget             = 200
    seed               = 0
    temperature        = 10.0
    cooling            = 0.98
    restart_interval   = 40
  SearchResult 字段：
    candidate          : <class 'scheduling_core.solution.Candidate'>
    schedule           : <class 'scheduling_core.schedule.Schedule'>
    objective          : <class 'float'>
    evaluations        : <class 'int'>
    status             : <class 'str'>
    elapsed_seconds    : <class 'float'>
    trace              : tuple[scheduling_algorithms.search.TracePoint, ...]

== 2. 默认初始解：LPT 优先级 + 贪心指派（只花 1 次评价）==
  initial_candidate order=('O0', 'O1', 'O2', 'O3') assign=('M0', 'M0', 'M0', 'M0')
  初始值 = 29
  algorithm=lpt: evaluations=1 status=BASELINE objective=29.0

== 3. 预算单位：budget=1 只返回初始解 ==
  evaluations=1 status=BUDGET objective=29.0
  trace[0]: proposed=29.0 current=29.0 best=29.0 accepted=True
```

主实验（`budget=10, seed=2`）：

```text
== 4. Random Search 逐评价轨迹（budget=10, seed=2）==
  evaluation  proposed  current  best  accepted
           1      29.0     29.0  29.0  True
           2      22.0     22.0  22.0  True
           3      28.0     22.0  22.0  False
           4      22.0     22.0  22.0  False
           5      27.0     22.0  22.0  False
           6      32.0     22.0  22.0  False
           7      25.0     22.0  22.0  False
           8      22.0     22.0  22.0  False
           9      23.0     22.0  22.0  False
          10      32.0     22.0  22.0  False
  最终候选 order=('O1', 'O2', 'O3', 'O0')
  evaluations=10 status=BUDGET objective=22.0（含初始点共 8 条 accepted=False，全部计数）

== 5. 重复的同一个候选也要计数 ==
  evaluations=8 status=BUDGET
  proposed 序列=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

== 6. 独立参照：oracle 确认这个实例的全局最优 ==
  枚举 24 个组合（4! × 1），全局最优 = 22
  搜索在第 2 次评价就碰到了这个值：这是运气，不是算法保证
```

**实验观察**（只是这批数据上的事实，不是理论结论）：

1. 第 2 次评价就命中 22，而脚本第 6 节用 Week 2 的独立 oracle 确认**这个实例的全局最优就是 22**。随机搜索一次就撞上了最优，纯属运气。
2. 同一实例换种子结果立刻变化：`seed=0` 和 `seed=3` 只到 26，`seed=1` 到 27。**单次运行的结果不能代表算法水平。**
3. 第 4 次与第 8 次提议的 22 被拒绝（与 `current` 相等，不严格改善）——这是「等值不接受」的直接证据。
4. 单工序单资格的例子中，8 次提议全是同一个候选，`evaluations` 仍然是 8。**重复评价照样消耗预算**，这是刻意的：否则「不断重复同一个解」会变成免费的策略。

月末批次（[artifacts/month1_refactored/results.csv](../../projects/01_scheduling_core/artifacts/month1_refactored/results.csv)）里还能看到预算账本的一致性：`lpt` 的 `evaluations` 恒为 1 且 `status=BASELINE`；`random` / `sa` / `multistart` 的 `evaluations` 恒等于 `budget=150`；`first` / `best` 在 `tiny_single` 上分别是 23 与 37 次（提前停在 `LOCAL_OPTIMUM`），在 `single_12` 上则是 150 次（跑满预算也没有走完一轮干净扫描）。

复跑方法（在项目目录下运行）：

```bash
python -m pytest tests/test_month1.py -k search_budget -v
```

---

## 8. 今日练习

1. **练习 1（定义）**：用自己的话写出「一次评价」包含哪三步，然后指出如果把 `validate_schedule` 从评价里去掉，预算会失去什么意义。
2. **练习 2（手算）**：给定初始值 40，提议序列 42、38、38、35、41，写出 5 次评价的 `proposed` / `current` / `best` / `accepted` 四列，并说明第 3、4 次的区别。
3. **练习 3（边界）**：把 `SearchConfig(algorithm="random", budget=0)` 与 `budget=1.0` 各构造一次，记录抛出的异常类型与消息，并解释为什么布尔值 `True` 也必须被拒绝。
4. **练习 4（代码阅读）**：不看 `search.py`，写出 `solve` 里 `record` 的伪代码，说明 `best` 的更新条件为什么与 `accepted` 无关。
5. **练习 5（实验）**：把第 7 节的实例换成 `generate_instance(20, jobs=12, machines=1)`，目标 `total_tardiness`，`budget=150`，跑 `random` 的三个种子，比较 `evaluations` 与 `status`，并解释为什么三者不会相同。

---

## 9. 验收清单

- [ ] 能写出 `solve(instance, config, initial=None) -> SearchResult` 并说明三个参数的作用。
- [ ] 能背出 `SearchConfig` 七个字段与默认值，并说出哪些取值会被 `__post_init__` 拒绝。
- [ ] 能列出 `SearchResult` 七个字段，区分 `objective` 与 `trace[-1].current`。
- [ ] 能解释「一次评价 = decode + validate_schedule + objective」，并指出初始化算第 1 次。
- [ ] 能解释为什么 `budget` 比「迭代多少轮」更公平（Best 一轮可能扫几百个邻居）。
- [ ] 能说出默认初始解来自 LPT 优先级 + 贪心指派，且所有算法共用。
- [ ] 能解释 `best` 单调不增、`current` 可以回升，以及为什么返回历史最好解。
- [ ] 能解释「被拒绝的候选」「重复的同一个候选」为什么都必须计数。
- [ ] 在项目目录下运行 `python examples/m1w3d1_random.py` 无报错，且输出与第 7 节一致。
- [ ] 在项目目录下运行 `python -m pytest tests/test_month1.py -k search_budget -v` 全部通过（18 条）。

---

## 10. 自测题

不看上文回答：

- Q1：`solve` 的三个参数分别是什么？`initial=None` 时初始解从哪里来？
- Q2：`SearchConfig` 的 `budget` 单位是什么？为什么不用「轮数」？
- Q3：一次评价包含哪三步？初始化算不算一次？
- Q4：`best` 与 `current` 的区别是什么？哪一个必须单调不增？
- Q5：把 `budget` 设成 1，`SearchResult` 会是什么？`status` 是什么？
- Q6：`ALGORITHMS` 里有哪六个算法？`OBJECTIVES` 里有哪三个目标名？
- Q7：为什么 `SearchResult` 返回的是历史最好解而不是最后走到的解？
- Q8：`type(self.budget) is not int` 为什么不能写成 `isinstance(self.budget, int)`？
- Q9：`multistart` 为什么永远不会返回 `LOCAL_OPTIMUM`？`lpt` 为什么只花 1 次评价？
- Q10：`random` 分支的接受准则是什么？等值候选会被接受吗？为什么？

### 参考答案

- A1：`instance`（问题输入）、`config`（算法/目标/预算/种子与参数）、`initial`（可选初始候选）。`initial=None` 时用 `initial_candidate(instance)`，即 LPT 优先级 + 贪心指派。
- A2：单位是**评价次数上限**（decode + validate + objective 的次数）。因为不同算法的一「轮」成本相差两个数量级，轮数之间不可比。
- A3：`decode`（解码）+ `validate_schedule`（独立可行性验证）+ `objective`（算目标）。初始化算第 1 次评价，`trace[0]` 就是它。
- A4：`best` 是历史最小值，必须单调不增；`current` 是当前所在解的值，接受更差候选时会回升（SA 里必然出现）。
- A5：只会做初始化那一次评价，返回的 `candidate` 等于 `initial_candidate(instance)`（或显式传入的 `initial`），`evaluations == 1`，`status == "BUDGET"`。
- A6：`('lpt', 'random', 'first', 'best', 'multistart', 'sa')`；`('makespan', 'total_tardiness', 'weighted_completion_time')`。
- A7：允许走坏的算法如果返回最后解，最终质量会随机波动；返回历史最好解才能保证「过程再乱，结果不下降」。
- A8：因为 `bool` 是 `int` 的子类，`isinstance(True, int)` 为真，`budget=True` 会通过校验并变成预算 1；`type(...) is not int` 把布尔值挡在外面。
- A9：`multistart` 的判断顺序是先重启再判断「没动」，而 `not moved` 本身就是重启条件之一，所以「不动就停」的分支不可达。`lpt` 是基线，不搜索，只评价初始解一次，不填满预算以免污染「每次评价的平均收益」。
- A10：`score < value`，只接受**严格改善**；等值候选一律拒绝，避免在平台上无限游走、把预算浪费在零收益的移动上。

---

## 11. 今日一句话总结

> **搜索契约先把「跑了几轮」翻译成「评价了多少次」：一次评价就是一次完整的解码 + 独立验证 + 目标计算，初始化算第 1 次，被拒绝和重复的候选照样计数；有了这本账，Random Search 才成为后面所有智能策略都必须打败的那个基线。**
