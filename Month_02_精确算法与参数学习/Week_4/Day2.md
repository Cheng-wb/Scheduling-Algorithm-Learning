# Day 2：hint、目标上界割与前缀固定——三件必须分开报告的事

> 当日主题：用 M1 的规则解构造初解，把常被笼统称作 `warm start` 的三种机制拆开，测出它们各自的性质与代价
> 当日产出：**初解与固定变量实验**（`solve_single_machine` 的三条正交开关 + `m2w4d2_warmstart` + 契约测试）
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 把「`warm start`」拆成三件性质不同的事：`hint`、`objective_cutoff`、`fixed_prefix`。
2. 说清 `set_hint`（`MIP start`）为什么**不提供任何质量保证**，以及它在 `detail` 里应当怎样留痕。
3. 说清 `objective_cutoff` 为什么是 `valid inequality`：它必须来自一个**已验证可行**的排程，因而不切最优解。
4. 说清 `fixed_prefix` 为什么是**邻域搜索而非强化**：它改变可行域，因而会改变最优值。
5. 说出「初解不劣于」这条契约由哪两条机制共同保证（上界割 + 退回初解）。
6. 用 `start_time` 反解初解序列，并解释为什么不能重放规则的排序键。
7. 读懂一张消融表：区分「并列（证明不了差异）」与「拉开（证明了差异）」两种结果。

---

## 2. 为什么 Day 2 要把「warm start」拆开

上一周讲 `formulation`，这一周开始讲「往同一个 `formulation` 上加东西」。最常被一起提起来的一组技巧是：

```text
拿一个现成的好解，喂给求解器，让它更快、更好。
```

这句话里其实混了三件**性质完全不同**的事：

```text
喂一个建议（hint）        →  求解器可以不听，性质：建议
加一条 obj <= UB 的约束    →  UB 来自可行解，性质：有效不等式
把解的一部分钉死           →  可行域真的变小了，性质：邻域搜索
```

它们被混在一起讲的原因很现实：三种做法都从「一个初解」出发，代码上看都是「给求解器一点额外信息」。但它们的**后果完全相反**：

```text
前两种保证   最优值不变（不切最优解）
第三种保证   最优值可能变差（切掉了别的解）
```

如果笔记里只写「用了 warm start，效果不错」，那么作者自己都分不清到底是「更快地找到了最优」还是「把问题改小了之后拿到了一个更小的数值」。Week 4 的整周纪律就是：

> **凡是改变解空间的技巧，都必须标出「它改变了什么」，并与未改变的版本对拍。**

第四种情况也要一并说清：`milp_warmstart` 的**契约**是「返回解不劣于初解」，它由「上界割 + 求解器未能求解时退回初解」两条机制共同保证。这条契约是**工程承诺**，不是数学结论——它必须在测试里被断言。

---

## 3. 三个机制：性质对照

### 3.1 定义

**定义（`hint` / `MIP start`）**：把一个已知解作为**建议**交给求解器，求解器可以用它来初始化 `incumbent`，也可以完全忽略。它不进入任何约束，因此**不改可行域、不保证被采纳**。

**定义（`objective_cutoff`）**：设 `UB` 是一个**已经验证可行**的排程的目标值，加入约束 `obj <= UB`。因为存在取到 `UB` 的可行解，这条约束不会把可行域切空、更不会切掉任何 `obj < UB` 的解，所以它是 `valid inequality`。

**定义（`fixed_prefix`）**：把初解序列的前 `k` 个位置固定为「第 `k` 位就是初解里的第 `k` 道工序」。这是往模型里加 `k` 条等式约束，可行域真的变小了，因此**可能把最优解排除在外**。

### 3.2 性质对照表

| 机制 | 改可行域吗 | 保证最优值不变吗 | 提供质量保证吗 | 在 `detail` 里的痕迹 |
|---|---|---|---|---|
| `set_hint` | 否 | 是 | **否**（建议而已） | `hint_kind` = `MIP start via CBC SetHint (advisory, not enforced)` |
| `objective_cutoff` | 是（加割） | 是（不切最优解） | 是（不劣于初解） | `objective_cutoff`、`cutoff_kind` |
| `fixed_prefix` | 是（真变小） | **否** | 否（只在初解邻域内最优） | `fixed_prefix`、`fixed_variables`、`free_variables` |

读懂最后两列的关系：`objective_cutoff` 也「改可行域」，但它改的方式是**只切掉比已知解更差的区域**，所以最优值不变；`fixed_prefix` 改的方式是**把一个坐标钉死**，最优值因此可能上升。**「改可行域」不等于「改最优值」**，判据永远是「最优解还在不在里面」。

### 3.3 一个常见的错误归纳

| 错误说法 | 正确说法 |
|---|---|
| 「warm start 能加速求解」 | `hint` 只是建议，是否采纳由求解器决定；加速与否要单独测 |
| 「warm start 保证不比初解差」 | 只有 `objective_cutoff`（或退回初解的工程包装）提供这条保证 |
| 「固定前缀是一种强化」 | 固定前缀会**改变最优值**，它是邻域搜索 |
| 「固定全部变量就是验证初解最优」 | 固定全部位置只是**复现**初解，它连「初解最优」都没验证 |

最后一条最值得记住：`fix_all` 的结果**必然**等于初解本身，因为模型退化成「给定时序、求最早开工」，只剩一个解。所以它测的不是「初解好不好」，而是「固定有没有真的生效」。测试 `test_fixing_all_variables_reproduces_seed_exactly` 正是这么用的：它把返回排程与规则初解**逐字段**（`operation_id`、`machine_id`、`start_time`、`end_time`）比对，一致才说明固定生效。

---

## 4. 初解从哪来：M1 规则 + 一个反解动作

### 4.1 初解来源

`_seed_schedule` 直接从 M1 的规则里取：`spt`、`edd`、`wspt`、`lpt`、`parallel_lpt`。`rule="best"` 时全部试一遍，取目标值最小的那条。两条工程细节：

```text
规则抛 ValueError（多工序、单机规则用在并行机上等）→ 按「该规则出局」处理，继续试下一条；
规则返回的排程过不了 schedule_errors  →  同样出局。
两者都不允许「伪造一个初解」——没有可用初解就报 FAILED。
```

### 4.2 必须按 `start_time` 反解，不能重放排序键

这是本日最容易写错的一处：

```python
def _sequence_from_schedule(instance, schedule):
    index = {op.id: position for position, op in enumerate(instance.operations)}
    ordered = sorted(schedule.operations, key=lambda item: item.start_time)
    return [index[item.operation_id] for item in ordered]
```

为什么不能「拿规则的排序键当序列」：M1 的规则在**有释放时间**时是 non-delay 列表调度（M1 Week 1 第 5 节），它的实际加工顺序与静态排序键并不相同。例如静态按 `p` 升序排出的顺序里，某个短任务可能因为 `r_j` 还没到而**被跳过**，机器先做了后面的任务。此时如果按排序键固定前缀，固定的是「一个根本没发生过的顺序」，`fixed_prefix` 就会指到错误的位置上。

测试 `test_warmstart_handles_release_times` 专门覆盖这一点：实例 `J1(r=5,p=4,d=12)`、`J2(r=0,p=2,d=3)`、`J3(r=8,p=3,d=9)`，手算最优 `ΣTj = 3`，断言模型算出 `3.0` 且 `seed_objective <= 3.0`。

### 4.3 手算：一个能分辨「割」与「固定」的小实例

用 M1 Week 1 的 CE-02 陷阱实例：

| Job | `pj` | `dj` |
|---|---:|---:|
| J1 | 1 | 1 |
| J2 | 1 | 3 |
| J3 | 3 | 2 |

**EDD 顺序** `J1, J3, J2`：

```text
C = [1, 4, 5]      T = [0, 4-2=2, 5-3=2]      ΣTj = 4
```

**最优顺序** `J1, J2, J3`：

```text
C = [1, 2, 5]      T = [0, 0, 5-2=3]          ΣTj = 3
```

现在把 EDD 的 `4` 当作初解喂进去，三种机制分别会得到什么：

```text
hint（只建议）      求解器可以无视建议，自己去搜 → 应得 3，但**不保证**
objective_cutoff    加 T_sum <= 4 → 最优解 3 仍可行（3 <= 4）→ 必得 3
fixed_prefix=1      把「第 1 位是 J1」钉死 → J1 确实在最优序首位（J1,J2,J3）→ 仍可能得 3
fixed_prefix=3      整条序钉死为 J1,J3,J2 → 只能得 4
```

这个实例说明两件事：

1. **割的方向是「上界」**：`obj <= UB` 允许更优解进来，所以它是有效不等式；写成 `obj >= UB` 就是错的。
2. **固定的危险性取决于初解质量**：初解恰好「前几位对」时，固定前缀看起来无害；初解全错时，固定多少位就把最优值抬高多少。所以「固定前缀」的实验必须选一个**初解不是最优**的实例才看得出效果——这正是第 7 节驱动脚本注释里写的那句话。

测试 `test_warmstart_hand_computed_values` 把上面的推理固化成断言：

```python
edd_seeded = milp_warmstart(trap, {**SPEC_TARDINESS, "rule": "edd"})
assert edd_seeded.detail["seed_objective"] == pytest.approx(4.0)   # 初解是差的 4
assert edd_seeded.objective <= 4.0                                  # 上界割的契约
assert edd_seeded.objective == pytest.approx(3.0)                   # 而且真的找到了 3
```

---

## 5. 实现：三条正交开关与两条契约

对应文件 [strengthening.py](../../projects/02_optimization_models/opt_models/strengthening.py) 的 `solve_single_machine`。

### 5.1 参数是正交的

```python
def solve_single_machine(instance, spec, *, set_hint, objective_cutoff, fixed_prefix,
                         hint_schedule=None, method): ...
```

三个布尔/整型参数互相独立，`method` 名跟着变（`milp_hint_only` / `milp_cutoff_only` / `milp_fix_prefix_3` …），这样批次结果表里一眼能看出「这一行开了哪些开关」。**正交参数 + 唯一方法名**是做消融的基本条件：只要有一个开关是「隐含打开」的，消融表就不可信。

### 5.2 上界割要取「已验证可行」的那个值

```python
if objective_cutoff:
    solver.Add(context.expression <= seed_value)
    detail["cutoff_kind"] = "valid inequality obj <= seed objective"
```

`seed_value` 来自 `hint_schedule`（若调用方传入）或规则本身，并且 `_seed_schedule` 里已经用 `schedule_errors` 过滤过。**「已验证可行」这四个字是这条割合法的全部依据**：如果 `seed_value` 来自一个不可行排程，它可能低于最优值，那时 `obj <= seed_value` 就把可行域切空了。

### 5.3 契约一：不劣于初解

```python
if status_code not in (solver.OPTIMAL, solver.FEASIBLE):
    if objective_cutoff:
        detail["fallback"] = (f"solver returned {status}; returned the seed schedule "
                              "(contract: never worse than the seed)")
        return _finish(..., hint_schedule, ..., status="FEASIBLE", best_bound=None, ...)
```

求解器连一个可行解都没给时，带割的方法**退回初解**并把状态记成 `FEASIBLE`（确实有一个可行解），而不是报 `UNKNOWN`。三条说明：

```text
1. 退回的解是「已验证可行 + 目标值 <= 割」的那个解，所以契约成立；
2. best_bound 记 None——CBC 在这个分支里没给出可用的界，
   不能把这个已知可行解的目标值冒充成界（那是 M2 最严重的伪证据）；
3. detail["fallback"] 必须写清「发生了退回」，否则读表的人会以为
   这个目标值是求解器搜出来的。
```

### 5.4 契约二：固定是加约束，只能更差或相等

`test_fixing_is_a_restriction_so_it_can_only_be_worse_or_equal` 在 5 个实例上断言

```python
assert fixed.objective >= free.objective - 1e-9
```

这条不等式的方向很容易记反。理由是纯数学的：固定前缀后的可行解集合是原集合的**子集**（加等式约束只会缩小），在子集上求最小值，结果不可能比在整个集合上更小。所以固定前缀对目标值的影响是**单调不优**——它换来的是更小的搜索空间，代价是可能错过最优解。

`test_fixing_zero_variables_reproduces_the_full_model` 提供反向锚点：`fix_ratio=0` 时不固定任何变量，结果必须与未固定模型一致。两个端点（0 与全部）都对上，才说明「固定的数量」真的控制了模型。

### 5.5 成本记账

```text
num_variables / num_constraints  模型规模
fixed_variables / free_variables 固定了多少、还剩多少
seed_rule / seed_objective       初解来自哪条规则、值是多少
rule_objectives                  所有试过的规则各自的值
hint_kind                        建议给了、但没保证被采纳
objective_residual               求解器自报值 与 M1 重算值 的差
max_time_round_residual          S_k 取整前后的最大偏差
```

前四项回答「实验条件是什么」，后三项回答「数值可信吗」。缺少任何一项，这张消融表都只能读出一半。

### 5.6 单机骨架：三个「不需要 Big-M」的线性化

`build_single_machine_milp` 用的是 Week 2 的位置式模型（`x[j][k]`：工序 `j` 是否排在位置 `k`），这里只记它为什么**不用** Big-M：

```python
solver.Add(start[k] >= sum(release[jobs[j]] * assign[j][k] for j in range(n)))
solver.Add(completion[k] == start[k] + sum(processing[jobs[j]] * assign[j][k] for j in range(n)))
solver.Add(tardiness[k] >= completion[k] - sum(due[jobs[j]] * assign[j][k] for j in range(n)))
```

三行的共同技巧是「**把选择项和被选中的参数乘在一起**」：右边只有被选中的那个作业贡献 `r_j` / `p_j` / `d_j`，其余项被 `x = 0` 抹掉。因为作业与位置一一对应（`Σ_k x[j][k] = 1`、`Σ_j x[j][k] = 1`），这三行的系数都限制在数据本身的量级内，不需要引入一个大常数 `M`。

这件事与今天的主题有直接关系：**这个模型的系数跨度天然很小**（span 与 Big-M 版本相差约 6 倍）。如果初解、割、固定三种机制都作用于这样一个模型上，那么它们带来的差异就更可能来自搜索路径，而不是数值条件——这也是为什么今天可以在小实例上干净地比较三种机制。

---

## 6. 手算：为什么必须挑「初解非最优」的实例

三个驱动实例的规则初解（`report.md` 第 2 节与 `results.csv` 的 `seed_value` 列）：

| 实例 | 规模 | 规则初解（SPT） | 最优值 | 五个变体 |
|---|---|---:|---:|---|
| `sgl_8x1` | 8 作业 | 85 | 85 | 全部 85（并列） |
| `sgl_12x1` | 12 作业 | 532 | 532 | 全部 532（并列） |
| `sgl_10x1_seed_suboptimal` | 10 作业 | **283** | **271** | 前三个 271，后两个 283 |

**前两个实例证不了任何东西**：初解恰好等于最优值，于是「不固定」与「固定全部」得到同一个数，这只能说明固定没算错，不能说明它**限制了**什么。驱动脚本的注释把这一点写得很直白：

```text
seed=81 上 SPT 初解不是最优（283 > 271），这样前缀固定的「限制解空间」
才看得出来；前两个实例的规则初解恰好等于最优，四档会并列，
那种情况下 fix_all 虽然正确，却证明不了它**限制了**什么。
```

第三个实例上初解的来源也值得读一遍：`spt=283`、`edd=283`、`wspt=312`。**两条规则恰好都停在 283，第三条更差**，说明 283 不是「某条规则偶然失手」，而是这个实例上规则族的共同水平（`283 - 271 = 12`，相对差约 4.4%）。这一点决定了第 7 节那张表的读法：表中六行都是**同一个初解**（SPT 的 283）的变体，而不是六条不同初解的对比。

还可以顺带做一次数值核查：`results.csv` 里 `sgl_10x1_seed_suboptimal` 五行的 `seed_value` 列全是 `283.0`，包括 `cutoff_only`（它不接收 `hint_schedule`，是脚本内部自己再跑一次 SPT 得到的）。两处独立算出同一个初解值，说明「初解」这件事在本实验里是**可复现的既定输入**，不是随调用方式变化的量。

**第三个实例才是证据**。它同时说明三件事：

```text
① 上界割不切最优解：cutoff_only 得 271，与基准、与「hint+割」完全相同；
② 前缀固定真的在限制解空间：fix_prefix_3 与 fix_all 都停在 283（= 初解），
   比完整模型能到的 271 差 12；
③ k 越大越贴近初解：本例 k=3 已经与 k=10 同值，说明 SPT 初解的前三位
   与最优序不一致，固定这三位就足以把 271 挡在门外。
```

第 ③ 点是本例最值得读的一句：`fix_prefix_3 = fix_all = 283` 说明**只固定前 3 位就已经把最优解排除**，剩下的 7 位怎么优化都无济于事。

同时必须诚实指出这张表**没有**证明什么：`hint_only` 与 `cutoff_and_hint` 都拿到 271，而**基准（什么都不加）也拿到 271**。所以在这个实例上，`hint` 与上界割的收益体现在「契约」而不是「数值」：

```text
hint：数值上无差别（求解器本来就能搜到 271）→ 只能说「没变差」，不能说「变好了」
割  ：数值上无差别，但它把「不劣于初解」从「也许会」变成「一定不会更差」
固定：数值上明确变差 12 → 这是「限制解空间」的代价，看得见
```

---

## 7. 实验：`m2w4d2_warmstart`

对应脚本 [m2w4d2_warmstart.py](../../projects/02_optimization_models/examples/m2w4d2_warmstart.py)，在项目目录下运行：

```bash
python examples/m2w4d2_warmstart.py
```

脚本在 `seed=81, jobs=10, machines=1` 的实例上先跑三条 M1 规则选初解，再跑六组配置（基准 / 只给 hint / 只加割 / hint+割 / 固定前 3 / 固定全部），最后断言三条结论。实际输出：

```text
== 1. 初解从哪来：M1 规则 ==
  spt    初解目标 = 283
  edd    初解目标 = 283
  wspt   初解目标 = 312
  取最好的规则：spt（283）作为初解

== 2. 三件事的正交组合（同一实例、同一预算）==
  配置                                 状态             目标      相对初解      冲突    耗时(s)
  不做任何事（基准）                          OPTIMAL       271       -12       0    0.105
  只给 hint                            OPTIMAL       271       -12       0    0.026
  只加目标上界割                            OPTIMAL       271       -12       0    0.052
  hint + 上界割                         OPTIMAL       271       -12       0    0.050
  固定前 3 个位置                          OPTIMAL       283        +0       0    0.016
  固定全部 10 个位置                        OPTIMAL       283        +0       0    0.016

== 3. 三条结论（都可证伪，不是口号）==
  ① 上界割是最优值不变的：基准 271 == 加割 271  →  它是有效不等式
  ② hint 不提供任何质量保证：只给 hint 得 271，与基准 271 的关系取决于求解器是否采纳建议
  ③ 固定全部位置 = 复现初解：283 == 初解 283  →  这不是强化，是把解空间缩到一个点
     固定前 3 个位置得 283：它是初解的**邻域**里的最优，k 越大越接近初解

全部断言通过。
```

配套的 15 行批次记录在 `artifacts/month2_w4/report.md` 第 2 节，三个实例 × 五个变体：

| 实例 | 变体 | 状态 | 目标 | 相对规则初解 | 耗时(s) |
|---|---|---|---:|---:|---:|
| sgl_8x1 | `hint_only` | OPTIMAL | 85 | +0 | 0.010 |
| sgl_8x1 | `cutoff_only` | OPTIMAL | 85 | +0 | 0.012 |
| sgl_8x1 | `cutoff_and_hint` | OPTIMAL | 85 | +0 | 0.009 |
| sgl_8x1 | `fix_prefix_3` | OPTIMAL | 85 | +0 | 0.008 |
| sgl_8x1 | `fix_all` | OPTIMAL | 85 | +0 | 0.008 |
| sgl_12x1 | `hint_only` | OPTIMAL | 532 | +0 | 0.044 |
| sgl_12x1 | `cutoff_only` | OPTIMAL | 532 | +0 | 0.035 |
| sgl_12x1 | `cutoff_and_hint` | OPTIMAL | 532 | +0 | 0.032 |
| sgl_12x1 | `fix_prefix_3` | OPTIMAL | 532 | +0 | 0.014 |
| sgl_12x1 | `fix_all` | OPTIMAL | 532 | +0 | 0.014 |
| sgl_10x1_seed_suboptimal | `hint_only` | OPTIMAL | 271 | -12 | 0.020 |
| sgl_10x1_seed_suboptimal | `cutoff_only` | OPTIMAL | 271 | -12 | 0.039 |
| sgl_10x1_seed_suboptimal | `cutoff_and_hint` | OPTIMAL | 271 | -12 | 0.041 |
| sgl_10x1_seed_suboptimal | `fix_prefix_3` | OPTIMAL | 283 | +0 | 0.016 |
| sgl_10x1_seed_suboptimal | `fix_all` | OPTIMAL | 283 | +0 | 0.015 |

三处读数要注意：

1. **耗时列在本实验里不构成证据**。所有变体都在 0.008～0.044 秒之间，而第 7 节那次手工运行的基准是 0.105 秒（同一配置、同一实例）。这个量级的差异主要来自进程调度与计时噪声，不能读成「固定前缀比完整模型快 6 倍」。要谈加速，必须换更大实例或做重复测量——在时间限制下，耗时读数本身就会抖动，重复测量也救不回来。
2. **`+0` 与 `-12` 的对比就是本实验的全部信息量**。前三行并列说明三件事都「没让结果变差」，后两行的 `+0` 说明「固定住了，无法改善」。
3. **`fix_all` 必然等于规则初解本身**（报告里那句注释）：`283 = 283` 是恒等式，把它读成「强化有效」是最典型的误读。
4. **状态列全是 `OPTIMAL`，这一列在这里不提供信息**。固定前缀之后模型仍然被搜完了——因为固定把问题变得**更容易**求解了。于是出现一个容易骗人的组合：`OPTIMAL` 加一个更差的目标值。读表时必须把「被证明最优」和「最优值是多少」当成两件事：前者说的是求解器在这个（被改小的）模型上搜完了，后者才是对原问题的回答。
5. **耗时最小的行恰好是结果最差的行**：`fix_all`（0.015 s）与 `fix_prefix_3`（0.016 s）最快，但它们回答的是**被改小的**问题；`hint_only`（0.020 s）稍慢却答对了。任何按耗时排序的「效率」结论，在这张表上都会把最差的设计排到最前。

### 7.1 这个实验能证什么、不能证什么

```text
能证：在 sgl_10x1_seed_suboptimal 上，前缀固定把结果封顶在初解（283），
      而同一实例的完整模型能到 271 —— 固定是限制解空间，不是强化。
能证：hint 与 cutoff 在这一实例上都到达 271，说明两条路径都不劣于规则初解。
不能证：hint 与 cutoff 谁更好（两者并列，本实验没有分辨力）。
不能证：fixing 在更大实例上一定更差（只有一个实例能分辨这件事）。
```

把「不能证」的两条写出来，是因为这张表最容易被过度引用：它的信息量集中在最后五行，其余十行是并列的。

---

## 8. 今日练习

1. **练习 1（定义辨析）**：用一句话分别说清 `hint`、`objective_cutoff`、`fixed_prefix` 对可行域做了什么，并指出哪一个会改变最优值。
2. **练习 2（手算）**：在 CE-02 陷阱实例上，把初解换成最优序 `J1, J2, J3`（值 3），预测 `fix_prefix_1` 与 `fix_prefix_2` 的结果，并说明为什么这时固定前缀看起来「无害」。
3. **练习 3（反解序列）**：给 `J1(r=5,p=4)`、`J2(r=0,p=2)`、`J3(r=8,p=3)` 写出 SPT 的静态排序键顺序与它的**实际**加工顺序，说明两者为什么不同。
4. **练习 4（契约）**：说出 `milp_warmstart` 的「不劣于初解」契约由哪两条机制保证，以及退回初解时为什么 `best_bound` 必须写 `None`。
5. **练习 5（读数）**：在 `report.md` 第 2 节里找出「能证明固定前缀限制了解空间」的那三行，并说明为什么另外十行证明不了同样的事。

---

## 9. 验收清单

- [ ] 能说出 `hint` / `objective_cutoff` / `fixed_prefix` 三者在「是否改可行域」「是否改最优值」上的差别。
- [ ] 能说出 `objective_cutoff` 是 `valid inequality` 的完整依据（割来自已验证可行的排程）。
- [ ] 能说出 `fixed_prefix` 为什么是邻域搜索，并用「可行解集合是子集」解释它的单调性。
- [ ] 能说出「不劣于初解」契约的两条保证机制，以及退回初解时的记账方式。
- [ ] 能解释初解序列为什么必须按 `start_time` 反解，而不能重放规则的排序键。
- [ ] 能手算 CE-02 陷阱实例的 EDD 值 4 与最优值 3，并推出三种机制各自的预期结果。
- [ ] 能指出 `sgl_8x1` / `sgl_12x1` 的并列结果为什么证明不了固定的限制作用。
- [ ] 能说出 `fix_all` 恒等于初解值，因此不能当作「强化有效」的证据。
- [ ] 在项目目录下运行 `python examples/m2w4d2_warmstart.py`，三条断言通过且前四组配置与后两组的结果差为 12。
- [ ] 在项目目录下运行 `python -m pytest tests/test_strengthening.py -q`，`test_fixing_all_variables_reproduces_seed_exactly` 等固定类测试全部通过。

---

## 10. 自测题

不看上文回答：

- Q1：`set_hint` 会改变可行域吗？会对解的质量提供保证吗？
- Q2：`objective_cutoff` 为什么是有效不等式？它合法的前提是什么？
- Q3：`fixed_prefix` 为什么可能让最优值变差？把理由压缩成一句话。
- Q4：`fix_all` 的结果一定等于什么？它能证明初解最优吗？
- Q5：`milp_warmstart` 的「不劣于初解」契约由哪两条机制保证？
- Q6：退回初解时为什么 `best_bound` 必须记 `None`？
- Q7：初解序列为什么必须按 `start_time` 反解？
- Q8：为什么 `sgl_8x1` 与 `sgl_12x1` 的五个变体并列，说明不了固定前缀的作用？
- Q9：在 `sgl_10x1_seed_suboptimal` 上基准也拿到 271，那么 hint 与上界割的收益体现在哪里？
- Q10：本实验的耗时列（0.008～0.044 秒）能用来论证加速吗？为什么？

### 参考答案

- A1：不改变可行域，也不提供任何质量保证——它只是把解作为建议交给求解器，采纳与否由求解器决定。
- A2：因为 `UB` 来自一个已经过独立验证的可行排程，`obj <= UB` 只排除比它更差的区域，不会切掉任何目标值更小的解。前提是「这个解确实可行」。
- A3：固定前缀往模型里加了等式约束，可行解集合变成了原来的子集，在子集上求最小值不可能比在原集合上更小。
- A4：一定等于初解的目标值（模型退化成「给定时序、求最早开工」，只剩一个解）。它不能证明初解最优，只能证明固定真的生效了。
- A5：一是 `obj <= UB` 这条有效不等式；二是求解器连可行解都没给出时退回初解并记 `FEASIBLE`。
- A6：因为 CBC 在这个分支里没有给出可用的界；把已知可行解的目标值填进 `best_bound` 会让 `gap` 恒为 0，制造「已证明最优」的伪证据。
- A7：因为规则在有释放时间时是 non-delay 列表调度，实际加工顺序与静态排序键不同；按排序键固定会指到没发生过的顺序上。
- A8：因为这两个实例的规则初解恰好等于最优值，五个变体必然同值；它只说明固定没算错，不说明固定限制了什么。
- A9：体现在契约而非数值：`hint` 只能说明「没变差」；上界割把「不劣于初解」从「也许会」变成「一定不会更差」。
- A10：不能。这个量级完全落在计时噪声里（同配置的基准在另一次运行里是 0.105 秒），要谈加速必须换更大实例并做重复测量。

---

## 11. 今日一句话总结

> **「warm start」是三件性质不同的事：`hint` 只是建议、`objective_cutoff` 是来自可行解的有效不等式（最优值不变）、`fixed_prefix` 是真正缩小可行域的邻域搜索（`sgl_10x1_seed_suboptimal` 上把 271 挡在门外，结果钉死在初解 283）；把三者混着报，就等于把「保证」和「代价」混成了一句口号。**
