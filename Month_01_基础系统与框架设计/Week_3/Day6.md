# Day 6：搜索对比与收敛曲线

> 当日主题：用真实运行记录判断方法差异，而不是靠算法名字
> 当日产出：**可复现的最小对比实验**（`m1w3d6_search.py` 的真实输出）+ **轨迹字段约定** + **差异分析框架**
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 说清楚「同一个实例、同一个预算」下六个方法（`lpt` 基线 + 五种搜索）的差异体现在哪几个字段上。
2. 会用 `evaluations` 与 `status` 区分「用满预算」与「提前停机」，并说出 `BUDGET` / `LOCAL_OPTIMUM` / `BASELINE` 三个状态各自在代码里从哪里来。
3. 说清楚为什么 `lpt` 在本日只是**共享初始基线**，而不是单机迟交问题的理论最优规则。
4. 知道逐评价记录包含六列 `evaluation / proposed / current / best / accepted / temperature`，并能说出每一列的含义。
5. 会验证「算法返回的最好值 = 轨迹末点的 `best` = 由返回 `Schedule` 重算的目标值」这一条等式链。
6. 会用「可行性 → 质量 → 成本」三段式顺序分析两次运行的差异，而不是先比较秒数。
7. 会用**初始值、最好值、改善发生的评价位置、是否到达平台**四个量描述一条曲线。
8. 知道为什么三个 `seed` 只能「检查流程、观察现象」，不足以「稳定估计很小的差异」。

---

## 2. 为什么第 6 天要做「对比」

前五天的成果都是「单个方法内部」的：

```text
Day 1～2  候选解 Candidate + 邻域 swap / insert / reassign
Day 3     decoder：把 Candidate 变成可行的 Schedule
Day 4     First / Best：固定扫描顺序的局部搜索
Day 5     SA：允许暂时变差，几何降温
```

五天之后手上已经有五个能跑的方法，但**「哪个更好」这个问题一天都还没回答过**。原因很简单：

> **「跑通了」和「更好」是两件事。**

对比实验的意义不在于排出一个名次表，而在于建立一个能重复执行、能逐字段解释差异的流程。没有这个流程，后面任何改进都只能是「我感觉这次结果好了」。

对比实验最容易被做坏的地方有三个：

1. **不同方法跑了不同实例。** 结果差异里混进了数据差异，无法归因。
2. **不同方法用了不同预算。** 「跑得久」被误读成「算法好」。
3. **只记最后的目标值，不记过程。** 于是「为什么好」永远说不清，也画不出收敛曲线。

所以今天的最小对比实验把三件事固定住：**同一个 `Instance`、同一个 `budget`、逐次记录**。剩下的差异才是方法差异。

---

## 3. 对比实验的四个字段

本日的对比实验只打印四个字段（外加算法名），因为它们恰好覆盖「质量 + 过程 + 成本」三个维度：

| 字段 | 来源 | 回答的问题 |
|---|---|---|
| `objective` | `SearchResult.objective` | 这次运行找到的最好解有多好 |
| `evaluations` | `SearchResult.evaluations` | 实际花掉多少预算，有没有提前停 |
| `status` | `SearchResult.status` | 是「跑满预算」还是「扫尽邻域」还是「没搜」 |
| `elapsed_seconds` | `SearchResult.elapsed_seconds` | 墙钟成本 |

三点必须记清：

- **`objective` 是「历史最好值」，不是「最后一次 `current`」。** SA 会让 `current` 上下浮动（Day 5 第 2 节），返回的必须是历史 `best`。
- **`evaluations` 不是「迭代次数」。** 一次评价 = 一次完整的「解码 + 独立校验 + 目标计算」。初始化点、被拒绝的候选、no-op、随机重启**全部计入**（`search.py` 模块文档字符串的第一句就写了这一点）。
- **`elapsed_seconds` 是墙钟时间**，包含解码、校验、邻居生成的开销，但**不含**写文件和绘图。不同 Python 版本、不同平台上的墙钟时间不能直接比较。

### 3.1 月度批次里的同一张表（三个 `seed` 的均值）

本日脚本用的实例与月度批次的 `single_12` 完全同参数。实测把脚本里 `generate_instance(20, jobs=12, machines=1)` 的输入序列化成 JSON 后，其 SHA-256 与批次里的 `instances/single_12.json` **逐字节相同**。所以可以直接对照 [月度报告](../MONTH1_REPORT.md) §6 的 `single_12` 一行：

| 算法 | `single_12` 三月均值 | 批次 `seed` 数 |
|---|---:|---:|
| `lpt` | 719 | 3 |
| `random` | 313 | 3 |
| `first` | 575 | 3 |
| `best` | 529 | 3 |
| `multistart` | 373 | 3 |
| `sa` | 261.67 | 3 |

**这张表是「月度批次」的数字，不是第 7 节脚本的输出。** 上表是**三个 `seed` 的主实验均值**（`seeds = [0, 1, 2]`），而第 7 节脚本只跑**一个 `seed = 0`**，是**一次运行**。一次运行落在均值的分布里，但**一次运行不等于均值**：`multistart` 的三月均值 373、中位数 371、标准差 52.03、最好值 322，单看一次运行根本无法判断它属于分布的哪一端。`lpt` 是确定性方法，三月均值恰好等于 719、标准差为 0，这不代表它有三个独立随机样本，只代表同一份初始解被评价了三次。

> **写报告时的纪律**：单次运行的数写成「一次运行」，三个 `seed` 的均值写成「三月均值」，并注明 `seed` 个数。**混用两者，就是把噪声写成信号。**

---

## 4. 差异分析框架：可行性 → 质量 → 成本

对比两个方法时最容易犯的错是**先比大小、再比秒数**。正确的顺序是固定的三段式：

```text
第一段  可行性与失败      有没有 status=FAILED？有没有非法排程？       （先证明结果是可用的）
第二段  质量              objective、gap、改善发生的评价位置           （再谈好坏）
第三段  成本              evaluations、elapsed_seconds                 （最后谈代价）
```

**顺序不能颠倒**：一个「目标值很好但排程非法」的结果，价值是 0，先比质量毫无意义。这就是为什么每一次评价内部都强制走一遍 `validate_schedule`（第 6.1 节）——把可行性检查固化进预算，而不是等到报告阶段再补。

### 4.1 每个实例比较四个量

对同一个实例上的两条曲线，逐项填写这四个量：

| 量 | 从哪里读 | 说明 |
|---|---|---|
| 初始值 | 轨迹第 1 行的 `best` | 所有方法共享同一个初始解，所以这一列应当完全相同 |
| 最好值 | `objective` / 轨迹末行的 `best` | 质量结论的唯一依据 |
| 改善发生的评价位置 | `best` 列发生下降的行号 | 判断「早收敛」还是「后程发力」 |
| 是否到达平台 | 末次改善到停机之间有多少行 | 平台很长说明剩余预算没被用上 |

以第 5.5 节的 4 作业实例为例：

```text
first : 初始 57 → 最好 36，改善发生在第 5、11 次评价，第 12～23 行是平台
sa    : 初始 57 → 最好 36，但用的是完整的 150 次评价
```

两条曲线的**最好值相同**，差异全部落在「改善位置」与「平台长度」上——这正是「只记最后的目标值」会完全丢掉的信息。

### 4.2 相位与停机：两种「跑满预算」

`status = BUDGET` 只说明「用满了预算」，不说明「搜索还在有效推进」。读 `status` 的正确方式是**三分**而不是二分：

```text
LOCAL_OPTIMUM      邻域扫尽 → 停机位置由实例结构决定
BUDGET（还在动）    预算用尽 → 可能还没收敛，例如第 7 节 12 作业实例上的 sa
BUDGET（已在平台）  预算用尽 → 36 已是理论最优，再跑一百多次也只是反复撞同一堵墙
```

### 4.3 三个 `seed` 能看出什么、不能看出什么

| 现象 | 合理推断 | 不能推断 |
|---|---|---|
| `first` / `best` 三个 `seed` 结果**完全相同** | 它们**不使用 RNG**，逐行轨迹必然一致 | 不能推断「它们比随机方法更稳定」——稳定来自确定性，不来自质量 |
| `sa` 三个 `seed` **差异较大** | 随机性与接受坏解共同作用，需要**多个 `seed` + 分布描述**（均值、标准差、最好值） | 三次运行的均值**不足以稳定估计很小的差异** |

月度批次里两种现象都真实出现过：`single_12` 上 `first` / `best` 的标准差都是 0.000（三个 `seed` 逐行相同），而 `multistart` 的标准差是 52.029、`random` 是 23.643。**描述后者时只报一个均值是不完整的，必须同时给出标准差或最好值。**

> **结论**：确定性方法报「一次结果」就够，因为它可复现；随机方法必须报「多次运行 + 分布」，否则读者无法判断两个方法之间的差距是不是噪声。

---

### 4.4 谁用满预算，谁提前停机

`status` 只有三个来源，全部在 [search.py](../../projects/01_scheduling_core/scheduling_algorithms/search.py) 的 `solve` 里显式赋值：

```text
BASELINE        算法是 lpt：只评价一次初始解，不搜索
BUDGET          跑满 budget 次评价后跳出主循环
LOCAL_OPTIMUM   扫描一整圈邻居都没有严格改善（moved == False），说明到达局部最优
```

`LOCAL_OPTIMUM` 只可能由 `first` / `best` 产生。原因是这段分支：

```text
restart = algorithm == "multistart" and (not moved or 本段评价数 >= restart_interval)
if restart:
    换一个随机起点，继续跑                 # 状态仍是 BUDGET
elif not moved:
    status = "LOCAL_OPTIMUM"; break        # 只有非 multistart 才走这里
```

> **结论**：`multistart` 遇到「没移动」时做的是重启，不是停机，所以它**永远不会**返回 `LOCAL_OPTIMUM`。

这带来一个画图时的硬约束：

```text
收敛曲线的横轴是评价数，不是迭代轮数。
不同算法可以提前停机，所以曲线的长度本来就不同。
不能把「提前停在 23 次」画成「跑满 150 次」——那会伪造出一条平坦的长尾。
```

横轴用评价数而不是墙钟秒数，是因为评价数是**可复现的**量：同样的 `Instance` + 同样的 `SearchConfig` 一定得到同样多的评价。秒数则受机器负载影响，不适合做横轴。

---

## 5. 手算 / 示例：4 作业单机实例的首次改善轨迹

为了让轨迹可以逐行对拍，这里换一个能手算的小实例：`seed=10`、4 个单机作业、目标 `total_tardiness`（这与月度配置里的 `tiny_single` 完全同参数）。

### 5.1 输入

| Job | `pj` | `rj` | `dj` |
|---|---:|---:|---:|
| J000 | 19 | 0 | 28 |
| J001 | 16 | 9 | 33 |
| J002 | 7 | 7 | 17 |
| J003 | 9 | 10 | 23 |

只有一台机器 `M0`，全作业单工序，`eligible_machine_ids` 都是 `("M0",)`。

### 5.2 初始解：LPT 基线

`initial_candidate` 按 `p` 降序排：J000(19) → J001(16) → J003(9) → J002(7)。逐项推进（`start = max(机器 ready, rj)`）：

```text
J000: start = max(0, 0)  = 0   → C = 19   T = max(0, 19-28) = 0
J001: start = max(19, 9) = 19  → C = 35   T = max(0, 35-33) = 2
J003: start = max(35, 10)= 35  → C = 44   T = max(0, 44-23) = 21
J002: start = max(44, 7) = 44  → C = 51   T = max(0, 51-17) = 34

ΣTj = 0 + 2 + 21 + 34 = 57
```

所以轨迹的第 1 行（初始化点）固定是 `proposed = current = best = 57`、`accepted = True`、`temperature` 为空。

### 5.3 `first` 的前两轮：手算两个被接受的候选

`first` 按 `neighbors()` 的固定扫描顺序逐个评价，遇到第一个严格改善就接受并跳出本圈扫描。

第 1 圈第 4 个候选是顺序 `J001 → J003 → J000 → J002`：

```text
J001: start = max(0, 9)  = 9   → C = 25   T = max(0, 25-33) = 0
J003: start = max(25, 10)= 25  → C = 34   T = max(0, 34-23) = 11
J000: start = max(34, 0) = 34  → C = 53   T = max(0, 53-28) = 25
J002: start = max(53, 7) = 53  → C = 60   T = max(0, 60-17) = 43

ΣTj = 0 + 11 + 25 + 43 = 79
```

它出现在轨迹第 4 行：`proposed = 79 > current = 57`，所以 `accepted = False`——**等值和更差的邻居一律不接受**。

第 1 圈第 5 个候选是顺序 `J002 → J001 → J003 → J000`：

```text
J002: start = max(0, 7)  = 7   → C = 14   T = max(0, 14-17) = 0
J001: start = max(14, 9) = 14  → C = 30   T = max(0, 30-33) = 0
J003: start = max(30, 10)= 30  → C = 39   T = max(0, 39-23) = 16
J000: start = max(39, 0) = 39  → C = 58   T = max(0, 58-28) = 30

ΣTj = 0 + 0 + 16 + 30 = 46
```

它出现在轨迹第 5 行：`proposed = 46 < current = 57`，`accepted = True`，`current` 与 `best` 同时降到 46。

### 5.4 真实轨迹（`first`, `budget=150`, `seed=0`）

```text
evaluation  proposed  current  best   accepted
    1          57        57      57     True     ← 初始化点，不消耗搜索
    2          89        57      57     False
    3          72        57      57     False
    4          79        57      57     False    ← 5.3 手算的候选
    5          46        46      46     True     ← 5.3 手算的候选，第 1 圈结束
    6          65        46      46     False
    7          60        46      46     False
    8          67        46      46     False
    9          57        46      46     False
   10          79        46      46     False
   11          36        36      36     True     ← 第 2 圈结束
   12 ～ 23    39 ～ 72   36      36     False    ← 第 3 圈扫尽 12 个邻居，无改善
```

第 3 圈结束后 `moved == False`，`status = LOCAL_OPTIMUM`，共 23 次评价后停机。

可以手算核对最后这个 36（顺序 `J002 → J003 → J001 → J000`）：

```text
J002: start = max(0, 7)  = 7   → C = 14   T = max(0, 14-17) = 0
J003: start = max(14, 10)= 14  → C = 23   T = max(0, 23-23) = 0
J001: start = max(23, 9) = 23  → C = 39   T = max(0, 39-33) = 6
J000: start = max(39, 0) = 39  → C = 58   T = max(0, 58-28) = 30

ΣTj = 0 + 0 + 6 + 30 = 36
```

**为什么刚好停在 23？** 三条信息拼起来就完全解释了：

```text
本实例 4 道工序、单机器资格时，neighbors() 去重后恰好产出 12 个候选
第 1 圈 4 次评价后接受改善并跳出     →  1 + 4  = 5
第 2 圈 6 次评价后接受改善并跳出     →  5 + 6  = 11
第 3 圈把 12 个候选全扫完仍无改善    → 11 + 12 = 23  →  LOCAL_OPTIMUM
```

### 5.5 同一实例上的六方法对比（真实运行）

| 算法 | `objective` | `evaluations` | `status` |
|---|---:|---:|---|
| `lpt` | 57 | 1 | `BASELINE` |
| `random` | 36 | 150 | `BUDGET` |
| `first` | 36 | 23 | `LOCAL_OPTIMUM` |
| `best` | 36 | 37 | `LOCAL_OPTIMUM` |
| `multistart` | 36 | 150 | `BUDGET` |
| `sa` | 36 | 150 | `BUDGET` |

这张表是今天最重要的教学材料，因为**六个方法的目标值里有五个相同**：

- **目标值相同不代表过程相同。** `first` 用 23 次评价拿到 36，`sa` 用满 150 次也拿到 36——在这个实例上二者没有质量差异，只有成本差异。
- **`evaluations` 的差异是真实的，不能忽略。** 画收敛曲线时，`first` 的曲线只有 23 个点。
- **这个实例太小，四种方法都能撞到最优解 36**，所以它适合用来核对轨迹，**不适合**用来给方法排名。

---

## 6. 实现：`search.py` 的预算与停机

对应文件 [search.py](../../projects/01_scheduling_core/scheduling_algorithms/search.py)。今天只读不改，重点看四件事。

### 6.1 预算单位：一次评价是什么

```python
def evaluate(candidate: Candidate) -> tuple[Schedule, float]:
    schedule = decode(instance, candidate)
    validate_schedule(instance, schedule)
    return schedule, float(objective(instance, schedule))
```

一次评价 = 解码 + **独立校验** + 目标计算。校验放在预算里是刻意设计：**被计费的每一步都必须是可行的**，否则「用满预算」就失去了可比性。

### 6.2 轨迹的第一行不是搜索

```python
trace = [TracePoint(1, value, value, value, True, None)]
```

初始化点占第 1 行，`proposed = current = best`、`accepted = True`、`temperature = None`。后果有两个：**`evaluations >= 1` 恒成立**，即使 `budget = 1` 也能返回一个可行解（`test_search_budget_reproducibility_and_incumbent` 用 `budget=1, 2, 60` 三个档位覆盖了这一点）；**LPT 的 `evaluations` 恒为 1**，这就是报表里 LPT 那一行评价数总是 1 的原因。

### 6.3 `record` 同时管「历史最好」和「追加轨迹」

```python
def record(candidate, schedule, score, accepted, temp=None) -> None:
    if score < best_value:
        best, best_schedule, best_value = candidate, schedule, score
    trace.append(TracePoint(len(trace) + 1, score, value, best_value, accepted, temp))
```

两点关键：

- **`record` 里 `value` 是闭包捕获的当前 `current` 值**，写在 `current` 被更新**之后**，所以第 5.4 节表格里的 `current` 列读的是「本步接受后的当前值」。这也是为什么 `first` 第 5 行的 `current` 已经是 46。
- **`best` 只在严格更小时更新**，因此 `best` 列单调不增。`test_search_budget_reproducibility_and_incumbent` 对此的断言是「轨迹的 `best` 序列等于它自身降序排序」，即逐个点核对单调性。

### 6.4 `best` 算法回填最后一行

`best` 算法在一圈扫描期间**不移动**（`current` 保持不变），扫完才一次性跳过去。为了不伪造「扫描期间就接受了改善」，代码在选定之后回填轨迹最后一行：

```python
if config.algorithm == "best":
    current, value = chosen, chosen_value
    last = trace[-1]
    trace[-1] = TracePoint(last.evaluation, last.proposed, value, last.best, moved, None)
```

读轨迹 CSV 时，`best` 的那一行 `current` 是**回填值**，不是扫描当时的当前值。这是逐行分析轨迹时必须记住的一个例外。

### 6.5 温度记录在「用完之前」

```python
record(candidate, schedule, score, accepted, temperature if config.algorithm == "sa" else None)
temperature *= config.cooling
```

所以第 `i` 次评价（`i >= 2`）记录的温度是 `T0 × cooling^(i-2)`，`random` / `first` / `best` / `multistart` 的温度列恒为空。`runs/*.trace.csv` 就照这个语义落盘，实测表头与前三行：

```text
evaluation,proposed,current,best,accepted,temperature
1,719.0,719.0,719.0,True,
2,662.0,662.0,662.0,True,10.0
3,661.0,661.0,661.0,True,9.8
```

（来自 `artifacts/month1_refactored/runs/single_12__main__sa__0.trace.csv`。）

---

## 7. 实验：`m1w3d6_search.py`

对应脚本 [m1w3d6_search.py](../../projects/01_scheduling_core/examples/m1w3d6_search.py)。在仓库根目录运行：

```bash
python projects/01_scheduling_core/examples/m1w3d6_search.py
```

在项目目录下等价的写法是：

```bash
python -m examples.m1w3d6_search
```

实例固定为 `generate_instance(20, jobs=12, machines=1)`（与 `configs/month1.json` 的 `single_12` 同参数），目标 `total_tardiness`，搜索 `seed=0`、`budget=150`，按 `ALGORITHMS` 的顺序逐个跑。实测输出：

```text
algorithm,objective,evaluations,status,seconds
lpt,719.0,1,BASELINE,0.000407
random,303.0,150,BUDGET,0.031973
first,575.0,150,BUDGET,0.031890
best,529.0,150,BUDGET,0.033041
multistart,371.0,150,BUDGET,0.047888
sa,263.0,150,BUDGET,0.044456
```

**实验观察**（注意：这是**一个实例、一个 `seed`** 的一次运行，不是理论结论）：

1. **本实例上 SA 的 263 最好**，比初始基线 719 降低了约 63%；`multistart` 的 371 次之。
2. **`first`（575）在本实例上不如 `random`（303）。** 这不矛盾——`first` 沿固定扫描顺序「第一个改善就跳」，很容易在 12 个作业的排列空间里早早撞到局部最优；`random` 虽然不做邻域结构，但每步都是全新的随机排列，反而更容易在 150 次内碰到好解。
3. **`first` / `best` 在这里用满了 150 次，`status` 是 `BUDGET` 而不是 `LOCAL_OPTIMUM`。** 因为 12 个作业的邻域有上百个候选，一圈还没扫完预算就见底了。对比第 5.5 节的 4 作业实例——**同样是 `first`，小实例上 23 次就停机，12 作业实例上跑满 150 次也没停机**。`status` 因此强烈依赖实例规模，不能脱离实例谈。
4. **秒数列彼此接近（0.03 ～ 0.05 秒）**，因为所有方法的 `budget` 相同、每次评价的成本相同（一次解码 + 一次校验 + 一次目标）。邻居生成的差异只体现在 `multistart` 略高的 0.048 上。

**关于 `lpt` 这一行的两条纪律**（照抄 stub 的原始要求，不得松动）：

- **`lpt` 在这里只是「共享初始基线」。** 五种搜索方法都从同一个初始 `Candidate` 出发，`lpt` 那一行就是把这份初始解评价一次，用来告诉读者「搜索到底改善了多少」。
- **`lpt` 不是单机迟交问题的理论最优规则。** `1||ΣTj` 是 NP-hard，没有任何多项式规则能保证最优（Day 1 与 CE-02 都讲过）。SPT / EDD / WSPT 的规则对照在 Week 1 的脚本里，**本批次的六行里根本没有它们**。
- **因此不能写「所有方法都击败了 LPT」这类越界结论**，更不能写「所有方法都击败了 EDD / WSPT」——**没有被纳入本批次运行过的规则，不能声称它被击败了。**

**关于真实数值的边界**：本日脚本的实例与批次里的 `single_12` 逐字节相同，但**这一次运行不等于月度批次**。批次的三个 `seed` 均值与各实例限制集中在 [月度报告](../MONTH1_REPORT.md) §6～§7；本日数字只在「本实例、`seed=0`、一次运行」的范围内成立。**不要把示意数字当成测量值，也不要把一次运行当成均值。**

---

## 8. 今日练习

1. **练习 1（轨迹核对）**：把 `m1w3d6_search.py` 的 `algorithm` 改成只跑 `first`，把 `budget` 改成 1500，观察 `status` 是否从 `BUDGET` 变成 `LOCAL_OPTIMUM`，并说明为什么加大预算反而能让它「停机」。
2. **练习 2（SA 轨迹分析）**：选一条 SA 轨迹，找到一处 `accepted=True` 且 `proposed > 该行之前的 current` 的行，确认同一行的历史 `best` 没有回升。要求写出具体行号与三个数值。
3. **练习 3（差异归因）**：对同一个 `Instance` 分别用 `seed=0` 和 `seed=1` 跑 `first`，解释为什么两条轨迹**逐行相同**，而 `sa` 的两条轨迹不同。
4. **练习 4（曲线长度）**：用手算说明第 5.4 节的 `first` 轨迹在横轴上只有 23 个点，并写出「若把它画成 150 个点」会伪造出什么信息。
5. **练习 5（成本核算）**：解释为什么 `elapsed_seconds` 不含写文件和绘图，以及为什么不同平台上的秒数不能直接比较。

---

## 9. 验收清单

- [ ] 能说出对比实验必须固定的三样东西：同一个 `Instance`、同一个 `budget`、逐次记录。
- [ ] 能解释 `objective` / `evaluations` / `status` / `elapsed_seconds` 四个字段各自回答什么问题。
- [ ] 能说出 `BUDGET` / `LOCAL_OPTIMUM` / `BASELINE` 三个状态在代码里的来源。
- [ ] 能解释为什么 `multistart` 永远不会返回 `LOCAL_OPTIMUM`。
- [ ] 能手算第 5 节的 LPT 初始值 57、候选 46、最优 36 三条时间线。
- [ ] 能解释 `first` 的轨迹为什么刚好是 23 行。
- [ ] 能写清 `lpt` 在本日只是共享初始基线，且不主张任何未被纳入本批次的规则被击败。
- [ ] 能说出 `runs/*.trace.csv` 的六列含义，以及 `best` 算法回填最后一行的例外。
- [ ] `python examples/m1w3d6_search.py` 能跑通并打印六个方法的目标值、评价数、状态与秒数。
- [ ] `python -m pytest tests/test_month1.py -k 'search or local_optimum or singleton' -q` 选定 25 条并全部通过。

---

## 10. 自测题

不看上文回答：

- Q1：对比实验为什么必须固定同一个实例和同一个预算？
- Q2：一次「评价」具体包含哪三步？初始化和被拒绝的候选算不算预算？
- Q3：`objective` 返回的是历史 `best` 还是最后一次 `current`？为什么？
- Q4：`status` 的三个取值分别从哪里来？
- Q5：为什么 `multistart` 不会返回 `LOCAL_OPTIMUM`？
- Q6：收敛曲线的横轴为什么用评价数而不是秒数？
- Q7：`first` 与 `best` 都扫描邻居，二者接受候选的规则差在哪？
- Q8：`lpt` 在本日实验中扮演什么角色？为什么不能写「所有方法击败了 EDD」？
- Q9：`runs/*.trace.csv` 的六列是什么？`best` 算法的轨迹有什么例外？
- Q10：为什么三个 `seed` 只够观察现象，不够「稳定估计很小的差异」？

### 参考答案

- A1：否则结果差异里会混进数据差异和预算差异，无法把差异归因到方法本身。
- A2：解码 + 独立校验 + 目标计算。初始化点、被拒绝的候选、no-op、随机重启全部计入预算。
- A3：历史 `best`。SA 会让 `current` 上下浮动，允许暂时变差是搜索策略，但结果管理上不能丢失已发现的最好解。
- A4：`BASELINE` 来自「算法是 `lpt`」；`BUDGET` 是主循环跑满预算后的默认值；`LOCAL_OPTIMUM` 来自「扫完一圈邻居 `moved == False`」。
- A5：因为它对 `not moved` 的响应是**随机重启**而不是停机，重启后继续跑，状态停留在 `BUDGET`。
- A6：评价数只由 `Instance` + `SearchConfig` 决定，可复现；秒数受机器负载与平台影响，不可复现。
- A7：`first` 遇到第一个严格改善的邻居就接受并跳出本圈；`best` 先把一整圈扫完，再取其中最好的一步。
- A8：`lpt` 提供所有方法共享的初始基线，用来衡量搜索改善了多少。SPT / EDD / WSPT 不在本批次运行范围内，没有被运行过的规则不能声称被击败。
- A9：`evaluation / proposed / current / best / accepted / temperature`。例外是 `best` 算法会把本圈最后一行的 `current` 回填成扫描结束后跳过去的值。
- A10：不同 `seed` 的最终值只是有限样本；连续 SA 事件既不独立也不同分布（概率随 Δ 与 T 变化，且搜索状态相关），小差异需要更多次运行才能与噪声区分开。

---

## 11. 今日一句话总结

> **对比实验的价值不在名次表，而在于把「同一个实例、同一个预算、逐次记录」固定住，于是 `objective`、`evaluations`、`status` 三个字段就能分别回答「多好」「花了多少」「是跑满还是扫尽」——而提前停机的曲线更短，这件事必须原样保留，不能补成跑满预算的样子。**
