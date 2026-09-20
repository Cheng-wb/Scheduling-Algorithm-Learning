# 03_industrial_fjsp：工业 FJSP 求解器（M3）

[学习路线](../../LEARNING_PLAN.md) · [月度学习索引](../../Month_03_工业排程与柔性车间/README.md)

对应第 3 月（M3，Week 1–4）。从「算法题」转向「真实生产调度」：Flow Shop / Job Shop 推到 Flexible Job Shop，再叠加真实业务约束——释放时间、交期、加权迟交、sequence-dependent 换型、机器日历、计划维护、机器资质、工人与工装、批处理、WIP 锁定工序、紧急订单。

## 为什么 M3 自带一套领域模型

**M1 的 `Operation.processing_time` 是一个整数**，语义是「这道工序在所有合格机器上耗时相同」。FJSP 的定义特征是 ``p_ij``——同一道工序在不同机器上工时不同。这不是加个可选字段就能兼容的：目标函数、解码器、验证器、CP-SAT 模型全部要按「工时依赖机器」重写。

改 M1 的模型会同时破坏 M1 与 M2 已封存的实验批次（它们的 `source_sha256` 覆盖 M1 的三个包），所以 M3 **自带一套更丰富的核心**。复用的是**纪律**而不是代码：输入不可变、输入与结果分离、独立验证器、确定性平局决胜、参考值分档、无 bound 时写 `None`。

## 数据模型

```text
订单层   Job            id / operation_ids（顺序即工艺路线）/ release_time / due_date / weight / priority
工序层   Operation      id / job_id / position / machine_times（逐机器工时）/ family / locked_*
资源层   Machine        id / name / calendar_id / group
         Calendar       可用窗 [start,end) 的并集；**空 = 无约束**（不是「永不可用」）
         Maintenance    计划停机窗，在日历之上再挖掉
         Qualification  机器 × 工序族 的资质
         Worker         次生资源：machine_ids（空 = 不限）+ capacity
         Setup          family → family 的换型时间
```

三层不要混：订单描述交期与优先级，工序描述「在哪做、做多久」，资源描述「能不能做、同时能做几个」。

## 独立验证器（11 项检查）

`fjsp_core/schedule_validation.py`。**不调用任何解码器或求解器，不假设工序列表有序，接受任意顺序。**

| # | 检查 | 诊断标签 |
|---|---|---|
| 1 | 每道工序恰好一次 | `missing` / `duplicate` / `unknown operation` |
| 2 | 机器存在且在该工序的 `machine_times` 里 | `illegal assignment` |
| 3 | 整数时刻、`start ≥ 0`、`end − start = p_ij` | `invalid time type` / `duration` |
| 4 | 不早于订单释放时刻 | `release` |
| 5 | 订单内相邻工序 precedence | `precedence` |
| 6 | 同机器不重叠 **+ 换型间隔** | `overlap` |
| 7 | 落在机器日历可用窗内 | `calendar` |
| 8 | 不与计划维护窗重叠 | `maintenance` |
| 9 | 机器有该工序族资质（仅当实例给出资质） | `qualification` |
| 10 | 资源能操作该机器、不超容量 | `worker` |
| 11 | 锁定工序的机器与开工时刻一致 | `locked` |

区间是半开的 `[start, end)`，所以**相接合法**——`[0,3)` 与 `[3,5)` 不重叠，资源占用相接也不算超容量。换型属于第 6 项：它只能在「已知机器上加工顺序」之后检查。

## 统一结果接口

`fjsp_core/result.py` 的 `ShopResult`，沿用 M2 的三条纪律：

1. **没有 bound 就写 `None`**（启发式），绝不写 0 或目标值；
2. **`build_time` 与 `solve_time` 分开记**；
3. **`OPTIMAL` 不等于解可行**——返回排程必须过独立验证器。

M3 额外要求每次求解都填 `breakdown`（`cmax` / `total_tardiness` / `setup`）。Week 3 的目标是加权和，只报一个数会让**三个分量的取舍完全不可见**。

## 方法注册表

```python
from fjsp_shop.registry import register
from fjsp_core.result import ShopResult

@register("fjsp_cpsat", "FJSP 的 CP-SAT 模型")
def fjsp_cpsat(instance, spec) -> ShopResult: ...
```

统一签名 `solve_fn(instance, spec) -> ShopResult`，`spec` 含 `objective`、`time_limit`、`seed`（多目标另加 `weights`）。`configs/month3.json` 引用的名字必须全部注册，否则该行记 `FAILED`（批次继续，不中断）。

| 周 | 方法 |
|---|---|
| W1 | `flow_johnson`、`flow_neh`、`jsp_priority`、`jsp_cpsat` |
| W2 | `fjsp_random`、`fjsp_shortest`、`fjsp_loadbalance`、`fjsp_cpsat` |
| W3 | `fjsp_cpsat_setup`、`fjsp_cpsat_calendar`、`fjsp_cpsat_multiobj` |
| W4 | `fjsp_cpsat_qualified`、`fjsp_cpsat_full` |

## 目录结构

```text
03_industrial_fjsp/
├── fjsp_core/          # 领域模型、输入校验、独立验证器、目标、统一结果
├── fjsp_shop/          # 模型与算法：flowshop / jsp / fjsp / cpsat_fjsp / industrial / constraints2
│                       #   另含 graph（析取图与关键路径）、gantt、oracle（小实例穷举）
├── fjsp_io/            # 实例生成、JSON 读写、标准实例解析、KPI
├── fjsp_experiments/   # 跨方法批次与各周驱动
├── configs/month3.json
├── examples/           # 按学习日组织的运行入口（m3wXdY_主题.py）
├── tests/              # 自动化验收
└── artifacts/          # 实际输入、运行记录与汇总
```

## 运行

在项目目录下：

```bash
python -m pytest -q
python -m fjsp_experiments.benchmark --config configs/month3.json --output artifacts/month3
python -m examples.m3w1d2_flowshop
```

或从仓库根目录：

```bash
python projects/03_industrial_fjsp/examples/m3_month3_benchmark.py --output projects/03_industrial_fjsp/artifacts/my_run
```

输出目录必须为空或不存在——否则会覆盖旧批次的证据。

## 与 M1 / M2 的关系

| 复用 | 不复用（并说明原因） |
|---|---|
| 输入不可变（`frozen=True` + `tuple`） | `Instance`：M1 的工时不依赖机器，容不下 `p_ij` |
| 输入与结果严格分离 | 验证器：M3 的约束集是 M1 的超集（日历/维护/资质/资源/WIP） |
| 独立验证器、确定性平局决胜 | Objective：多目标加权和与 KPI 是 M3 新增的 |
| 无 bound 写 `None`、参考值分档 | 结果接口：M3 增加 `breakdown`，便于做权重敏感性 |

**跨月不变的是方法论**：先把问题精确定义，再把输入变成不可变数据，用基线产生结果，用独立验证器判定可行性，用分档的参考值说明「有多好」，最后明确每条结论的适用边界。
