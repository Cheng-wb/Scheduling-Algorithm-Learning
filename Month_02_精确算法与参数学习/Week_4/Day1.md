# Day 1：识别同质机器对称性，用消融核验「强化不得改题」

> 当日主题：识别同质并行机上的机器置换对称性，逐项开关 `symmetry breaking` 与 `redundant constraint`，用「最优值不变」核验强化合法性
> 当日产出：**强化消融实验**（`strengthening.py` 的 `detect_machine_symmetry` / `add_load_ordering` / `add_redundant_bounds` + `m2w4d1_symmetry` + 正确性测试）
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 说清什么叫「同质并行机的机器置换对称性」，并写出这一对称性成立的两个前提。
2. 用一句话说出 `symmetry breaking` 的合法性来源：**每个最优解都能被重标号成一个满足该约束的解**。
3. 区分三类「多写一条约束」的动作：`symmetry breaking`、`redundant constraint`、`valid inequality`——它们都不许改变最优值，但来源不同。
4. 手算一个小实例，验证「负载降序」这类破缺约束只在**互为镜像**的解之间做选择。
5. 说出 `detect_machine_symmetry` 在什么情况下必须返回 `False`，以及此时硬套破缺会犯什么错。
6. 说出「强化效果」的正确判据是**最优值不变**，而不是耗时变短或冲突数下降。
7. 面对一次「强化让冲突数上升」的实测结果，如实记录为负收益，而不是粉饰成调参问题。

---

## 2. 为什么 Day 1 要谈「对称」和「冗余」

前两周（Week 2 的 formulation 对比、Week 3 的区间模型）反复出现同一个现象：**同一个问题可以有多种写法，而不同写法在求解器里的表现相差很大**。到 Week 4，题目从「换 formulation」变成「同一个 formulation 上加东西」——加对称破缺、加冗余约束、加初解、加固定变量。这类动作有个共同的危险：

> **加一条约束很容易，证明它没把最优解切掉很难。**

写错一条约束，模型照样能跑、照样给你一个「OPTIMAL」，只是答案变成了**另一个问题**的最优值。这种 bug 在日志里不报错、在状态码里不异常，只能靠**对拍**抓出来。所以今天要先立一条纪律，再谈技巧：

```text
强化（strengthening）的定义不是「听起来更紧」，而是：
    加上它之后，最优值完全不变。

最优值变了  →  不是强化，是改题（建模错误）。
```

这条纪律决定了今天的实验形式：**消融**（ablation）。同一个实例、同一份预算，把 `symmetry_breaking` 与 `redundant_constraints` 两个开关逐项打开，看四组结果的目标值是否逐字相同。`report.md` 的第一句判据就写着：

```text
**判据**：同一实例的四个变体目标值必须完全相同。不同即说明强化改变了最优值，
那是建模错误，不是性能差异。
```

补一句工程上的理由：并行机模型是「对称性」最典型、也最容易讲清楚的载体（机器同质时，把 M0/M1/M2 的编号重排一遍，任何排程都还是合法排程）。从这个最干净的例子入手，比一上来在 JSP 上讨论对称破缺要可控得多。

---

## 3. 三个定义与一条判据

### 3.1 定义

**定义（对称变换）**：设 `σ` 是机器编号集合上的一个置换。若对任意可行排程 `S`，把 `S` 里每台机器的编号按 `σ` 替换后得到的 `S'` **仍然可行**，则称 `σ` 是模型的一个对称变换。

**定义（同质机器对称性）**：同质并行机（`P` 类型，加工时间与机器无关）且**每道工序的资格集合都等于全部机器**时，机器编号的**任意**置换都是对称变换。此时模型有 `m!` 个对称变换，解空间里存在大量「只差一个编号」的重复解。

**定义（`symmetry breaking`）**：往模型里加一组约束，使得这 `m!` 个镜像解中**至少保留一个**、其余被判掉。合法性要求：被判掉的解必须都是某个保留解的镜像，否则会切掉最优解。

```text
把「对称变换能否保持可行性」和「能否保持目标值」分开看：
    保持可行性   →  解空间里出现镜像解（对称性存在）
    保持目标值   →  才能在镜像解里挑代表（破缺合法）
两者缺一不可，第二项在目标依赖机器编号时会失败（今天第 5.2 节有反例）。
```

### 3.2 三个动作的区别

| 动作 | 来源 | 为什么不变最优值 | 今天的例子 |
|---|---|---|---|
| `symmetry breaking` | 解空间的镜像冗余 | 被切掉的解都能重标号成保留的解 | 机器负载降序 `load[M_k] >= load[M_{k+1}]` |
| `redundant constraint` | 模型自身已经蕴含 | 它只是把隐含事实显式写出来 | `Cmax >= LB`、`C >= r + p` |
| `valid inequality` | 由一个**已验证可行解**推出 | 它只排除「比已知解更差」的区域 | 目标上界割 `obj <= UB` |

三者的**共同点**是都不许改变最优值；**不同点**是合法性的论证方式完全不同：第一类靠置换群，第二类靠模型蕴含，第三类靠一个具体的可行解。混着叫「强化技巧」会导致判断失误——`fixed_prefix` 会被不少资料也算作「warm start 技巧」，但它**不满足这条共同点**。

### 3.3 判据

**定义（强化正确性判据）**：对同一实例，未强化模型与强化模型的最优值必须相等。在本仓库里这条判据有三种独立证据：

```text
证据一：同一实例、同一预算，逐项开关强化，比对目标值（本日实验 §7）。
证据二：与 M1 的独立穷举 oracle 对拍（tests/test_strengthening.py）。
证据三：让同一条约束在「它本来就不合法」的实例上跑一遍，确认它被跳过。
```

证据三是很多资料会漏掉的一条：只证明「合法时结果不变」是不够的，还要证明「不合法时**没有**被加上去」。今天第 5.2 节与第 6.3 节都在做这件事。

---

## 4. 手算：镜像解与负载降序

取一个最小到能心算的例子：**2 台同质机器，3 道工序，`p = [5, 3, 3]`**，目标 `P||Cmax`。

总加工量 `Σp = 11`，解析下界：

```text
LB = max( max_j p_j , ceil(Σp / m) ) = max(5, ceil(11/2)) = max(5, 6) = 6
```

达到下界的一个排程：

```text
M0: J2(3) → J3(3)      负载 6
M1: J1(5)              负载 5
Cmax = 6 = LB           →  已证明最优
```

把两台机器的编号互换，得到另一个同样最优的排程：

```text
M0: J1(5)              负载 5
M1: J2(3) → J3(3)      负载 6
Cmax = 6
```

两个排程的目标值相同、工序集相同，只有机器编号不同——这就是一对**镜像解**。现在看破缺约束 `load[M0] >= load[M1]`：

```text
负载对 (6, 5)：6 >= 5 成立  →  保留
负载对 (5, 6)：5 >= 6 不成立 →  判掉
```

**判掉的那个解是保留解的重标号**，所以最优值 `6` 不受影响。这就是 `add_load_ordering` 的全部逻辑：它把每对镜像解砍掉一个，保留一个代表。

再补一个容易看漏的点：

```text
「负载降序」不是「Cmax 降序」，也不要求被保留的解负载相等。
本例保留了 (6, 5)，最大值仍在 M0 上；若写反方向（load[M0] <= load[M1]），
保留的会是 (5, 6)——仍然合法，只是选了另一侧代表。
方向可以任选，前提是整组约束按同一方向写。
```

对应的测试断言在 `test_symmetry_breaking_reorders_loads_not_the_objective`：它取回强化模型给出的排程，断言 `loads["M0"] >= loads["M1"]`。这条断言回答的是「约束真的加上了吗」，与「最优值没变」是两个不同的问题——**一个证明约束生效，一个证明约束合法**。

---

## 5. 实现：一个可复用骨架 + 两个薄函数

对应文件 [strengthening.py](../../projects/02_optimization_models/opt_models/strengthening.py)。

### 5.1 骨架 `build_parallel_model`

Week 3 已经建立过这套编码，这里只强调三个「写错就会静默出错」的位置：

```python
for machine_id in eligible:
    literal[key] = model.NewBoolVar(f"x_{op.id}_{machine_id}")
    start[key] = model.NewIntVar(job.release_time, horizon, f"s_{op.id}_{machine_id}")
    end[key] = model.NewIntVar(0, horizon, f"e_{op.id}_{machine_id}")   # 下界是 0，不是 r_j
    interval[key] = model.NewOptionalIntervalVar(start, p, end, literal, ...)
    model.Add(end[key] == 0).OnlyEnforceIf(literal[key].Not())          # 未选中的区间压成 0
model.AddExactlyOne([literal[(op.id, machine_id)] for machine_id in eligible])
```

三个要点：

1. **只为合格机器建变量**。给不合格的 `(工序, 机器)` 对也建布尔量，模型就能把工序派到它上不了的机器上——那不是「不可行」，而是「模型非法」，M1 的独立验证器会直接报 `illegal assignment`。少建变量的代价是 `ExactlyOne` 的取值范围变成 `eligible`，这恰好就是资格约束本身。
2. **未选中的区间必须被压成 `end == 0`**。因为完工时间是用 `end_of_operation[o] = Σ_m end[o][m]` 求和的：若不把未选中项压成 0，求出来的「完工时间」会包含一台根本没用的机器的 `end`。这条正是 Week 3 第 2 节里 `OptionalIntervalVar` 那个「多出来的布尔量」的真实用途。
3. **`horizon` 是合法上界**，不是估计值：`_default_horizon` 取 `最晚释放时间 + Σp`，把全部工序串行排完也不会超过它。`horizon` 同时是变量的上界，因此它的大小直接进入模型的系数跨度。

### 5.2 `detect_machine_symmetry`：什么时候**不许**破缺

```python
def detect_machine_symmetry(instance: Instance) -> bool:
    machine_ids = {machine.id for machine in instance.machines}
    if len(machine_ids) < 2:
        return False
    return all(set(op.eligible_machine_ids) == machine_ids for op in instance.operations)
```

两个必须返回 `False` 的情形：

```text
情形一：只有一台机器。没有可交换的对象，symmetry breaking 无从谈起。
情形二：存在某道工序的资格集合小于全部机器（例如 J1 只能上 M0）。
        此时「互换 M0/M1」会把它变成一道没有合格机器的工序 ——
        置换不再保持可行性，破缺约束会切掉最优解。
```

情形二的实测证据在 `test_symmetry_rows_are_skipped_when_machines_differ`：实例是 `J1(p=5, 只上 M0)`、`J2(p=4)`、`J3(p=4)`，手算最优 `Cmax = 8`（`J1 → M0` 独占 `0-5`，`J2`、`J3` 各占一台机器的 `4` 单位）。脚本打开 `symmetry_breaking=True`，结果里

```text
symmetry_breaking_applied = False
symmetry_skipped_reason   = machines are not interchangeable
symmetry_rows             = 0
objective                 = 8.0   （与手算一致）
```

**「打开开关但什么都不做」是正确行为**，并且在 `detail` 里留痕。调用方看到 `symmetry_rows = 0` 就知道这次开关是空转的，不会误以为自己做过一次有意义的实验。

### 5.3 `add_load_ordering`：2 条约束

```python
for left, right in zip(context.machines, context.machines[1:]):
    model.Add(sum(p_o * literal[(o, left)]  for o in operations)
              >= sum(p_o * literal[(o, right)] for o in operations))
```

`m` 台机器加 `m - 1` 条约束，把 `m!` 个镜像解压到 `m!/m` 类以上。注意这条约束的**形状**：右边是「工序是否落在该机器上」的线性组合，系数是加工时间——所以它就是「负载」本身，没有引入新变量，也没有 Big-M。

`detail` 里同时记录三件事，缺一不可：

```text
machine_symmetry_detected  数据层面是否具备对称性
symmetry_breaking_applied  本次求解是否真的加了破缺
symmetry_rows              实际追加的约束条数
symmetry_skipped_reason    若被跳过，原因是哪一个
```

### 5.4 `add_redundant_bounds`：7 条约束与一个真实的坑

```python
if context.objective == "makespan":
    model.Add(context.makespan >= context.lower_bound)      # Cmax >= LB
for op in instance.operations:
    model.Add(context.end_of_operation[op.id] >= job.release_time + op.processing_time)
```

第一族是 `Cmax >= LB`，其中 `LB = max(max_j p_j, ceil(Σp/m), max_j(r_j+p_j))`；第三项是 M1 的下界函数没有、但带释放时间时必须补的。第二族是每道工序 `C >= r + p`（由 `S >= r` 与 `C = S + p` 蕴含）。

**为什么说「改进来自把已知事实写进模型」**：`LB` 是**解析**算出来的，不是求解器发现的。把 `Cmax >= LB` 写进模型，求解器的传播器就能用这个下界往上收紧 `Cmax` 的域，bound 报告里也更早出现 `LB`。所以读实验表时要看清一件事：

```text
强化组报出的界提高到 LB，不等于「求解器找到了更好的界」，
而等于「我们把本来就知道的界喂给了它」。证据的归属必须写清楚。
```

代码注释里记录了一个**本模块真实踩过的坑**，值得整段抄下来：

```text
曾经这里写过「所有工序完工之和不超过 m·Σp」。带释放时间时它是**错的**：
机器空转会让 Σ C_o 超过该值，于是它把一个合法最优解切掉了。
识别方法是让同一个实例在「开/关强化」两种设定下各求一次最优——
最优值不同即证明这条约束不是冗余约束，而是新约束。
```

这就是第 3.3 节判据的来历：**判据不是理论上推出来的，是踩出来之后补上的**。凡是「看起来显然而已」的约束，都要走一遍「开/关对拍」流程。

---

## 6. 正确性核验：三种证据

### 6.1 证据一：同实例四变体对拍

`tests/test_strengthening.py::test_symmetry_breaking_keeps_optimum` 用 5 个实例（两个手算实例、一个无对称实例、两个随机实例）分别跑「未强化 / 只加冗余 / 加满强化」三次，断言

```python
assert plain.objective == bounded.objective == strengthened.objective
```

这条断言比「三次都 OPTIMAL」强得多：三个 `OPTIMAL` 只说明三次都搜完了，等式才说明**搜的是同一个问题**。

### 6.2 证据二：与 M1 的独立穷举对拍

`test_parallel_optimum_matches_independent_oracle` 调用 M1 的 `exhaustive_optimum`，把强化模型的结果与一个**完全不依赖求解器**的穷举对拍。三个手算实例的期望值都写在测试注释里：

```text
hand_p32223   p=[3,3,2,2,2]，2 台机器   →  最优 Cmax = 6
hand_release  J0/J1(r=0,p=4)、J2/J3(r=10,p=3)  →  最优 Cmax = 13
asymmetric    J1 只上 M0，p=[5,4,4]      →  最优 Cmax = 8
```

`hand_release` 的手算过程值得抄一遍：两台机器各自先做 `p=4`，机器空转到 `10` 再做 `p=3`，得到 `M0 = 0-4, 10-13`、`M1 = 0-4, 10-13`，`Cmax = 13`。解析下界 `max(4, ceil(14/2)=7, max_j(r_j+p_j)=13) = 13` 与手算相等——**下界恰好紧，所以这个实例的最优值可以解析证明**，不必依赖求解器。

### 6.3 证据三：该跳过的时候必须跳过

除了第 5.2 节的「机器不对称」情形，还有第二种跳过理由，写在 `test_tardiness_objective_skips_machine_symmetry` 里：

```text
目标换成 total_tardiness 时，机器置换**不再保持目标值**：
同一道工序换一台机器加工，完工时间可能平移，迟交量随之改变。
所以破缺约束在这类目标下不合法，必须跳过：
symmetry_skipped_reason = objective total_tardiness is not invariant under machine relabelling
```

这就把第 3.1 节那句话的两半都落实了：**保持可行性**由全资格保证，**保持目标值**由目标对机器置换的不变性保证。`makespan` 满足（最大完工时间与机器编号无关），`total_tardiness` 不满足。

### 6.4 「OPTIMAL」不是这条下界给的

实验里会看到两个数并排出现：

```text
强化后的最优值 = 27
解析下界 makespan_lower_bound = 24
```

下界 `24` **低于**最优值 `27`，说明这个解析下界是**松的**——它不足以证明 `27` 最优。脚本对此打印了一句提醒：

```text
注意：下界不等于最优值时，'OPTIMAL' 是求解器自己搜完得到的结论，
     不是这个解析下界给的。两者是独立的证据，不要混为一谈。
```

这与 M1 Week 1 第 12 节「`solution == LB` 才能证明最优」是同一条纪律。这里补一个新认识：**同一个模型里可以同时存在「松的解析下界」和「求解器自证的最优值」，两者互不否定**。冗余约束把那个松下界喂给求解器，它的作用是帮助传播，不是把下界变成 27。

---

## 7. 实验：`m2w4d1_symmetry`

对应脚本 [m2w4d1_symmetry.py](../../projects/02_optimization_models/examples/m2w4d1_symmetry.py)，在项目目录下运行：

```bash
python examples/m2w4d1_symmetry.py
```

脚本做四件事：在两个实例上检测对称性；在一台 6 作业 3 机器的同质并行机实例上跑三组配置（`baseline` / `symmetry` / `symmetry+redundant`）；断言三者最优值相同；打印两类强化各自追加的约束条数。实际输出：

```text
== 1. 对称性检测：哪些实例是同质并行机 ==
  5j/3m 同质     detect_machine_symmetry = True
  5j/1m 单机     detect_machine_symmetry = False
  说明：单机只有一台机器，没有可交换的对象，对称破缺无从谈起。

== 2. 消融：强化手段逐项开关（同一实例、同一预算）==
  配置                     状态            目标      界      冲突    耗时(s)
  baseline               OPTIMAL       27     27     190    0.022
  symmetry               OPTIMAL       27     27     377    0.020
  symmetry+redundant     OPTIMAL       27     27     529    0.028

== 3. 最优值必须不变（强化 ≠ 改题）==
  三种配置的最优值全部 = 27  →  强化成立
  独立下界 makespan_lower_bound = 24  →  与最优值 27 相比：松：不足以证明最优
  注意：下界不等于最优值时，'OPTIMAL' 是求解器自己搜完得到的结论，
        不是这个解析下界给的。两者是独立的证据，不要混为一谈。

== 3b. 公平起见：强化也可能是负收益 ==
  迭代数（conflicts）： baseline=190, symmetry=377, symmetry+redundant=529
  本例中对称破缺**增加**了冲突数：这些实例本来就小，
  额外约束的开销没有被搜索空间的缩小抵消。如实记录，不粉饰。

== 4. 冗余约束到底加了多少条 ==
  变量数（对称破缺前）: 61
  add_redundant_bounds 追加约束数 = 7
  add_load_ordering   追加约束数 = 2

全部断言通过。
```

驱动脚本 [w4_engineering.py](../../projects/02_optimization_models/opt_experiments/w4_engineering.py) 把同一件事做成了 2×2 的完整消融（两个实例 × 四个变体），结果落在 `artifacts/month2_w4/report.md` 第 1 节：

| 实例 | 变体 | 状态 | 目标 | 界 | 冲突 | 耗时(s) |
|---|---|---|---:|---:|---:|---:|
| par_6x3 | `sym=0_red=0` | OPTIMAL | 27 | 27 | 190 | 0.020 |
| par_6x3 | `sym=0_red=1` | OPTIMAL | 27 | 27 | 370 | 0.020 |
| par_6x3 | `sym=1_red=0` | OPTIMAL | 27 | 27 | 377 | 0.029 |
| par_6x3 | `sym=1_red=1` | OPTIMAL | 27 | 27 | 529 | 0.045 |
| par_10x3 | `sym=0_red=0` | OPTIMAL | 29 | 29 | 898 | 0.040 |
| par_10x3 | `sym=0_red=1` | OPTIMAL | 29 | 29 | 701 | 0.035 |
| par_10x3 | `sym=1_red=0` | OPTIMAL | 29 | 29 | 1461 | 0.058 |
| par_10x3 | `sym=1_red=1` | OPTIMAL | 29 | 29 | 1574 | 0.048 |

四件必须如实读出的事：

1. **正确性成立**：两个实例各自四个变体的目标值完全相同（`par_6x3` 全是 27、`par_10x3` 全是 29）。这是本日实验的**主结论**。
2. **效果是负的**：`par_6x3` 上冲突数 `190 → 377 → 529`，`par_10x3` 上 `898 → 1461 → 1574`。加约束**增加**了搜索代价。
3. **有一个例外要单独说**：`par_10x3` 的 `sym=0_red=1` 是 701，比基准 898 **更低**——冗余约束在两台实例上的表现不一致（`par_6x3` 是 190→370 上升，`par_10x3` 是 898→701 下降）。所以只能说「这次实测里冗余约束一例正收益、一例负收益」，不能概括成「冗余约束总是有害」。
4. **为什么小实例上会负收益**：额外约束缩小了搜索空间，也**增加了每个节点上的传播代价**。实例小、搜索本来就在毫秒级完成时，前者的收益还没有体现，后者已经全部付出。这不是「技巧错了」，而是「技巧的收益随实例规模变化」。

必须写进笔记的一句：**月验收明确要求「无改进也如实分析」**，所以这一节的价值恰恰在于它没有美化结果。把负收益写清楚，比报一个「最优值不变，强化有效」有用得多——前者是证据，后者是口号。

---

## 8. 今日练习

1. **练习 1（定义辨析）**：把「对称破缺」「冗余约束」「有效不等式」三者的合法性论证各写一句，指出它们共同的不变量是什么。
2. **练习 2（手算）**：对 `p = [4, 4, 2]`、2 台同质机器，写出全部最优排程，标出哪些互为镜像，并说明 `load[M0] >= load[M1]` 保留了哪一个。
3. **练习 3（反例构造）**：构造一个实例，使得「按机器编号破缺」会切掉最优解。提示：让某道工序只上一台机器，然后按第 5.2 节的方式检验 `detect_machine_symmetry` 的返回值。
4. **练习 4（判据应用）**：设计一个实验，用来证伪「`C >= r + p` 这条冗余约束是合法的」。说清你要比较哪两个数、以及结论怎么读。
5. **练习 5（读数）**：在 `report.md` 第 1 节里找出「强化让结果变慢」与「强化让结果变快」的各一行，说明为什么不能只报其中一行。

---

## 9. 验收清单

- [ ] 能说出同质机器对称性成立的两个前提（全资格 + 目标对机器置换不变）。
- [ ] 能说出 `symmetry breaking` 的合法性来源是「镜像解仍是最优解」，而不是「约束更紧」。
- [ ] 能区分 `symmetry breaking` / `redundant constraint` / `valid inequality` 的合法性论证。
- [ ] 能手算 `p = [5, 3, 3]`、2 台机器的镜像解对，并说明破缺约束只砍其中一侧。
- [ ] 能说出 `detect_machine_symmetry` 返回 `False` 的两种情形，以及硬套破缺的后果。
- [ ] 能解释 `end == 0` 这条「未选中区间压零」约束为什么必须有。
- [ ] 能说出强化正确性的三种证据，以及为什么「三次都 OPTIMAL」不算证据。
- [ ] 能如实报告本日实测的负收益（冲突数 190→377→529、898→1461→1574）。
- [ ] 在项目目录下运行 `python examples/m2w4d1_symmetry.py`，三条断言通过且三种配置最优值相同。
- [ ] 在项目目录下运行 `python -m pytest tests/test_strengthening.py -q`，`test_symmetry_breaking_keeps_optimum` 全部通过。

---

## 10. 自测题

不看上文回答：

- Q1：什么叫机器置换对称变换？同质并行机上它成立需要哪两个条件？
- Q2：`symmetry breaking` 凭什么不改变最优值？
- Q3：`redundant constraint` 与 `valid inequality` 的合法性来源有什么不同？
- Q4：`p = [5, 3, 3]`、2 台机器，写出两个最优排程，指出它们的关系。
- Q5：`detect_machine_symmetry` 在什么情况下必须返回 `False`？
- Q6：目标是 `total_tardiness` 时为什么必须跳过机器对称破缺？
- Q7：`OptionalIntervalVar` 未选中时为什么要把 `end` 压成 0？
- Q8：为什么「未强化 / 只加冗余 / 加满强化」三次都是 `OPTIMAL` 不能证明强化合法？
- Q9：本日实测里强化让冲突数上升说明了什么？能不能概括成「强化总是有害」？
- Q10：解析下界 24 与最优值 27 并存，这两条信息各自能证明什么？

### 参考答案

- A1：把机器编号做置换后，任何可行排程仍是可行排程。需要两个条件：每道工序的资格集合都等于全部机器；目标函数对机器置换不变。
- A2：因为这 `m!` 个解互为镜像，约束只保留每类镜像中的一个代表；被切掉的解都能通过重标号变回保留的那个，所以最优值不变。
- A3：`redundant constraint` 由模型自身蕴含（写出来只是显式化）；`valid inequality` 由「一个已知可行解」推出（它只排除比该解更差的区域）。
- A4：`M0={3,3}, M1={5}` 与 `M0={5}, M1={3,3}`，两者互为机器编号互换的镜像解，`Cmax` 都是 6。
- A5：只有一台机器时（没有可交换对象）；存在某道工序的资格集合小于全部机器时（置换会破坏可行性）。
- A6：因为机器置换不再保持目标值——换机器会平移完工时间，迟交量随之改变，破缺约束会切掉最优解。
- A7：因为完工时间是用 `end_of_operation = Σ_m end[o][m]` 求和的，未选中的项若不是 0，会把一台没用的机器的 `end` 混进完工时间里。
- A8：因为三次 `OPTIMAL` 只说明三次都搜完了，不说明搜的是同一个问题；只有三个目标值**相等**才说明强化没有改题。
- A9：说明额外约束的传播代价超过了搜索空间缩小的收益（小实例上常见）。不能概括为「总是有害」：同一张表里 `par_10x3` 的 `sym=0_red=1` 冲突数就比基准低（701 < 898）。
- A10：下界 24 只能证明「最优值不低于 24」；`OPTIMAL` 27 是求解器搜索得到的结论，两条证据互相独立，下界松不等于求解器的结论错。

---

## 11. 今日一句话总结

> **强化手段的合法性判据只有一条——最优值不变；今天用 2×2 消融证明了对称破缺与冗余约束在实测实例上确实不改最优值，也如实测出它们在两个小实例上把冲突数从 190 推到 529、从 898 推到 1574 的负收益：加约束缩小搜索空间，同时也要为每个节点付传播代价。**
