# Day 5：区分 OPTIMAL / FEASIBLE / UNKNOWN / INFEASIBLE / MODEL_INVALID

> 当日主题：把求解器返回的五个状态各自的含义与保证逐条说清，并守住一条纪律——除了「有解」的状态，绝不读任何解；`INFEASIBLE` 时求解器返回的 0 也绝不写进 `best_bound`
> 当日产出：[cpsat_models.py](../../projects/02_optimization_models/opt_models/cpsat_models.py) 的状态映射与读出纪律 + [m2w3d5_statuses.py](../../projects/02_optimization_models/examples/m2w3d5_statuses.py) 的实测输出（五个状态各一个可复现实例）
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 说出五个求解器状态各自的**保证**是什么，并说出其中哪两个允许读取解。
2. 说明 `UNKNOWN` 与 `INFEASIBLE` 的区别为什么是决定性的，以及把前者当后者汇报会毁掉什么结论。
3. 说明 `MODEL_INVALID` 与 `INFEASIBLE` 的区别，并各举一个触发场景。
4. 说出为什么 `INFEASIBLE` 时 `BestObjectiveBound()` 返回的 0 不能写进 `best_bound`。
5. 解释 `FEASIBLE` 状态下 `best_bound` 可能是「平凡界」，并用一个实例说明它几乎不含信息量。
6. 说出 `num_search_workers = 1` + 固定 `random_seed` 能保证什么、不能保证什么。
7. 解释为什么「实测求解时间」总是略大于 `time_limit`，并说出多出来的时间花在哪里。
8. 说出 M2 统一的八个状态词里，哪五个来自 CP-SAT、哪三个是工程包装。

---

## 2. 为什么状态词表是本周的核心产出

前面四天都在建模型，但一个求解器调用真正返回的东西不是「一个解」，而是**三元组**：

```text
（状态, 解, 界）
```

其中状态决定了另外两项能不能用。这件事在 CP-SAT 上尤其要紧，因为它返回的状态有五个，而它们的含义差别很大：

```text
OPTIMAL       已经证明没有更好的解了
FEASIBLE      找到一个解，但没证明它最好
UNKNOWN       没判定出来（既没找到解，也没证明不可行）
INFEASIBLE    证明了根本没有可行解
MODEL_INVALID 模型本身非法，求解器拒绝执行
```

把这五个状态分清楚，是做求解器实验的**门槛**。越过分不清这道门槛，下面这些错误会一个接一个地出现：

```text
把 UNKNOWN 记成 INFEASIBLE        →  报告里出现「该实例无解」的假结论
把 INFEASIBLE 的 bound 0 记下来    →  无解被伪装成「下界为 0」，gap 看起来正常
把 FEASIBLE 的目标值当最优值       →  「最优值」这个词被滥用，跨方法比较失真
把 MODEL_INVALID 当实例无解        →  建模 bug 被掩盖成问题性质，且永远查不出来
```

这四类错误在文献与工程代码里都很常见，而且**它们都不会报错**——错误的数字会安静地流进结果表。所以今天要把状态这件事做成硬约束。

---

## 3. 概念：五个状态各自的保证

### 3.1 定义（状态的保证）

| 状态 | 求解器保证了什么 | 允许读解吗 | 有可比的界吗 |
|---|---|---|---|
| `OPTIMAL` | 存在一个解，且不存在目标值更小的解 | 允许 | 有，且 `bound == objective` |
| `FEASIBLE` | 存在一个解；是否还有更好的解**未知** | 允许 | 可能有，但可能很弱 |
| `UNKNOWN` | **什么都没保证**：没找到解、也没证明不可行 | 不允许 | 没有 |
| `INFEASIBLE` | 不存在任何可行解 | 不允许（没有解） | 没有（返回的 0 是占位符） |
| `MODEL_INVALID` | 模型非法，求解器没有执行求解 | 不允许 | 没有 |

三条要背下来的判据：

```text
判据 1：只有 OPTIMAL 与 FEASIBLE 允许读 solver.Value() / BooleanValue()
判据 2：只有 OPTIMAL 时「最优值」这个词才是准确的
判据 3：任何状态下，「界」都只能用求解器明确给出的那个数；取不到就是 None
```

### 3.2 `UNKNOWN` 与 `INFEASIBLE` 的区别

这两个状态经常被混为一谈，因为它们在「有没有解」这个问题上都给不出解。但它们的**认识论地位**完全相反：

```text
INFEASIBLE：我们**知道**没有解。这是关于问题的一个结论。
UNKNOWN   ：我们**不知道**有没有解。这是关于我们自己的一个结论（预算不够）。
```

所以：

- `INFEASIBLE` 可以写进报告：「该实例在给定约束下无可行解」；
- `UNKNOWN` 只能写：「在 X 秒预算内未判定」。

把后者写成前者，等于把「我没算出来」说成「这个问题没有解」。**这是实验报告里性质最严重的一类错误**，因为它把一个可利用的信息（「需要更多预算或更好的模型」）变成了一个错误的结论。

### 3.3 `MODEL_INVALID` 与 `INFEASIBLE` 的区别

```text
INFEASIBLE    ：题目**对**，但答案不存在。
MODEL_INVALID ：题目**错**了，所以求解器不知道该怎么答。
```

`MODEL_INVALID` 的典型触发方式：

```text
1. 变量的 domain 为空（例如 NewIntVar(5, 3, ...) 或上界小于下界）
2. 表达式整型溢出（系数过大，超出 int64）
3. 约束的 enforcement literal 与变量域矛盾到无法编码
```

**`MODEL_INVALID` 永远是建模 bug，不是实例的性质**。它必须和 `INFEASIBLE` 分开报——把建模 bug 当成「实例无解」，会让整个实验的结论建立在错误的问题上，而且**它永远不会自己暴露**（因为报告里写的是「无解」，看起来像个正常结果）。

### 3.4 `FEASIBLE` 的界可能没有信息量

`FEASIBLE` 状态下，求解器**可能**给出一个界，也可能给一个几乎没用的界。最典型的是 `total_tardiness` 这类「目标非负」的问题：

```text
所有工序的完工时间都不超过交期时，总拖期 = 0
所以  最优值 >= 0  恒成立
```

于是「下界 0」是一条**永远成立、也永远没用**的界。第 7 节第 2 小节实测里 `best_bound = 0.0`、`相对 gap = 1.0000` 就是这个情形——gap 是 1，说明这个界到最优值之间的距离等于最优值本身，也就是「证明离得还非常远」。

**这条观察有一个直接的方法论后果**：比较两个方法的 `gap` 之前，必须先看 `best_bound` 是不是平凡界。拿「界为 0 的 gap 1.0」去和一个「真正收紧了界的 gap 0.1」比较，会得出完全错误的结论。

### 3.5 一个必须小心的读数：`raw_best_bound`

M2 的包装层把求解器返回的原始值原样记在 `detail["raw_best_bound"]` 里，为的是让「哪些数被丢掉了」这件事可见。在 `INFEASIBLE` / `UNKNOWN` / `MODEL_INVALID` 三种状态下，这个数都是 `0.0`：

```text
INFEASIBLE  : raw_best_bound = 0.0   ←  无解，0 是未赋值的占位符
UNKNOWN     : raw_best_bound = 0.0   ←  什么都没判定，0 同样是占位符
MODEL_INVALID: raw_best_bound = 0.0  ←  求解器根本没跑
```

**把它写进 `best_bound` 就是伪证据**：对最小化问题来说，「下界为 0」意味着「最优值不小于 0」，而这在无解的情形下毫无意义；更糟的是，如果目标本身就非负（`total_tardiness`、`makespan`），这个 0 看起来还「像那么回事」——**错误变得不可见，才是最危险的**。

所以包装层的写法是把三种状态一律置 `best_bound = None`，并把原始值单独留在 `detail` 里备查。这条纪律的文字表述是：

> **没有可比的下界时就写 `None`，绝不填 0，也绝不拿目标值冒充。**

---

## 4. 手算与推演：四个可复现实例

### 4.1 `OPTIMAL`：小实例，预算足够

```text
实例：p = [3,3,2,2,2]，2 台机器，makespan
手算下界：max(3, ceil(12/2)) = 6
可行排程：一台做两个 3（负载 6），另一台做三个 2（负载 6）
→  最优值 6，且求解器在 1 秒预算内证完
```

期望状态 `OPTIMAL`，且 `bound == objective == 6`。

### 4.2 `INFEASIBLE`：单个工序就超容量

```text
实例：3 个工序，每个 p = 5，`resource_demand = 2`，`resource_capacity = 1`
推理：任意时刻，只要有一个工序在跑，占用就是 2 > 1 → 违法
      而每个工序都必须在某个时刻跑 → 任何排程都违法
→  无可行解
```

**分支数期望为 0**：这个矛盾在传播阶段就能被发现——`Cumulative` 的传播器会直接发现「单个区间的需求就超过容量」，不需要搜索任何组合。这是 Week 3 里「传播战胜搜索」最干净的一个例子。

### 4.3 `FEASIBLE`：短预算截断

```text
实例：generate_instance(51, jobs=12, machines=1)，total_tardiness
预算：0.05 秒（远小于搜完所需）
```

期望：找到一个解（状态 `FEASIBLE`），界是平凡界 0。**这个实例的最优值在更长预算下是 532**（本日 5 秒档的实测），所以 0.05 秒时看到的目标值必然是次优的。

### 4.4 `UNKNOWN`：预算小到连可行解都搜不出来

```text
实例：generate_instance(50, jobs=25, machines=3)，makespan
预算：0.01 秒
```

期望：三个都是空——没解、没界、`iterations` 为 0。**这不是「无解」，只是「没算」**。

### 4.5 三个状态的对照表

```text
状态           objective   best_bound   schedule   可以汇报成什么
OPTIMAL        6.0         6.0          有         「最优值是 6」
FEASIBLE       610.0       0.0          有         「0.05 秒内找到 610，未证明最优」
UNKNOWN        None        None         None       「0.01 秒内未判定」
INFEASIBLE     None        None         None       「无可行解」
MODEL_INVALID  None        None         None       「模型非法（建模 bug）」
```

对照着看就很清楚：**五行的区别全在头两列**，而这两列正是最容易被草率填上的地方。

---

## 5. 实现：状态映射与读出纪律

### 5.1 状态映射

映射是一一对应的，不做任何「脑补」：

```python
_CP_STATUS_TO_M2 = {
    cp_model.OPTIMAL: "OPTIMAL",
    cp_model.FEASIBLE: "FEASIBLE",
    cp_model.INFEASIBLE: "INFEASIBLE",
    cp_model.UNKNOWN: "UNKNOWN",
    cp_model.MODEL_INVALID: "MODEL_INVALID",
}
```

M2 的统一词表一共有 8 个（`opt_solvers.result.STATUSES`）：

```text
OPTIMAL / FEASIBLE / INFEASIBLE / UNKNOWN / MODEL_INVALID   ← CP-SAT 原生的五个
FEASIBLE_OR_UNKNOWN   ← CP-SAT 在「只找可行解」模式下的原生状态
FAILED                ← 包装层异常（建模阶段出错、spec 参数非法等），原因进 detail
NOT_SOLVED            ← 求解器根本没被调用
```

后三个是**工程包装**，不对应某个具体的求解器状态码，而是用来记录「求解流程本身出了问题」。三者的分工要清楚：

| 包装状态 | 什么时候用 | 举例 |
|---|---|---|
| `FAILED` | 求解之前的环节出错 | 目标名拼错、`time_scale` 传了 2.5、权重太小无法整数化 |
| `NOT_SOLVED` | 求解器未被调用 | （本仓库目前的路径都会走到 `FAILED`） |
| `FEASIBLE_OR_UNKNOWN` | 求解器明确表示「只找可行解」 | 需要显式打开只找可行解的参数时 |

一个具体的设计决定值得记下来：**建模阶段的异常映射成 `FAILED`（并记 `stage = "spec"`），不是 `MODEL_INVALID`**。理由是把 `MODEL_INVALID` 留给「求解器自己判定模型非法」这一种情形——只有求解器说的才算，包装层无权代言。这样 `MODEL_INVALID` 这个状态就始终指向真实问题，而不是被包装层的异常污染。

### 5.2 读出纪律

```python
_SOLVED_STATUSES = (cp_model.OPTIMAL, cp_model.FEASIBLE)

if status not in _SOLVED_STATUSES:
    # INFEASIBLE / UNKNOWN / MODEL_INVALID：没有可读的解，也没有可比的界
    # INFEASIBLE 时 BestObjectiveBound() 会返回 0，直接写进结果就是伪证据
    detail["raw_best_bound"] = float(solver.BestObjectiveBound())
    return _finish(m2_status(status))
```

这段代码里有两个要点：

1. **提前返回**：三种「无解」的状态在读任何 `Value()` 之前就返回了。这不只是省事——**在 `UNKNOWN` 下读 `solver.Value()` 会拿到未初始化的内部值**，那些值是内存里的残留数据，可能违反约束也可能大得离谱。用一个真实的实验可以确认这一点：在 `UNKNOWN` 状态下读出的排程会违反机器互斥，`start` 甚至可能是天文数字。所以「不读」不是保守，是必需。
2. **原始界单独留存**：`detail["raw_best_bound"]` 保留了求解器的原话，便于事后核对「这个 0 是什么」。**保留原始数据与不在结果里使用它是两件事**，前者是透明，后者是纪律。

### 5.3 目标值的独立重算

有解时，目标值**不由求解器读**，而是把解还原成 M1 的 `Schedule` 之后，调用 M1 的目标函数重算：

```python
objective = float(M2_OBJECTIVES[objective_name](instance, schedule))
cp_objective = float(solver.ObjectiveValue()) / built.divisor
detail["cp_objective"] = cp_objective
detail["cp_objective_matches_m1"] = math.isclose(cp_objective, objective, abs_tol=1e-6)
```

这样做的收益是：**「模型里的目标」与「问题定义的目标」被放在一起对了一次账**。如果两者不一致（例如 A 的目标被建成了 B 的、或者除数弄错了），`cp_objective_matches_m1` 会变成 `False`。这是建模层最隐蔽的一类错误——求解器会正常给出「最优」，但它最优化的不是你要的东西。

---

## 6. 时间限制与参数

### 6.1 三个参数

```python
solver.parameters.max_time_in_seconds = time_limit   # 搜索预算（墙钟秒）
solver.parameters.num_search_workers = 1             # 单线程
solver.parameters.random_seed = seed                 # 固定种子
```

三个参数各管一件事：

| 参数 | 作用 | 不设会怎样 |
|---|---|---|
| `max_time_in_seconds` | 搜索的时间预算 | 默认无限制，可能跑很久 |
| `num_search_workers = 1` | 单线程搜索 | 多线程下搜索轨迹随线程调度变化，难以复现 |
| `random_seed` | 固定随机源 | 搜索中的随机决策不可复现 |

### 6.2 可复现性的准确说法

「固定种子 + 单线程 = 可复现」这句话**只对了一半**，第 7 节的实测会把另一半展示出来：

```text
同一实例、同一 spec，跑两次：
  第一次 -> 状态 FEASIBLE, objective 563.0, 分支 26194, 冲突 6372
  第二次 -> 状态 FEASIBLE, objective 563.0, 分支 26735, 冲突 6826
```

**目标值一致，但分支数与冲突数不同**。原因是时间预算按**墙钟**截断：

```text
搜索是确定性的（单线程 + 固定种子），但「什么时候被时间限制叫停」取决于机器负载。
两次运行的挂钟走的快慢略有差别 → 在搜索树里停下的位置不同 → 分支数与冲突数不同
```

所以准确的说法分两种情形：

```text
给足预算、搜到最优（OPTIMAL）  →  目标值完全可复现，搜索轨迹也一致
时间限制下截断（FEASIBLE）     →  目标值稳定，但「搜到哪一步」不保证逐位一致
```

短预算下的抖动更明显。第 7 节第 6 小节做了 5 次重复测量：

```text
time_limit=0.05 五次目标值 -> [610.0, 610.0, 610.0, 643.0, 643.0]
time_limit=5.0  三次         -> [('FEASIBLE', 532.0, 1.0), ...]  （三次完全相同）
```

再跑一遍同一段代码，`time_limit=0.05` 的五次结果变成 `[643.0, 643.0, 643.0, 643.0, 643.0]`，同一档在另一次阶梯测量里还出现过 `665.0`；而 `time_limit=5.0` 的三次仍然全是 `532.0`。所以这一档的取值必须在**一次运行内**读，不能跨运行引用。

**短预算下目标值逐次不同；长预算下稳定收敛到同一个值。** 这解释了一件事：本仓库的测试在断言「可复现」时，断言的是**目标值相等**，而不是分支数相等——因为后者在时间限制下本来就不该相等。

### 6.3 实测求解时间为什么总是略大于 `time_limit`

第 7 节的阶梯里，`time_limit=0.05` 的实测求解时间是 `0.0503 s`，`time_limit=5.0` 是 `5.0146 s`。多出来的部分是：

```text
预求解（presolve）在时间预算之外花的时间
求解结束后读取解、组装 SolveResult 的时间
计时器的调用开销
```

所以**「实测求解时间」与「求解器内部的墙钟」是两个数**。后者由 `detail["cp_wall_time"]` 记录（求解器自己统计的），前者是包装层用 `time.perf_counter()` 量出来的。跨方法比较耗时时必须说清用的是哪一个——MILP 侧的时间记录方式不同，混用会让比较毫无意义。

---

## 7. 实验：`m2w3d5_statuses`

对应脚本 [m2w3d5_statuses.py](../../projects/02_optimization_models/examples/m2w3d5_statuses.py)，在项目目录下运行：

```bash
python examples/m2w3d5_statuses.py
```

脚本给五个状态各配一个可复现的最小实例，逐项打印状态、目标、界、原始界、有无排程、分支数与耗时；再用重复测量说明可复现性的边界。实际输出：

```text
=== 1. OPTIMAL：预算内既找到解、又证完了 ===
  cpsat_parallel，makespan，time_limit = 1.0
    M2 状态         : OPTIMAL（CP-SAT 原生 OPTIMAL）
    objective       : 6.0
    best_bound      : 6.0
    raw_best_bound  : 6.0  <- 求解器原始返回值
    schedule        : 有
    iterations      : 96
    build/solve     : 0.0018 s / 0.0085 s
    独立验证器      : 通过，Cmax = 6
    相对 gap        : 0.0000
  判据：状态 OPTIMAL 且 bound == objective。此时「这是最优值」有证明，不是猜测。

=== 2. FEASIBLE：找到解，但没证完 ===
  generate_instance(51, jobs=12, machines=1)，total_tardiness，time_limit = 0.05
    M2 状态         : FEASIBLE（CP-SAT 原生 FEASIBLE）
    objective       : 610.0
    best_bound      : 0.0
    raw_best_bound  : 0.0  <- 求解器原始返回值
    schedule        : 有
    iterations      : 2259
    build/solve     : 0.0016 s / 0.0504 s
    独立验证器      : 通过，Cmax = 160
    相对 gap        : 1.0000
  注意 best_bound = 0.0：这是「所有完工时间都不超过交期」的平凡下界。
  它不是垃圾，但几乎没有信息量 —— gap = 1.0 说明证明离得还很远。
  短预算下这个目标值还会随机器负载抖动（见第 6 节的重复测量）。

=== 3. UNKNOWN：预算内什么都没判定出来 ===
  generate_instance(50, jobs=25, machines=3)，makespan，time_limit = 0.01
    M2 状态         : UNKNOWN（CP-SAT 原生 UNKNOWN）
    objective       : None
    best_bound      : None
    raw_best_bound  : 0.0  <- 求解器原始返回值
    schedule        : None
    iterations      : 0
    build/solve     : 0.0027 s / 0.0111 s
  UNKNOWN 的含义是「不知道」：既没有可行解，也没有不可行的证明。
  它和 INFEASIBLE 的区别是决定性的 —— 不能把 UNKNOWN 当成「无解」来汇报。

=== 4. INFEASIBLE：证明了无可行解 ===
  3 个工序、每工序占 2 单位、resource_capacity = 1
    M2 状态         : INFEASIBLE（CP-SAT 原生 INFEASIBLE）
    objective       : None
    best_bound      : None
    raw_best_bound  : 0.0  <- 求解器原始返回值
    schedule        : None
    iterations      : 0
    build/solve     : 0.0018 s / 0.0004 s
  单个工序的需求 2 就超过容量 1，任何时刻都不可行，所以分支数是
  0：求解器在传播阶段就判死了，不需要搜索。
  特别注意 raw_best_bound = 0.0 —— 这个 0 被刻意丢掉，best_bound 写的是 None。

=== 5. MODEL_INVALID：模型本身非法，求解器拒绝执行 ===
  solve_model_invalid_demo：所有变量上界设成 -1（空域）
    M2 状态         : MODEL_INVALID（CP-SAT 原生 MODEL_INVALID）
    objective       : None
    best_bound      : None
    raw_best_bound  : 0.0  <- 求解器原始返回值
    schedule        : None
    iterations      : 0
    build/solve     : 0.0009 s / 0.0005 s
  MODEL_INVALID 不是「问题无解」，而是「题目本身写错了」：
  变量的 domain 为空、表达式整型溢出等等。它属于建模 bug，必须与
  INFEASIBLE 分开报 —— 把建模 bug 当成「实例无解」会直接毁掉实验结论。

=== 6. 时间限制与参数 ===
  同一实例、同一 spec，跑两次（num_search_workers=1、seed=7）：
    第一次 -> 状态 FEASIBLE, objective 563.0, 分支 26194, 冲突 6372
    第二次 -> 状态 FEASIBLE, objective 563.0, 分支 26735, 冲突 6826
  实测观察：两次的目标值一致，但分支数与冲突数不同。原因是时间预算
  按**墙钟**截断，两次运行在搜索树里停下的位置本来就不同（机器负载波动）。
  所以「可复现」的准确说法是：给足预算、搜到最优时目标值可复现；
  在时间限制下截断时，只有目标值稳定，搜索轨迹本身不保证逐位一致。
  测试里断言的也正是目标值相等，不是分支数相等。

  time_limit 阶梯（同一实例，只改预算）：
    time_limit=0.05  状态 FEASIBLE  objective=643.0    bound=0        分支=1558    实测求解 0.0503 s
    time_limit=0.2   状态 FEASIBLE  objective=608.0    bound=0        分支=5862    实测求解 0.2008 s
    time_limit=1.0   状态 FEASIBLE  objective=563.0    bound=0        分支=26878   实测求解 1.0010 s
    time_limit=5.0   状态 FEASIBLE  objective=532.0    bound=1        分支=82146   实测求解 5.0146 s
  实测求解时间始终略大于 time_limit：预算是给搜索的，
  建模、读解、返回还要额外花时间；detail['cp_wall_time'] 是求解器自己记的墙钟。

  短预算 vs 长预算的重复测量（同一 spec 各跑 5 次）：
    time_limit=0.05 五次目标值 -> [610.0, 610.0, 610.0, 643.0, 643.0]
    time_limit=5.0  三次（状态, 目标值, bound）-> [('FEASIBLE', 532.0, 1.0), ('FEASIBLE', 532.0, 1.0), ('FEASIBLE', 532.0, 1.0)]
  实测观察：短预算下目标值逐次不同（墙钟截断点不同，得到的是不同的次优解）；
  长预算下每次都稳定收敛到同一个值。所以「可复现」不是免费的，
  它取决于预算是否足以让搜索走完同一段确定性路径。
```

（上面这段是**一次运行**的原始输出。重跑同一脚本时只有两处会变：`time_limit=0.05` 那一行的 `objective`（另一次跑到过 `665.0`）与所有 `分支` 数；四个预算下的**单调递减趋势**与 `time_limit=5.0` 的 `532.0` 不变。）

（第 7 节的词表输出略，见脚本实际运行。）

八处观察：

1. **五个状态各自都有可复现的实例**：这不是理论枚举，而是五个能稳定跑出来的现象。实验设计上值得学的一点是——**每个状态都要有一个「最小可复现实例」**，否则你会分不清某个状态到底是求解器的行为还是自己实例的偶然。
2. **`OPTIMAL` 的判据是 `bound == objective`**：实测是 `6.0` 与 `6.0`。这两列相等是「证明最优」的可操作判据；只看到状态名 `OPTIMAL` 就相信，等于把权威当证据。
3. **`FEASIBLE` 的界可以完全没信息量**：`best_bound = 0.0`、`gap = 1.0`。而这个实例在更长预算下的最优值是 532（本日 5 秒档的实测），所以 0.05 秒时的 610、643 都只是次优解。**「找到解」与「找到好解」是两件事。**
4. **`UNKNOWN` 的三项全是 `None`**：`objective` / `best_bound` / `schedule` 都是空。对照 `raw_best_bound = 0.0`，可以清楚看到包装层丢掉的是什么。
5. **`INFEASIBLE` 的分支数是 0**：矛盾在传播阶段就被发现了。这是 Week 3 里「传播可以完全替代搜索」的直接证据。
6. **`MODEL_INVALID` 也是三项全空**：从结果表上它与 `INFEASIBLE` 长得一模一样，**唯一的区别就是状态名**。这正是为什么状态名必须逐字保留、不能归并成「失败」——归并之后这两类问题就再也分不开了。
7. **可复现性的边界是可测的**：两次运行目标值相同（563.0）、分支数不同（26194 / 26735）。5 次重复测量里，短预算给出两个不同的值（610 与 643），长预算三次全部相同。跨运行比较时，`time_limit=0.05` 这一档还出现过多达 665 的取值——**「可复现」是一个有前提的性质，不是一个开关。**
8. **时间阶梯的单调性在同一次运行内成立**：这一次运行是 643 → 608 → 563 → 532，另一次是 665 → 608 → 563 → 532，两次都单调递减。**更多的预算换来了更好的解**，而不是换来不同的解——这条单调性也是「求解器没有跑飞」的一个健康信号；但引用具体数值时必须说明是哪一次运行。

---

## 8. 今日练习

1. **练习 1（状态判定）**：给出四个「求解器输出」，判断各自应该汇报成什么（状态 + 能不能用目标值 + 能不能用界），并说明理由。其中至少有一个是 `UNKNOWN` 被伪装成 `INFEASIBLE` 的情形。
2. **练习 2（构造实例）**：构造一个实例，使求解器返回 `UNKNOWN` 而不是 `INFEASIBLE`（提示：预算很小 + 实例规模较大），并说明为什么不能把它的结果写成「无解」。
3. **练习 3（构造实例）**：构造一个触发 `MODEL_INVALID` 的模型（不要用脚本里那个 `horizon = -1` 的做法），并说明它为什么不是 `INFEASIBLE`。
4. **练习 4（平凡界）**：举出两个「最优值下界恒为 0」的目标函数，并说明为什么这类目标的 `gap = 1.0` 不代表方法很差。
5. **练习 5（可复现性）**：说明为什么「单线程 + 固定种子」在时间限制下仍然不能保证逐位可复现，并给出一个能保证完全可复现的实验设计（提示：预算给到什么程度）。

---

## 9. 验收清单

- [ ] 能默写五个状态名，并说出各自「保证什么」。
- [ ] 能说出哪两个状态允许读解，以及为什么另外三个不能读。
- [ ] 能说清 `UNKNOWN` 与 `INFEASIBLE` 在认识论上的区别，并说明混淆它们的后果。
- [ ] 能说清 `MODEL_INVALID` 与 `INFEASIBLE` 的区别，并各举一个触发场景。
- [ ] 能解释 `INFEASIBLE` / `UNKNOWN` 时 `raw_best_bound` 都是 0 的原因，以及为什么不能写进 `best_bound`。
- [ ] 能举出一个 `best_bound` 是平凡界的例子，并说明 `gap = 1.0` 的正确读法。
- [ ] 能说出 `num_search_workers = 1` + 固定种子保证什么、不保证什么。
- [ ] 能说出「实测求解时间」与 `detail["cp_wall_time"]` 的区别。
- [ ] 在项目目录下运行 `python examples/m2w3d5_statuses.py`，能看到五个状态各一次，且三个「无解」状态的 `objective` / `best_bound` 都是 `None`。
- [ ] 在项目目录下运行 `python -m pytest -q tests/test_cpsat_models.py` 全部通过（含 `INFEASIBLE` / `MODEL_INVALID` / `UNKNOWN` / `FEASIBLE` 四种状态的测试）。

---

## 10. 自测题

不看上文回答：

- Q1：五个求解器状态分别是什么？各自保证什么？
- Q2：哪两个状态允许读 `solver.Value()`？为什么另外三个不能读？
- Q3：`UNKNOWN` 与 `INFEASIBLE` 的区别是什么？把前者写成后者会有什么后果？
- Q4：`MODEL_INVALID` 与 `INFEASIBLE` 的区别是什么？谁是「题目的性质」、谁是「建模的 bug」？
- Q5：`INFEASIBLE` 时 `BestObjectiveBound()` 返回什么？为什么不能写进 `best_bound`？
- Q6：`best_bound = 0.0` 的 `total_tardiness` 结果，`gap = 1.0` 该怎么读？
- Q7：`num_search_workers = 1` + 固定 `random_seed` 能保证逐位可复现吗？在什么条件下可以？
- Q8：为什么实测求解时间总是略大于 `time_limit`？
- Q9：M2 的八个状态里，哪三个是工程包装？各自的用途是什么？
- Q10：为什么「建模阶段出错」映射成 `FAILED` 而不是 `MODEL_INVALID`？

### 参考答案

- A1：`OPTIMAL`（已证明最优）、`FEASIBLE`（有解未证明）、`UNKNOWN`（未判定）、`INFEASIBLE`（已证明无解）、`MODEL_INVALID`（模型非法，未执行求解）。
- A2：只有 `OPTIMAL` 与 `FEASIBLE`。另外三个状态下求解器没有有效解，读 `Value()` 会拿到未初始化的内部值（可能是违反约束的、也可能是天文数字），那是内存残留而不是解。
- A3：`INFEASIBLE` 是「知道没有解」的结论；`UNKNOWN` 是「不知道有没有解」的状态。把后者写成前者，等于把「我没算出来」说成「这个问题没有解」，把一个可改进的信息（加预算或改模型）变成一个错误结论。
- A4：`INFEASIBLE` 是题目的性质（问题对，但答案不存在）；`MODEL_INVALID` 是建模的 bug（题目写错了，求解器无法执行）。前者要改实例或约束，后者要改代码。
- A5：返回 `0.0`。对最小化问题它字面上意味着「最优值不小于 0」，在无解的情形下毫无意义；而且目标非负时它看起来「像那么回事」，错误会变得不可见。
- A6：它的意思是「下界离最优值的距离等于最优值本身」，即证明几乎没推进。读法是「找到一个次优解，但完全没证明它有多好」，不能拿来和方法之间的 gap 比较，因为 0 是平凡界（由目标非负直接得到）。
- A7：不能保证。搜索本身是确定性的，但「时间限制什么时候叫停」取决于墙钟，两次运行的机器负载不同、停下位置就不同。只有给足预算、搜到 `OPTIMAL` 时，目标值与搜索轨迹才完全可复现。
- A8：因为 `time_limit` 只管搜索阶段；预求解、求解结束后读取解与组装结果、以及计时开销都在预算之外。
- A9：`FEASIBLE_OR_UNKNOWN`（只找可行解模式下的原生状态）、`FAILED`（包装层异常，原因记在 `detail`）、`NOT_SOLVED`（求解器未被调用）。
- A10：为了让 `MODEL_INVALID` 始终指向「求解器自己判定模型非法」这一种情形。包装层的异常无权代言求解器的判断；否则这个状态会被污染，读者无法从状态名区分「模型真的非法」与「包装代码抛了异常」。

---

## 11. 今日一句话总结

> **求解器返回的不是「一个解」而是「（状态, 解, 界）」，五个状态里只有 `OPTIMAL` 和 `FEASIBLE` 允许读解、只有 `OPTIMAL` 才配叫「最优值」；而 `INFEASIBLE` 与 `UNKNOWN` 时求解器顺手返回的那个 0 必须被丢掉——把它写进 `best_bound`，就等于让「无解」和「没算出来」都伪装成「下界是 0」。**
