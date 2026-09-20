# Day 4：CP-SAT 的 FJSP 模型

> 当日主题：用「可选区间 + `ExactlyOne` + `NoOverlap` + 前驱约束」四组约束把两维决策一起写进模型
> 当日产出：**`build_model` 的规模读数、`fjsp_cpsat` 的两个 `OPTIMAL` 与一次限时敏感性实验、目标名闸门**
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 为每道工序的每台合格机器写出一个**可选区间**（`NewOptionalIntervalVar`），并说明 `presence` 文字变量同时承担了什么。
2. 说清四组约束各管什么，并论证这四组约束的可行解集合与实例的可行排程集合一一对应。
3. 独立算出一个实例的时间上界 `H = max_j r_j + Σ_o max_m p_om`，并给出它成立的三行论证。
4. 手算三个实例的变量数、约束数与 `horizon`，并说清 proto 的「约束数」里为什么包含区间定义。
5. 说清 `OPTIMAL` 的准确含义：求解器证明的是**它自己的模型**最优，以及这个结论成立的适用条件。
6. 区分 `best_bound` 的两种性质：`proven`（已证明）与 `search_progress`（搜索进度），并说出 `gap` 各自怎么读。
7. 解释为什么本模型遇到别的目标名要拒绝，而不是「解完了再报另一个目标」。
8. 说出目标值为什么要用 `evaluate` 独立重算，而不是直接用求解器的读数。

---

## 2. 为什么今天要用 CP-SAT 来做这件事

前三天把两维决策分开处理了：Day 1 只看「选机」值多少分，Day 2 只做「顺序 → 合法排程」，
Day 3 把「选机」写成三个策略。每一次都**冻结了另一维**，代价是每次只能看到一半。

`FJSP` 的难点恰恰在两维的耦合：一台机器上排谁、以及每道工序去哪台机器，是同一个决定的两面。
想把它们一起优化，就要一个能同时表达这两件事的模型。

CP-SAT 在这里有一个非常自然的写法：**给每道工序的每台合格机器各建一个区间，
让「区间在不在」本身成为决策变量**。

```text
选机  ->  哪个区间的 presence 为真
排序  ->  NoOverlap 在每台机器上决定这些区间的先后
```

这两件事在模型里的地位完全对称，没有谁先谁后 —— 这正是前三天做不到的事。

`OPTIMAL` 这个词今天第一次出现，它的含义必须一开始就说清：**求解器证明的是它自己的模型最优**。
如果模型漏掉了一条真实约束，那么它证明的只是「这个更松问题的最优」。
所以本方法的第一件事不是求解，而是**先检查实例是不是模型覆盖得了的**。

---

## 3. 概念：四组约束与它们的语义

### 3.1 每道工序一个 `[start, end)`，逐机器一个可选区间

```text
对每道工序 o：
    start_o, end_o     两个共享的整数变量（整道工序只有一个开工、一个完工）
    对每台合格机器 m：
        x_{o,m}  = 布尔变量（presence）
        iv_{o,m} = NewOptionalIntervalVar(start_o, p_om, end_o, x_{o,m})
```

**共享** `start` / `end` 是这套写法的关键：不论工序最后落在哪台机器上，
它在时间轴上都只有一个开工时刻。`presence` 变量承担两件事：

| `presence` 的角色 | 含义 |
|---|---|
| 选择变量 | `x_{o,m} = 1` 表示工序 `o` 被安排到机器 `m` |
| 区间开关 | `x_{o,m} = 0` 时 `iv_{o,m}` 不参与任何约束（它「不存在」） |

### 3.2 `ExactlyOne`：一次只在一台机器上做

```python
model.AddExactlyOne(literals)     # 对每道工序，它的全部可选区间里恰好一个为真
```

这一条把「选机」这件事收口：不能一台都不选（工序必须被加工），
也不能同时选两台（一道工序不能同时在两台机器上做）。

### 3.3 `NoOverlap`：一台机器一次只做一件事

```python
model.AddNoOverlap(intervals)     # 对每台机器，它的全部区间两两不重叠
```

注意传进去的是**该机器上的全部区间**，包括那些 `presence` 为假的 ——
`AddNoOverlap` 会自动忽略不存在的区间。这正是它比 Big-M 写法省事的地方：
互斥是**一条**约束，不需要序对二元变量、不需要 `M`、也不需要为「两台机器上的先后各自成立」操心。

### 3.4 precedence：订单内的工艺路线

```python
model.Add(ends[before] <= starts[after])    # 对每条工艺路线上相邻的两道工序
```

一条线性不等式就够了：`end(前道) <= start(后道)`。

### 3.5 目标与时间上界

```text
makespan = max_o end_o          （AddMaxEquality）
Minimize(makespan)
H = max_j r_j + Σ_o max_m p_om  （start / end / makespan 的上界）
```

`H` 是一个**朴素上界**，它同时决定了三件事：变量定义域的大小、模型的规模、
以及「这个模型总能给出一个不超过 `H` 的可行解」。

---

## 4. 推导：模型为什么是完整的、上界为什么成立

### 4.1 四组约束的可行解集合 = 全部可行排程

一边是模型：给每个 `start_o`、`end_o`、`presence` 变量取值。另一边是实例的**可行排程**。
两者一一对应，两个方向都要说：

```text
模型 -> 排程：
    ExactlyOne  保证每道工序恰好选中一台机器 m
    interval 定义保证 end_o = start_o + p_om，也就是它在 m 上占用 [start_o, end_o)
    NoOverlap   保证同一台机器上的这两段不重叠
    precedence  保证同一订单内前道先做完
  -> 读出来的就是一张合法的排程（机器资格、工艺路线、机器互斥都成立）

排程 -> 模型：
    把 presence 取成「实际用的那台机器」、start / end 取成实际时刻
  -> 四组约束全部成立（因为排程本身就是合法的）
```

两个方向都成立，所以**模型没有漏约束，也没有多约束**。
「多约束」这一侧值得留意：模型里没有任何一条约束是排程本身不需要的
（比如没有额外的对称破除、没有人为的先后顺序），因此模型的最优值就是问题的最优值。

### 4.2 时间上界

```text
对任何可行排程：makespan <= （全部工序的实际工时之和） + （最晚的释放时间）
              <= Σ_o max_m p_om + max_j r_j
              = H
```

第一步是「串行摊平」：把每台机器上的工序按时间顺序接起来，
总时间不会超过全部工序工时之和（机器之间有并行，去掉并行只会变长）。
第二步把每道工序的工时放大到它最慢的那台机器上，再把释放时间放大到最晚的那一个 ——
两处都是**放大**，所以不等式方向不变。

> **理论结论（`OPTIMAL` 的适用条件）**：CP-SAT 报 `OPTIMAL` 意味着
> 「在**本模型**的全部可行解中，`makespan` 的最小值已经找到并证明」。
> 由 4.1，本模型与纯 `FJSP` 的可行排程一一对应，所以在这个范围内它说的是问题本身。
> 一旦实例里含有本模型没有建模的约束（模型与排程不再一一对应），这句话就失效了。
> 所以 `fjsp_cpsat` 的第一件事不是求解，而是在建模之前检查实例是否落在覆盖范围内。

### 4.3 `best_bound` 的两种性质

`solver.BestObjectiveBound()` 这个读数在不同状态下含义不同，必须分开读：

| 状态 | `best_bound` 的性质 | `bound_kind` | 怎么读 |
|---|---|---|---|
| `OPTIMAL` | 已证明：模型的最优值就是它 | `proven` | 可以当作最优值引用 |
| `FEASIBLE` | 搜索爬到的最好界，还没证明完 | `search_progress` | 只能说「当前已知的最优解不超过 X」 |

```text
gap = (objective - best_bound) / objective
```

`gap` 是这两个读数之间的距离。它在限时求解里同时受「解有多好」与「搜索走了多远」影响，
所以**不能**当质量指标用 —— 这一点与 M2 Week 2 Day 3 的实测结论是同一条：
判断界要看它是不是被证明了，判断搜索要看 `branches` / 时间。

---

## 5. 手算：三个实例的规模与上界

**变量数**（`tiny_2x2`，`4` 道工序、每道 `2` 台合格机器）：

```text
4 个 start + 4 个 end + （4 道工序 x 2 台机器 = 8）个 presence + 1 个 makespan = 17
```

`fjsp_6x4_f2` 有 `18` 道工序、每道 `2` 台合格机器：

```text
18 + 18 + 36 + 1 = 73
```

**约束数**，按 proto 的字段分类（`tiny_2x2`）：

```text
interval     8    （proto 里每个可选区间自己占一条约束）
exactly_one  4    （每道工序一条）
no_overlap   2    （每台机器一条）
linear       2    （两条工艺路线各一条 precedence）
lin_max      1    （目标的那条 AddMaxEquality）
             ---
             17
```

这里有一处**必须提前说清的读数陷阱**：`stats()["constraints"]` 是 proto 里约束的条数，
而 proto 把每个区间定义也记成一条 `interval` 约束。所以：

```text
「约束数 17」里真正的逻辑约束是 9 条（4 + 2 + 2 + 1），另外 8 条是区间定义。
```

把 `interval` 读成「额外约束」会直接算错模型规模。这也是今天脚本里专门写了一个
按字段分类的计数函数的原因：`interval 8 · exactly_one 4 · no_overlap 2 · linear 2 · lin_max 1`
比一个孤零零的 `17` 有用得多。

`assign_2x3`（`4` 道工序、每道 `3` 台合格机器）与 `fjsp_6x4_f2` 的手算：

```text
assign_2x3    变量 = 4 + 4 + 12 + 1 = 21
              约束 = interval 12 + exactly_one 4 + no_overlap 3 + linear 2 + lin_max 1 = 22
fjsp_6x4_f2   变量 = 18 + 18 + 36 + 1 = 73
              约束 = interval 36 + exactly_one 18 + no_overlap 4 + linear 12 + lin_max 1 = 71
```

**时间上界**：

```text
tiny_2x2      max_j r_j = 0；Σ_o max_m p_om = 3 + 3 + 3 + 3 = 12  ->  H = 12
assign_2x3    max_j r_j = 0；Σ_o max_m p_om = 9 + 8 + 7 + 9 = 33  ->  H = 33
fjsp_6x4_f2                                                       ->  H = 200
```

`H` 与「最优值」没有关系，它只保证「装得下」：`tiny_2x2` 的 `H = 12`，
而它的最优值是 `2` —— 变量域比最优值宽出六倍是常态。

---

## 6. 实现：`build_model` 与 `fjsp_cpsat` 的分工

代码在 [cpsat_fjsp.py](../../projects/03_industrial_fjsp/fjsp_shop/cpsat_fjsp.py)，
分成两层：

```python
build_model(instance, spec=None) -> object     # 只建模：CpModel + 反查字典 + stats()
fjsp_cpsat(instance, spec)       -> ShopResult # 建模 + 求解 + 独立复核 + 组装结果
```

把两层分开有两个理由。第一，模型规模可以**单独读**：`build_model(...).stats()`
不需要跑求解器，规模表因此是「零成本」的读数。第二，第 7 节里两条拒绝消息有一条正是走
`build_model` 的 —— 只建模不求解的入口也必须拦。

求解部分的参数与读数：

```python
solver.parameters.max_time_in_seconds = ...  # 来自 spec["time_limit"]
solver.parameters.num_search_workers = NUM_SEARCH_WORKERS    # 常量 1
solver.parameters.random_seed = ...          # 固定种子
```

三个参数都是为了「同一 spec 两次运行给出同一个目标值」。单线程的代价是多线程的搜索吞吐用不上，
同样预算内的解质量会略低 —— 这一点在第 7 节的耗时列里会如实记下来。

结果的组装有三处刻意的选择：

| 读数 | 来源 | 理由 |
|---|---|---|
| `objective` | `evaluate(instance, schedule, ...)` 独立重算 | 求解器读数与独立计算是两条路径，一致才算数 |
| `best_bound` | `solver.BestObjectiveBound()` | 求解器自己给出的界，配 `bound_kind` 说明它的性质 |
| `status` | 求解器状态映射到统一状态名 | 与启发式共用同一个结果结构，便于比较 |

`bound_kind` 的取值只有两个：

```text
proven            求解器已经证明：模型的最优值就是 best_bound
search_progress   搜索爬到的最好界，还没有证明完 —— 它不是「问题的最优值」
```

---

## 7. 实验：`m3w2d4_cpsat`

脚本：[m3w2d4_cpsat.py](../../projects/03_industrial_fjsp/examples/m3w2d4_cpsat.py)。

在项目目录 `projects/03_industrial_fjsp` 下运行：

```bash
python examples/m3w2d4_cpsat.py
```

实际输出（原样粘贴）：

```text
=== CP-SAT 的 FJSP 模型 ===

== 1. 模型规模 ==
  实例          工序  可选区间  变量  约束  horizon
  tiny_2x2         4        8     17    17       12
  assign_2x3       4       12     21    22       33
  fjsp_6x4_f2     18       36     73    71      200
  约束数的构成（按 proto 的字段类型分类）：
    tiny_2x2      interval 8 · exactly_one 4 · no_overlap 2 · linear 2 · lin_max 1
    fjsp_6x4_f2   interval 36 · exactly_one 18 · no_overlap 4 · linear 12 · lin_max 1
  手算核对 tiny_2x2：4 道工序 x 2 台合格机器 = 8 个可选区间（proto 里每个区间
  自己占一条 interval 约束）；4 条 ExactlyOne；2 台机器各 1 条 NoOverlap；
  2 条 precedence（linear）；1 条 AddMaxEquality（lin_max）。
  8 + 4 + 2 + 2 + 1 = 17。也就是说「约束数」里有 8 条是区间定义，
  真正的逻辑约束是 9 条 —— 读模型规模时要把这两类分开。
  变量 = 4 个 start + 4 个 end + 8 个 presence + 1 个 makespan = 17。

== 2. tiny_2x2：小到能指望求解器证明最优 ==
  tiny_2x2（2 订单 x 2 工序）              tl =  2.0s
    status      = OPTIMAL
    objective   = 2.0
    best_bound  = 2.0   （proven）
    gap         = 0.0
    branches    = 38   conflicts = 0
    build_time  = 0.001205s   solve_time = 0.010967s   solver wall_time = 0.010s
    solver_objective - 独立重算 = 0.0
    LB（朴素下界，与求解器无关）= 2    horizon = 12
    排程 = O00@M0[0,1)  O10@M1[0,1)  O01@M0[1,2)  O11@M1[1,2)
  best_bound == objective，说明求解器证明了它自己的模型最优；
  这个实例的最优性还有一条独立证据：LB = 2 已经等于目标值（下界碰上界）。

== 3. fjsp_6x4_f2：18 道工序 ==
  fjsp_6x4_f2（seed 104）              tl =  2.0s
    status      = OPTIMAL
    objective   = 42.0
    best_bound  = 42.0   （proven）
    gap         = 0.0
    branches    = 622   conflicts = 25
    build_time  = 0.003032s   solve_time = 0.042215s   solver wall_time = 0.042s
    solver_objective - 独立重算 = 0.0
    LB（朴素下界，与求解器无关）= 33    horizon = 200
    排程 = J005_O0@M0[0,4)  J001_O0@M1[0,2)  J004_O0@M2[0,14)  J002_O0@M3[0,2)  J000_O0@M1[2,3)  J001_O1@M1[3,12)  J000_O1@M0[4,14)  J005_O1@M3[4,24)  J000_O2@M0[14,15)  J004_O1@M1[14,22)  J003_O0@M2[14,20)  J003_O1@M0[20,31)  J002_O1@M2[20,28)  J001_O2@M1[22,42)  J005_O2@M3[24,28)  J004_O2@M2[28,38)  J002_O2@M3[28,32)  J003_O2@M0[31,42)

== 4. 限时敏感性：fjsp_10x5_f3（seed 105，30 道工序）==
  fjsp_10x5_f3                       tl =  1.0s
    status      = FEASIBLE
    objective   = 57.0
    best_bound  = 42.0   （search_progress）
    gap         = 0.2631578947368421
    branches    = 4863   conflicts = 1040
    build_time  = 0.005476s   solve_time = 1.000587s   solver wall_time = 1.000s
    solver_objective - 独立重算 = 0.0
    LB（朴素下界，与求解器无关）= 51    horizon = 519
  fjsp_10x5_f3                       tl =  2.0s
    status      = FEASIBLE
    objective   = 56.0
    best_bound  = 42.0   （search_progress）
    gap         = 0.25
    branches    = 10722   conflicts = 2280
    build_time  = 0.005070s   solve_time = 2.002559s   solver wall_time = 2.002s
    solver_objective - 独立重算 = 0.0
    LB（朴素下界，与求解器无关）= 51    horizon = 519
  fjsp_10x5_f3                       tl = 10.0s
    status      = OPTIMAL
    objective   = 56.0
    best_bound  = 56.0   （proven）
    gap         = 0.0
    branches    = 21259   conflicts = 6254
    build_time  = 0.004766s   solve_time = 5.066198s   solver wall_time = 5.066s
    solver_objective - 独立重算 = 0.0
    LB（朴素下界，与求解器无关）= 51    horizon = 519
  1 秒与 2 秒都只能报 FEASIBLE：可行解已经找到，但没有证明它最优；
  此时 best_bound 是**搜索进度**，不是「问题的最优值」。
  gap = (objective - best_bound) / objective，落在 detail['bound_kind'] 里区分这两种界。

== 5. 拒绝模型覆盖不了的输入 ==
  目标不是 makespan：
    拒绝：fjsp_cpsat optimizes ('makespan',), got 'total_tardiness'; use a dedicated method for other objectives
  只建模、不求解的入口也一样拦：
    拒绝：fjsp_cpsat optimizes ('makespan',), got 'total_tardiness'; use a dedicated method for other objectives
  本模型的最小化对象就是 makespan，拿它去报别的目标名是偷换指标 ——
  宁可拒绝，也不要给出一个「目标名与实际最小化对象不一致」的结果。
  同一道闸门（require_plain_fjsp）还会挡下实例里本模块没有建模的约束：
  模型少了那几族变量，产出的排程一定过不了独立验证器，
  所以拒绝发生在建模之前，而不是让求解器去解一个残缺的模型。
  benchmark 会把这种行记成 FAILED 并带上原因，而不是记成「求解器给了非法解」。

== 6. 纪律复核 ==
  solver_objective_delta = 0.0（目标值由 fjsp_core 独立重算，不取求解器读数）
  num_search_workers = 1（固定 1 线程才可复现）
  model_stats = {'variables': 73, 'constraints': 71, 'optional_intervals': 36, 'operations': 18, 'horizon': 200}
  validate_schedule 报错数 = 0
  breakdown（只列非零分量）= {'cmax': 42.0, 'total_tardiness': 13.0}
```

输出里带 wall-clock 时间的行（`build_time` / `solve_time` / `solver wall_time`）
会随机器状态在小数末位抖动；`branches` / `conflicts` 这类求解器内部计数也可能在小范围内变动。
其余数字（状态、目标值、界、模型规模、`horizon`）可复现。

### 7.1 怎么读这段输出

**第 1 节的规模表要配第 5 节的手算一起读。** `tiny_2x2` 的 `17` 个变量拆开是
`4 + 4 + 8 + 1`；`17` 条约束拆开是 `8 + 4 + 2 + 2 + 1`，其中 `8` 条是区间定义。
`horizon` 那一列可以独立核对：`tiny_2x2` 是 `3 + 3 + 3 + 3 = 12`。

**第 2 节是「下界碰上界」的第二个例子。** `tiny_2x2` 的 `best_bound = 2.0` 与
`objective = 2.0` 相等、`gap = 0`、`bound_kind = proven`：求解器证明了它自己的模型最优。
而 Day 1 手算的 `LB = 2` 是**另一条**独立证据 —— 两条路径在这里互证。
`branches = 38`、`conflicts = 0` 说明这个证明几乎不需要搜索。

**第 3 节的 `42` 是今天最重要的一个数字。** 同一个实例上，Day 3 的三个启发式给出
`87 / 67 / 61`，而两维一起优化的模型在 `0.042` 秒、`622` 个分支上证明 `42` 是最优。
注意 `LB = 33`：这个朴素下界离 `42` 还有 `9`，所以**是 CP-SAT 自己**给出了「`42` 就是最优」
这个结论，而不是靠下界碰出来的。

**第 4 节是今天最值得反复看的一段。** 同一个实例、同一个模型，只改时间预算：

| `time_limit` | 状态 | 目标值 | `best_bound` | 界的性质 | `gap` | 分支 |
|---|---|---|---|---|---|---|
| `1.0s` | `FEASIBLE` | `57.0` | `42.0` | `search_progress` | `0.2632` | `4863` |
| `2.0s` | `FEASIBLE` | `56.0` | `42.0` | `search_progress` | `0.25` | `10722` |
| `10.0s` | `OPTIMAL` | `56.0` | `56.0` | `proven` | `0.0` | `21259` |

三行里 `best_bound` 从 `42.0` 变成 `56.0`，而目标值只从 `57` 变成 `56`。
这不是「界变差了」，而是**两个不同的量**：前两行的 `42.0` 是搜索爬到的界（还没证明完），
第三行的 `56.0` 是证明了的界。把它们混着读，会得出「解变好了但界变差了」这种自相矛盾的结论。
`detail['bound_kind']` 就是用来分开这两者的。

另外注意 `1.0s` 与 `2.0s` 的对比：预算翻倍，分支数从 `4863` 涨到 `10722`，
目标值只降了 `1` 分钟。**限时求解的收益不是线性的**：多给的预算买到的是搜索深度，
不是等比例的改进，所以每次改时间预算都要重新记录实测值，不能靠外推。

**第 5 节的输出只有两条，都是同一道闸门。** 一条走求解入口 `fjsp_cpsat`、
一条走只建模不求解的入口 `build_model` —— 两个入口都要拦，因为「模型能建出来」
不等于「可以拿它的解冒充问题的最优」。最后一段说的是另一类输入：
实例里有本模型没有建模的约束时，模型少了那几族变量，解一定过不了独立验证器，
所以拒绝必须发生在建模之前。

**第 6 节是三条纪律的读数。** `solver_objective_delta = 0.0`：目标值由 `fjsp_core`
独立重算，与求解器读数完全一致；`num_search_workers = 1`：单线程才可复现；
`validate_schedule` 报错数 `0`：求解器给出的排程过了那个不依赖 CP-SAT 的验证器。
`breakdown` 只列非零分量，`cmax 42` 与 `total_tardiness 13` 是这个实例的两个旁证。

---

## 8. 今日练习

1. **练习 1（手算）**：`assign_2x3` 是 `4` 道工序、每道 `3` 台合格机器。先自己手算它的
   变量数与约束数，再与第 7 节第 1 节的 `21` 与 `22` 对账（提示：`22` 里有多少条是区间定义？）。
2. **练习 2（推导）**：证明 `H = max_j r_j + Σ_o max_m p_om` 是任意可行排程的 `makespan` 上界。
   再举一个实例说明 `H` 可以比最优值大很多倍。
3. **练习 3（建模）**：如果把 `exactly_one` 换成 `at_most_one`，模型会多出什么可行解？
   那些解对应的「排程」在验证器眼里是什么？
4. **练习 4（编码）**：给 `build_model` 加一个参数 `extra_precedence: tuple[tuple[str, str], ...]`，
   为指定的工序对追加 `end(前) <= start(后)`。用 `('J000_O2', 'J001_O0')` 试一次，
   看最优值从 `42` 变成多少，并解释这个方向为什么只能让目标值变大或不变。
5. **练习 5（判读）**：某报告写「`fjsp_10x5_f3` 在 `1` 秒预算下 `best_bound = 42`，
   所以这个实例的最优值不超过 `42`」。这句话错了几处？

---

## 9. 验收清单

- [ ] 能写出四组约束各自的语义，并说明 `presence` 变量同时承担了哪两个角色。
- [ ] 能论证模型的可行解集合与实例的可行排程集合一一对应（两个方向都要说）。
- [ ] 能独立算出 `tiny_2x2` 的 `H = 12` 与 `fjsp_6x4_f2` 的 `H = 200`。
- [ ] 能说清「约束数 17 里有 8 条是区间定义」，并复述 `tiny_2x2` 的构成。
- [ ] 能说清 `OPTIMAL` 的准确含义，以及它成为问题最优性结论时必须补上的适用条件。
- [ ] 能区分 `bound_kind` 的 `proven` 与 `search_progress`，并用第 7 节第 4 节的三行数据举例。
- [ ] 能解释 `gap` 的两种读法，以及它在限时求解里为什么不能当质量指标。
- [ ] 能说出目标值为什么必须用 `evaluate` 重算，以及 `num_search_workers = 1` 换来了什么。
- [ ] 在项目目录下运行 `python examples/m3w2d4_cpsat.py`，输出与本日第 7 节一致（结构必须一致）。
- [ ] 在项目目录下运行 `python -m pytest tests/test_week2.py -q`，与本日相关的用例全部通过。

---

## 10. 自测题

- Q1：为什么每道工序要建 `k` 个可选区间，而不是建一个区间再附加一个「机器编号」变量？
- Q2：`start_o` 与 `end_o` 是整道工序共享的。如果给每台机器的区间各建一对独立的 `start`/`end`，会出什么问题？
- Q3：`H = max_j r_j + Σ_o max_m p_om`。这里的 `Σ_o max_m p_om` 用的是**最慢**机器，为什么不用最快？
- Q4：`tiny_2x2` 的 `H = 12`，而它的最优值是 `2`。变量域比最优值大，会不会让求解变慢？
- Q5：`stats()["constraints"] = 17` 而逻辑约束只有 `9` 条。为什么会差 `8`？
- Q6：`fjsp_6x4_f2` 上 CP-SAT 给 `42`、朴素下界给 `33`。能否说「CP-SAT 把下界从 33 提到了 42」？
- Q7：`1.0s` 与 `2.0s` 两行的 `best_bound` 都是 `42.0`。这说明 `2.0s` 的搜索白跑了吗？
- Q8：为什么 `AddNoOverlap` 能忽略 `presence` 为假的区间？如果它不能忽略，模型会怎样？
- Q9：把 `no_overlap` 删掉、只留 `exactly_one` 与 `precedence`，会得到什么类型的「排程」？验证器会报什么？
- Q10：本模型只支持 `makespan`。如果解完之后再用 `evaluate` 报 `total_tardiness`，为什么不行 —— 数值上不是能算出来吗？

### 参考答案

- A1：因为「机器编号」是一个离散的、取值互斥的变量，而 CP-SAT 表达「互斥取值」最紧的方式是
  文字变量（`presence`）。更实际的理由是：`AddNoOverlap` 只接受区间列表，
  每个区间必须自带「我在不在」。把区间建在「(工序, 机器)」这一对上，
  `ExactlyOne`（对工序）与 `NoOverlap`（对机器）两条约束就能各自作用在同一批区间上，
  不需要任何中间映射。
- A2：那就不再是「一道工序」了：`k` 台机器会有 `k` 个互不相干的区间，
  求解器可以同时点亮两个（两个区间各自与别的工序不重叠），工序在时间轴上出现两次。
  `ExactlyOne` 只能限制「几个区间为真」，限制不了「它们落在哪个时间」。
  共享 `start` / `end` 才是「一次只被加工一次」的表达。
- A3：因为那是**上界**，不是估计值：用最慢机器算出来的串行总时间，一定不小于任何真实排程的时间；
  用最快机器算出来的数字可能小于真实排程，那样变量的定义域就装不下可行解了，
  模型会莫名其妙地不可行。上界宁可松，不可错。
- A4：会有影响，但影响多大是一个**实测**问题，不是理论结论。定义域越宽，
  同一个值域上能传播出的结论越少，求解器需要探索的空间越大。
  本实例上 `38` 个分支就证完了，看不出代价；而 `fjsp_10x5_f3` 的 `H = 519`、最优值 `56`，
  限时预算下界只爬到 `42` —— 定义域的宽度在这里是不是瓶颈，需要单独做实验才能回答。
- A5：proto 把每个区间定义本身也记成一条约束（`interval` 字段）。`tiny_2x2` 有
  `4 x 2 = 8` 个可选区间，所以 `17 = 8 + 9`：`9` 条逻辑约束、`8` 条区间定义。
- A6：不能，这是两个不同来源的量。`33` 是**与求解器无关**的朴素下界（关键工序与总工作量两条），
  `42` 是 CP-SAT 在它自己的模型上证明的最优值。可以说的是「`42` 与 `33` 之间没有别的
  已证明结论」；「CP-SAT 提高了下界」这种说法把两条不同的推理混成了一条。
- A7：没有白跑。两行的 `best_bound` 相同，但目标值从 `57` 降到 `56`（可行解变好了一份），
  分支数也从 `4863` 涨到 `10722`（搜索推进了）。界没有改善不等于没有进展 ——
  这也是为什么必须把 `objective`、`best_bound`、`branches` 三个读数分开看。
- A8：因为 CP-SAT 的区间自带 `presence` 文字，未点亮的区间在传播里就等价于「不存在」。
  如果它不能忽略，那么所有「没被选中」的机器上也会出现这道工序的占用时间，
  于是任何两道合格机器相同的工序都会互相冲突 —— 模型会大面积不可行，
  或者被迫给未选中的区间安排时间，二者都不是我们要表达的意思。
- A9：会得到「同一道工序可以同时占用多台机器、也可以与别的工序在同一台机器上重叠」的
  松弛物。`exactly_one` 保证了每道工序恰好在一台机器上，但机器上的互斥没了，
  于是多道工序可以在同一台机器上同时加工。验证器会报机器重叠类错误，
  而且这类「解」的 `makespan` 通常远小于真最优 —— 正是「受限枚举冒充最优」的另一个版本。
- A10：数值上算得出来，但那不是同一条结论。`evaluate` 会给出一个**合法排程**的拖期值，
  可是模型里没有任何变量、约束或目标项与交货期有关：这个解是为 `makespan` 找出来的，
  它在拖期上的表现是「顺带的结果」。把它当成「本方法对拖期的优化结果」，
  等于用一个没优化过拖期的解去回答一个拖期问题。宁可拒绝，也不给出
  「目标名与实际优化对象不一致」的结果。

---

## 11. 今日一句话总结

> **FJSP 在 CP-SAT 里只有四组约束：每道工序一个共享的 `[start, end)`、逐机器一个可选区间、每道工序一条 `ExactlyOne`、每台机器一条 `NoOverlap`，再加工艺路线的 `end(前) <= start(后)`；`tiny_2x2` 上它用 `38` 个分支证明 `2` 是最优，`fjsp_6x4_f2` 上用 `622` 个分支证明 `42`，而同一个实例在 `1` 秒预算下只能报 `FEASIBLE` 并把 `best_bound = 42` 标成 `search_progress` —— 这两行不是「界变差了」，是同一个字段在承担两种不同的含义。**
