# Day 1：domain、传播、IntervalVar、OptionalIntervalVar 与整数时间缩放

> 当日主题：把 CP-SAT 的五个基本零件摆出来看清——域是集合、区间是三元组、传播沿约束收紧域、可选区间多一个布尔、时间必须是整数
> 当日产出：[cpsat_models.py](../../projects/02_optimization_models/opt_models/cpsat_models.py) 的建模层 + [m2w3d1_intervals.py](../../projects/02_optimization_models/examples/m2w3d1_intervals.py) 的实测输出
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 说出 CP-SAT 的 `domain` 与 MILP 的整数变量域在表达能力上的差别，并写出一个「MILP 写不出来、CP 写得出来」的域。
2. 说明 `IntervalVar` 由哪三个量定义，并解释为什么它不出现在 `tightened_variables` 里。
3. 对一个三道工序的优先级链，手算传播后每道工序 `start` 的上界，并说明传播为什么是「沿约束的连接走」。
4. 说明 `AddNoOverlap` 对同一个三区间模型能给出多紧的界，并解释它比链式传播弱在哪里。
5. 说出 `OptionalIntervalVar` 比 `IntervalVar` 多出的决策是什么，以及 `AddExactlyOne` 在这套模型里承担的角色。
6. 解释为什么 CP-SAT 的时间变量必须是整数，以及 `time_scale` 如何在不改变最优排程的前提下满足这个要求。
7. 用一个实际实验说明：求解器回填的域是**有效但不一定最紧**的松弛区间，不能当作传播不动点引用。
8. 读懂 `build_cpsat_model` 的每条约束分别对应调度语义里的哪一句话。

---

## 2. 为什么 Day 1 要先看零件

Month 1 建起来的流水线是这样的：

```text
JSON → Parser → Instance → Validator → 可信输入
                                     ↓
                        Rules → Schedule → Objective → 数字
```

`Rules` 那一层全是启发式，它给你一个解，但**不给你「离最优还差多少」**。Month 2 要补这一环，而 Month 2 的第一周（LP）和第二周（MILP）都把问题写成了「变量 + 线性约束 + 线性目标」这一种形状。Week 3 换一种形状：

```text
M2 W1  LP    变量是实数，约束是超平面，解一定在极点上
M2 W2  MILP  变量带整数限制，用 LP 松弛 + 分支定界求解
M2 W3  CP    变量是**集合**，约束保留结构（区间、互斥、容量），用传播 + 搜索求解  ← 本周
```

第三种形状不是「MILP 的另一种写法」，它的底层数据结构就不一样。今天就做一件事：**把这套结构拆开，一个个零件看清楚**，不要在这时候就去追最优值。

今天不追求最优值，追求的是「看到 CP-SAT 给你的东西时知道它是什么」。

---

## 3. 概念：domain 是集合，IntervalVar 是三元组

### 3.1 定义（domain）

**定义（CP 变量的域）**：CP 变量的取值集合称为它的**域**（domain）。域是若干整数区间的并，可以带上「洞」。

```text
MILP 的整数变量：  x ∈ { lb, lb+1, ..., ub }        域只能是一个连续区间
CP 的变量：        x ∈ [0,3] U [10,12] U {20}      域是任意整数集合
```

这个差别不是装饰性的。调度里到处都是「带洞」的域：

| 场景 | 域 | MILP 能直接写吗 |
|---|---|---|
| 只在某些时段可加工（班次表） | `[480,720] U [840,1080]` | 不能，要拆成额外布尔变量 |
| 只在几台指定机器上加工 | 机器索引集合，例如 `{2, 5, 7}` | 要写成一组指派变量 |
| 两个候选开工时刻 | `{0, 15}` | 要写成 `15 * b`（b 是布尔） |

所以第一句要记住的话是：**CP 把「域」当一等公民，MILP 把「域」当成上下界**。第 7 节的实测里，`Domain.FromIntervals([[0,3],[10,12],[20,20]])` 得到的域打印出来就是 `[0,3][10,12][20]`，中间的两个洞是真实存在的，不是表示技巧。

### 3.2 定义（IntervalVar）

**定义（区间变量）**：`IntervalVar` 是一个三元组 `(start, size, end)`，它强制

```text
end = start + size
```

`size` 在建模时给定（可以是常数，也可以是一个变量）。三个量里有两个是独立的，第三个由关系式确定。

`IntervalVar` 本身是**派生对象**，不进 `tightened_variables`。这一点在第一次读输出时很容易搞错：第 7 节的「第 2 节」小节里，`demo_start` 与 `demo_end` 都是普通整数变量，但区间 `demo_iv` 不打印——它没有自己的域，它的全部含义就是那条 `end = start + size` 的关系。

三条与调度语义的对应关系要背下来：

```text
start            工序开始时刻
size             加工时长
end              完工时刻，恒等于 start + size
```

### 3.3 定义（OptionalIntervalVar）

**定义（可选区间）**：`OptionalIntervalVar(start, size, end, presence)` 比 `IntervalVar` 多一个布尔变量 `presence`：

```text
presence = 1  区间「存在」：占用 (start, end) 这段时间
presence = 0  区间「不存在」：不占用任何时间，start / end 的取值不再有调度含义
```

这是 CP 建模里最重要的一次「升维」：**「要不要做这件事」本身成为一个决策变量**。MILP 也能表达它（用 Big-M），但 Big-M 会把线性松弛弄松；CP 的 presence 是原生的，没有 Big-M 常数。

### 3.4 一个容易混淆的地方

`presence = 0` 时 `start` 与 `end` 仍然有值（求解器总要给变量赋值），只是那个值**没有物理意义**。所以读解的时候必须先看 `presence`，再决定要不要读 `start`：

```text
presence[工序][机器] = 1  →  这个工序在这台机器上加工，start/end 有意义
presence[工序][机器] = 0  →  跳过，不要把这个 start 当成「它在别处开工的时刻」
```

M2 的读取逻辑把这件事放在 `_read_schedule` 里一次做对：先找 `presence = 1` 的那台机器，再从它对应的 `start` / `end` 反推排程，避免把未选中的机器的坐标读进结果。而且它把「恰好一台」做成了一条断言——若筛选出的机器数不等于 1，直接抛 `ValueError`，而不是硬取第一个。**宁可报错，不要给一个来源不明的排程**，这条纪律和 Month 2 第一周「没有 bound 就写 `None`」是同一个思路。

### 3.5 三套词表的对照

从 MILP 那一周走过来，最容易出错的地方是「同一个词在两边的意思不一样」。把三套词表并排记住：

| CP-SAT 术语 | 调度语义 | MILP 里的对应物 |
|---|---|---|
| `domain` | 工序可选的开工时刻集合 | 整数变量域 `[lb, ub]`（不带洞） |
| `IntervalVar` | 一个工序占用的时间窗 | `start` / `end` 两个连续变量 + 一条等式 |
| `OptionalIntervalVar` | 「这个工序放不放这台机器」 | 指派变量 `x[op][m]` + Big-M 约束 |
| `presence` | 该区间的「存在性」 | 指派布尔变量 `x[op][m]` |
| `AddExactlyOne` | 每道工序恰好被一台机器加工 | `Σ_m x[op][m] = 1` |
| `AddNoOverlap` | 一台机器同一时刻只能有一个工序 | 析取约束（两两先后 + Big-M） |
| `AddCumulative` | 有限容量资源的时刻占用不超标 | 每个时刻一条容量行（需要时间索引） |
| `propagation` | 用约束把域收紧 | 预处理（presolve）与割平面 |
| `conflict` | 搜索中撞到的矛盾，可记为 nogood | 冲突分析 / 割 |
| `BestObjectiveBound` | 「最优值不会比这更好」的证明 | 分支定界里的 dual bound |

**这张表里最需要警惕的是最后三行**：两边的界都叫「界」，但产生机制不同。表里对齐的只是**含义**——「最优值不会低于这个数」——不是**强度**。

---

## 4. 手算：传播如何沿约束收紧域

### 4.1 算例

三道工序串成一个 job，每道长 5，公共上界 `H = 30`：

```text
start_k ∈ [0, 30]，end_k ∈ [0, 30]， end_k = start_k + 5
约束：end_0 <= start_1，end_1 <= start_2
```

### 4.2 手算传递闭包

**前向**（用下界推下界）：

```text
end_0 = start_0 + 5 >= 0 + 5 = 5       →  end_0 >= 5
start_1 >= end_0 >= 5                  →  start_1 >= 5
end_1 = start_1 + 5 >= 10              →  end_1 >= 10
start_2 >= end_1 >= 10                 →  start_2 >= 10
```

**后向**（用上界推上界）：

```text
end_2 <= 30（变量自身域的帽）           →  start_2 = end_2 - 5 <= 25
end_1 <= start_2 <= 25                 →  end_1 <= 25
start_1 = end_1 - 5 <= 20              →  start_1 <= 20
end_0 <= start_1 <= 20                 →  end_0 <= 20
start_0 = end_0 - 5 <= 15              →  start_0 <= 15
```

合起来：

```text
start_0 ∈ [0, 15]      end_0 ∈ [5, 20]
start_1 ∈ [5, 20]      end_1 ∈ [10, 25]
start_2 ∈ [10, 25]     end_2 ∈ [15, 30]
```

**这就是传播**：约束 `end_k <= start_{k+1}` 把两个变量的域连起来，一端收紧，另一端跟着收紧。这个过程一直做到不动点为止。注意它是**多项式时间**的——不需要枚举任何组合，只需要沿约束的连接来回扫。

### 4.3 同一组区间上，`NoOverlap` 只能给到哪

把「三道串行」换成「三道互斥」，即同一个模型上只放一条 `AddNoOverlap([iv0, iv1, iv2])`，没有任何 precedence：

```text
三个 start ∈ [0, 30]，三个 end = start + 5
一条约束：三者两两不重叠
```

手算它给出的界：

```text
start_k <= H - size = 30 - 5 = 25        （谁排最后都行，所以每道都可能最晚开工）
start_k >= 0
```

**只有这么紧。** `NoOverlap` 不会去算「三个长 5 的任务放在一台机器上至少要 15」——这个全局量要靠别的机制（搜索、或者额外加一条冗余下界约束）。原因是 `NoOverlap` 的推理是**局部**的：它检查的是区间之间两两的先后关系，而不是「总工时」这个全局量。

第 7 节的实测输出与这两段手算逐项对得上：链式模型的 `chain_start0 -> [0, 15]`、`chain_start1 -> [5, 20]`、`chain_start2 -> [10, 25]`；互斥模型的三个 `start` 全是 `[0, 25]`。

### 4.4 一个必须记牢的坑：回填的域不一定最紧

实测输出里有一个与手算不一致的地方，值得单独拿出来：

```text
实测：chain_end0 -> [5, 25]
手算：end_0 <= 20（由 end_0 <= start_1 <= 20 得到）
```

打印出来的上界 25 比手算的 20 松。这不是手算错了，也不是求解器错了——**它是「回填的域」与「传播不动点」的差别**。用一次独立的可行性测试可以判定谁紧：

```text
在同一个链式模型上加约束 end_0 >= 20  →  状态 OPTIMAL   （有解）
在同一个链式模型上加约束 end_0 >= 21  →  状态 INFEASIBLE（无解）
```

所以 `end_0 <= 20` 才是真正紧的上界，而回填的 25 只是一个**有效但更松**的区间。

三条结论记下来：

1. `fill_tightened_domains_in_response = True` 回填的域是**有效松弛**：打印出来的区间一定包含真实可行取值，不会给出错误的信息；
2. 但它**不是传播不动点**：不同变量上打印的界可能松紧不一，彼此之间也不保证自洽；
3. 所以它适合做**定性观察**（「传播确实沿链走下去了」），不适合当作数值结论引用。

把这条经验记成一条通用纪律：**求解器给你的每一个读数，都要先问清它保证的是什么。**

---

## 5. 实现：`build_cpsat_model` 的建模层

对应文件 [cpsat_models.py](../../projects/02_optimization_models/opt_models/cpsat_models.py)。

三个注册方法（`cpsat_parallel` / `cpsat_jsp` / `cpsat_cumulative`）共用一份建模逻辑，好处是：语义只有一处实现，测试只需要盯住一处。

| 名字 | 角色 |
|---|---|
| `build_cpsat_model(instance, objective, ...)` | 唯一的建模入口，返回 `_BuiltModel` |
| `_BuiltModel` | 模型句柄：`model` + `starts` / `ends` / `presence` / 选机结果 / 目标除数 |
| `_objective_expression(...)` | 把 M1 的目标翻译成 CP-SAT 表达式，同时给出还原真实单位的除数 |
| `_read_schedule(solver, built, time_scale)` | 从求解器读数，还原成 M1 的 `Schedule` |
| `_solve_built(...)` | 设参数、计时、把结果包成统一 `SolveResult` |
| `cumulative_profile(...)` | 独立重算容量占用 |

建模的每一行都对应一句调度语义：

```text
每道工序：start ∈ [r * scale, horizon]       释放时间以下不能开工
           end = start + size                区间定义
每台合格机器：一个 OptionalIntervalVar         选机 = 一组布尔
每道工序：AddExactlyOne(presences)            恰好被一台机器加工
每台机器：AddNoOverlap(该机器上的区间)         机器互斥
每个 job：Add(ends[前道] <= starts[后道])      工序顺序
可选：AddCumulative(全部区间, 需求, 容量)      有限容量资源
```

`prefer_fixed_route` 是给 JSP 用的一个开关：当一道工序只有一个合格机器时，直接建**必选区间**而不是可选区间，`presence` 变量数量变成 0。这样经典 JSP 的模型形状与教科书一致（一工序一区间），也少掉一大堆无用的布尔变量。

还有一个纪律上的细节值得记住：**`build_time` 与 `solve_time` 是分开量的**。前者是建模型的时间，后者是 `solver.Solve` 的时间。跨方法比较时混在一起会得出错误结论——不同建模方式的开销可以差一个数量级。

---

## 6. 整数时间缩放：为什么 CP-SAT 的时间必须是整数

CP-SAT 的变量是**整数变量**，`IntervalVar` 的 `start` / `size` / `end` 也必须是整数。而调度数据经常是「小时：`1.5`」「分钟：`2.25`」这种非整数。

本仓库的处理方式是用 `time_scale` 把时间单位放大：

```text
真实单位的时间 t   →   模型里的整数 t * scale
建模：end = start + p * scale
还原：start // scale, end // scale
```

关键性质：因为放大的量只有加工时长与释放时间，而它们都是「整数 × scale」，所以 `end = start + size` 放缩之后仍然成立，还原时的整除是**精确**的（没有舍入误差）——前提是 `scale` 取得足够让所有时间都变成整数。

两条纪律：

1. **`time_scale` 只影响模型的坐标，不影响排程的语义**。第 7 节的实测里 `time_scale` 取 1 / 2 / 4，三次得到的排程完全相同（`[('M0',0,2),('M0',2,4),('M0',4,6),('M1',0,3),('M1',3,6)]`），Cmax 都是 6；
2. **目标值要除回来**。`makespan` 在放大后的模型里是 `6 * scale`，汇报时必须除以 `scale`，否则 `time_scale=4` 的「Cmax = 24」看起来像变差了。代码把这个除数记在 `detail["objective_divisor"]` 里，实测值就是 1 / 2 / 4。

M1 的 `processing_time` / `release_time` 本来就是 `int`，所以 `time_scale = 1` 是恒等映射——这不是巧合，是 M1 在数据层就做的选择，Week 3 直接受益。

顺带记住另一处同类的整数化：权重是 `float`，而 CP-SAT 的目标系数必须是整数，所以 `weighted_completion_time` 会把权重乘 1000 取整（`WEIGHT_SCALE`），并在系数退化到 0 时报错而不是悄悄截断。

---

## 7. 实验：`m2w3d1_intervals`

对应脚本 [m2w3d1_intervals.py](../../projects/02_optimization_models/examples/m2w3d1_intervals.py)，在项目目录下运行：

```bash
python examples/m2w3d1_intervals.py
```

脚本做五件事：打印三种域 → 看 `IntervalVar` 的三元组 → 回填两个模型的域 → 看可选区间的布尔 → 用三种 `time_scale` 各解一次。实际输出：

```text
=== 1. domain：集合，不是区间 ===
Domain.FromIntervals([[0,3],[10,12],[20,20]])  ->  [0,3][10,12][20]
Domain.FromValues([1,3,5,7])                      ->  [1][3][5][7]
域写成 [0,3] U [10,12] U {20} 的变量，求解后取值 0
MILP 的整数变量域只能写成 [lb, ub]；CP 的域是任意集合，这是两者最底层的差别。

=== 2. IntervalVar：end = start + size ===
start 初始域 [0,30]，end 初始域 [0,30]，size 固定 5
IntervalVar 由 (start, size, end) 定义，本身是派生对象，不进 tightened_variables。

=== 3. propagation：沿约束收紧域（实测观察）===
优先级链 end_k <= start_k+1，每道 5，H = 30   ->  状态 OPTIMAL
  chain_start0     -> [0, 15]
  chain_end0       -> [5, 25]
  chain_start1     -> [5, 20]
  chain_end1       -> [10, 25]
  chain_start2     -> [10, 25]
  chain_end2       -> [15, 30]
三个长 5 的区间 + 一条 NoOverlap，H = 30      ->  状态 OPTIMAL
  noov_start0      -> [0, 25]
  noov_end0        -> [5, 30]
  noov_start1      -> [0, 25]
  noov_end1        -> [5, 30]
  noov_start2      -> [0, 25]
  noov_end2        -> [5, 30]
观察：链把上界一路推下来（start0 <= 15、start1 <= 20、start2 <= 25）；
      NoOverlap 只给出 start <= H - size = 25 —— 三者谁排最后没定，这就是最紧的界。
注意：这里的域是**求解过程中的域**（含传播收紧的界，也可能含搜索的定值），
      适合定性观察传播，不能当作传播不动点引用。

=== 4. OptionalIntervalVar：多一个布尔 presence ===
一个工序、两台机器、恰好一个成立，另加 start <= 4      ->  状态 OPTIMAL
  opt_start            -> [0, 0]
  opt_end              -> [7, 11]
  opt_presence_M0      -> [0, 0]
  opt_presence_M1      -> [0, 1]
presence 是 BoolVar；它成立时区间才占用机器时间。选机决策 = 一组布尔变量。

=== 5. 整数时间缩放 ===
time_scale=1: 状态 OPTIMAL, Cmax=6, 目标除数=1
   排程（真实时间单位）[('M0', 0, 2), ('M0', 2, 4), ('M0', 4, 6), ('M1', 0, 3), ('M1', 3, 6)]
time_scale=2: 状态 OPTIMAL, Cmax=6, 目标除数=2
   排程（真实时间单位）[('M0', 0, 2), ('M0', 2, 4), ('M0', 4, 6), ('M1', 0, 3), ('M1', 3, 6)]
time_scale=4: 状态 OPTIMAL, Cmax=6, 目标除数=4
   排程（真实时间单位）[('M0', 0, 2), ('M0', 2, 4), ('M0', 4, 6), ('M1', 0, 3), ('M1', 3, 6)]
放大 k 倍只是把同一组时间换成整数坐标；end = start + p * k 整除回来是精确的。
M1 的 processing_time / release_time 本来就是 int，所以 time_scale=1 即恒等映射。
```

五处观察：

1. **域的洞是真的**：`Domain.FromIntervals([[0,3],[10,12],[20,20]])` 打印成 `[0,3][10,12][20]`，三段之间的 `4..9`、`13..19` 不在域里。第 1 节模型里没有目标函数，所以求解器随手取了域里的值 0——**没有目标时，「求解器取值」这句话不含任何决策含义**。
2. **链式传播与手算逐项一致**：`[0,15]`、`[5,20]`、`[10,25]` 正是第 4.2 节算出来的上界，`[5,10,15]` 的下界也对得上。
3. **互斥传播明显更弱**：三个 `start` 全是 `[0,25]`，与第 4.3 节的手算一致。
4. **`chain_end0` 是 `[5,25]` 而不是手算的 `[5,20]`**：这是第 4.4 节那个坑的现场证据。求解器回填的是有效但更松的区间，且彼此松紧不一；把它当不动点引用会得出错误结论。
5. **可选区间让「选机」变成布尔决策**：`opt_presence_M0 -> [0,0]`、`opt_presence_M1 -> [0,1]`，配合脚本里那条 `start <= 4`，求解器必须选 M1（选 M0 时长 7 的区间放不进 `[0,4]`）。`opt_start -> [0,0]` 与 `opt_end -> [7,11]` 就是这次传播的结果。

脚本只打印、不写文件；Week 3 的落盘产物由 [w3_cpsat.py](../../projects/02_optimization_models/opt_experiments/w3_cpsat.py) 统一负责。

---

## 8. 今日练习

1. **练习 1（手算）**：把第 4.2 节的链改成四道工序、每道长 4、`H = 30`，手算全部 `start` / `end` 的传播闭包，并说明最晚开工的是哪一道。
2. **练习 2（手算）**：`H = 20`、三道工序各长 5、同一台机器只加 `NoOverlap`，手算每个 `start` 的界的上界；再说明「三道总工时 15」这条信息能不能靠传播得到。
3. **练习 3（概念）**：写出一个 `presence = 0` 时 `start` 会被求解器赋一个无意义值的例子，并说明 `_read_schedule` 为什么必须先筛 `presence`。
4. **练习 4（代码阅读）**：不运行脚本，先手写 `build_cpsat_model` 里「每台机器一条 `AddNoOverlap`」那段（含「该机器上区间数 > 1 才加」这个条件），再与源码对照。
5. **练习 5（缩放）**：某实例的加工时间是「0.5 小时」为单位的小数，最小单位 0.25。说明 `time_scale` 至少要取多少，以及目标除数为什么也是这个值。

---

## 9. 验收清单

- [ ] 能写出一个 MILP 表达不了、CP 能直接表达的域，并说明它对应哪种调度场景。
- [ ] 能说出 `IntervalVar` 的三个量里哪两个是独立的，并解释它为什么不出现在 `tightened_variables` 里。
- [ ] 能手算优先级链的传播闭包（下界前向推、上界后向推），并说明传播是多项式时间的。
- [ ] 能说出 `NoOverlap` 对同一个三区间模型给出的界是 `H - size`，并解释它为什么弱。
- [ ] 能说出 `OptionalIntervalVar` 多出的决策是什么，以及 `AddExactlyOne` 约束的是什么。
- [ ] 能说出读解时必须先看 `presence` 再读 `start` 的原因。
- [ ] 能解释 `time_scale` 为什么能保证恢复真实时间时整除是精确的。
- [ ] 能说出「回填的域」与「传播不动点」的差别，并知道用可行性测试判定某个界紧不紧。
- [ ] 在项目目录下运行 `python examples/m2w3d1_intervals.py`，输出里能看到链式传播的 `[0,15] / [5,20] / [10,25]` 与三次 `time_scale` 排程一致。
- [ ] 在项目目录下运行 `python -m pytest -q tests/test_cpsat_models.py` 全部通过（含缩放与传播相关的测试）。

---

## 10. 自测题

不看上文回答：

- Q1：CP 变量的「域」与 MILP 整数变量的取值范围，本质差别是什么？
- Q2：`IntervalVar` 由哪三个量定义？哪一个是派生出来的？
- Q3：为什么 `IntervalVar` 本身不出现在回填的 `tightened_variables` 里？
- Q4：三道各长 5 的工序串成链、`H = 30`，传播后 `start_2` 的域是什么？
- Q5：同样三个区间只加一条 `NoOverlap`，`start_k` 的界是什么？为什么比链式传播弱？
- Q6：`OptionalIntervalVar` 比普通区间变量多出什么？`presence = 0` 时 `start` 有物理意义吗？
- Q7：`AddExactlyOne` 在并行机模型里约束的是哪一句话？
- Q8：CP-SAT 为什么要求时间变量是整数？`time_scale` 的代价是什么？
- Q9：`time_scale = 4` 时 `makespan` 的目标值为什么要除 4？不除会看到什么假象？
- Q10：求解器回填的域能不能直接当作「传播后的最紧界」引用？怎么判定某个界紧不紧？

### 参考答案

- A1：MILP 的整数变量域只能是连续区间 `[lb, ub]`；CP 的域是任意整数集合，可以带洞，例如 `[0,3] U [10,12] U {20}`。带洞的域在调度里对应「可加工时段」「可选机器集合」这类真实结构。
- A2：由 `(start, size, end)` 定义，其中 `end = start + size` 是派生关系，所以三个量里只有两个独立。
- A3：因为它没有自己的域——它的全部含义就是那条 `end = start + size` 的关系，真正有域的是 `start` 与 `end` 两个整数变量。
- A4：`start_2 ∈ [10, 25]`（下界由两次 `end >= start + 5` 前向推得，上界由 `end_2 <= 30` 后向推得）。
- A5：`start_k ∈ [0, 25]`，即 `H - size`。因为 `NoOverlap` 只做区间两两的局部推理，不会累加「三个任务的总时长」这个全局量。
- A6：多一个布尔变量 `presence`，表示「这个区间在不在」。`presence = 0` 时 `start` 仍有取值但**没有物理意义**，必须先筛 `presence` 再读坐标。
- A7：约束「每道工序恰好被一台机器加工」，即该工序在所有合格机器上的 `presence` 之和等于 1。
- A8：CP-SAT 的变量是整数变量，`IntervalVar` 的时间量也必须是整数。`time_scale` 的代价是模型坐标被放大、目标值与时间读数都要除回来，放大倍数越大搜索空间也越大。
- A9：因为放大后的目标值是真实值的 4 倍；不除回来会把「同一排程」误读成「变差了 4 倍」，而实际上三次排程完全相同、Cmax 都是 6。
- A10：不能。回填的域是**有效但不一定最紧**的松弛区间，彼此松紧还不一致（实测 `chain_end0` 是 `[5,25]`，而真正紧的上界是 20）。判定办法是加一条约束做可行性测试：`end_0 >= 21` 返回 `INFEASIBLE`，说明 20 才是紧的上界。

---

## 11. 今日一句话总结

> **CP-SAT 的五个零件——域是集合、区间是 `(start, size, end)` 三元组、传播沿约束的连接收紧域、可选区间让「做不做」成为布尔决策、时间必须是整数——合起来解释了一件事：CP 建模保留问题的组合结构，而不是把它压成一张线性规划表；也正因为如此，阅读求解器给的每个读数之前都要先问清它保证的是什么。**
