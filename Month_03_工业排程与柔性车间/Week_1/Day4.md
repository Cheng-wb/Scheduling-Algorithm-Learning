# Day 4：用 CP-SAT 求 JSP，并用与求解器无关的方式复核

> 当日主题：把 Job Shop 写成 CP-SAT 模型，然后**不信任求解器**地复核它给的答案
> 当日产出：**求解模块 `jsp.py` 中的 `jsp_cpsat`**（区间变量 + 每机器 `NoOverlap` + 每订单先后链）
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 写出 JSP 的 CP-SAT 模型：三类约束 + 一个 `makespan` 变量，并说清每类约束在表达什么。
2. 说明 `NewIntervalVar` 与 `NewOptionalIntervalVar` 的区别，以及「每道工序多台合格机器」时为什么必须用后者。
3. 说出 `AddNoOverlap` 与「两两不等」的区别：前者是区间不重叠的专门约束，比手工两两 `Add` 更紧。
4. 解释 `horizon` 的作用，以及它取小了会发生什么。
5. 知道 `OPTIMAL` / `FEASIBLE` / `INFEASIBLE` / `UNKNOWN` 各自的含义，以及墙钟预算对状态的影响。
6. 说出为什么「求解器说 OPTIMAL」之后仍然要跑 `validate_schedule`。
7. 说明求解器给出的 `best_bound` 只对「它正在最小化的那个目标」有意义，换目标必须不报。

---

## 2. 为什么第 4 天要引入 CP-SAT

Day 3 教会我们「怎么看懂一份排程」，但没有教怎么**造**一份好排程。到了 Job Shop，造排程这件事的难度是硬的：

**理论结论**：`Jm||Cmax`（Job Shop 的最小化 `makespan`）是 NP-hard 的，且是**强** NP-hard（Garey、Johnson 与 Sethi 1976）。也就是说，不存在已知的多项式时间精确算法；`Fm|prmu|Cmax`（`m >= 3`）同样 NP-hard。

于是工程上有三条路：

```text
1. 精确解法：分支定界、约束规划、整数规划 —— 小实例上能证明最优，大实例上只能给界
2. 启发式：优先级派工（Day 2 的 jsp_priority）—— 秒级出解，但没有任何最优性保证
3. 元启发式：禁忌搜索、模拟退火、遗传算法 —— 不属于今天的范围
```

今天走第 1 条路，并且**刻意把它放在启发式之后**：先有 Day 2 的启发式基线，再有今天的精确解法，才能回答「启发式到底差多少」这个问题。

**为什么选 CP-SAT 而不是自己写分支定界**：

1. **建模语言就是调度语言**。区间变量（`interval`）直接表示「一道工序占住一台机器的一段时间」，`AddNoOverlap` 直接表示「同一台机器上不许重叠」。用纯整数规划要写大 M 约束（`start_j >= end_i - M(1 - y_ij)`），又慢又容易写错。
2. **它同时是 CP 与 SAT/LP 的混合体**。CP-SAT 会用 SAT 求解器处理布尔结构与冲突学习，用 LP 松弛提供下界，还带专门的调度传播器（precedence、NoOverlap 的边查找）。
3. **它给的是声明式的界**。求解器能报「当前最好解」与「可证明的下界」，这正是结果字段 `objective` / `best_bound` 的来源。

**必须写在前面的警告**：求解器说 `OPTIMAL`，意思是「在我的模型里、以我最小化的那个目标、在给定预算内，我证明了没有更好的解」。它**不**意味着：

- 排程满足领域约束（模型可能漏写了一类约束，或者我把工时表填错了）；
- 目标值算得对（我用的是 `AddMaxEquality` 汇总完工时刻，如果汇总写错，「最优」是最优于一个错的目标）；
- 这个解对别的目标也好（见第 5 节）。

所以今天的产出有一半是求解器，另一半是**与求解器完全无关的复核链条**：`validate_schedule`（独立校验可行性）、`makespan`（独立重算目标值）、`check_critical_path`（独立用 Day 3 的图论方法复核 `最长路径 = makespan`）。

---

## 3. CP-SAT 的 JSP 模型

**决策变量**（对每道工序 `o`、每台合格机器 `m`）：

```text
布尔变量 y[o][m]      : 工序 o 是否排在机器 m 上（每道工序恰好选一台）
区间变量 I[o][m]      : 在 m 上的占用区间（新式可选区间：仅当 y[o][m] 为真时出现）
开始/完工变量 s[o], e[o]: 工序 o 的开工与完工时刻（与所选区间绑定）
makespan 变量 M        : 所有 e[o] 的最大值
```

**三类约束 + 一条目标**：

```text
(1) 区间长度     I[o][m].size == 该工序在机器 m 上的工时
                 —— 工时表是输入，不是决策；柔性只体现在「选哪台机器」
(2) 机器不重叠   对每台机器 m：AddNoOverlap([I[o][m] for 所有 o])
                 —— 可选区间会自动把「没选 m 的工序」排除在外
(3) 订单先后链   对每订单的相邻工序：s[下一道] >= e[上一道]
                 —— 工艺路线是硬约束，任何解都不能违反
(4) 目标         Minimize(M)，其中 M = max over o of e[o]（AddMaxEquality）
```

**为什么用「可选区间 + `ExactlyOne`」而不是「先选机器再建区间」**：前者只建一份模型就能表达柔性（工序有 `k` 台合格机器就 `k` 个可选区间，`ExactlyOne` 保证恰好选一个），后者要么枚举机器组合、要么改一次结构建一次模型。

**`horizon`**：所有区间变量的时间上界。取小了会**切掉可行解甚至最优解**（求解器可能报 `INFEASIBLE`，而实例明明有解）—— 这是最隐蔽的建模错误之一：模型没有错，只是搜索空间被人为截断了。本仓库的做法是把 `horizon` 记进 `detail`，并用手算的下界与简单构造（例如「按订单串行排」这种显然合法的排程）验证它足够大。

**「每道工序恰好选一台机器」在经典 JSP 上退化**：手写的标准格式实例每道工序只有一台合格机器，于是 `y` 只有一个分量、恒为真，模型退化成「纯 JSP」。这就是 `tiny3x3` 输出里「机器选择变量数 = 9，每道工序一个布尔向量」的含义。

**建模代码的形状**（[jsp.py](../../projects/03_industrial_fjsp/fjsp_shop/jsp.py) 里 `build_jsp_model` 的骨架，去掉细节）：

```python
model = cp_model.CpModel()
starts, ends = {}, {}
intervals_by_machine = {machine.id: [] for machine in instance.machines}

for operation in instance.operations:
    choices = []
    for machine_id, minutes in operation.machine_times:      # 合格机器列表
        start = model.NewIntVar(0, horizon, f"start_{operation.id}_{machine_id}")
        end = model.NewIntVar(0, horizon, f"end_{operation.id}_{machine_id}")
        # 可选区间：只有被选中的那台机器上，这段区间才「存在」
        interval = model.NewOptionalIntervalVar(start, minutes, end, flag, name)
        choices.append(flag)
        intervals_by_machine[machine_id].append(interval)
    model.AddExactlyOne(choices)                              # 恰好选一台机器

for machine_id, intervals in intervals_by_machine.items():
    model.AddNoOverlap(intervals)                             # (2) 机器不重叠

for job in instance.jobs:
    for before, after in zip(job.operation_ids, job.operation_ids[1:]):
        model.Add(starts[after] >= ends[before])              # (3) 订单先后链

makespan_var = model.NewIntVar(0, horizon, "makespan")
model.AddMaxEquality(makespan_var, [ends[op.id] for op in instance.operations])
model.Minimize(makespan_var)                                  # (4) 目标
```

这段骨架里每一行都能对上前面列的「三类约束 + 一条目标」。**注意 `AddMaxEquality`**：它是「`makespan` 变量等于所有完工时刻的最大值」的**等价**约束（双向），不是单向上界。写成单向的 `model.Add(makespan_var >= end)` 会得到一个偏大的目标，求解器会「优化」一个与真实 `makespan` 无关的量。

**想验证自己真的读懂了**：把 `AddMaxEquality` 改成单向下界，跑一次 `tiny3x3`，看目标值变成什么，再看 `validate_schedule` 与 `makespan()` 复核是否还能通过（第 8 节练习 3 与练习 4 是这个方向）。

---

## 4. 手算下界：`max(最大机器负载, 最长订单工时)`

**理论结论**：对「一道工序只有一台机器可选」的经典 JSP，以下两个量都是 `Cmax` 的**合法下界**：

```text
L1 = max over 机器 m of (m 上所有工序工时之和)       —— 机器不能并行干活
L2 = max over 订单 j of (j 的所有工序工时之和)       —— 订单内部必须串行
LB = max(L1, L2)
```

理由：任何排程里，同一台机器上的工序两两不重叠，所以该机器的完工时刻至少是它的总负载 `L1`；同一订单的工序必须串行，所以该订单的完工时刻至少是它的总工时 `L2`。`makespan` 是「所有机器、所有订单都做完」，因此不小于两者。

**关键的限制条件**：这两个式子**只对经典 JSP 成立**。在柔性实例（一道工序有多台合格机器）里，「把工序摊到哪台机器」本身是决策的一部分，`L1` 不再是下界 —— 把负载从一台机器挪到另一台就能改变它，下界必须换成「所有工序的工时之和 ÷ 机器台数」这类更弱的式子。

本仓库的处理是**直接拒绝**：`jsp_lower_bounds` 一旦发现某道工序有多个合格机器就抛 `ValueError`，而不是给出一个看似合理其实不成立的数。这条纪律与 `best_bound` 的纪律是同一条：**界必须是可证明的，否则宁可不报。**

`LB` 的用处：如果求解器给出的目标值**恰好等于** `LB`，那么不需要看求解器的状态也能断定这个值就是最优的 —— 因为存在下界 `LB` 与其相等的可行解。这是「用下界证明最优」的最简单形式：**不需要任何求解器，两个手算的量就能证明最优性。**

---

## 5. 状态、界、gap 三件事的纪律

**状态**（`cp_status` 与 `ShopResult.status` 的对应关系）：

| CP-SAT 状态 | 放入 `ShopResult.status` | 含义 |
|---|---|---|
| `OPTIMAL` | `OPTIMAL` | 证明了这个目标值不可能被改进 |
| `FEASIBLE` | `FEASIBLE` | 找到可行解，但没证到最优（通常是预算用尽） |
| `INFEASIBLE` | `INFEASIBLE` | 模型在给定 `horizon` 内无解 |
| `UNKNOWN` | `UNKNOWN` | 连可行解都没有找到（预算太小或模型病态） |
| `MODEL_INVALID` | `MODEL_INVALID` | 模型本身不合法（例如变量越界），不是实例的问题 |

**界**：`best_bound` 只对**正在最小化的那个目标**有意义。本仓库的实现是：

```text
目标 == makespan        -> best_bound = 求解器报的界，bound_kind = solver_objective_bound
目标 != makespan        -> best_bound = None，   bound_kind = not_reported_for_this_objective
```

后半句是重点：如果我用 `total_tardiness` 为目标求解，求解器报的界是 `total_tardiness` 的下界，把它填进「`makespan` 的界」这一栏就是假陈述。Week 1 的选择是**宁可不报**。

**gap**：`(objective - best_bound) / |objective|`。只有同时有目标值与界时才存在；`best_bound = None` 时 `gap` 也是 `None`（而不是 0）。把「没有界」显示成 0 会把「完全不知道」伪装成「已证最优」。

**三类结果在业务上的读法**：

| 情况 | 状态 | 有什么 | 该做什么 |
|---|---|---|---|
| 证到最优 | `OPTIMAL` | 最优值 + 界（两者相等） | 直接采信，但仍要过复核链条 |
| 截断但有解 | `FEASIBLE` | 可行排程 + 界 + `gap > 0` | 可用作基线；想更好就加预算或换方法 |
| 截断且无解 | `UNKNOWN` | 什么都没有 | 不能当作「无解」；加预算重试或改模型 |
| 确实无解 | `INFEASIBLE` | 无排程 | 先怀疑 `horizon` 与建模，再怀疑实例本身 |

**`UNKNOWN` 是最容易被误读的一格**：它既不是「解很差」，也不是「实例无解」，而是「搜索在预算内连第一个可行解都没构造出来」。把 `UNKNOWN` 当成 0 分处理、或者当成「不一致」处理，都是错的。本仓库在结果对象里保留这个状态原样，不做平滑。

---

## 6. 复核链条：为什么不信求解器

四道独立检查，每一道都能单独抓住一类错误：

```text
1. build_jsp_model 返回的 built 里带 interval_count，先对一遍「区间数 = 工序数」
2. validate_schedule(instance, schedule)   —— 与 CP-SAT 无关，逐条查机器不重叠、订单先后、工时匹配
3. makespan(instance, schedule)            —— 独立重算目标值，与 result.objective 比对
4. check_critical_path(instance, schedule) —— 用 Day 3 的析取图复核「最长路径 = makespan」
```

第 4 条是今天特有的：它不仅查可行性，还查「这份排程是不是左移的」。`jsp_cpsat` 在返回前会做左移归一化（把每道工序挪到当前顺序下的最早可行时刻），所以第 4 条能通过；如果哪天左移被跳过（实例上存在「左移就会破坏」的别的条件），这个检查会**抛错而不是硬算**，正好把「分析的前提不成立」这件事暴露出来。

**这些检查各自能抓住什么**：

| 检查 | 能抓住 |
|---|---|
| `interval_count` 核对 | 建模型时漏建/多建工序区间 |
| `validate_schedule` | 机器重叠、工艺顺序颠倒、工时与工序不匹配、机器不可用 |
| `makespan` 重算 | `AddMaxEquality` 写错、目标值取错字段 |
| `check_critical_path` | 解没有左移、`horizon` 截断导致的畸形解 |

**模型的五个组成部分，以及各自写错时的症状**（把「症状」和「上面哪条检查」对上，是今天最实用的一件事）：

| 模型部件 | 作用 | 写错时的症状 | 被哪条检查抓住 |
|---|---|---|---|
| `NewIntervalVar`（每道工序一个） | 给每道工序一个「起点 + 时长 = 终点」的区间 | 区间数少于工序数 | `interval_count` 核对 |
| 可选区间 + `AddExactlyOne`（多台合格机器时） | 每道工序**恰好**选一台机器 | 一台都不选（漏排）或选了多台 | `validate_schedule` |
| `AddNoOverlap`（每台机器一个） | 同机器上区间不重叠 | 两道工序在同一台机器上重叠 | `validate_schedule` |
| 前驱链（同订单相邻工序） | 工艺顺序不能颠倒 | 后道工序排到前道之前 | `validate_schedule` |
| `AddMaxEquality`（makespan 变量） | 目标值 = 所有工序完工时刻的最大值 | 目标值比真实最大值小（只取了部分区间） | `makespan` 重算 |

**逐条对应的意义**：这五行说明「复核链条」不是四道泛泛的保险，而是**每一道都指向一类具体的建模错误**。反过来说，如果某条检查在任何输入下都不会失败，它就只是仪式 —— 本周保留的四条，每一条都能指出「它防的是哪一种错」。

还有一层：**这张表是从「错误」往「检查」倒着读的**。写模型时想的是「我要加哪条约束」，写完之后该反过来问「这条约束如果写错，表现成什么样、被哪条检查抓住」。这张表的五行就是对这个问题的回答 —— 答不出来，说明那条检查只是习惯，不是核对。

**`horizon` 是另一个隐藏前提**：每道工序的 `start` / `end` 变量与 `makespan` 变量的上界都是 `_horizon(instance)`，它的定义是「最大释放时间 + 每道工序在**最慢**那台机器上的工时之和」。

为什么它是**安全上界**（截断它不会丢掉最优解）：任取一个可行排程，看任意订单 `j`，它的完工时刻不会超过「自己的释放时间 + 自己所有工序的工时之和」；后者又不超过「最大释放时间 + 全部工序取最慢机器时的工时之和」，也就是 `horizon`。所以**最优 makespan 一定不超过 `horizon`**，上界不紧也无所谓。

反过来，域里确实存在「故意空等很久」的可行排程，它的 makespan 会超过 `horizon` —— 那么模型里根本表示不出它。**这两种情形的区分很重要**：按 `_horizon()` 这个式子算出来的截断，丢掉的只是「明显更差的解」，不是最优解。**注意这里有一个前提**：安全的是这个式子。第 3 节说过，一旦人为把它取小（比如把 `tiny3x3` 的 18 改成 8），被切掉的就可能连最优解一起带走，求解器还会报 `INFEASIBLE` —— 那时候错的不是实例，是上界。**先说清「为什么这个上界安全」，再接受它，顺序不能反。**

---

## 7. 实验：`m3w1d4_jsp_cpsat.py`

脚本链接：[m3w1d4_jsp_cpsat.py](../../projects/03_industrial_fjsp/examples/m3w1d4_jsp_cpsat.py)。

在项目目录下运行：

```bash
cd projects/03_industrial_fjsp
python examples/m3w1d4_jsp_cpsat.py
```

第 1 节（模型结构）的实际输出：

```text
变量数 = 28，约束数 = 37
horizon = 18（时间上界，全部区间变量都落在 [0, horizon] 内）
interval_count = 9（= 工序数）
机器选择变量数 = 9（每道工序一个布尔向量，本实例每道工序只有一台合格机器）
开始时刻变量数 = 9，完工时刻变量数 = 9
makespan 变量 = makespan

约束的三个来源：
  (1) 每道工序一个区间：长度 = 该工序在所选机器上的工时
  (2) 每台机器一条 AddNoOverlap：同机器上的区间两两不重叠
  (3) 每个订单一条先后链：start[k+1] >= end[k]
  目标：Minimize(makespan)，makespan = 所有工序完工时刻的最大值
```

`interval_count = 9` 与实例的 9 道工序一致 —— 这是第 6 节复核链条的第 1 条。

第 2 节（手算实例，最优值必须是 7）：

```text
--- tiny3x3 / jsp_cpsat ---
status      = OPTIMAL
objective   = 7.0
best_bound  = 7.0
gap         = 0.0
solve_time  = 0.007 s
breakdown   = {'cmax': 7.0, 'total_tardiness': 0.0, 'setup': 0.0}
cp_status   = OPTIMAL
cp_objective= 7.0，与独立算出的目标值一致 = True
horizon     = 18，interval_count = 9
left_shifted= True
validate_schedule 通过；makespan() 复核 = 7
check_critical_path = 7（= makespan，说明返回的解已左移归一化）

下界复核：最大机器负载 = 7，最长订单工时 = 6，取大 = 7（手算：M0 负载 5、M1 负载 7、M2 负载 6）
求解器给出的最优值 = 7.0，与下界相等说明达到了下界：True

机器顺序：
  M0：J0_O0 -> J2_O1 -> J1_O2
  M1：J1_O0 -> J0_O1 -> J2_O2
  M2：J2_O0 -> J1_O1 -> J0_O2
```

**这是今天最重要的一个交叉验证**：三条互不相干的推理给出同一个数 7。

```text
(1) 手算排程（Day 3 的 HAND_MADE，不经过任何算法） -> makespan 7
(2) 求解器（CP-SAT，OPTIMAL）                      -> 7
(3) 手算下界 max(机器负载 7, 订单工时 6)            -> 7，又由 (1) 知它可达 -> 7 必是最优
```

另外三台机器上的顺序与 Day 3 手算排程**逐字相同**（`M0：J0_O0 -> J2_O1 -> J1_O2` 等），说明这两天的两套独立代码（图分析 vs 求解器）落到同一个解上。

第 3 节（稍大实例 `jsp_6x4`）：

```text
订单 6 个，机器 4 台，工序 18 道，每道工序只有一台合格机器
下界：最大机器负载 = 67，最长订单工时 = 44，两者取大 = 67
--- jsp_6x4 / jsp_cpsat ---
status      = OPTIMAL
objective   = 67.0
best_bound  = 67.0
gap         = 0.0
solve_time  = 0.007 s
breakdown   = {'cmax': 67.0, 'total_tardiness': 29.0, 'setup': 0.0}
cp_status   = OPTIMAL
cp_objective= 67.0，与独立算出的目标值一致 = True
horizon     = 203，interval_count = 18
left_shifted= True
validate_schedule 通过；makespan() 复核 = 67
check_critical_path = 67（= makespan，说明返回的解已左移归一化）

最优值 67.0 与下界 67 的差 = 0.0（下界不一定可达，差非负并不说明求解有问题）
同日对照：jsp_priority(mwr) = 71.0，best_bound = None（启发式不报界）
```

三个观察：

1. **最优值 67 = 下界 67**，所以 67 是这套实例上的最优 `makespan`，这件事不依赖求解器的状态字段。这也说明 `LB` 虽然是初等下界，有时却恰好紧。
2. `breakdown` 里的 `total_tardiness = 29.0`：目标是最小化 `makespan`，但排程同样有了 29 的总拖期。**「`makespan` 最优」不等于「拖期也最优」** —— 这只是以 `makespan` 为目标的一个最优解，不能据此说它是最小拖期的解。请对照第 5 节的纪律理解这一条。
3. 同一天同一个实例上 `jsp_priority(mwr)` 给出 71，`best_bound = None`。启发式不报界这条纪律在这里具体化了：它确实没报，所以「与最优的差 4」这个比较是拿 `jsp_cpsat` 的结果当参照算出来的，而不是启发式自己声明了界。

第 4 节（时间预算决定状态）—— 柔性实例 `fjsp_10x5_f3`，每道工序有 3 台合格机器：

```text
实例：fjsp_10x5_f3（seed 105，10 订单 x 5 机器，每道工序有 3 台合格机器）
configs/month3.json 对这个方法登记了两个敏感性预算：tl_5 = 5 秒、tl_30 = 30 秒

预算 1.0 秒：status = FEASIBLE，objective = 57.0，best_bound = 42.0，gap = 0.2631578947368421
          cp_wall_time = 1.000 s
          排程通过独立验证；makespan() = 57

预算 10.0 秒：status = OPTIMAL，objective = 56.0，best_bound = 56.0，gap = 0.0
          cp_wall_time = 4.179 s
          排程通过独立验证；makespan() = 56

结论：FEASIBLE 表示「找到可行解但没证到最优」，此时 best_bound 才有意义；
      预算是墙钟时间，所以同一预算下各次的搜索规模可能不同，但本实例上目标值与界在多次运行中保持稳定。
```

怎么读这段：

1. **同一个实例、同一个模型，预算不同地位不同**。1 秒只给到 `FEASIBLE`（目标值 57、界 42、`gap` 0.263），10 秒证到 `OPTIMAL`（56）。注意 4.179 秒 < 10 秒：求解器证完就停了，不会把预算耗尽。
2. `gap = 0.2631578947368421 = (57 - 42) / 57`，是「还没证到的相对距离」，与 56 的差距无关。
3. **两次 `validate_schedule` 都通过**，`makespan()` 分别为 57 与 56 —— 被截断的那次给出的排程同样是**可行**的，只是不够好。`FEASIBLE` 不是「可疑」，是「可行但未证最优」。
4. 最后那句「目标值与界在多次运行中保持稳定」是**实测得到的观察**，不是普遍规律：我在同一台机器上重复跑了 4 次 1 秒预算，57 / 42 / 0.2632 三个数每次都一样，而变化的是分支计数。墙钟预算下这种稳定性没有保证，所以本仓库把 `cp_wall_time` 也记进 `detail`。**说成「每次跑都一样」就是过度推广了。**

第 5 节（界的纪律）：

```text
objective = makespan         status = OPTIMAL   objective = 7.0 best_bound = 7.0 bound_kind = solver_objective_bound
objective = total_tardiness  status = OPTIMAL   objective = 0.0 best_bound = None bound_kind = not_reported_for_this_objective

同一个排程的 breakdown 分量（cmax / total_tardiness / setup）都照实记录：
  breakdown = {'cmax': 7.0, 'total_tardiness': 0.0, 'setup': 0.0}
```

**读这一节时要注意一个陷阱**：`tiny3x3` 是从手写的标准格式文件读进来的，而标准格式里**没有交期字段** —— `load_standard_jsp` 构造的 `Job` 里 `due_date = None`。按 `total_tardiness` 的定义「没有交期的订单不参与」，这个实例上任何排程的拖期都是 0，所以第二行的 `objective = 0.0` 是**退化结果**，不代表「求解器找到了拖期更优的排程」。这一行想说的是**界的行为**：目标换成 `total_tardiness` 之后，`best_bound` 变成 `None`、`bound_kind` 变成 `not_reported_for_this_objective` —— 求解器确实报了一个数，但那个数是拖期的下界，不是 `makespan` 的；本仓库选择不把它填进 `best_bound`。

真正有交期的实例（例如 `generate_instance` 生成的 `jsp_6x4`，`due_factor = 1.6`）上拖期才是有内容的量，第 3 节 `breakdown` 里那个 29 就是它。

脚本最后的当日结论：

```text
1. CP-SAT 的 JSP 模型只有三类约束：区间长度、机器 NoOverlap、订单先后链。
2. tiny3x3 上求解器给出的 7 与手算最优值一致 —— 三个互相独立的推理得到同一个数。
3. 求解器给的下界只对「它正在最小化的那个目标」有意义，换目标必须不报。
4. OPTIMAL 不等于可行：排程仍然要过独立的 validate_schedule 与关键路径复核。
```

---

## 8. 今日练习

1. **练习 1（建模）**：把第 3 节的 `(3) 订单先后链` 从「相邻工序」改成「同一订单所有工序两两先后约束」（`O(k^2)` 条），说明为什么这在语义上等价、在效率上更差，并想清楚哪一种在 CP-SAT 里传播更强。
2. **练习 2（手算）**：对 `tests/data/tiny3x3.jsp` 手算 `L1`（三台机器的负载）与 `L2`（三个订单的工时），验证 `LB = 7`；再想一个例子说明 `LB` 可以严格小于真正的最优 `Cmax`。
3. **练习 3（复核）**：在 `tiny3x3` 上把 `horizon` 人为改成 8（小于 18），看看求解器给出什么状态。解释这个状态下 `INFEASIBLE` 的含义 —— 是实例不可行，还是模型被人为截断了？
4. **练习 4（界）**：写一段代码，在 `jsp_6x4` 上分别以 `makespan` 与 `total_tardiness` 为目标求解，记录两个 `breakdown`，并说明为什么「两个目标各自的最优解」通常不是同一个排程。
5. **练习 5（工程）**：给 `jsp_cpsat` 增加一个 `num_search_workers` 参数并验证：设为 0（自动并行）时，同一实例同一预算的两次运行是否给出同一个解。用这个实验说明「确定性从哪来」。

---

## 9. 验收清单

- [ ] 能写出 JSP 的 CP-SAT 模型，说出三类约束各在表达什么。
- [ ] 能说清 `NewIntervalVar` 与 `NewOptionalIntervalVar` 的区别，以及柔性实例为什么必须用后者。
- [ ] 知道 `horizon` 取小了会切掉可行解，且求解器会报 `INFEASIBLE` 而不是报「模型错了」。
- [ ] 能手算 `LB = max(最大机器负载, 最长订单工时)`，并说明它只对经典 JSP 成立。
- [ ] 知道「目标值 == 下界」本身就是最优性证明，不依赖求解器的状态字段。
- [ ] 能列出 `OPTIMAL` / `FEASIBLE` / `INFEASIBLE` / `UNKNOWN` / `MODEL_INVALID` 的含义。
- [ ] 知道 `best_bound` 只对正在最小化的目标有意义，换目标时必须不报。
- [ ] 能说出四种复核检查各能抓住哪一类错误。
- [ ] 知道 `jsp_cpsat` 返回前做了左移归一化，左移被跳过时会在 `detail` 里记原因。
- [ ] `python examples/m3w1d4_jsp_cpsat.py` 退出码 0，输出与第 7 节一致。
- [ ] `python -m pytest -q tests/test_week1.py` 全绿（含 CP-SAT 在 `tiny3x3` 上等于手算最优值的用例）。

---

## 10. 自测题

- Q1：CP-SAT 的 JSP 模型里，哪一类约束是「硬约束」、哪一类是「排程决策」？
- Q2：`AddNoOverlap` 为什么比「任意两道工序两两不重叠」的布尔约束更好？
- Q3：柔性实例里为什么不能继续用 `L1 = 最大机器负载` 当下界？
- Q4：`horizon` 取小了会出现什么现象？它算不算建模错误？
- Q5：求解器报 `OPTIMAL` 之后，为什么还要跑 `validate_schedule`？
- Q6：`best_bound = None` 与 `best_bound = 0` 有什么区别？
- Q7：以 `total_tardiness` 为目标求解时，为什么本仓库不把求解器报的界填进 `best_bound`？
- Q8：为什么 `tiny3x3` 上「以拖期为目标」得到 0 是退化结果？
- Q9：同一实例同预算跑两次，为什么目标值可能不同？本仓库怎么处理这件事？
- Q10：`check_critical_path` 在什么情况下会拒绝一份求解器给的 OPTIMAL 解？

### 参考答案

- A1：区间长度（工时表）与订单先后链是硬约束，它们定义了「什么叫做一份合法排程」；机器上的顺序是决策，模型里由「哪些区间被选中、以及 `AddNoOverlap` 怎么给它们定序」隐式表达。注意 `AddNoOverlap` 自己不产生顺序，顺序是求解器在搜索中确定的。
- A2：`AddNoOverlap` 是调度专用的全局约束，CP-SAT 内部用「边查找」算法在区间之间传播（把所有区间按最早开始/最晚结束排序后筛出真正可能冲突的对），而不是展开成 `O(k^2)` 条布尔约束。区间数大时差距明显，而且全局约束的传播更强、更早发现不可行。
- A3：因为 `L1` 的前提是「哪道工序在哪台机器上是固定的」。柔性实例里这是决策的一部分，把工序挪到别的机器就能改变该机器的负载，所以 `L1` 不再是任何合法解都必须跨过的高度。
- A4：可行解被切掉，求解器可能报 `INFEASIBLE`，或者报一个比真实最优更差的目标值。这是建模错误（模型的搜索空间与实例的可行域不一致），但模型本身语法合法，所以 `MODEL_INVALID` 不会出现 —— 正因为它不报错，才更隐蔽。
- A5：`OPTIMAL` 只是「在模型内部最优」。模型可能漏写一类约束（例如两道本该互斥的工序被写成了可以并行），工时表可能填错，`AddMaxEquality` 可能写错。`validate_schedule` 不看模型，只看实例与排程，能抓住这些模型侧的错误。Day 3 的与今天的实验都是这个思路：**两个独立实现互相检查**。
- A6：`None` 表示「本仓库选择不报这个界」（没有可证明的界，或目标不是它）；`0` 表示「可证明的界是 0」。这两件事完全不同：前者是「不知道」，后者是「知道得很弱但确实是 0」。把 `None` 显示成 0 会把「不知道」伪装成「有一个界」。
- A7：因为求解器报的界是**它正在最小化的那个目标**的下界。以拖期为目标时，报出来的数是拖期的下界；把它填进 `best_bound`（本仓库语义是「目标的界」并在目标为 `makespan` 时与它对应）就是一句假陈述。Week 1 的做法是：目标不是 `makespan` 时 `best_bound = None`，`bound_kind` 记为 `not_reported_for_this_objective`。
- A8：因为 `tiny3x3` 来自标准格式文件，而标准格式里没有交期字段，`load_standard_jsp` 构造的订单 `due_date = None`。按照 `total_tardiness` 的定义「没有交期的订单不参与」，这个实例上任何排程的拖期都是 0，与排程好坏无关。
- A9：预算是**墙钟时间**（`cp_wall_time` 记录它），同样的秒数在不同负载的机器上能搜的节点数不同；并行搜索（`num_search_workers > 1`）还会引入线程调度带来的不确定性。本仓库的做法是固定 `num_search_workers = 1` 与 `random_seed`，并把 `cp_wall_time` 记进 `detail`，让「同一预算下结果可能不同」这件事在数据里可见，而不是假装它不存在。
- A10：当返回的解不满足左移性时 —— 即排程里存在被人为推迟过的工序（`left_shifted = False`，`slack` 非空），此时「最长路径 = `makespan`」的前提不成立，函数会抛 `ValueError` 并在消息里列出被推迟的工序，而不是返回一个错的长度。

---

## 11. 今日一句话总结

> **CP-SAT 把「找最优排程」变成「写对三类约束」，但把「这个答案可不可信」留给了解题人 —— `OPTIMAL` 只是求解器对模型的承诺，不是对领域的承诺。**
