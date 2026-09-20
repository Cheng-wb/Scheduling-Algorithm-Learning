# M3 Week 3 周总结：工业约束 I —— 释放时间、换型、日历与多目标

> 笔记：[Day1](Week_3/Day1.md) · [Day2](Week_3/Day2.md) · [Day3](Week_3/Day3.md) · [Day4](Week_3/Day4.md) · [Day5](Week_3/Day5.md) · [Day6](Week_3/Day6.md) · [Day7](Week_3/Day7.md)

## 1. 本周目标与成果

Week 1～2 的模型只会排「谁先谁后、在哪台机器」。本周把四种真实约束加进来：

```text
释放时间 / 交期    订单的时间属性：起点域下界与 ΣT，不新增硬约束
sequence-dependent setup   相邻对之间的时间间隔，需要新的编码（紧前弧）
日历 / 计划维护    机器自己的时间表，需要新的几何（可用区段 = 日历减维护）
多目标            α·Cmax + β·ΣT + γ·setup，一个标量目标 + 一套归一化口径
```

三个模型注册进 `fjsp_shop.registry`：`fjsp_cpsat_setup`、`fjsp_cpsat_calendar`、
`fjsp_cpsat_multiobj`，签名统一为 `solve(instance, spec) -> ShopResult`，返回的排程都过
`fjsp_core.schedule_validation.validate_schedule`，`breakdown` 由 `objective_breakdown` 独立重算。
另外交付七个可运行脚本、七天笔记、`tests/test_week3.py`，以及实验驱动
`fjsp_experiments/weight_sensitivity.py`（写进 `artifacts/month3_w3/`：`results.csv` 36 行 × 21 列、
`metadata.json`、`report.md`、`schedules.json`）。**输出目录非空时驱动直接拒绝**——
那张表的价值在于「同样的输入得到同样的表」。

## 2. 核心概念

| 概念 | 一句话定义 | 它回答的问题 |
|---|---|---|
| 释放时间 / 交期 | 订单第一道工序的最早开工时刻 / 承诺完工时刻 | 这批料最早什么时候到、迟了没有 |
| 总迟交 `ΣT` | `Σ_j max(0, C_j - d_j)`，不带订单权重 | 迟了多少 |
| 加权和 `weighted sum` | `α·Cmax + β·ΣT + γ·setup` | 三个分量怎么合成一个数 |
| 交换率 | 归一化后「1 单位 `ΣT`」值多少单位 `Cmax` | 多花 1 分钟迟交能换回几分钟完工 |
| `sequence-dependent setup` | 换型时间由「前一道是谁」决定，不是工序固有属性 | 顺序本身要花多少钱 |
| `calendar` / `maintenance` | 机器可用区段 = 日历窗扣掉维护窗 | 这台机器什么时候能开工 |
| `split` / `blocker` | 日历的两条编码（每窗一个布尔 / 起点域 + 停机区间） | 同一可行集怎么写进模型 |
| 归一化 `normalization` | 各分量除以一个分母再加权（`none` / `trivial` / `ideal`） | 数值尺度不同的分量怎么比 |

**「最优」是相对于目标说的。** 只把 `Cmax` 写进目标，模型就没有义务在并列解里挑 `ΣT` 最小的那一条（Day 6 的 `(63, 67, 3)` 与 `(63, 55, 3)`）。

## 3. 三个模型与适用条件

| 模型 | 日历编码 | 收得下什么 | 有界吗 |
|---|---|---|---|
| `fjsp_cpsat_setup` | `blocker` | 释放时间 / 交期 / 换型 / 日历 / 维护 | 目标单一时有；加权和需口径 `exact` |
| `fjsp_cpsat_calendar` | `split` | 同上（与 `setup` 同一个模型的另一条编码） | 同上 |
| `fjsp_cpsat_multiobj` | `blocker` | 同上，且目标是 `weighted_sum` | 归一化非 `exact` 时 `best_bound = None` |
| `fjsp_cpsat` / `fjsp_shortest` / `fjsp_random` | — | 只认纯 FJSP + 释放时间 | 前两者无 |

上一代模型遇到带工业约束的实例一律**拒收**：
`plain FJSP only (release times are supported); unsupported constraints: calendars, maintenances, setups`。
**这是可诊断的失败**：异常点名了三个不认识的约束，调用方据此换模型，而不是拿到一条少算换型、跨过停机段的排程还以为它能执行。

**`split` 与 `blocker` 共用同一份几何**（可用区段 → `fitting_windows` → `starting_domain`），
所以可行集相同、最优值必然相同；差的只是规模——`C1a` 是 `11/20` 与 `7/12`，
`G201` 是 `348/411` 与 `298/292`。**换模型会改可行集，换编码不会。**

## 4. 接口约定（API Contract）

```python
# fjsp_shop/registry.py —— 与 Week 1～2 同一套注册表
available() -> list[str] / get(name) / load_week_modules()
fjsp_cpsat_setup / fjsp_cpsat_calendar / fjsp_cpsat_multiobj (instance, spec) -> ShopResult

# spec：weights 必须放在 spec["weights"] 里，顶层的 alpha / gamma 会被忽略
{"objective": "weighted_sum", "time_limit": 10.0, "seed": 0,
 "weights": {"alpha": 1.0, "beta": 0.25, "gamma": 0.0},
 "normalization": {"mode": "trivial"}}          # none / trivial / ideal

parse_weights(spec) -> Weights                 # 缺省 (1.0, 0.0, 0.0)
Normalization.scaled(weights) -> (α', β', γ', exact)

# 结果字段
result.breakdown                      # {cmax, total_tardiness, setup, weighted_tardiness}
result.best_bound                     # 只有 exact 口径才允许换算回原始单位
result.detail["model_size"]           # {variables, constraints, horizon}
result.detail["calendar_mode"]        # split / blocker
result.detail["failure_reason"]       # 建模期判死时才有内容
```

`normalization.mode = "ideal"` 要求调用方给出三个**正数**分母，否则 `ValueError`；未知模式同样报错。
归一化系数全程不取整（`OBJ_SCALE = 1_000_000` 只用于把浮点权重变成整数系数），所以只要没有舍入，
`exact` 为真、`best_bound` 可以按口径换算回原始单位；否则 `best_bound = None`、报告状态降级为
`FEASIBLE`，`detail["optimality_scope"]` 写明「归一化加权和，不是报告的目标」。

## 5. 关键数值证据：权重敏感性表

实例 `T`（2 机器 4 订单，每单 1 道工序，`F0->F1 = 1`、`F1->F0 = 8`），6 组权重 × 3 种口径共 18 行，
由 `fjsp_experiments/weight_sensitivity.sweep` 生成（与 `artifacts/month3_w3/` 的落盘结果同源）。
格子里是「排程 `(Cmax, ΣT, setup)` / 归一化加权和」：

| 设置 | `(α, β, γ)` | 口径 `none` | 口径 `trivial` | 口径 `ideal` |
|---|---|---|---|---|
| `cmax_only` | (1, 0, 0) | (9, 9, 2) / 9.00 | (9, 9, 2) / 0.1800 | (9, 9, 2) / 1.0000 |
| `tardiness_light` | (1, 0.25, 0) | (9, 9, 2) / 11.25 | (9, 9, 2) / 0.1996 | (16, 2, 9) / 2.0278 |
| `tardiness_heavy` | (1, 4, 0) | (16, 2, 9) / 24.00 | (16, 2, 9) / 0.3896 | (16, 2, 9) / 5.7778 |
| `tardiness_only` | (0, 1, 0) | (16, 2, 9) / 2.00 | (16, 2, 9) / 0.0174 | (16, 2, 9) / 1.0000 |
| `setup_only` | (0, 0, 1) | (13, 13, 1) / 1.00 | (13, 13, 1) / 0.0312 | (13, 13, 1) / 1.0000 |
| `balanced` | (1, 1, 1) | (9, 9, 2) / 20.00 | (9, 9, 2) / 0.3208 | (13, 9, 1) / 6.9444 |

逐行手算校验 `|α·Cmax + β·ΣT + γ·setup - 求解器报的原始加权和|` 最大偏差 `0.0e+00`
（归一化那一列没有自动校验，靠 Day 7 第 5.2 节的手算逐位对上）。

三组分母与翻转点（`ΔCmax = +7`、`ΔΣT = -7` 大小相等，所以 `β* = d_ΣT / d_cmax`）：
`none` 的分母是 `(1, 1, 1)` → `β* = 1.0000`；`trivial` 是 `(50, 115, 32)` → `2.3000`；
`ideal` 是 `(9, 2, 1)` → `0.2222`。`β = 0 / 0.25 / 4` 依次选出
`S1 / S1 / S2`（前两种口径）与 `S1 / S2 / S2`（`ideal`），其中 `S1 = (9, 9, 2)`、
`S2 = (16, 2, 9)`；`(13, 9, 1)` 只在 `ideal` 口径下出现。读表三条：

- **口径决定交换率，不决定「对错」**：`none` 下 1 单位 `ΣT` 值 1 单位 `Cmax`、`trivial` 下值
  `0.4348`、`ideal` 下值 `4.5`；同一个 `β = 0.25` 在 `none` 下选 `S1`、在 `ideal` 下选 `S2`。
- **`none` 那列的两个加权和完全相同**（分母都是 1，自检位）；`trivial` 的归一化值都 `< 1`、
  `ideal` 的都 `>= 1`——前者是上界分母，后者是下界分母。
- **`ideal` 的分母只能来自被证明的最优值**：`min Cmax = 9.0`、`min ΣT = 2.0`、`min setup = 1.0`，
  三个都必须 `OPTIMAL`；`plant_batch` 上 `min setup = 0`，驱动**没有**用别的数顶替，
  而是把那一整列标成 `SKIPPED`——这是方法的固有边界。

同一套口径在第二个实例 `plant_batch` 上给出 `β* = 0.0123`（`none`）与 `0.0546`（`trivial`）：
翻转点随实例走，不是一组通用常数。

## 6. 手算与独立复核

```text
手算 Cmax     单机上 Cmax = Σp + Σsetup：6 + 3 = 9（Day 4，也是 min Cmax）
手算换型      相邻对 3 分钟 vs 任意前后对 6 分钟（Day 4，换型是顺序相关的）
手算理想点    (9, 2, 1) = 三个单目标最优值，各自 OPTIMAL（Day 7 第 2 节）
手算交换率    β* = d_ΣT / d_cmax = 1/1、115/50、2/9（Day 3 第 5.3 节）
手算归一化    0.3208 = 9/50 + 9/115 + 2/32；6.9444 = 13/9 + 9/2 + 1（Day 7 第 5.2 节）
手算不可行下界 10 + min(4, 3) = 13（Day 6 第 5.1 节，与求解器一致）
排程结论      -> validate_schedule；读数 -> objective_breakdown 独立重算（最大偏差 0.0e+00）
```

**两个如实报告的零结果**：

```text
Day 5 的 C1a：维护窗 (5, 10) 被日历窗蕴含，「加维护」没有改变可行集，最优值仍是 Cmax = 13。
Day 6 的 D6：两个方向的换型都是 2 分钟，`total_setup_time` 退化——两条排程都是 OPTIMAL、
              目标值都是 2，但 ΣT 差 12 分钟：目标函数的值相等时，排程没有唯一解。
```

## 7. 测试证据

`tests/test_week3.py`（23 个用例）与共享地基 `tests/test_foundation.py`（40 个）一起跑，
63 个全绿；整个项目的测试套件 `python -m pytest -q` 是 181 个：

```bash
cd projects/03_industrial_fjsp
python -m pytest -q tests/test_week3.py tests/test_foundation.py
# 63 passed in 2.08s
```

测试里的期望值一律手算或用独立实现得到：换型的相邻对间隔、日历扣维护后的可用区段、
`split` 与 `blocker` 在同一实例上的相等、加权和与 `breakdown` 的一致性、
非 `exact` 口径下 `best_bound = None`、以及「每个返回的排程都过独立验证器」。
本周引用的三个名字都在注册表里，缺失的 = `[]`：

```text
available() = ['fjsp_cpsat', 'fjsp_cpsat_calendar', 'fjsp_cpsat_full', 'fjsp_cpsat_multiobj',
  'fjsp_cpsat_qualified', 'fjsp_cpsat_setup', 'fjsp_loadbalance', 'fjsp_random', 'fjsp_shortest',
  'flow_johnson', 'flow_neh', 'jsp_cpsat', 'jsp_priority']
```

## 8. 确定性契约

```text
相同实例 + 相同 spec  ->  相同排程与相同目标值（CP-SAT 一律 num_search_workers = 1）
随机种子：random_seed 由 spec["seed"] 固定，不改全局随机状态
平局：加权和相等时选到哪条排程由搜索路径决定 —— 值相同，排程不承诺唯一
口径：exact 为假时不报告 best_bound，报告状态降级为 FEASIBLE
耗时：每行读数都会变（建模 0.01 秒起、求解 0.19 ~ 0.33 秒浮动）—— 属观测值，不是规格值
驱动：输出目录非空直接拒绝，不覆盖
```

## 9. 已知局限

```text
换型矩阵：只测了 2x2 的族数；真实车间的族数决定矩阵规模，需要按实例生成
归一化：只实现了一种线性口径（各自除以一个常数）；非线性口径没实现也没测
理想点：任一分量为 0 时该口径不可用，驱动跳过整列，没有替代方案
迟交口径：total_tardiness 不带订单权重；Job.weight 目前只进 weighted_tardiness
权重扫描：6 组权重、2 个实例 —— 口径的影响还需要更多实例才敢下一般性结论
规模与耗时：变量数、约束数只是规模的描述，不是耗时的预测（G201 上模型大三成的反而更快）
```

## 10. 遗留问题

| # | 问题 | 状态 |
|---|---|---|
| 1 | 加了维护却没有任何变化，怎么报？ | 如实报零结果：`C1a` 的维护被日历蕴含，说明该实例的维护是冗余的 |
| 2 | 单目标最优解会不会比多目标解更差？ | 会：`min Cmax` 的 `(63, 67, 3)` 被等权模型的 `(63, 55, 3)` 支配 |
| 3 | 同一个 `β` 在两种口径下选出不同排程，谁错了？ | 都没错：口径就是定价，先用业务语言回答「1 分钟迟交值几分钟完工」 |
| 4 | 加权和的 `best_bound` 能信吗？ | 只有 `exact` 为真时能按口径换算回原始单位；否则一律 `None`，不填 0 |

## 11. 待个人完成

闭卷重做三件事：一是实例 `T` 上 `β*` 的三组值，从两条候选排程的 `ΔCmax` 与 `ΔΣT` 自己推一遍；
二是把表里任意一行在三种口径下的归一化值手算出来，与表对齐；三是写出「加一层归一化之后，
模型最小化的对象变成了什么」，并说清为什么它不等于报告值。三件事都不看笔记写出来，
才算把本周的两条主线（工业约束的建模与多目标的口径）收进自己的手里。
