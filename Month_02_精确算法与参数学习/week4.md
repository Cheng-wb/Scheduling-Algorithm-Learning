# M2 Week 4 周总结：强化、初解、诊断、预算与统一接口

> 笔记：[Day1](Week_4/Day1.md) · [Day2](Week_4/Day2.md) · [Day3](Week_4/Day3.md) · [Day4](Week_4/Day4.md) · [Day5](Week_4/Day5.md) · [Day6](Week_4/Day6.md) · [Day7](Week_4/Day7.md)

## 1. 本周目标与成果

本周把「工程手段」这一层补齐：同质机器对称性与强化（对称破缺、冗余约束、有效不等式）、M1 规则解接入为 warm start（`hint` / `objective_cutoff` / 前缀固定）、数值缩放与不可行诊断（`span`、极小冲突集）、求解预算的配置与终止原因记录、以及三类方法共用的统一结果接口。

两个新模块 [strengthening.py](../projects/02_optimization_models/opt_models/strengthening.py)（960 行）与 [diagnostics.py](../projects/02_optimization_models/opt_models/diagnostics.py)（503 行），加七个示例脚本与周驱动 [w4_engineering.py](../projects/02_optimization_models/opt_experiments/w4_engineering.py)。产物在 `artifacts/month2_w4/`：`report.md` 四节、`results.csv` **29 行记录 / 0 失败**、`metadata.json`（预算口径 + 源码哈希）、`scaling.json`。

本周**最重要的产出不是手段奏效，而是一套判据**：强化不得改变最优值、效率要看冲突数与同预算结果、报告必须无改进也如实分析。按这套判据，本周交出的多数手段是**负收益**，且全部如实记录。

## 2. 核心概念

| 概念 | 一句话定义 | 读它回答的问题 |
|---|---|---|
| `symmetry breaking` | 用约束把等价的镜像解裁到只剩一个 | 同质机器上重复搜索能不能去掉 |
| `redundant constraint` | 被其余约束蕴含、不改变可行域的约束 | 加了它能不能帮求解器传播 |
| `valid inequality` | 对全部（整数）可行解成立的不等式 | 能不能安全地收紧松弛 |
| `warm start` / `MIP start` / `hint` | 把已知可行解当**建议**交给求解器 | 搜索能不能提前找到好解 |
| `variable fixing` | 固定一部分变量后重解 | 这是**限制可行域**，不是强化 |
| `numerical scaling` | 系数之间的量级比（`span`） | 模型数值是否健康 |
| 极小冲突集 | 去掉任一个假设就不再不可行的集合 | 不可行到底卡在哪几个假设上 |
| `termination reason` | 求解器为什么停下 | 是「证完了」还是「时间到了」 |
| `identical machines` | 加工性能完全相同的并行机 | 什么条件下才允许做对称破缺 |

**三层知识要分开**：对称性的定义、`Σ C_o <= m·Σp` 在有释放时间时**不成立**（Week 4 的真 bug）、以及「本批实例上破缺推高冲突数」——依次是定义、事实、实验观察。

## 3. 七天链路与三条判据

```text
Day 1 识别对称性 → 加破缺/冗余约束     判据：最优值不得改变
Day 2 规则初解 → hint / cutoff / fixing  区分：建议、有效不等式、限制
Day 3 缩放与诊断 → span / 冲突集          纪律：冲突是相对一组假设的
Day 4 预算与终止原因 / workers / seed     纪律：解出 X 必须带预算
Day 5 统一 SolveResult 接口               纪律：没有 bound 写 None，不写 0
Day 6 同实例同预算比较 → 选择矩阵         纪律：跨方法只按 objective 排序
Day 7 复盘 → week4.md + 月末验收对应表
```

三条判据：**正确性判据**（强化不得改变最优值，改变即建模错误）、**效率判据**（同实例比冲突数 / 节点数 / 迭代数 + 同预算的目标值，不靠单一耗时）、**报告判据**（无改进也如实分析，结论必须带实例、目标与预算）。

顺序不能换：没有统一接口就没有共同列可比，所以 Day 5 必须排在 Day 6 之前。

## 4. 消融结果一：强化（同质并行机，`Cmax`）

| 实例 | `sym=0_red=0` | `sym=0_red=1` | `sym=1_red=0` | `sym=1_red=1` |
|---|---:|---:|---:|---:|
| par_6x3 目标 / 冲突数 | 27 / 190 | 27 / 370 | 27 / 377 | 27 / 529 |
| par_10x3 目标 / 冲突数 | 29 / 898 | 29 / 701 | 29 / 1461 | 29 / 1574 |

**正确性通过**：两实例的四个变体目标值分别恒为 27 与 29。这是判据本身——若某个变体给出别的数，说明强化把最优解切掉了，是建模错误（本周的冗余约束 bug 正是这类错误：`Σ C_o <= m·Σp` 在有释放时间的实例上不成立）。

**效率是负收益**：`par_6x3` 全开 529 / 基线 190 = **2.78 倍**；`par_10x3` 全开 1574 / 基线 898 = **1.75 倍**。且 `par_10x3` 的 `sym=0_red=1`（701）低于基线、全开（1574）高于基线 75%——**同一手段在不同变体上方向相反**，所以不能凭单点下结论。诚实结论：本批小实例上破缺与冗余约束没有收益。

## 5. 消融结果二：warm start（单机，`ΣT`）

| 实例 | 规则种子 | `hint_only` | `cutoff_only` | `cutoff_and_hint` | `fix_prefix_3` | `fix_all` |
|---|---:|---:|---:|---:|---:|---:|
| sgl_8x1 | 85 | 85 | 85 | 85 | 85 | 85 |
| sgl_12x1 | 532 | 532 | 532 | 532 | 532 | 532 |
| `sgl_10x1_seed_suboptimal` | 283 | **271** | **271** | **271** | 283 | 283 |

三种机制必须分开讲：`set_hint` 只是**建议**（不保证被采纳）；`objective_cutoff` 加的是 `obj <= UB` 这条**有效不等式**（不切掉最优解）；前缀固定**改变可行域**，是邻域搜索而不是强化。

决定性证据只在第三个实例上（种子 283，10 作业）：`hint` / `cutoff` 都到 271（相对种子改善 `(283-271)/283 = 4.24%`），而 `fix_prefix_3` 与 `fix_all` 停在 **283** ——初解不是最优时，前缀固定把解**封顶在初解处**。另两个实例的规则种子恰好等于最优值，五个变体并列，因此**证明不了**限制的代价；这一点必须写明，否则会误读成「fixing 无害」。

## 6. 诊断与预算的关键数值

```text
缩放不变的是比值：scale = 1 / 1/10 / 1/100 时 span 恒为 33.5，horizon 67 → 670 → 6700
模型间可比的是 span：紧模型 33.5  vs  Big-M 201.0（402 / 2 = 201）——差 6.00 倍
极小冲突集随假设变化：slack = 0.5 / 1 / 2 → 1 / 2 / 3 个作业，求解次数 4 / 6 / 8（= 2|集| + 2）
预算决定终止原因：1 s → 1519（界 65.0982，gap 0.9571）；10 s 与 30 s → 968（界 65.5093，gap 0.9323）
                   3 s 档抖动：三次重复给出 1519 / 968 / 968；四档全部 FEASIBLE，从未证明最优
两类时间不可合并：build_time 0.016 ～ 0.022 s，占 wall 的 2.1% → 0.1%（占比下降只因分母变大）
                   parallel_24 的时间索引模型建模约 0.53 s，超过 5 秒预算的 10%
```

`gap` 从 0.9571 到 0.9323 只降 0.0248，而目标值从 1519 降到 968（降 36.3%）——**`gap` 的平稳会掩盖质量的大幅变化**，这也是不能只看 `gap` 的原因之一。

## 7. 选择矩阵（由四组同实例同预算实测归纳）

| 情形 | 推荐 | 依据 |
|---|---|---|
| 规模小、必须保证最优 | 时间索引 MILP 或 CP-SAT | `single_12` / `single_20` 上 `milp_alt` 0.749 s / 0.980 s 证明最优 |
| 单机、排序型、目标含迟交 | 序列 MILP 建模最直接，但界弱；有预算压力就换时间索引 | 同一实例界 65.5 对 903（13.8 倍），5 s 未证明对 0.98 s 证明 |
| 并行机、只看 `Cmax`、规模不大 | CP-SAT 区间 + `AddNoOverlap` | `parallel_12` 上 0.047 s 证明最优 |
| 多工序 / JSP 型 | CP-SAT 的 precedence + 每机器 `NoOverlap` | Week 3 的模型 |
| 大规模、预算内搜不完 | 先给规则可行解，再让精确方法在剩余预算改进；`gap > 0` 是常态 | `parallel_24` 上三种精确方法均未证明最优 |
| 只要一个能用的解、且要快 | 启发式；但**没有 `bound`**，不要与精确方法并列 `gap` | 全部启发式行 `gap = None`，0.001 ～ 0.002 s |
| 需要可复现的对照实验 | 固定 `workers = 1`、固定 `seed`、逐次记预算 | Day 4 的 3 s 档抖动 |

跨方法的排序依据只有 `objective` + `status`。**`gap` 不可跨方法比较**：`parallel_24` 上 `cpsat_parallel`（71 / 界 24.0 / gap 0.6620）解更好但 gap 更大，`milp_alt`（74 / 界 42.2 / gap 0.4293）解更差但 gap 更小。

强化手段（破缺、冗余约束、warm start、前缀固定）**不在这张表的推荐列**：本批实例没有测出收益，只能写成「在什么条件下可能有益，本批未测出」。

## 8. 接口约定（API Contract）

```python
# opt_solvers/result.py —— 统一结果（M2 共享地基，本周只解释与验收，不重写）
STATUSES = ("OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN", "MODEL_INVALID",
            "FEASIBLE_OR_UNKNOWN", "FAILED", "NOT_SOLVED")
FEASIBLE_STATUSES = ("OPTIMAL", "FEASIBLE", "FEASIBLE_OR_UNKNOWN")
SolveResult(method, status, objective=None, best_bound=None, schedule=None,
            build_time=0.0, solve_time=0.0, iterations=None, detail={})
    # frozen + slots；__post_init__ 校验状态白名单与 best_bound <= objective + 1e-6
    # wall_time = build_time + solve_time（属性，不是字段）
    # gap = (objective - best_bound) / max(1, |objective|)；任一端为 None → None（不是 0）
    # proven_optimal 只看 status == "OPTIMAL"；to_row() 的 None 保持为空
validate_result(instance, result) -> list[str]   # 挂 M1 的 schedule_errors；schedule 为 None 时返回 []
require_feasible(instance, result) -> Schedule   # 不通过直接抛异常

# opt_models/strengthening.py —— 本周建模层
detect_machine_symmetry(instance) -> SymmetryReport
add_load_ordering(machine_vars) -> m - 1 行          # 只对同质机器
add_redundant_bounds(...) -> 1 + n 行
solve_single_machine(instance, spec, *, set_hint, objective_cutoff,
                     fixed_prefix, hint_schedule, method) -> SolveResult

# opt_models/diagnostics.py —— 本周诊断层
scaling_report(instance) -> ScalingReport            # span 是比值，缩放不变
rescale_instance(instance, factor) -> Instance        # 整数性保持
diagnose_infeasibility(instance, ...) -> ConflictReport   # 求解器充分集 + 删除过滤极小集
```

统一签名 `solve_fn(instance, spec) -> SolveResult`，方法名经 `registry` 注册（本周合计 14 个方法）。**缺值一律 `None`**：启发式没有 `bound`，`best_bound` 与 `gap` 恒为 `None`——把 `best_bound` 填成目标值会让 `gap` 恒为 0，是最严重的伪证据。

## 9. 测试与产物证据

`tests/test_strengthening.py`（639 行）用六个手算实例覆盖本周：`parallel_hand_instance`（p=[3,3,2,2,2] → 6）、`parallel_release_instance`（→ 13）、`asymmetric_parallel_instance`（→ 8）、`single_hand_instance`（`ΣT = 2`）、`single_edd_trap_instance`（EDD 4 对最优 3）、`single_release_instance`（`ΣT = 3`）。关键用例：`test_symmetry_breaking_keeps_optimum`、`test_parallel_optimum_matches_independent_oracle`、`test_symmetry_rows_are_skipped_when_machines_differ`、`test_tardiness_objective_skips_machine_symmetry`、`test_fixing_is_a_restriction_so_it_can_only_be_worse_or_equal`、`test_cutoff_is_a_valid_inequality_not_a_change_of_problem`。

全仓测试：**216 passed, 3 warnings**（`python -m pytest -q`，约 9.7 s）。产物：`artifacts/month2_w4/` 的 `report.md`（60 行 / 四节）、`results.csv`（29 行 × 19 列，含 `symmetry_breaking` / `redundant_constraints` 布尔列与 `reported_conflict` / `minimal_conflict` / `reduction_steps`）、`metadata.json`（`budget_unit = one solver call under an explicit time limit` + 源码哈希）、`scaling.json`。

## 10. 已知局限

- **只在小实例上验证**：4 ～ 24 作业。所有效率结论（破缺负收益、3 s 档抖动）都只在这批实例上成立。
- **没有独立测试集**：全部调参结论都在生成实例上得出，没有留出验证集。
- **`diagnostics.py` 的 pytest 覆盖已补上**：`tests/test_diagnostics.py` 16 个测试函数，覆盖 span 的比值不变性、`rescale_instance` 的结构保持、交期公式、IIS 的不可约性验证、以及失败分支（缺 `deadlines` → `FAILED`；预算过小 → `UNKNOWN`；可行 → 无冲突且排程过验证器）。整文件 1.2 秒跑完——测试本身的速度就是纪律，因为删除过滤会对冲突集反复重解。**仍有一处未直接覆盖**：「求解器报 INFEASIBLE 但归因不到任何假设」那条分支需要一个通不过 `validate_instance` 的实例才能构造，目前只能靠代码审查确认其存在，没有伪造用例假装覆盖。
- **删除过滤的代价随实例规模线性增长**：每试一个假设就要重解一次（`solves = 2|极小集| + 2`），所以实例要小、预算要短。
- **冲突是相对一组假设的**：求解器无法判断成因是坏数据还是坏模型；极小冲突集也**不唯一**（本周已给出第二组同样极小的集合）。
- **`workers` / `seed` 只有单点对照**：`workers = 1` 与 `4` 在这一行上结果相同，不能推广成「workers 不影响结果」。
- **例子脚本两处措辞/写法瑕疵**：`m2w4d5` 第 5 节括号文本是固定模板（本次状态是 `FEASIBLE` 而非 `OPTIMAL`）；`m2w4d6` 的 `min(..., key=lambda item: item[1].objective or float("inf"))` 在目标值为 `0.0` 时会误判。

## 11. 遗留问题

1. 破缺与冗余约束在小实例上是负收益——在更大实例（≥ 50 作业）或**非平凡目标**下是否翻转？需要一次跨规模实验。
2. 前缀固定封顶在初解处（283 对 271）。改成**局部邻域**（只固定一部分、允许重排）能否突破？这是局部搜索的入口。
3. 3 s 档的抖动是机器负载还是求解器初始化开销？需要固定机器状态并重复 20 次以上的测量才能分辨。
4. 时间索引模型的 `build_time` 在 24 作业上已占预算 10%，更大规模会不会使建模成为瓶颈？需要一次建模时间的规模扫描。
5. ~~`diagnostics.py` 的测试覆盖需要补~~ —— 已补 `tests/test_diagnostics.py`（16 个测试函数），四条失败分支中三条可直接构造并已覆盖，第四条「无可归因假设」在当前 API 下无法构造，已在测试文件里如实注明而不是伪造用例。

## 12. 待个人完成

- 在**自选实例**（不是仓库里的生成实例）上重跑一次预算扫描，确认「同一 seed 不保证同一轨迹」这条是否同样出现。
- 用 `rescale_instance` 把自选实例缩放三档，亲手确认 `span` 不变而 `horizon` 等比变化。
- ~~补一个 `diagnostics.py` 的 pytest 文件~~ —— 已完成（见第 11 节）。
- ~~把 `examples/m2w4d6_selection_matrix.py` 的排序键改成显式判 `None`~~ —— 已改为显式判 `None`。它原本的写法是 `key=lambda item: item[1].objective or float("inf")`，**目标值为 `0.0` 时会被当成假值**，于是这个「最好的解」永远选不上（`0.0 or inf` 得到 `inf`）。当前实例集里没有目标为 0 的案例，所以这个 bug 一直没暴露——这正是「手算/边界用例不可省」的又一个例子。
- 读完 `artifacts/month2_w4/report.md` 全文四节，逐条对上本周七天的笔记，找出任何一处数字不一致。
