# M3 Week 4 周总结：六条工业约束、两个求解器与一张覆盖表

> 笔记：[Day1](Week_4/Day1.md) · [Day2](Week_4/Day2.md) · [Day3](Week_4/Day3.md) · [Day4](Week_4/Day4.md) · [Day5](Week_4/Day5.md) · [Day6](Week_4/Day6.md) · [Day7](Week_4/Day7.md)

## 1. 本周目标与成果

前三周把「两台机器上怎么排」从 JSP 推到 FJSP、再推到带释放时间与交期的版本。
本周把它推到**车间能真的照着执行**的程度：加六条约束、给一份可复核的 KPI、
跑一次全约束端到端实验。交付四层：

```text
资质与人员层   fjsp_cpsat_qualified —— qualification（机器资质）+ worker 能力与容量
全约束层       fjsp_cpsat_full —— 机器相关工时 + 柔性 + 释放/交期 + 换型 + 日历/维护
                                + 资质 + 人员 + 锁定工序
可复核层       fjsp_io/kpi.py 的多目标 KPI + fjsp_io/json_bundle.py 的完整往返存档
证据层         MODEL_COVERAGE 覆盖表（11 行）+ tests/test_week4.py + 六层累加消融
```

两个求解器都注册进 `fjsp_shop.registry`，可被 `configs/month3.json` 直接调用
（交付核对：`describe_missing(['fjsp_cpsat_qualified', 'fjsp_cpsat_full']) == []`）；
每个返回的排程都过 `validate_schedule`，目标值由 `fjsp_core.objective` 独立重算。
另外交付七个可运行脚本（`examples/m3w4d1_*.py` … `m3w4d7_*.py`）与七天笔记。

## 2. 核心概念

| 概念 | 一句话定义 | 它回答的问题 |
|---|---|---|
| `qualification` | `(machine, family)` 合格对 | 这道工序**允许**在哪几台机器上做 |
| `worker` 能力 | `Worker.machine_ids`：这个人会开哪几台机器 | 这道工序**能派给谁** |
| `worker` 容量 | `Worker.capacity`：同时能看几台机器 | 一个人能不能被同时占两次 |
| `batching`（族编码） | 同族相邻对换型 `0`、异族付 `Setup` 分钟 | 哪些工序可以当成一批连续做 |
| `locked operation` | `locked_machine_id` + `locked_start`：已在机的活钉死 | 哪一部分排程**不许改** |
| `urgent order` | `Job.priority` 进有效权重 `w_j · (1 + p_j)` | 谁先谁后（只改目标，不改可行域） |
| `KPI` 口径 | `Σload / Σspan`，不是每台机器利用率的算术平均 | 一列数字是怎么算出来的 |
| JSON 往返 | 实例 + 结果 + KPI 写成一个 bundle 再读回来相等 | 半年后还能不能复现这一格 |
| 覆盖表 | 约束 → 字段 → 归属 → 验证器检查 → 求解器用法（11 行） | 这条约束**真的接上了**吗 |
| `bound` / `gap` | 证明了的下界 / `(目标值 - 下界) / 目标值` | 这个数有没有证据 |

**「可行」与「最优」是两件事，「没定义」与「定义为 0」也是两件事。**
前者决定状态是 `FEASIBLE` 还是 `OPTIMAL`，后者决定换型矩阵缺一行时
验证器报 `setup undefined` 而不是当成 `0`。

## 3. 两个求解器与适用条件

| 方法 | 换型编码 | 覆盖的约束 | 什么时候精确 | 什么时候只是可行解 |
|---|---|---|---|---|
| `fjsp_cpsat_qualified` | 区间膨胀：按 `max_outgoing_setup(族)` 拉长占用，配 `AddNoOverlap` | 全部六条 | 预算内证明时 | 只找到可行解时 |
| `fjsp_cpsat_full` | 精确槽位链：`AddAllowedAssignments` 查表定相邻槽的真实间隔 | 全部六条 | 同上 | 同上 |

**两者的唯一差别是换型编码**，其余五条约束的实现完全共用。编码差别牵动三个方向：

```text
可行域    full = 实例的真实可行域；qualified = 真实可行域的一个**子集**
规模      qualified 更小（不需要槽位变量与查表约束）
分支成本  full 的单位分支更贵（表约束传播时逐个查表）
```

子集关系有一个直接后果：**膨胀模型的最优值一定不低于精确模型的最优值**，
跨模型比下界因此没有「谁搜得更好」的含义。

## 4. 接口约定（API Contract）

```python
# fjsp_shop/constraints2.py —— 本周的两个名字；与前三周同一套注册表
fjsp_cpsat_qualified / fjsp_cpsat_full (instance, spec) -> ShopResult
# spec 带 objective / time_limit / seed；urgency 打开时 priority 进目标函数
# 两者都返回 worker_id 已填好的排程，且排程必过独立验证器

MODEL_COVERAGE: tuple[CoverageRow, ...]   # 11 行，每行 constraint / field / owner
                                          # / validator_check / solver_use

# fjsp_io/kpi.py —— 多目标 KPI
kpi_report(instance, result) -> dict      # cmax / total_tardiness / setup / worker ...
normalize(kpi, reference) -> dict         # 当前 / 参考；分母为 0 时返回 1.0
format_kpi(kpi) -> str                    # 纯 ASCII，可直接进报告

# fjsp_io/json_bundle.py —— 完整往返
make_bundle(instance, result, kpi, verify=True) -> dict   # verify 先过验证器再打包
bundles_equal(a, b) -> list[dict]         # 返回**差异清单**，空列表表示相等
# 读回来不重算 KPI：bundle 是存档，不是缓存
```

## 5. 关键数值证据

**（a）六层累加消融**（同一份工序数据，约束逐层累加；`makespan`、seed `0`、`15` 秒／次、单线程。
来自 `python -m fjsp_experiments.w4_industrial --output artifacts/month3_w4`）：

| 阶段 | 新增约束 | `fjsp_cpsat_full` | 变化 | `fjsp_cpsat_qualified` | 变化 |
|---|---|---:|---|---:|---|
| `base` | 机器相关工时 + 柔性 + 释放/交期 | 9 | — | 9 | — |
| `+setup` | 工序族换型 | 9 | 没有改变 | 13 | **变了** |
| `+calendar` | 机器日历 | 9 | 没有改变 | 28 | **变了** |
| `+qualification` | 机器资质 | 27 | **变了** | 29 | **变了** |
| `+worker` | 次生资源能力 + 容量 | 27 | 没有改变 | 29 | 没有改变 |
| `+locked` | WIP / 锁定工序 | 31 | **变了** | 35 | **变了** |

单调性核对（目标值随约束增加不下降）：两条链都**通过**。四行「没有改变」的原因并不同：

```text
+setup (full)      基础最优解同族连排 —— 换型约束在最优解上处处取等，一个点都没砍掉
+calendar (full)   基础最优解收尾 9 < 第一个窗的 10 —— 约束在最优解上留了 1 分钟余量
+worker (两条链)   最优排程四道工序都在 M1 上，W1 一人按顺序看完即可，其余两人全程空闲
```

**「没有改变」不等于「约束没接上」，也不等于「这个实例对这条约束不敏感」。**
判据是「约束在最优解上取不取等」：取等的一层，换型矩阵变大一点就会立刻咬住；
有余量的一层，要最优值涨过窗口边界才会咬住。`+worker` 那两行属于**原因一**
（最优解恰好不需要额外的人）；而 `+setup`、`+calendar` 在 `qualified` 上的「变了」
**混杂了原因二** —— 膨胀编码本身比实例更紧，这一部分变化不能全部算到实例头上。

**（b）膨胀编码多收的钱可以逐个指认。** `+locked` 层两个求解器的差值是 `4`：

```text
full        A@M1[0,4)  B@M1[4,9)   C@M1[20,26)  D@M1[26,31)     收尾 31
qualified   A@M1[0,4)  B@M0[4,10)  C@M1[20,26)  D@M1[30,35)     收尾 35
```

`C` 与 `D` **都是 `F1` 族，真实换型 `0`**，精确版让它们紧贴，膨胀版却按
`max_outgoing(F1) = 4` 要求了 4 分钟间隔：**多收的 4 分钟落在两道同族工序之间。**

**（c）两个求解器在 batch 实例上的正面对比**（seed `0`；两个预算各测一次）：

| 预算 | 实例 | 目标函数 | `fjsp_cpsat_full` | 下界 | `fjsp_cpsat_qualified` | 下界 |
|---:|---|---|---:|---:|---:|---:|
| `8` 秒 | `ind_worker` | `makespan` | `FEASIBLE` 108 | 41 | `FEASIBLE` **98** | 41 |
| `8` 秒 | `ind_qualified` | `weighted_sum` | `FEASIBLE` 80 | 34 | `FEASIBLE` **77** | 36 |
| `15` 秒 | `ind_worker` | `makespan` | `FEASIBLE` 101 | 41 | `FEASIBLE` **97** | 41 |
| `15` 秒 | `ind_qualified` | `weighted_sum` | `FEASIBLE` 78 | 34 | `FEASIBLE` **75** | 36 |

四行全是 `FEASIBLE`：两个预算对这两个实例都不够证明最优，所以表里的数字
**全是「预算内最好的可行解」，不是最优值**。短预算下膨胀模型两对比较都赢 ——
它不是靠可行域赢的，是靠**出手快**赢的：模型更小、单位分支更便宜。
这四行是各一次观测：预算用尽时搜索停在哪里由墙钟决定，重跑可能得到别的可行解
（实测 `ind_qualified` 的 `qualified` 一行出现过 `76` 与 `77`）；稳定的是「全是 `FEASIBLE`」这个判断。

**（d）界与间隙。** `ind_worker` 配置在 `10` 秒下是 `FEASIBLE 108`、下界 `41`，
相对间隙 `(108 - 41) / 108 = 62.04%`；同实例同 seed 的另两次运行：
`30` 秒 → `FEASIBLE 97`（下界 `45`，预算用尽未证完）、`60` 秒 → `OPTIMAL 97`（求解 `30.78` 秒）。
**状态是这一次运行的属性，不是方法的天性。**

**（e）预求解的代价。** `ind_qualified` 配置、`5` 秒预算、只改 `cp_model_presolve`：
`True` → `UNKNOWN`（目标值、下界、分支数**全空**，求解 `4.26` 秒）；
`False` → `FEASIBLE 88`（下界 `34`、分支 `210085`、求解 `5.01` 秒）。
两行的墙钟都接近预算，**只有分支数告诉我们发生了什么**。

## 6. 手算与独立复核

```text
手算下界      基础层的三类下界（最长工序 / 最长订单链 / 机器负载）都是 9 = 实测最优值
手算下界      +qualification 层：资质表没有 (M0, F1) -> C、D 只能上 M1，且这一对的最小占用
              （同族紧贴）是 6 + 5 = 11 分钟，比 M1 第一个窗的 10 分钟还长
              -> 要么 C、D 整体等第二个窗（16 + 11 = 27），要么 C 占住第一个窗而 A、B、D
              全落到第二个窗（最少 29）-> 下界 27 = 实测
手算下界      +locked 层：C 钉在 M1 开工 20、占 6 分钟，后继 D 最早 26 开工 -> 31 = 实测
手算区间      worker 那两层：W1 的四段占用 [0,4) [4,9) [16,22) [22,27) 互不重叠，容量 1 够用
手算 KPI      利用率总和 0.740741，逐台算术平均只有 0.370371 —— 口径差一倍，用前者
手算权重重算  同一份排程：solver 目标 10、evaluate 报 5 —— 差的正是 (1 + priority) 这一维
往返核对      bundle 读回来 bundles_equal = []；改一个字段后差异清单 = ['result', 'result.schedule']
```

`recompute_objective(...)` 是本周加的一处**口径补丁**：`evaluate` / `weighted_tardiness`
没有 `priority` 这一维，而求解器打开 `urgency` 时用的是有效权重 `w_j · (1 + p_j)`。
两者对同一份排程会给出不同的数，所以目标值必须由感知 `urgency` 的那条路径重算 ——
这不是「谁算错了」，是**同一份排程在两个口径下的两个值**，报表里不能混用。

## 7. 测试证据

```bash
cd projects/03_industrial_fjsp
python -m pytest -q
# 181 passed in 32.38s
```

本周新增用例覆盖：资质拒绝、人员能力与容量拒绝（**相接合法**：`[start, end)` 半开区间）、
锁定工序的执行、`fjsp_cpsat_full` 在全约束实例上返回过验证器的排程、JSON bundle 往返相等、
以及**覆盖表完整性** —— 逐行断言每个列出的字段确实是 `owner` 上的字段、
确实被验证器或求解器读过。注册表核对：

```text
available() 里含 fjsp_cpsat_qualified 与 fjsp_cpsat_full
describe_missing(['fjsp_cpsat_qualified', 'fjsp_cpsat_full']) = [] —— 两个名字都在
```

## 8. 确定性契约

```text
证明完成的运行（OPTIMAL）：相同实例 + 相同 spec -> 相同排程、相同目标值、相同分支数
预算用尽的运行（FEASIBLE / UNKNOWN）：只有「走过的那条路径」是确定的，
        停在哪里由墙钟决定 —— 可行解、下界、分支数都只是观测值（详见 Day 6 第 7.1 节）
CP-SAT：num_search_workers = 1，random_seed 由 spec["seed"] 固定
全约束路径默认关预求解并降低线性化级别 —— 这是「在 15 秒预算下的选择」，不是通用默认值
迭代顺序：一律按 instance.operations 的原始顺序建变量，不依赖 dict 的插入顺序
耗时与 bundle 长度：每行读数都会变（bundle 长度随 build_time / solve_time 的位数浮动）
```

## 9. 选型建议

```text
实例里有换型、且同族工序多   -> fjsp_cpsat_full（精确槽位链，可行域更大）
实例很小或预算极短           -> fjsp_cpsat_qualified（模型小，出手快）
需要 worker_id / 资质判定    -> 两个都做，只是换型编码不同
任何情况下报数字             -> 同时报 status + best_bound，别只报目标值
```

每条建议的依据与边界：第 1 条因为精确槽位链不让同族工序白付钱（第 5(b) 节那 `4` 分钟）；
第 2 条的依据是第 5(c) 节的 `8` 秒与 `15` 秒两次实测，**更长预算下会不会反转本次没有测量**，
所以只写「预算极短」；第 3 条因为资质与人员与换型编码无关；第 4 条因为跨模型不能直接比下界
（`F' ⊆ F` 决定了膨胀模型的下界天然更高，只有**同一个模型内部**的界才有「搜索进展」的含义）。

## 10. 已知局限

```text
覆盖范围：模型实现了 11 条约束；实例里若带有本模型没有建模的约束，两个求解器一律先拒绝
批处理：模型里**没有 batch 对象**，用的是「同族相邻对不付换型」的族编码 ——
        它能表达「同族连排不花钱」，不能表达「一个批有固定开工时刻」「批的大小有上限」
        「批内必须凑满 N 件」；能表达与不能表达的边界见 Day 2 第 3 节
最优性证据：全约束实例只有 CP-SAT 自证一档，没有独立穷举可与它互证
目标值与优先级：evaluate / weighted_tardiness 没有 priority 这一维，
        重算必须走 recompute_objective，否则同一份排程会读出两个数
预求解：全约束路径默认关闭它，这是 15 秒预算下的选择；换到很长预算下默认值应翻回来
长预算排序：两个求解器在 8 秒与 15 秒下的排序测量过，更长预算下未测量
```

## 11. 遗留问题

| # | 问题 | 状态 |
|---|---|---|
| 1 | 膨胀编码多收的钱能不能省掉？ | 能，但要换精确槽位链；代价是模型规模与单位分支成本，两条路都留着 |
| 2 | 目标值不动，是约束没生效吗？ | 不是：要分成「最优解恰好避开」与「模型比实例更紧」两种原因（Day 6 第 3.3 节） |
| 3 | 下界能不能跨模型比？ | 不能。`F' ⊆ F` 决定了膨胀模型的下界天然更高 |
| 4 | KPI 的归一化有没有别的口径？ | 只实现了「当前 / 参考」；百分位或历史基线类需要跨实例统计，样本量不够 |
| 5 | 紧急订单只能改权重吗？ | 本周只做了权重版；「截止时间硬约束」版没有实现 |
| 6 | `FEASIBLE` 的数字能进报告吗？ | 能，但状态与下界必须一起出现，否则读者无法判断可信度 |

## 12. 待个人完成

闭卷重做两件事：一是第 5(a) 节那张消融表的**手算版** —— 在没有求解器的情况下逐层推出
`9 / 9 / 9 / 27 / 27 / 31`，特别是 `+qualification` 那一跳（为什么下界从 9 涨到 27）
与 `+locked` 那一跳（为什么是 31）；二是第 5(c) 节那两个求解器的短预算对比，
说清「膨胀模型可行域更小却解出更小目标值」这一点的机制。
两件事都不看笔记写出来，才算把本周的两条主线（约束如何进模型 / 读数如何被证据约束）收进手里。
