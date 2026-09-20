# Day 5：模拟退火、温度与接受率

> 当日主题：用可控的「暂时变差」换取跳出局部最优的机会
> 当日产出：**SA 的接受准则与三条轨迹**（`proposed` / `current` / `best`）+ 实验脚本 [m1w3d5_sa.py](../../projects/01_scheduling_core/examples/m1w3d5_sa.py)
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 写出接受准则：`Δ = f(y) − f(x)`，`Δ ≤ 0` 无条件接受，否则以概率 `exp(−Δ/T)` 接受。
2. 说出冷却进度 `T ← cooling × T` 在每一次提议之后执行，并写出第 k 次评价使用的温度。
3. 解释为什么 `proposed` / `current` / `best` 必须分成三条轨迹，以及为什么返回的是 `best`。
4. 说明温度的**量纲与目标差值相同**，因此同一个 `T` 在 `makespan` 与 `total_tardiness` 上含义不同。
5. 说出 `temperature` 必须有限且为正、`cooling` 必须在 `(0, 1]`，并知道代码用什么条件一次性拦住非法值。
6. 解释为什么允许 no-op（`i=j` 或重抽到原机器），以及为什么它必须照样计入评价。
7. 会用 `accepted_count / proposals` 在窗口上计算接受率，并说明为什么 no-op 与等值接受都算「接受」。
8. 说清本实现是**有限预算的几何降温启发式**，不声称渐近全局最优。

---

## 2. 为什么第 5 天要允许「变差」

Day 2 ～ Day 4 的三种方法（First、Best、Multi-start）有一个共同前提：**只接受严格改善。** 这条规则很安全，但也把搜索锁死了——一旦当前解的邻域里没有任何更好的邻居，搜索就停下，而「局部最优」只是相对于当前邻域的结论；当目标曲面存在大量等值平台或很浅的局部最优时，纯下坡搜索会频繁被「小坑」挡住。

模拟退火（Simulated Annealing, SA）的让步非常直接：

> **允许暂时变差，并且用概率控制「变差多少可以容忍」。**

```text
纯下坡（First / Best）：只能向下 → 掉进第一个小坑就出不来
SA：                 大概率向下，小概率向上 → 有机会翻过坑沿，落到更好的盆地
```

代价同样直接：**`current` 会上下浮动，所以最后的 `current` 完全不能当作答案。** 接受变差是搜索**策略**，而「不丢失历史上找到的最好解」是结果**管理**，两者必须同时成立——这就是第 4 节要把三条轨迹分开的原因。

> **本实现是「有限预算 + 几何降温」的启发式，不声称具有渐近全局最优保证。** 教科书里的全局收敛结论依赖对数降温、无限次提议等条件，本项目两条都不满足。

---

## 3. 接受准则与冷却进度

**定义（接受准则）**：设当前解目标为 `f(x)`、候选目标为 `f(y)`，令 `Δ = f(y) − f(x)`：

```text
Δ ≤ 0  →  接受（概率 1，不需要算指数）
Δ > 0  →  以概率 exp(−Δ / T) 接受
```

```python
delta = score - value
accepted = (
    score < value
    if config.algorithm == "random"
    else delta <= 0 or rng.random() < exp(-delta / max(temperature, 1e-12))
)
if accepted:
    current, value = candidate, score
```

这段代码有四个必须读懂的点：

| 代码 | 含义 |
|---|---|
| `delta <= 0 or ...` | **等值候选（`Δ = 0`）也走这一支**，被无条件接受；只有严格变差才去掷骰子 |
| `or` 的短路 | `Δ ≤ 0` 时 `rng.random()` **不会被调用**——所以「是否等值」会影响随机数消耗，从而影响后续提议序列 |
| `max(temperature, 1e-12)` | 除零保护。构造函数已经要求 `T` 有限且为正，只有在反复冷却到极小值时才可能用到这个下限 |
| `if accepted: current, value = ...` | 被拒绝时候选被丢弃，但**评价已经花掉了**（`record` 照样记一行） |

**冷却进度**在循环的最后一行：

```python
temperature *= config.cooling
```

它在**每一次提议之后**执行，无论该次提议是否被接受。于是：

```text
第 k 次评价（k ≥ 2）使用的温度 = T0 × cooling^(k − 2)
第 1 次评价是初始化点，temperature 记录为 None（不消耗温度）
```

**参数校验**（`SearchConfig.__post_init__`）：

```python
if (
    not isfinite(self.temperature)
    or self.temperature <= 0
    or not 0 < self.cooling <= 1
):
    raise ValueError("invalid annealing parameters")
```

`not isfinite(T) or T <= 0` 一次拦住 `0`、负数、`inf` 与 `nan`；`0 < cooling <= 1` 拦住 `0` 与大于 1 的冷却因子，但**放行 `cooling=1.0`**（温度不降，退化为定温随机游走）。

**关于量纲**：`exp(−Δ/T)` 要求 `Δ/T` 无量纲，所以 **`T` 的单位必须与目标值相同**。`makespan` 的时间差常常只有个位数，`T=10` 意味着「几点的差距几乎照单全收」；`total_tardiness` 的差值动辄几十上百，同一个 `T=10` 相对就是「几乎全拒绝」。第 5.3 节给出实测对比：同一实例、同一 `seed`、同一 `T=10`，`makespan` 的接受率是 0.9530，`total_tardiness` 只有 0.5638。

---

## 4. 三条轨迹必须分开

`trace` 的每一行同时记录三个目标值，它们回答的是三个不同的问题：

| 字段 | 含义 | 约束 |
|---|---|---|
| `proposed` | 本次提议候选的目标值 | 无约束（可以比当前差很多） |
| `current` | 接受/拒绝**之后**的当前解目标值 | **可以上升** |
| `best` | 历史最小值 | **必须单调不增** |

> **理论结论**：`current` 承担探索，`best` 承担结果——允许变差是搜索策略，不允许丢失历史最好是结果管理，两者互不冲突但必须分开记录。

手算示例见第 5.2 节（当前 20、历史最好 18，此时接受一个 23 的候选）。`SearchResult` 里对应的是：

```text
result.objective = best_value    result.schedule = best_schedule
result.trace[-1].current         （最后一次走到的值，不是答案）
```

---

## 5. 手算 / 示例：接受概率与三条轨迹

### 5.1 接受概率算术

| 目标差值 `Δ` | 温度 `T` | 接受概率 | 说明 |
|---|---|---|---|
| 5 | 10 | 0.606531 | 中等温度：变差 5 点大概率被接受 |
| 5 | 1 | 0.006738 | 低温：变差 5 点几乎必被拒绝 |
| 1 | 10 | 0.904837 | 小幅度变差几乎必被接受 |
| 0 | 任意 | 1 | 等值：走 `delta <= 0` 分支，不算指数 |
| −6 | 任意 | 1 | 严格改善：无条件接受 |

```text
exp(−5 / 10) = exp(−0.5)   = 0.606531
exp(−5 / 1)  = exp(−5)     = 0.006738
exp(−1 / 10) = exp(−0.1)   = 0.904837

同一个 Δ=5，温度从 10 降到 1，接受概率从 0.6065 掉到 0.0067（约 90 倍）
```

温度与 Δ 的量纲相同这一点，用「Δ=5 在 `makespan` 里是 5 个时间单位、在 `total_tardiness` 里是 5 个迟交单位」就能记住：**同一个 `T` 在两个目标上代表完全不同的容忍度。**

### 5.2 手算示例：三条轨迹的分叉

```text
evaluation  proposed  current  best  accepted  说明
（起始）     ——        20       18    ——        搜索开始前已有 current=20、best=18
2           23        23       18    True      Δ = 23 − 20 = +3 > 0，按概率接受
                                              → current 升到 23，best 保持 18
3           17        17       17    True      Δ = 17 − 23 = −6 ≤ 0，无条件接受
                                              → current 与 best 同时降到 17
```

```text
算术：
  第 2 次评价：Δ = +3，接受概率 = exp(−3/T)；本行 current = 23 > 上一行 current = 20
  第 3 次评价：Δ = −6 ≤ 0，接受概率 = 1；current 与 best 一起下降
  三列的关系：current 可以上升，best 只在「严格更低」时变化
```

**对比表**：

| 轨迹 | 第 2 次评价后 | 第 3 次评价后 | 是否允许上升 |
|---|---|---|---|
| `proposed` | 23 | 17 | 是（候选是随机提议） |
| `current` | 23 | 17 | **是（这就是 SA 的核心让步）** |
| `best` | 18 | **17** | 否（单调不增） |

### 5.3 真实实例上的三条轨迹

| 项 | 值 |
|---|---|
| 生成式 | `generate_instance(20, jobs=12, machines=1)` |
| 目标 | `total_tardiness` |
| `budget` | 150 |
| `seed` | 0 |
| `cooling` | 0.98 |
| `temperature` | 1.0 / 10.0 / 100.0 三档 |

```text
T=100 的 trace 开头（高温期，current 频繁上升）
  #  1  proposed=  719.0  current=  719.0  best=  719.0  accepted= True  temperature=-
  #  2  proposed=  662.0  current=  662.0  best=  662.0  accepted= True  temperature=100.000
  #  3  proposed=  661.0  current=  661.0  best=  661.0  accepted= True  temperature=98.000
  ...（完整 150 行见第 7 节的脚本输出）

T=100 的 trace 结尾（低温期，接受变差变得罕见）
  #148  proposed=  296.0  current=  296.0  best=  288.0  accepted= True  temperature=5.236
  #149  proposed=  331.0  current=  296.0  best=  288.0  accepted=False  temperature=5.131
  #150  proposed=  297.0  current=  297.0  best=  288.0  accepted= True  temperature=5.029
```

```text
算术（T=100 的运行）：
  初始值 719.0 → best 终值 288.0；best 列单调不增（脚本断言为 True）
  current 上升的次数 = 26（第一次上升发生在 #11）
  最后一次评价：current = 297.0，best = 288.0，而返回的 objective = 288.0 = best
  温度核对：第 2 次评价 T = 100.0，第 150 次评价 T = 100 × 0.98^148 = 5.0287

算术（接受率，窗口 [2, 150] 排除第 1 个初始化点）：
  T=1  ：0.5101 → 76/149      T=10 ：0.5638 → 84/149
  T=100：0.8188 → 122/149
```

**对比表**（同一实例 + 同一 seed，只改初始温度）：

| `temperature` | objective | `current` 上升次数 | 全程接受率 | 前半段 | 后半段 |
|---|---|---|---|---|---|
| 1.0 | **255.0** | 0 | 0.5101 | 0.6486 | 0.3733 |
| 10.0 | 263.0 | 2 | 0.5638 | 0.6486 | 0.4800 |
| 100.0 | 288.0 | 26 | 0.8188 | 0.9324 | 0.7067 |

**读表要点**：

1. `T=1` 的运行里 `current` 一次都没上升过（0 次）——温度太低，SA 实质上退化成只下坡的搜索。
2. `T=100` 的运行里 `current` 上升 26 次，探索最积极，但**最终 `best` 反而最差**（288.0）。「探索多」和「结果好」不是一回事。
3. 单次运行的排序**不能**当作参数结论：月度批次在 `single_12`（同生成式、3 个 seed、预算 150）上的 `total_tardiness` 均值是——默认 `T=10, cooling=0.98` 为 261.67（标准差 5.13，最好 256）、`T=0.1` 为 262.0（标准差 7.55）、`T=10, cooling=0.9` 为 255.33（标准差 5.51，最好 250）、`T=100` 为 282.67（标准差 13.80）。**只有 `T=100` 的差距明显超过标准差**；其余三档彼此的差异比各自的波动还小。这就是「一次运行 ≠ 均值」这条纪律在这里的体现。

### 5.4 与 First / Best 的对照：等值接受

| 方法 | `Δ = 0` 的邻居 | `Δ > 0` 的邻居 | 能否穿过等值平台 |
|---|---|---|---|
| `first` | 拒绝（严格小于才动） | 拒绝 | 否 |
| `best` | 拒绝（严格小于才动） | 拒绝 | 否 |
| `sa` | **接受**（走 `delta <= 0` 分支） | 以 `exp(−Δ/T)` 概率接受 | **能** |

实测证据（两道工序 `p = [3, 3]`、单机、`makespan`）：

```text
原候选   order=('O0', 'O1') → makespan = 6
交换后   order=('O1', 'O0') → makespan = 6
两个候选不同，但 Δ = 0 → `delta <= 0` 分支直接接受，不靠概率
```

**结论**：First 与 Best 会拒绝这类等值移动（Day 3 第 6.4 节），SA 接受它，于是**SA 有机会沿着平台横着走到局部搜索到不了的位置**——这是「允许变差」之外的第二个自由度。

---

## 6. 实现：`search.py`

对应文件 [search.py](../../projects/01_scheduling_core/scheduling_algorithms/search.py)。

### 6.1 提议集合：swap / insert / reassign 三选一

```python
def random_move() -> Candidate:
    # 允许 no-op，仍计入评价，避免单元素/单资格情况下死循环。
    if not current.order:
        return current
    kind = rng.randrange(3)
    i = rng.randrange(len(current.order))
    j = rng.randrange(len(current.order))
    if kind == 0:
        return swap(current, i, j)
    if kind == 1:
        return insert(current, i, j)
    return reassign(
        instance,
        current,
        i,
        rng.choice(instance.operations[i].eligible_machine_ids),
    )
```

| 设计 | 原因 |
|---|---|
| 三种移动等概率（`rng.randrange(3)`） | 不引入人为偏好；换机维度只在有资格选择时才起作用 |
| `i` 与 `j` 独立抽取，**允许 `i == j`** | `swap(i, i)`、`insert(i, i)` 都是 no-op |
| 机器从 `eligible_machine_ids` 里重抽，**允许抽回原机器** | no-op；同时保证候选一定合法（不会制造 `illegal assignment`） |
| `if not current.order: return current` | 空实例的保护分支 |

**为什么必须允许 no-op？** 因为如果不允许（例如「必须抽到不同的解才返回」），那么在**单工序实例**或**单资格实例**上根本不存在不同的候选，循环会永远抽不出解——变成一个死循环。允许 no-op 后，候选等于当前解本身、`Δ = 0`、走 `delta <= 0` 分支被接受，它照样消耗 1 次评价，因此循环一定会因预算耗尽而终止。单工序实例（1 道工序、1 台机器）上，`swap(0,0)`、`insert(0,0)`、`reassign` 回 `"M0"` 三种移动**必然**都退化成 no-op，所以这个实例是「no-op 合法且计数」的最干净证明：预算 12 就得到 12 行 `accepted=True`、`proposed = current = best = 3.0` 的轨迹，并且**没有死循环**（第 7 节实测）。

### 6.2 循环结构与 `status`

```python
elif config.algorithm in ("random", "sa"):
    while len(trace) < config.budget:
        ...
        temperature *= config.cooling
```

SA 与 Random Search 共用「每次提议一个候选」的循环：循环条件只看到 `len(trace) < budget`，**没有任何提前退出**，所以 **SA 的 `status` 恒为 `BUDGET`、`evaluations` 恒等于 `budget`**。这与 `first` / `best` 可能提前返回 `LOCAL_OPTIMUM` 形成对比，也是测试里 `if algorithm in ("random", "sa", "multistart"): assert result.evaluations == budget` 这一条断言的来源。

### 6.3 温度是怎么进 trace 的

```python
record(candidate, schedule, score, accepted, temperature if config.algorithm == "sa" else None)
temperature *= config.cooling
```

`record` 在**冷却之前**被调用，所以记录的是本次提议**实际使用**的温度；`random` / `first` / `best` / `multistart` 的 `temperature` 列恒为 `None`，第 1 行（初始化点）也是 `None`，因为它不参与任何提议。

### 6.4 接受率的口径

**定义（窗口接受率）**：`窗口 [lo, hi) 的接受率 = 该窗口内 accepted=True 的评价数 / 该窗口内的评价数`，窗口从第 2 次评价开始。第 1 个初始化点必须排除，因为它的 `accepted` 固定为 `True`，把它算进分子会凭空抬高接受率。

同时要记住两件事：

1. **no-op 与等值接受都算 accepted。** 它们不是「有效探索」，只是合法事件；所以**高接受率本身不证明探索有效**——`T=100` 的 0.8188 反而对应最差的 `best`。
2. **绝不能把 SA 的接受率与其他算法的 `accepted` 混算。** `first` / `best` 的一个 `accepted=True` 代表一整轮（可能上百次评价），而 SA 的代表一次提议（Day 3 第 6.3 节）。

### 6.5 本实现的边界

| 声明 | 是否成立 |
|---|---|
| 有限预算内一定终止，返回一个可行解 | 成立（预算耗尽即退出） |
| 返回的是历史上找到的最好解 | 成立（`best` 只在严格更小时更新） |
| 固定 `seed` + 固定输入 → 轨迹可复现 | 成立（单机 `Random` 实例，不改全局随机状态） |
| 渐近收敛到全局最优 | **不声称**。需要无限次提议与特定的降温条件，本实现是几何降温 + 有限预算 |

---

## 7. 实验：`m1w3d5_sa`

对应脚本 [m1w3d5_sa.py](../../projects/01_scheduling_core/examples/m1w3d5_sa.py)，在项目目录下运行：

```bash
python examples/m1w3d5_sa.py
```

脚本分五部分：接受概率算术、三条轨迹的手算示例、参数合法性检查、同一实例上的三个初始温度、no-op 与等值移动。固定 `seed`，不写 `artifacts/`。

**实际运行输出**（原文粘贴）：

```text
==============================================================================
第 1 部分：接受准则 exp(-Δ/T) 的算术
==============================================================================
Δ=5, T=10 → exp(-5/10) = 0.606531
Δ=5, T=1 → exp(-5/1) = 0.006738
Δ=1, T=10 → exp(-1/10) = 0.904837
Δ<=0 时无条件接受（概率 1），不需要算指数。
注意 T 与 Δ 的量纲相同：Δ 是目标差值，所以 T 也必须用目标值的单位。
makespan 的单位是时间，total_tardiness 的单位是迟交量，
同一个 T=10 在两个目标上代表完全不同的「容忍度」。

==============================================================================
第 2 部分：手算示例 —— current=20 时接受一个 23 的候选
==============================================================================
evaluation,proposed,current,best,accepted,说明
1,-,20,18,-,搜索开始前已有 current=20、best=18
2,23,23,18,True,Δ=23-20=+3>0，按概率 exp(-3/T) 接受 → current 升到 23，best 保持 18
3,17,17,17,True,Δ=17-23=-6<=0，无条件接受 → current 与 best 同时降到 17
允许 current 变差是搜索策略；不允许丢失历史最好是结果管理，两者不能混。

==============================================================================
第 3 部分：参数合法性 —— temperature 必须有限且为正，cooling 必须在 (0, 1]
==============================================================================
SearchConfig({'temperature': 0.0}) → ValueError: invalid annealing parameters
SearchConfig({'temperature': -1.0}) → ValueError: invalid annealing parameters
SearchConfig({'temperature': inf}) → ValueError: invalid annealing parameters
SearchConfig({'temperature': nan}) → ValueError: invalid annealing parameters
SearchConfig({'cooling': 0.0}) → ValueError: invalid annealing parameters
SearchConfig({'cooling': 1.5}) → ValueError: invalid annealing parameters
SearchConfig({'cooling': 1.0}) → 接受
isfinite(inf) = False，isfinite(nan) = False，
所以 `not isfinite(T) or T <= 0` 一次拦住 0、负数、inf 与 nan。
cooling=1.0 合法：温度不降，退化为定温随机游走。

==============================================================================
第 4 部分：同一实例 + 同一 seed 上的三个初始温度
==============================================================================
instance = generate_instance(20, jobs=12, machines=1)，objective = total_tardiness
budget=150，seed=0，cooling=0.98
temperature,objective,evaluations,status,rises,rate_all,rate_first_half,rate_second_half
1.0,255.0,150,BUDGET,0,0.5101,0.6486,0.3733
10.0,263.0,150,BUDGET,2,0.5638,0.6486,0.4800
100.0,288.0,150,BUDGET,26,0.8188,0.9324,0.7067
接受率一律按 accepted 评价数 / 窗口评价数统计，窗口从第 2 次评价开始，排除第 1 个初始化点。

同一个 T=10 在两个目标上的实测差别（同一实例、同一 seed、同一 cooling=0.98）:
objective,initial,temperature,objective_final,rises,rate
makespan,103.0,10.0,96.0,7,0.9530
total_tardiness,719.0,10.0,263.0,2,0.5638
makespan 的 Δ 通常只有个位数，T=10 意味着「几点的差距几乎照单全收」；
total_tardiness 的 Δ 动辄几十上百，同一个 T=10 相对就是「几乎全部拒绝」。
所以调温度时必须连着目标值的量级一起看，不能把结论搬到另一个目标上。

T=100 的 trace 开头（高温期 current 频繁上升）:
  #  1  proposed=  719.0  current=  719.0  best=  719.0  accepted= True  temperature=-
  #  2  proposed=  662.0  current=  662.0  best=  662.0  accepted= True  temperature=100.000
  #  3  proposed=  661.0  current=  661.0  best=  661.0  accepted= True  temperature=98.000
  #  4  proposed=  651.0  current=  651.0  best=  651.0  accepted= True  temperature=96.040
  #  5  proposed=  619.0  current=  619.0  best=  619.0  accepted= True  temperature=94.119
  #  6  proposed=  619.0  current=  619.0  best=  619.0  accepted= True  temperature=92.237
  #  7  proposed=  589.0  current=  589.0  best=  589.0  accepted= True  temperature=90.392
  #  8  proposed=  589.0  current=  589.0  best=  589.0  accepted= True  temperature=88.584
  #  9  proposed=  489.0  current=  489.0  best=  489.0  accepted= True  temperature=86.813
  # 10  proposed=  454.0  current=  454.0  best=  454.0  accepted= True  temperature=85.076
T=100 的 trace 结尾:
  #148  proposed=  296.0  current=  296.0  best=  288.0  accepted= True  temperature=5.236
  #149  proposed=  331.0  current=  296.0  best=  288.0  accepted=False  temperature=5.131
  #150  proposed=  297.0  current=  297.0  best=  288.0  accepted= True  temperature=5.029
best 单调不增? True（719.0 → 288.0）
最后一次评价的 current=297.0，best=288.0；返回的 objective=288.0 取的是 best。
温度按 T ← cooling × T 逐次冷却：第 2 次评价用 T=100.0，最后一次评价用 T=5.0287。
核对：100 × 0.98^148 = 5.0287，与 trace 记录一致。
T=1 的运行里 current 从未上升过（rises=0），说明低温下几乎只见下坡路；
T=100 的运行里 current 频繁上升，最终 best 反而更差——这正是「短期变差换探索」的代价。

==============================================================================
第 5 部分：no-op 与等值移动
==============================================================================
swap(i, i) == 原候选 ? True
insert(i, i) == 原候选 ? True
reassign 回原机器 == 原候选 ? True
单工序实例上三种移动必然退化成 no-op，neighbors() 也产生不出任何新候选。
  #  1  proposed=    3.0  current=    3.0  best=    3.0  accepted= True  temperature=-
  #  2  proposed=    3.0  current=    3.0  best=    3.0  accepted= True  temperature=10.000
  #  3  proposed=    3.0  current=    3.0  best=    3.0  accepted= True  temperature=9.800
  #  4  proposed=    3.0  current=    3.0  best=    3.0  accepted= True  temperature=9.604
  #  5  proposed=    3.0  current=    3.0  best=    3.0  accepted= True  temperature=9.412
  #  6  proposed=    3.0  current=    3.0  best=    3.0  accepted= True  temperature=9.224
  #  7  proposed=    3.0  current=    3.0  best=    3.0  accepted= True  temperature=9.039
  #  8  proposed=    3.0  current=    3.0  best=    3.0  accepted= True  temperature=8.858
  #  9  proposed=    3.0  current=    3.0  best=    3.0  accepted= True  temperature=8.681
  # 10  proposed=    3.0  current=    3.0  best=    3.0  accepted= True  temperature=8.508
  # 11  proposed=    3.0  current=    3.0  best=    3.0  accepted= True  temperature=8.337
  # 12  proposed=    3.0  current=    3.0  best=    3.0  accepted= True  temperature=8.171
评估次数 12（= budget）、accepted 全为 True? True、objective=3.0
no-op 照样计入预算、照样被「Δ<=0 无条件接受」接受，却不会死循环。

等值移动：两道工序 p 都是 3，交换前后目标相同
  原候选   order=('O0', 'O1') → makespan=6
  交换后   order=('O1', 'O0') → makespan=6
  两个候选不同? True；Δ=0 → `delta <= 0` 分支直接接受，不靠概率。
Best/First 只接受严格改善（Δ<0），会拒绝这类等值移动；SA 接受它，
所以 SA 有机会沿着等值平台走到局部搜索到不了的位置。
但接受率高本身不等于探索有效：no-op 与等值接受都算 accepted，
高温下 rate 很高，也可能只是原地打转。
```

**实验观察**（只陈述输出里看得到的事实）：

1. **三条轨迹的分叉是可见的**：`#149` 的 `proposed=331.0` 被拒绝（`current` 保持 296.0），`#150` 的 `proposed=297.0` 被接受（`current` 变成 297.0），而 `best` 全程停在 288.0。
2. **返回的是 `best`**：`objective=288.0` 等于末行 `best`，而不是末行 `current=297.0`。
3. **温度公式可核对**：第 2 次评价 `T=100.0`，末次评价 `T=5.0287 = 100 × 0.98^148`。
4. **参数校验的信息量**：`0`、负数、`inf`、`nan`、`cooling=0`、`cooling=1.5` 全部被拒；`cooling=1.0` 被接受。
5. **no-op 的代价与必要性**：单工序实例 12 次评价全是 no-op，全部被接受，`evaluations` 恰好等于 `budget`，没有死循环。
6. **同一个 `T=10` 在两个目标上的接受率差 0.39**（0.9530 对 0.5638），量纲问题在实测里成立。

---

## 8. 今日练习

1. **练习 1（手算）**：`Δ = 2`，`T = 4`，写出接受概率的表达式与四位小数；再算 `T = 0.5` 时的值，并说明温度下降一个数量级时概率下降多少个数量级。
2. **练习 2（三条轨迹）**：给定 `current = 50`、`best = 42`，提议 61 被接受、提议 39 被接受、提议 45 被拒绝。写出这三次之后的三列值，并指出哪一次让 `best` 更新。
3. **练习 3（窗口接受率）**：用第 7 节 `T=100` 的输出核对 `rate_first_half = 0.9324`（窗口 `[2, 75]`）与 `rate_second_half = 0.7067`（窗口 `[75, 150]`）的分母各是多少，并解释为什么后半段接受率明显更低。
4. **练习 4（量纲）**：固定实例与 `seed`，只把 `objective` 从 `total_tardiness` 换成 `makespan`，观察接受率从 0.5638 变成 0.9530。解释为什么会这样，并说出调温度时应当先看什么。
5. **练习 5（代码阅读）**：不看 `search.py`，写出 `random_move()` 在什么情况下返回与原解完全相同的候选，并说明为什么这个分支不能删掉。

---

## 9. 验收清单

- [ ] 能写出接受准则的三个分支（`Δ<0`、`Δ=0`、`Δ>0`），并知道 `Δ≤0` 时不算指数、不消耗随机数。
- [ ] 能写出第 k 次评价（`k ≥ 2`）使用的温度公式 `T0 × cooling^(k−2)`，并解释冷却在每次提议后执行。
- [ ] 能解释 `proposed` / `current` / `best` 三条轨迹各自的约束，并说明返回值是 `best`。
- [ ] 能说明 `temperature` 与 `cooling` 的合法范围，以及代码用哪个条件一次性拦住非法值。
- [ ] 能解释温度与目标差值同量纲，并用实测的 0.9530 / 0.5638 说明后果。
- [ ] 能解释 no-op 为什么必须允许、为什么照样计入评价。
- [ ] 会按 `accepted_count / proposals` 在窗口上算接受率并排除第 1 个初始化点；能说明 no-op 与等值接受都算 accepted，因此高接受率不证明探索有效。
- [ ] 能说出本实现不声称渐近全局最优，并给出理由（有限预算 + 几何降温）。
- [ ] 在项目目录下运行 `python -m examples.m1w3d5_sa`，核对第 7 节的输出与脚本实际输出一致。
- [ ] 在项目目录下运行 `python -m pytest tests/test_month1.py -k 'sa_accepts or search_budget' -v`，19 条测试全部通过（本日无新增测试）。

---

## 10. 自测题

不看上文回答：

- Q1：写出 SA 的接受准则，`Δ ≤ 0` 和 `Δ > 0` 分别怎么处理？
- Q2：冷却 `T ← cooling × T` 在什么时候执行？第 5 次评价用的是哪个温度？
- Q3：`proposed`、`current`、`best` 三列里，哪一列允许上升？哪一列必须单调不增？
- Q4：搜索结束时返回的是哪一列对应的排程？为什么不能返回 `current`？
- Q5：`temperature` 与 `cooling` 的合法取值范围是什么？`cooling = 1.0` 合法吗？
- Q6：为什么说温度与 Δ「量纲相同」？举一个同 `T` 不同目标的例子。
- Q7：no-op 是什么？为什么不能把它从实现里删掉？
- Q8：no-op 和等值移动会不会消耗评价？会不会被接受？
- Q9：接受率的分母为什么必须排除第 1 个初始化点？
- Q10：为什么「接受率高」不等于「探索有效」？

### 参考答案

- A1：`Δ = f(y) − f(x)`；`Δ ≤ 0` 无条件接受；`Δ > 0` 以概率 `exp(−Δ/T)` 接受。
- A2：在每一次提议之后（无论接受还是拒绝）执行；第 5 次评价（`k=5 ≥ 2`）使用的温度是 `T0 × cooling^3`。
- A3：`current` 允许上升（这正是「暂时变差」）；`best` 必须单调不增；`proposed` 无约束。
- A4：返回 `best` 对应的排程。`current` 可能正处在一次被接受的变差之后，它只是一个搜索位置，不是找到的最好解。
- A5：`temperature` 有限且严格为正；`cooling` 在 `(0, 1]`；`cooling = 1.0` 合法（温度不降，退化为定温随机游走）。
- A6：因为接受概率是 `exp(−Δ/T)`，比值必须无量纲，所以 T 与 Δ 同单位。同一实例上 `T=10` 在 `makespan` 上接受率 0.9530，在 `total_tardiness` 上只有 0.5638。
- A7：no-op 是「候选与原解完全相同」的移动（`i == j`，或 `reassign` 重抽到原机器）。删掉它会让单工序 / 单资格实例陷入「必须抽到不同解」的死循环。
- A8：会消耗 1 次评价（`record` 照样记一行）；会被接受（`Δ = 0` 走 `delta <= 0` 分支）。
- A9：因为第 1 个初始化点的 `accepted` 固定为 `True`，它不是一次真实的提议事件，算进分子会凭空抬高接受率。
- A10：no-op 与等值接受都算 `accepted`，它们不产生任何位置移动；`T=100` 的接受率 0.8188 反而对应最差的 `best`。

---

## 11. 今日一句话总结

> **模拟退火用 `exp(−Δ/T)` 把「暂时变差」变成一个可控的概率事件：`current` 可以上升、`best` 必须单调不增、返回的永远是 `best`；而温度与目标差值同量纲、no-op 也要照样记账——所以接受率高只说明提议被收下，不说明搜索走对了方向。**
