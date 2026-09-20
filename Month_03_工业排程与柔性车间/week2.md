# M3 Week 2 周总结：柔性作业车间（FJSP）的两维决策

> 笔记：[Day1](Week_2/Day1.md) · [Day2](Week_2/Day2.md) · [Day3](Week_2/Day3.md) · [Day4](Week_2/Day4.md) · [Day5](Week_2/Day5.md) · [Day6](Week_2/Day6.md) · [Day7](Week_2/Day7.md)

## 1. 本周目标与成果

Week 1 里每道工序的机器是固定的；本周把它松开：每道工序有若干台**合格机器**（`machine_times`），
「去哪台机器」变成决策变量，问题从 JSP 变成 FJSP。交付三层：

```text
启发式层    fjsp_random / fjsp_shortest / fjsp_loadbalance —— 先定机器指派，再用非延迟 ECT 派工
精确层      fjsp_cpsat —— 可选区间 + ExactlyOne + NoOverlap，两维一起优化
证书层      exhaustive_optimum —— 与解码器、CP-SAT 都不共享代码的独立穷举
```

四个方法全部注册进 `fjsp_shop.registry`，可被 `configs/month3.json` 直接调用；
每个返回的排程都过 `fjsp_core.schedule_validation.validate_schedule`，目标值由 `evaluate` 独立重算。
另外交付四个手算实例（`toy_instances.py`）、七个可运行脚本与七天笔记。

## 2. 核心概念

| 概念 | 一句话定义 | 它回答的问题 |
|---|---|---|
| 合格机器 | `Operation.machine_times` 里列出的机器（约束） | 这道工序允许在哪几台机器上做 |
| 机器指派 | 每道工序实际选中哪台机器（决策） | 这道工序在哪台机器上做 |
| 两维决策 | 机器指派 x 工序顺序 | 谁先谁后、在哪台机器上 |
| 拓扑序 | 每个订单内部保持工艺路线先后的顺序 | 哪些顺序是合法的 |
| 附加式 vs 插入式 | 工序接在机器末尾 / 插进第一个放得下的空档 | 空档要不要用 |
| 非延迟派工 | 有可开工的工序就立刻开工，不故意留空 | 顺序维怎么快速决定 |
| 下界 `LB` | `max(max_o min_m p_om, ceil(Σ_o min_m p_om / \|M\|))` | 目标值离最优还有多远 |
| 主动排程族定理 | 对正则目标，主动排程族里一定含一个最优排程 | 为什么穷举能只走拓扑序 |
| 证书边界 | 一个方法敢证明的东西有明确范围 | 哪些结论有证据、哪些只是数字 |

**「LB == makespan」才能证明最优，`LB < makespan` 什么也证明不了。** 本周的
`tiny_2x2` 是前者（`LB = 2 = 最优值`），`assign_2x3` 是后者（`LB = 5`、最优 `10`）。

## 3. 四个方法与适用条件

| 方法 | 什么时候精确 | 什么时候只是启发式 | 什么时候拒绝 | 有下界吗 |
|---|---|---|---|---|
| `fjsp_random` | 从不（随机指派 + 规则派工） | 纯 FJSP 与带释放时间的实例 | 目标不是 makespan 时不检查目标、实例含未建模约束 | 否 |
| `fjsp_shortest` | 从不（局部最快不等于全局最好） | 同上 | 同上 | 否 |
| `fjsp_loadbalance` | 从不 | 同上 | 同上 | 否 |
| `fjsp_cpsat` | 预算内搜完并证明时 | 只找到可行解时 | 目标不是 makespan / 实例含未建模约束 | 目标为 makespan 时才有 |
| `exhaustive_optimum` | 空间 `<= limit` 且纯 FJSP + 释放时间时 | 不使用（它不做近似） | 空间超限 / 非 makespan / 未建模约束 | 它给出的就是最优值本身 |

**启发式一律 `best_bound = None` 且 `gap = None`**：不是「下界等于目标值」，
也不是「暂时不知道」，而是**没有证明能力**。CP-SAT 的界要配 `bound_kind`
（`proven` / `search_progress`）才能读。

## 4. 接口约定（API Contract）

```python
# fjsp_shop/registry.py —— 与 Week 1 同一套注册表；本周的四个名字见第 7 节
available() -> list[str] / describe(name) / describe_missing(names)

# 统一入口：solve(instance, spec) -> ShopResult；spec 带 objective / time_limit / seed
fjsp_random / fjsp_shortest / fjsp_loadbalance / fjsp_cpsat (instance, spec) -> ShopResult

# fjsp_shop/fjsp.py —— 解码与派工（Week 1 的 jsp_cpsat 之外的第二条构造路径）
decode(instance, assignment, order) -> Schedule   # 两个参数：指派与顺序
dispatch(instance, assignment, rule) -> Schedule  # rule 取 ect / est / spt / mwkr
DISPATCH_RULES = ("ect", "est", "spt", "mwkr")
build_model(instance, spec=None) -> object        # 只建模：stats() 给 variables / constraints / horizon

# fjsp_shop/oracle.py —— 独立穷举（不 import 解码器，也不 import CP-SAT）
topological_order_count(instance) -> int     # n! / Π_j (k_j!)
enumeration_space(instance) -> int           # Π_o |合格机器_o| x 拓扑序个数
exhaustive_optimum(instance, objective="makespan", limit=200_000) -> tuple[float, Schedule]

# fjsp_shop/toy_instances.py —— 笔记、脚本、测试共用的四个手算实例
TOY_INSTANCES = {"tiny_2x2", "gap_2x2", "assign_2x3", "jsp_fixed_2x2"}
```

**`Operation.time_on(machine_id)` 对不合格机器返回 `None`**，`min_time` 给出最快的机器工时；
方法必须按 `machine_times` 判断资格，不能假设「第 i 道工序上第 i 台机器」。

## 5. 关键数值证据

四个方法在同一批实例、同一份 `spec`（`objective = "makespan"`、`time_limit = 10s`、固定种子）下实测：

| 实例 | 工序 | `fjsp_random` | `fjsp_shortest` | `fjsp_loadbalance` | `fjsp_cpsat` | 参考值 |
|---|---:|---:|---:|---:|---:|---|
| `tiny_2x2` | 4 | 7 | 2 | 2 | **2**（OPTIMAL） | 2（oracle 证书） |
| `gap_2x2` | 4 | 15 | 10 | 10 | **10**（OPTIMAL） | 10（oracle 证书） |
| `assign_2x3` | 4 | 14 | 11 | 13 | **10**（OPTIMAL） | 10（oracle 证书） |
| `jsp_fixed_2x2` | 4 | 7 | 7 | 7 | 7（OPTIMAL） | 7（oracle 证书） |
| `jsp_6x4`（seed 102） | 18 | 74 | 74 | 74 | **67**（OPTIMAL） | 67（仅 CP-SAT 自证） |
| `fjsp_6x4_f2`（seed 104） | 18 | 87 | 67 | 61 | **42**（OPTIMAL） | 42（仅 CP-SAT 自证） |
| `fjsp_10x5_f3`（seed 105） | 30 | 115 | 111 | 90 | **56**（OPTIMAL） | 56（仅 CP-SAT 自证） |

读这张表的四条：

- **CP-SAT 在七个实例上一个都不差于启发式**：四行严格更好，三行与最好的启发式持平
  （`tiny_2x2`、`gap_2x2` 本来就小到启发式能碰到最优，`jsp_fixed_2x2` 是选机退化的实例）。
- **只有 `jsp_fixed_2x2` 一行四种方法全部一致**：它每道工序只有一台机器，「选机」这一维退化，
  说明分歧是随选机自由度一起来的。
- **代价在另一列**：启发式七次运行合计 `0.0027 ~ 0.0032` 秒（最慢一次 `0.0011` 秒），
  CP-SAT 合计 `4.7043` 秒（最慢一次 `4.6139` 秒）—— 量级差约 `4200` 倍。
  `jsp_cpsat` 的预算实验（Day 4）还给出另一条：同一实例 `1s` → `FEASIBLE` 57（界 42）、
  `10s` → `OPTIMAL` 56，**状态是这次运行的属性，不是方法的天性**。
- **参考值分两档**：四个小实例有 oracle 证书（穷举 + 独立验证器，两条独立路径互证），
  三个生成实例只有 CP-SAT 自证。两档不能当成同一档用。

维度分解（`fjsp_6x4_f2`，Day 7）：只动机器指派的极差 `26`（`87 / 67 / 61`），只动工序顺序的极差 `18`
（`67 / 57 / 74 / 75`），两张子表共用的那一格都是 `67`；组合两维偏好得到 `52`，比任何一维单打都好，
但仍比两维一起优化的 `42` 高 `10` —— **这 `10` 分钟就是「两维分别调到最好」与「两维同时决定」
之间的差距，也是两维耦合的价钱。**

## 6. 手算与独立复核

本周每条结论都配了一条**与实现无关**的复核路径：

```text
手算下界       tiny_2x2 的 LB = max(1, ceil(4/2)) = 2 = 最优值（下界碰上界）
手算串行链     jsp_fixed_2x2 的 O00 与 O11 都只能在 M0 上做，3 + 4 = 7 是下界也是可达值
手算串行链     gap_2x2 的订单 J1 串行：O10 最快 8（M1）+ O11 最快 2（M0）= 10
求解器结论     -> oracle 穷举（Day 5）：tiny 2 / jsp_fixed 7 / gap 10 / assign 10
排程结论       -> validate_schedule（机器资格、工艺路线、机器不重叠、释放时间）
读数与独立性   -> 目标值由 evaluate 独立重算（最大偏差 0.0e+00）；oracle.py 从 fjsp_shop import 的模块数 = 0
```

穷举 oracle 的空间公式是 `Π_o |合格机器_o| x (拓扑序个数)`，默认上限 `200000`：
`tiny_2x2` 是 `16 x 6 = 96`，`assign_2x3` 是 `81 x 6 = 486`，
`fjsp_6x4_f2` 是 `2^18 x 137225088000 = 3.59727e+16` —— 超限直接拒绝，**不降级成抽样**。
它只给 `makespan` 发证书：别的目标名、以及实例里本模块没有建模的约束，
一律在枚举之前抛 `ValueError`。

Day 5 还留下一个**把错误留着**的可复现反例：不检查工艺路线、枚举全部 `4! = 24` 个排列会
得到 `4`，而独立验证器对这个排程报 `precedence: O10 -> O11`，真最优是 `5`。
**受限枚举给出的不是保守的上界，而是一个更小、更诱人的错值。**

## 7. 测试证据

`tests/test_week2.py`（33 个用例）与共享地基 `tests/test_foundation.py`（40 个）一起跑，73 个全绿：

```bash
cd projects/03_industrial_fjsp
python -m pytest -q tests/test_week2.py tests/test_foundation.py
# 73 passed in 1.35s
```

测试里的期望值一律**手算或用独立实现得到**：解码器在手工追踪的小实例上的时间线、
三个启发式的手查指派、`fjsp_cpsat` 与 `exhaustive_optimum` 在微小实例上的相等、
退化实例（`flexibility = 1`）上的正确性、以及「每个返回的排程都过独立验证器」。
本周注册的四个名字：

```text
available() = ['fjsp_cpsat', 'fjsp_loadbalance', 'fjsp_random', 'fjsp_shortest']
configs/month3.json 引用的本周四个名字，缺失的 = []
```

## 8. 确定性契约

```text
相同实例 + 相同 spec  ->  相同排程与相同目标值（启发式与 CP-SAT 都一样）
CP-SAT：num_search_workers = 1，random_seed 由 spec["seed"] 固定
随机指派：RNG 由 spec["seed"] 派生，不改全局随机状态
平局：派工规则的比较键是 (规则键, job.id, operation.id)，不依赖字典序
耗时：每行读数都会变（0.0010 ~ 0.0011 秒之间浮动）—— 属观测值，不是规格值
```

## 9. 已知局限

```text
覆盖范围：纯 FJSP + 释放时间；实例里若带有本模型没有建模的约束，四个方法一律在建模 / 枚举前拒绝
oracle：只能证明 makespan，空间上限 200000 —— 18 道工序的实例就已经远超它的能力
最优性证据：小实例有两档（oracle 证书 / CP-SAT 自证），大实例只剩 CP-SAT 自证一档
启发式：派工规则默认 ect，没做「规则 x 指派」的系统搜索；也不为 makespan 以外的目标做任何事
下界与目标名：LB < makespan 时下界证明不了任何事；换目标名时 CP-SAT 与 oracle 直接拒绝，
              三个启发式会报出别名的目标值 —— 那个数不是它们优化出来的（Day 6 第 4 段）
```

## 10. 遗留问题

| # | 问题 | 状态 |
|---|---|---|
| 1 | 生成实例的最优值凭什么信？ | 只有 CP-SAT 自证一档，本周如实标注，不冒充两条路径互证 |
| 2 | 两个维度的极差能不能相加？ | 不能：极差是「另一维固定」时的撬动量，组合实测 `52` 与相加的直觉不符 |
| 3 | 小实例上启发式偶尔追平最优，为什么？ | 实例小到派工规则就能碰到最优；`jsp_fixed_2x2` 则是选机退化 |
| 4 | `best_bound = None` 会不会让表里的 `gap` 空着？ | 会，`gap` 也是 `None` —— 绝不填 0 |
| 5 | 排列枚举为什么不能当 oracle？ | 会绕过工艺路线，给出比真最优更小的假值（Day 5 的可复现反例） |
| 6 | 三个启发式共用 ect，是不是说明 ect 最好？ | 不是：共用是为了让 Day 6 的差异可归因；换 `est` 在两个指派上都更好 |

## 11. 待个人完成

闭卷重做两件事：一是 `tiny_2x2` 的完整手算（四条时间线、`LB = 2`、四种方法各自的读数为什么是
`7 / 2 / 2 / 2`），二是 `fjsp_6x4_f2` 上「只动顺序」那张子表的手推（为什么同一个指派下
`est` 能比 `ect` 少 `10` 分钟、而这 `10` 分钟搬到另一组指派上就不成立）。
两件事都不看笔记写出来，才算把本周的两条主线（两维决策与证书边界）收进自己的手里。
