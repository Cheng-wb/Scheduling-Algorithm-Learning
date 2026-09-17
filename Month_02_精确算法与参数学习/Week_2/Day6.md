# Day 6：同实例、同预算比较 tight / loose / alt

> 当日主题：把「强度」与「搜索行为」分成两组实验测，并让脚本自己用测出来的数字下结论
> 当日产出：**三个实例 × 三个 formulation 的对照表**（root LP bound、incumbent、nodes、runtime、gap）+ 四条自动生成的观察
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 设计一个可比较的实验口径：同实例、同目标、同预算、两组测量分开跑。
2. 说清 `root_lp` 组与 `limit` 组各自回答什么问题，以及为什么不能混用它们的读数。
3. 从三张表里读出 formulation 强度的差异（root LP bound）与搜索行为的差异（incumbent / nodes / runtime / gap）。
4. 说出「限时结束后的 `best_bound` 是搜索进度值，不是强度值」的理由，并能举出本日支持这个说法的数字。
5. 逐实例报告 tight 与 loose 的对照结果，包括 **loose 更好的那些行**，并说明为什么这些结论不能外推成一般规律。
6. 算出「formulation 设计的代价」：建模成本 + 搜索成本，并说明为什么在这个实例族上 `alt` 仍然更快。
7. 说清 `_finish` 里的下界一致性检查如何让 `OPTIMAL` 这个状态变可信。
8. 用自己的实测数字说明「改变强度的是变量定义，不是系数紧度」。

---

## 2. 为什么 Day 6 要设计口径，而不是直接跑

到昨天为止，手上有了三个 formulation、一堆数字、以及两个**互相矛盾**的直觉：

```text
直觉一：tight 的 M 更小 → 模型更紧 → 应该更好
直觉二：alt 的界接近最优 → 模型更强 → 应该更快
```

这两个直觉都可能在具体测量里落空，因为「更好」至少有三种含义：

| 「更好」的含义 | 该看的读数 | 本日对应实验组 |
|---|---|---|
| 松弛更强（界离最优更近） | root LP bound | `root_lp` |
| 同样的预算里找到的解更好 | `objective`（incumbent） | `limit` |
| 同样的预算里爬得更远 / 花得更少 | `nodes`、`solve_time`、`gap` | `limit` |
| 连建模一起算更省 | `build_time + solve_time` | `limit` + `root_lp` |

**口径的设计就是把这四种含义分到不同的读数上**。今天最容易被混淆的一处是 `best_bound`：它在 `root_lp` 组里是强度指标（LP 解到最优），在 `limit` 组里是进度指标（搜索爬到哪算哪）。同一个字段名，两种含义，必须靠实验组区分。

---

## 3. 实验设计

### 3.1 三个实例

| 名称 | 生成参数 | 预算 | 参考值 | 参考值来源 |
|---|---|---|---|---|
| single_a | seed 50, 8 jobs, 1 machine | 5.0s | 85 | 独立穷举（`exhaustive_optimum`） |
| single_c | seed 60, 15 jobs, 1 machine | 5.0s | 657 | 模型证明（某个模型解到 `OPTIMAL`） |
| single_d | seed 50, 20 jobs, 1 machine | 10.0s | 912 | 模型证明 |

目标统一为 `total_tardiness`，三个方法统一为 `milp_tight` / `milp_loose` / `milp_alt`。

**参考值的三种来源**按可信度排序（脚本里的 `reference()` 就是这么写的）：

```text
1. 独立穷举           → 8 job 实例能用（穷举是另一条计算路径，可信度最高）
2. 模型证明           → 15/20 job 实例只能用这个（某个模型解到 OPTIMAL 且过验证器）
3. 目前最好可行值      → 兜底（没有模型证明最优时，只能说「目前最好」）
```

**参考值本身的强弱会直接决定读法**：`single_a` 的 85 是两个模型都证明过的（三个方法都给出 `OPTIMAL 85`），且与独立穷举一致；`single_c` / `single_d` 的 657 / 912 只有 `milp_alt` 一个人证明过。后两个实例上 sequence 模型的最好可行值是 732 / 981（甚至 720 / 1019），**它们离参考值的差距才是今天的主角**。

### 3.2 两组测量

```text
root_lp 组：每个方法加 root_lp=True，时限 60s（实际都在 0.3s 内解完）
            读数：best_bound —— 松弛强度
limit   组：每个方法用实例自己的预算（5s / 5s / 10s）
            读数：objective / best_bound / gap / iterations / solve_time —— 搜索行为
```

每个方法在每个实例上跑两次（一次 LP、一次限时 MIP），共 `3 实例 × 3 方法 × 2 组 = 18` 次测量。

---

## 4. 结果：root LP bound（强度）

| 实例 | tight | loose | alt | 参考最优 | alt bound / 参考 |
|---|---|---|---|---|---|
| single_a | 0.0000 | 0.0000 | 83.9347 | 85 | 98.75% |
| single_c | 0.0000 | 0.0000 | 656.0508 | 657 | 99.86% |
| single_d | 0.0000 | 0.0000 | 911.7667 | 912 | 99.97% |

三行读下来的结论有两层：

**第一层（本日最需要记住的一句）**：

> `tight` 与 `loose` 的 root LP bound 完全相同 —— 在本实例族上都是 `0.0000`。**Big-M 的紧度没有改变松弛强度。**

这与 Day 3 的结论一致（那里是 8 job 与 15 job 两个实例、两个目标、四行「相等」全为「是」），今天在三个实例、三个方法上再次确认。**不要把它写成「tight Big-M 给出更强的 root LP bound」** —— 本日的测量正好相反：两者给出的界都等于平凡下界 `0`。

**第二层**：

> `alt` 的 root bound 直接落在最优值附近（`98.75%` → `99.97%`），改变松弛强度的是**变量定义**。

机制在 Day 5 第 3.4 节已经推导过：`alt` 把互斥写成「每台机器每个时刻的占用数 `<= 1`」的容量约束，LP 放松后这条约束仍然有效；而 sequence 模型的互斥是两条「择一成立」的约束，`x = 1/2` 时两边同时放松，机器容量在松弛里消失。同一个实例上的差距是 `0` 与 `83.9347` —— **这不是任何系数调整能弥补的差距**。

---

## 5. 结果：限时 MIP（搜索行为）

| 实例 | 方法 | 状态 | incumbent | final bound | gap | nodes | 求解(s) |
|---|---|---|---|---|---|---|---|
| single_a | milp_tight | `OPTIMAL` | 85.0 | 85.0000 | 0.0000 | 130 | 1.544 |
| single_a | milp_loose | `OPTIMAL` | 85.0 | 85.0000 | 0.0000 | 124 | 1.527 |
| single_a | milp_alt | `OPTIMAL` | 85.0 | 85.0000 | 0.0000 | 0 | 0.204 |
| single_c | milp_tight | `FEASIBLE` | 732.0 | 60.3039 | 0.9176 | 305 | 5.042 |
| single_c | milp_loose | `FEASIBLE` | 720.0 | 57.6507 | 0.9199 | 13010 | 5.205 |
| single_c | milp_alt | `OPTIMAL` | 657.0 | 657.0000 | 0.0000 | 0 | 0.625 |
| single_d | milp_tight | `FEASIBLE` | 981.0 | 63.0999 | 0.9357 | 207 | 10.081 |
| single_d | milp_loose | `FEASIBLE` | 1019.0 | 58.8305 | 0.9423 | 580 | 10.034 |
| single_d | milp_alt | `OPTIMAL` | 912.0 | 912.0000 | 0.0000 | 0 | 0.810 |

### 5.1 先说最容易被误读的一列：`final bound`

看 `single_d`：`milp_tight` 的 `final bound` 是 `63.0999`，`milp_loose` 是 `58.8305`。如果拿这一列去比「谁松弛更强」，会得出「tight 更强」的结论 —— 而第 4 节刚刚测出两者的 root bound 都是 `0`，完全相同。

**这一列是搜索进度，不是强度。** 预算 10s 内，`tight` 的搜索把界从 `0` 爬到 `63.0999`，`loose` 爬到 `58.8305`；两者都远未收敛（`gap` 0.9357 与 0.9423）。**要谈强度，就看第 4 节的 root LP bound；要谈搜索行为，才看这一节。**

同一列在 `alt` 上是 `912.0000 = incumbent`，因为它真的解到了最优（`gap = 0`）。`gap = 0` 与 `gap = 0.94` 是两种完全不同的状态：前者是「已证明」，后者是「预算花完了还没证明」。

### 5.2 tight 与 loose 的逐实例对照（不预设结论）

| 实例 | 指标 | tight | loose | 谁更小 |
|---|---|---|---|---|
| single_a | incumbent | 85 | 85 | 相同 |
| single_a | nodes | 130 | 124 | **loose** |
| single_a | solve_time | 1.544 | 1.527 | **loose** |
| single_c | incumbent | 732 | 720 | **loose** |
| single_c | nodes | 305 | 13010 | tight |
| single_c | solve_time | 5.042 | 5.205 | tight |
| single_d | incumbent | 981 | 1019 | tight |
| single_d | nodes | 207 | 580 | tight |
| single_d | solve_time | 10.081 | 10.034 | **loose** |

这张表里有两处值得反复看：

1. **`single_a` 上 loose 在两个读数上都更小**（节点 124 vs 130、时间 1.527 vs 1.544）：这是一个「tight 应该更好」的直觉落空的实例。两者都解到了 `OPTIMAL 85`，所以差别纯粹落在搜索路径上 —— 但下面会看到，这个量级的差距在重跑波动之内，不足以支撑任何结论。
2. **`single_c` 上 loose 的 incumbent 更好（720 vs 732）**，但它的节点数是 `13010` 对 `305`（约 43 倍），`gap` 也略高（0.9199 vs 0.9176）。**「找到更好的解」与「爬得更远」在这个实例上是两个方向**：`loose` 的松弛系数更大、LP 更容易产生「看起来不划算」的分支，但它在某个阶段的可行解质量反而更高。

**这些结论不能外推。** 下面是把上表原样重跑一遍的实测结果（同一实例、同一 spec、同一预算，每个方法跑两次）：

| 实例 | 方法 | 第 5 节记录的 nodes / 时间 | 重跑两次的 nodes / 时间 |
|---|---|---|---|
| single_a | tight | 130 / 1.544s | 130、130 / 1.583s、1.576s |
| single_a | loose | 124 / 1.527s | 124、124 / 1.629s、0.946s |
| single_c | tight | 305 / 5.042s | 16500、16500 / 6.198s、6.094s |
| single_c | loose | 13010 / 5.205s | 33750 / 5.048s、49948 / 5.596s |
| single_d | tight | 207 / 10.081s | 695、702 / 10.036s、10.061s |
| single_d | loose | 580 / 10.034s | 1593、1535 / 10.032s、10.032s |

三条理由由此成立：

1. **`nodes` 在限时搜索里不是可复现读数**：`single_c` 上 tight 从 `305` 变成 `16500`（约 54 倍），`single_d` 上 tight 从 `207` 变成 `695`（约 3.4 倍）。因此「节点数谁更小」只在本批测量内部成立。
2. **但同一方法的 `incumbent` 与 `final bound` 在重跑中完全一致**（`85`、`732` / `60.3039`、`720` / `57.6507`、`981` / `63.0999`、`1019` / `58.8305`）—— 波动的是「预算内走完了多少个节点」，不是「搜索走到了哪」。这也说明上表的 `objective` 与 `best bound` 比 `nodes` 可靠得多。
3. **限时是 wall-clock 预算、且在节点边界上检查**：`single_c` 上 tight 的重跑用了 `6.198s`（超出 `5.0s` 预算），因为检查发生在节点之间，单个节点解不完就不会被打断。机器负载一变，「预算内走完多少节点」就变，而搜索路径本身并不依赖时钟 —— 这也解释了为什么 `incumbent` 稳定、`nodes` 不稳。

另外 `single_a` 上两边的差距（`6` 个节点、`0.017s`）远小于重跑波动（`loose` 重跑两次用了 `1.629s` 与 `0.946s`，相差 `0.683s`），所以上面 `single_a` 那两行的胜负**没有统计意义**，只能算「本轮实测」。CBC 通过 `pywraplp` 不暴露随机种子（`detail["seed_effective"] = False`），无法通过固定种子消除这种波动。

### 5.3 正确的结论形状

把第 4 节与第 5 节合起来，今天能写下的结论只有这一种形状：

```text
强度：tight 与 loose 在本实例族上的 root LP bound 完全相同（都是 0）
      —— Big-M 的紧度不是松弛强度的杠杆（可复现，确定性测量）

搜索：tight 与 loose 的搜索行为在本批测量里互有胜负
      —— 本轮实测 single_a 上 loose 的两个读数都更小（124 对 130 节点），
         single_c / single_d 上 tight 在节点与 incumbent 上占优
      —— 但 nodes 不是可复现读数（同一方法重跑最多相差约 54 倍），
         incumbent 与 final bound 才是稳定的；这些只是本批观察，不是一般规律

设计：alt 的 root bound 从 0 提升到最优值的 98.75%–99.97%，
      三个实例全部在预算内解到 OPTIMAL（0 个分支节点）
      —— 改变强度的是变量定义，这是本轮实测里量级最大的一项差异
```

---

## 6. 实现：设计的代价、脚本结构与 `_finish` 的守门

### 6.1 formulation 设计的代价

| 实例 | alt 建模/求解 | tight 建模/求解 | alt 合计 | tight 合计 |
|---|---|---|---|---|
| single_a | 0.0301s / 0.204s | 0.0051s / 1.544s | 0.235s | 1.549s |
| single_c | 0.1852s / 0.625s | 0.0075s / 5.042s | 0.810s | 5.050s |
| single_d | 0.3114s / 0.810s | 0.0255s / 10.081s | 1.121s | 10.107s |

**`alt` 的建模成本比 sequence 模型高一个量级**（`0.03s` 对 `0.005s`、`0.31s` 对 `0.026s`），而且随实例规模增长；它的 LP 求解成本也更高（第 4 节的 `root_lp` 组里 `alt` 要 `0.18–0.32s`，sequence 模型只要 `0.002–0.006s`）。

但**把建模与搜索一起算，`alt` 在三个实例上都仍然更快**（`0.235s` 对 `1.549s`、`0.810s` 对 `5.050s`、`1.121s` 对 `10.107s`）。原因就是第 4 节的强度差异：强松弛省下的是**整棵搜索树**，而建模成本只是一次性的、可预测的小额开销。

代价必须一起记住：

```text
alt 的风险不在「慢」，而在「大」
  变量数随 H 线性增长（3 job 时是 sequence 的 4.6 倍，8 job 时 10.8 倍，40 job 时 17.1 倍）
  H 很大时首先碰到规模闸门 MAX_TIME_INDEXED_VARS = 400_000，直接拒绝建模
  —— 也就是说，「换个更强的 formulation」这条路有时间界的天花板，
     不是所有实例都能用
```

### 6.2 脚本结构

脚本 [m2w2d6_formulation_comparison.py](../../projects/02_optimization_models/examples/m2w2d6_formulation_comparison.py) 的结构：

| 函数 | 职责 |
|---|---|
| `INSTANCE_SPECS` | 三个实例的生成参数与各自预算（常量表） |
| `reference(instance, objective, results)` | 按「穷举 > 模型证明 > 目前最好可行值」给出参考值 |
| `collect(instance, budget)` | 跑完一个实例的两组实验，返回 `{组: {方法: SolveResult}}` |
| `print_instance(...)` | 打印一个实例的两组读数 |
| `print_observations(...)` | 打印四条观察，**逐条引用上面的表格数字** |
| `main()` | `load_week_modules()` → 方法名检查 → 逐实例运行 |

两处工程细节：

1. **`load_week_modules()` 必须在 `main()` 里显式调用**：注册表的填充依赖 `opt_models.milp_scheduling` 被导入这一副作用，脚本不导入模型模块就拿不到方法名。
2. **观察段落不手工润色**：`print_observations` 里的每一句判断都由测出来的数字生成（谁更小、谁更接近），避免「先写结论再跑实验」。

### 6.3 `_finish` 的守门：为什么 `OPTIMAL` 可信

今天三张表里有 5 个 `OPTIMAL`（`single_a` 三行、`single_c`/`single_d` 的 `alt` 行）。这些状态之所以可以直接采信，是因为 `_finish` 在返回之前做了两道交叉检查：

```python
recomputed = float(M2_OBJECTIVES[built.objective_name](instance, schedule))
if abs(solver_objective - recomputed) > 1e-6:
    detail["solver_objective_delta"] = round(solver_objective - recomputed, 9)

if best_bound > recomputed + 1e-6:
    # 模型是精确的：下界不可能高于「已由独立验证器复核过的可行解目标值」
    detail["failure_reason"] = f"best_bound {best_bound} > verified objective {recomputed}"
    return _no_solution(built, "FAILED", ...)
if best_bound > recomputed:
    best_bound = recomputed          # 亚 ULP 级越界，夹到可行解目标值
    detail["bound_clamped"] = True
```

三件事一次做完：

1. **目标值重算**：`objective` 字段来自独立重算，不来自求解器；
2. **下界一致性检查**：`best_bound` 高于「已验证可行解的目标值」时直接判 `FAILED` —— 这在数学上不可能发生（下界不可能高于一个可行解），一旦发生就说明模型或解码有错；
3. **亚 ULP 容差**：浮点噪声级别（`< 1e-6`）的越界夹到可行解目标值，避免 `SolveResult` 的「下界不得高于可行解」断言被一个 ULP 触发。

所以表格里的 `gap = 0.0000` 不是「求解器说它收敛了」，而是「重算过的最优值与下界相等」。**`OPTIMAL` 这个状态是经过检查的结论，不是求解器的自称。** 这也是为什么第 5 节的数字可以放心地当作参考值使用（`single_c` / `single_d` 的 657 / 912 就是这样来的）。

---

## 7. 实验：`m2w2d6_formulation_comparison`

脚本：[m2w2d6_formulation_comparison.py](../../projects/02_optimization_models/examples/m2w2d6_formulation_comparison.py)。

在项目目录 `projects/02_optimization_models` 下运行：

```bash
python -m examples.m2w2d6_formulation_comparison
```

实际输出（原样粘贴，总耗时约 40 秒）：

```text
=== 同实例、同预算：tight / loose / alt ===

## 实例 single_a：{'seed': 50, 'jobs': 8, 'machines': 1}，目标 total_tardiness，预算 5.0s
   参考值：85（来源：独立穷举）
   method       组       状态       目标值   best bound    gap    nodes   建模(s)  求解(s)
   milp_tight   root_lp  UNKNOWN          -      0.0000       -    None   0.0102    0.003
   milp_loose   root_lp  UNKNOWN          -      0.0000       -    None   0.0033    0.002
   milp_alt     root_lp  UNKNOWN          -     83.9347       -    None   0.0158    0.011
   milp_tight   limit    OPTIMAL       85.0     85.0000  0.0000     130   0.0051    1.544
   milp_loose   limit    OPTIMAL       85.0     85.0000  0.0000     124   0.0024    1.527
   milp_alt     limit    OPTIMAL       85.0     85.0000  0.0000       0   0.0301    0.204

## 实例 single_c：{'seed': 60, 'jobs': 15, 'machines': 1}，目标 total_tardiness，预算 5.0s
   参考值：657（来源：模型证明）
   method       组       状态       目标值   best bound    gap    nodes   建模(s)  求解(s)
   milp_tight   root_lp  UNKNOWN          -      0.0000       -    None   0.0078    0.002
   milp_loose   root_lp  UNKNOWN          -      0.0000       -    None   0.0129    0.005
   milp_alt     root_lp  UNKNOWN          -    656.0508       -    None   0.1639    0.185
   milp_tight   limit    FEASIBLE     732.0     60.3039  0.9176     305   0.0075    5.042
   milp_loose   limit    FEASIBLE     720.0     57.6507  0.9199   13010   0.0184    5.205
   milp_alt     limit    OPTIMAL      657.0    657.0000  0.0000       0   0.1852    0.625

## 实例 single_d：{'seed': 50, 'jobs': 20, 'machines': 1}，目标 total_tardiness，预算 10.0s
   参考值：912（来源：模型证明）
   method       组       状态       目标值   best bound    gap    nodes   建模(s)  求解(s)
   milp_tight   root_lp  UNKNOWN          -      0.0000       -    None   0.0148    0.006
   milp_loose   root_lp  UNKNOWN          -      0.0000       -    None   0.0157    0.003
   milp_alt     root_lp  UNKNOWN          -    911.7667       -    None   0.1353    0.322
   milp_tight   limit    FEASIBLE     981.0     63.0999  0.9357     207   0.0255   10.081
   milp_loose   limit    FEASIBLE    1019.0     58.8305  0.9423     580   0.0173   10.034
   milp_alt     limit    OPTIMAL      912.0    912.0000  0.0000       0   0.3114    0.810

== 观察 1：root LP bound（formulation 强度）==
  instance   tight      loose      alt        参考最优   alt bound / 参考
  single_a   0.0000     0.0000     83.9347          85     98.75%
  single_c   0.0000     0.0000     656.0508        657     99.86%
  single_d   0.0000     0.0000     911.7667        912     99.97%
  tight 与 loose 的 root bound 完全相同（都是 0）—— Big-M 的紧度没有改变松弛强度；
  alt 的 root bound 直接落在最优值附近 —— 改变松弛强度的是**变量定义**：
  互斥写在时间格点上，LP 没法再让所有工序在同一条时间轴上重叠。

== 观察 2：限时 MIP（搜索行为）==
  instance   method        状态      incumbent   final bound    gap      nodes   求解(s)
  single_a  milp_tight   OPTIMAL         85.0       85.0000  0.0000      130    1.544
  single_a  milp_loose   OPTIMAL         85.0       85.0000  0.0000      124    1.527
  single_a  milp_alt     OPTIMAL         85.0       85.0000  0.0000        0    0.204
  single_c  milp_tight   FEASIBLE       732.0       60.3039  0.9176      305    5.042
  single_c  milp_loose   FEASIBLE       720.0       57.6507  0.9199    13010    5.205
  single_c  milp_alt     OPTIMAL        657.0      657.0000  0.0000        0    0.625
  single_d  milp_tight   FEASIBLE       981.0       63.0999  0.9357      207   10.081
  single_d  milp_loose   FEASIBLE      1019.0       58.8305  0.9423      580   10.034
  single_d  milp_alt     OPTIMAL        912.0      912.0000  0.0000        0    0.810
  这里的 final bound 是**搜索进度**：预算内爬到哪里算哪里，不代表松弛强度；
  要判断「谁更慢」，看 objective 与 gap 是否收敛到 0，以及花费的 nodes。

== 观察 3：tight 与 loose 的逐实例对照（不预设结论）==
  single_a
    incumbent: tight 85 / loose 85（相同）
    nodes: tight 130 / loose 124（loose 更小）
    solve_time: tight 1.544 / loose 1.527（loose 更小）
    状态 tight=OPTIMAL / loose=OPTIMAL，gap tight=0.0000 / loose=0.0000
  single_c
    incumbent: tight 732 / loose 720（loose 更小）
    nodes: tight 305 / loose 13010（tight 更小）
    solve_time: tight 5.042 / loose 5.205（tight 更小）
    状态 tight=FEASIBLE / loose=FEASIBLE，gap tight=0.9176 / loose=0.9199
  single_d
    incumbent: tight 981 / loose 1019（tight 更小）
    nodes: tight 207 / loose 580（tight 更小）
    solve_time: tight 10.081 / loose 10.034（loose 更小）
    状态 tight=FEASIBLE / loose=FEASIBLE，gap tight=0.9357 / loose=0.9423
  node 数在限时搜索里会随运行波动（同一预算跑两次可能不同），
  所以「谁更小」只在同一批测量内部成立，不能外推成一般规律。

== 观察 4：formulation 设计的代价 ==
  instance   alt 建模/求解           tight 建模/求解         alt 合计   tight 合计
  single_a   0.0301s / 0.204s      0.0051s / 1.544s      0.235s     1.549s
  single_c   0.1852s / 0.625s      0.0075s / 5.042s      0.810s     5.050s
  single_d   0.3114s / 0.810s      0.0255s / 10.081s      1.121s     10.107s
  alt 的建模成本比 sequence 模型高一个量级（并随 H 增长），但搜索成本省得更多：
  在这三个实例上，连建模一起算 alt 仍然更快。代价在模型规模：
  变量数随时间界线性增长，时间界很大时先要过规模检查（模块里的 MAX_TIME_INDEXED_VARS）。
```

上面是某一批运行的原始记录（脚本输出不做任何润色）。重跑时 `objective`、`best bound`、`gap` 与 `status` 都一致，而 `nodes` 与各类耗时会有波动 —— 第 5.2 节给出了重跑的对照表，本节后面所有引用都以这一段粘贴的数字为准。

### 7.1 三张表里最值得记住的两行

**第一行**：`single_d` 的 `milp_alt` 在 `0.810s` 内解到 `OPTIMAL 912`，而两个 sequence 模型各花了 `10s` 还没证明最优（`gap 0.94`），最好的可行值是 `981` / `1019`。**同一实例、同一预算约束下，差距是「10 倍时间 + 9% 的解质量」对「1 秒内精确解」**。

**第二行**：`single_a` 的 `milp_loose` 比 `milp_tight` 少 6 个节点、快 0.017s。这个差距小到不值得写进任何结论，但它的方向很重要 —— **它推翻了「tight 一定更快」的直觉**，提醒我们大小实例上的搜索行为必须实测。

### 7.2 本日实验不能说什么

- 不能说「tight 一定比 loose 快」或反过来 —— 三个实例上互有胜负，且节点数会波动；
- 不能说「`alt` 一定更快」—— 本次三个实例都在 `H = 71–180` 的范围内，`H` 更大时它会先碰到规模天花板；
- 不能说「限时结束时的 `best_bound` 代表强度」—— 那是搜索进度，强度只看 `root_lp` 组；
- 不能说「模型最强就能解决一切」—— 本日所有实例都是单机单工序、目标 `ΣTj`，换目标或换结构必须重新测。

---

## 8. 今日练习

1. **练习 1（口径）**：如果只允许跑一组实验（要么 `root_lp`、要么 `limit`），你会保留哪一组？请给出理由，并说明另一组的什么信息会永久丢失。
2. **练习 2（判读）**：`single_c` 的 `milp_loose` 用了 `13010` 个节点、找到的 incumbent 却比 `milp_tight`（`305` 个节点）更好。请给出至少两种可能的解释，并说明如何设计实验区分它们。
3. **练习 3（计算）**：算出三个实例上 `alt` 相对 `tight` 的「总时间加速比」（`tight 合计 / alt 合计`），并说明这个比值随时间界增长的趋势。
4. **练习 4（实验）**：把 `single_a` 的预算从 `5.0s` 改成 `1.0s` 与 `0.5s` 各跑一次，记录 tight 与 loose 的 nodes 与 solve_time。它们还都解到 `OPTIMAL 85` 吗？「谁更小」的结论变了吗？
5. **练习 5（审查）**：有人根据本日观察 2 写道「`milp_tight` 的 final bound 63.0999 高于 `milp_loose` 的 58.8305，所以 tight 的松弛更强」。请指出这句话的错误，并给出正确的表述方式。

---

## 9. 验收清单

- [ ] 能说出 `root_lp` 组与 `limit` 组各自回答什么问题，以及为什么不能混用读数。
- [ ] 能复述本日的强度结论：tight 与 loose 的 root LP bound 都是 `0`，`alt` 是 `83.9347 / 656.0508 / 911.7667`。
- [ ] 能**不**写出「tight Big-M 给出更强的 root LP bound」，并能说明 Big-M 紧度改的是什么（矩阵系数、限时搜索的 incumbent 与 nodes）。
- [ ] 能解释为什么限时结束后的 `best_bound` 是进度值，并举出 `single_d` 上 `63.0999` / `58.8305` 的例子。
- [ ] 能逐实例报告 tight 与 loose 的对照结果，包括 `single_a` 上 loose 更好的那两行。
- [ ] 能说出「节点数会随运行波动」以及它为什么限制了结论的外推。
- [ ] 能算出 `alt` 的建模成本高一个量级、但「建模 + 搜索」合计仍然更快，并能说出它的规模天花板。
- [ ] 能说清 `_finish` 的两道交叉检查（目标值重算、下界一致性）如何让 `OPTIMAL` 可信。
- [ ] 在项目目录下运行 `python -m examples.m2w2d6_formulation_comparison`，能看到三张表与四条观察（耗时约 40 秒，节点数可与本日记录略有出入）。
- [ ] 在项目目录下运行 `python -m pytest tests/test_milp_scheduling.py -q`，其中三 formulation 一致性与 LP 界相关的用例通过。

---

## 10. 自测题

- Q1：为什么同一个字段 `best_bound` 在两组实验里含义不同？
- Q2：本日三个实例上 tight 与 loose 的 root LP bound 分别是多少？这个结果支持什么结论、不支持什么结论？
- Q3：`alt` 的 root bound 与最优值的比值是 `98.75%` / `99.86%` / `99.97%`，这个比值随时间界增长说明了什么？
- Q4：`single_c` 的 `milp_loose` 节点数是 `13010`、`milp_tight` 是 `305`，能否据此说「loose 更慢」？为什么？
- Q5：`single_a` 上 loose 在节点与时间上都更小，能否据此说「loose 更好」？
- Q6：为什么 `alt` 的建模时间是 sequence 模型的一个量级以上，却仍然值得用？
- Q7：`alt` 的规模天花板是什么？在这个天花板之外该用什么？
- Q8：`gap = 0.0000` 与 `status = OPTIMAL` 的关系是什么？`_finish` 在其中做了什么？
- Q9：本日参考值有三种来源（穷举 / 模型证明 / 最好可行值），它们的可信度差别在哪里？
- Q10：如果要写一句「一句话结论」总结本日，你会怎么写？请确保它不含未测量的断言。

### 参考答案

- A1：`root_lp` 组里 LP 解到最优，`best_bound` 就是松弛强度；`limit` 组里求解器在预算内随时可能被截断，`best_bound` 是「搜索爬到哪算哪」的进度值。
- A2：都是 `0.0000`。支持的结论是「在本实例族、`ΣTj` 目标下，Big-M 的紧度不改变 root LP bound」；不支持的结论是「tight 永远不会更差」或「tight 更强」这类一般规律。
- A3：说明 `alt` 的松弛已经接近完美（`H` 越大、工序越多，容量约束的松弛越接近真实问题）；同时也说明 sequence 模型的界恒为 `0`，两者不在同一个量级。
- A4：不能。节点数在限时搜索里会随运行波动，且 `loose` 的 incumbent 更好（`720` 对 `732`）——「节点多」与「解更差」在本实例上并不同时成立；要下结论必须重复多次测量。
- A5：不能。`8` 个 job 的实例规模太小、两边差距（`6` 个节点、`0.017s`）落在波动范围内；只能说「本轮实测中 loose 更省」。
- A6：因为它的强松弛省下的是整棵搜索树（`single_d` 上从 `10s` 未证明变成 `0.81s` 精确解），而建模成本只是一次性的小额开销；总账上它仍然更快。
- A7：规模闸门 `MAX_TIME_INDEXED_VARS = 400_000`（变量数随 `H` 线性增长）。超出后应回到 sequence 模型或使用其它 formulation / 启发式，而不是硬扛。
- A8：`_finish` 重算目标值、检查 `best_bound <= recomputed`、并把亚 ULP 的越界夹平；`OPTIMAL` 表示求解器证明最优，而这份证明的可信度来自上述交叉检查。
- A9：穷举是另一条独立计算路径（最强）；模型证明依赖具体模型与求解器（次之）；最好可行值只是「目前没找到更好的」（最弱，且不能作为下界比较的基准）。
- A10：例如「在本次三个实例上，`alt` 的 root LP bound 达到最优值的 98.75% 以上并把三者都解到 `OPTIMAL`，而两种 Big-M 的 root bound 都是 0；tight 与 loose 的搜索行为互有胜负且节点数会波动 —— 改变强度的是变量定义，不是系数紧度」。要点是不含未测量的一般性断言。

---

## 11. 今日一句话总结

> **本次实测中，tight 与 loose 的 root LP bound 完全相同（都是 `0`），说明 Big-M 紧度不是松弛强度的杠杆；`alt` 的界达到最优值的 98.75% 以上、三个实例全部在预算内解到 `OPTIMAL`，代价是建模成本高一个量级与随时间界线性增长的规模 —— 比强度只看 root LP bound，比搜索行为才看 incumbent / nodes / runtime / gap。**
