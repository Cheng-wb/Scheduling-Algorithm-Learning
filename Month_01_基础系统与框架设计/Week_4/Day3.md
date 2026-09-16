# Day 3：结果 schema、排程与轨迹

> 当日主题：把「一个目标值」拆成运行层、解层、过程层三种粒度，并让每一层都能被独立重新验证。
> 当日产出：**三层结果 schema 与重算脚本**（`examples/m1w4d3_schema.py`）
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 说出三种结果粒度的文件名、行数与各自回答的问题。
2. 列出 `results.csv` 的 18 个列名，并把它们归类成「标识 / 参数 / 结果 / 参考 / 诊断」。
3. 说清 `runs/<run_id>.json` 的三段结构（`config` / `candidate` / `schedule`）与 `trace.csv` 的六个字段。
4. 说出 `metadata.json` 记录的九项内容，并解释 `source_sha256` 与 `config_sha256` 的分工。
5. 记住四个 `status` 的含义，并解释为什么它们**都不是**最优性声明。
6. 区分 `optimum` 与 `best-known` 两类参考，并说出本批次哪些实例属于哪一类。
7. 会复算 `gap=(value-reference)/max(1,|reference|)`，并解释参考为 0 时的退化。
8. 解释失败行的 `objective` 为什么存空值而不是 0，以及失败行为什么不能从总次数里消失。

---

## 2. 为什么第 3 天要把「一个数字」拆成三层

Day 2 解决了「题是同一道题」。今天解决下一个问题：**报告里的 42.0 到底是从哪里冒出来的。**

如果只留下一个 `objective` 列，任何人都无法回答下面这些必然会被问到的问题：

```text
42.0 是哪个算法、哪个 seed 跑出来的？排程是什么？那道排程合法吗？
搜索过程是一路改善，还是先变差再变好？
42.0 与参考值 40.0 之间差的 2 是怎么算出来的？
```

一次运行其实产生三种不同粒度的东西，混在一起就永远说不清：

```text
results.csv                 一次运行 = 一行        批次层「谁跑出了什么」
   └── runs/<run_id>.json   一次运行 = 一个文件    解层「配置 + 最好候选 + 完整排程」
          └── .trace.csv    一次评价 = 一行        过程层「每一步的 proposed/current/best」
```

三层的索引是**单向的**：从 `results.csv` 的 `run_id` 能找到对应的 run JSON 与 trace，反过来没有意义。因此：

- **不要把三种粒度混进一张表。** 把 trace 的每一行当成一条运行记录去求均值，等于把 150 次评价当成 150 次实验，均值会被重复计数彻底带偏。
- **不要把过程层的量当结果层的量。** trace 里的 `current` 是「此刻手上的解」，`best` 才是「到目前为止最好的解」；只有 `best` 的最后一个值才等于结果行里的 `objective`。

> **一句话**：结果的可信度不取决于数字本身，而取决于「每一个数字都能追溯到它的输入、参数和排程」。

---

## 3. 三种粒度与字段清单

### 3.1 粒度 1：`results.csv`（162 行 + 表头）

| 列 | 类别 | 含义 |
|---|---|---|
| `run_id` | 标识 | `{instance}__{group}__{algorithm}__{seed}`，四元组唯一 |
| `instance` | 标识 | 实例名，指向 `instances/<name>.json` |
| `input_sha256` | 标识 | 输入 JSON 的字节级哈希（Day 2 第 6 节） |
| `group` | 标识 | `main` 或某个 `sa_t*_c*` 敏感性设置 |
| `algorithm` | 参数 | 六种方法之一 |
| `seed` | 参数 | 算法 seed（0/1/2），不是输入 seed |
| `objective_name` | 参数 | 目标函数名，决定用哪个评估器复算 |
| `budget` | 参数 | 评价上限 |
| `temperature` | 参数 | 初始温度（非 SA 方法也照记，便于对齐） |
| `cooling` | 参数 | 冷却率 |
| `status` | 结果 | 终止原因，见第 4 节 |
| `objective` | 结果 | 最好目标值；失败时为空 |
| `evaluations` | 结果 | 实际消耗的评价次数 |
| `elapsed_seconds` | 结果 | 墙钟时间，复现时不比较 |
| `reference_type` | 参考 | `optimum` 或 `best-known` |
| `reference` | 参考 | 参考值 |
| `gap` | 参考 | 归一化差异 |
| `failure_reason` | 诊断 | 异常类型与消息；成功时为空 |

### 3.2 粒度 2：`runs/<run_id>.json`（162 个文件）

```text
{
  "config":    { algorithm, objective, budget, seed, temperature, cooling, restart_interval },
  "candidate": { order: [...],  assignments: [...] },
  "schedule":  { operations: [ { operation_id, machine_id, start_time, end_time }, ... ] }
}
```

三段对应三个层次：`config` 是**参数**（怎么搜的）、`candidate` 是**决策**（排序 + 选机）、`schedule` 是**结果**（时间推进后的排程）。注意 `candidate.order` 与 `candidate.assignments` 的长度都等于工序数，`assignments` 与 `instance.operations` 逐位对齐——这是第 5 节重算能够成立的前提。

### 3.3 粒度 3：`runs/<run_id>.trace.csv`（162 个文件，每次评价一行）

| 列 | 含义 |
|---|---|
| `evaluation` | 第几次评价（从 1 开始） |
| `proposed` | 这一步被提出的解的目标值 |
| `current` | 提出并判定之后当前解的目标值 |
| `best` | 到目前为止的历史最好值 |
| `accepted` | 这一步是否被接受 |
| `temperature` | 该步的温度；只有 `sa` 有值，其余为空 |

两个容易看错的地方：

1. **第 1 行是初始解**，它不经过任何接受判定，所以 `accepted=True`、`temperature` 为空（源码里是 `TracePoint(1, value, value, value, True, None)`）。`trace` 的行数就等于 `results.csv` 的 `evaluations`：`routes_12__main__lpt__0` 是 1 行，`tiny_single__main__first__0` 是 23 行，`routes_12__main__sa__0` 是 150 行。
2. **`best` 必须单调不增**（最小化问题）。如果画图时发现 `best` 上升，先检查画的是不是 `current`。

### 3.4 附：`summary.csv` 与 `metadata.json`

`summary.csv`（54 行 = 6 实例 × 9 个「实例 × 组 × 算法」组合）的列：

```text
instance, group, algorithm, successful, failed, mean, median, stdev, best,
mean_gap, mean_evaluations, mean_seconds
```

`metadata.json` 的九项：

| 字段 | 记录什么 | 为什么重要 |
|---|---|---|
| `schema_version` | 记录格式版本 | 格式变了要能识别 |
| `created_utc` | 批次创建时间 | 对应哪一次运行 |
| `python` | 解释器版本 | 复现环境对齐 |
| `platform` | 操作系统 | 差异解释 |
| `git_commit` | 提交哈希 | 源码版本 |
| `working_tree_dirty` | 工作区是否有未提交改动 | 有改动时提交哈希不足以定位源码 |
| `source_sha256` | 四个包全部 `*.py` 的联合哈希 | 复现前的第一道闸门（Day 4 第 6 节） |
| `config_sha256` | 配置文件的字节哈希 | 配置是否被改过 |
| `budget_unit` | 一次评价的口径 | 「预算 150」到底数的是什么 |

`budget_unit` 的内容是 `full decode + validate + objective, including initialization and rejection`：「150 次评价」= 150 次完整「解码 + 独立验证 + 目标计算」，包含初始解、被拒绝的候选与 no-op 移动。口径不写清，跨报告比较预算就没有意义。

---

## 4. 状态不是最优性声明

### 4.1 四个 `status`

| `status` | 含义 | 本批次计数 |
|---|---|---:|
| `BASELINE` | 规则基线完成，未进入搜索循环 | 18 |
| `BUDGET` | 评价预算用尽，搜索被上限截断 | 132 |
| `LOCAL_OPTIMUM` | 邻域内已无严格改善的邻居，提前停机 | 12 |
| `FAILED` | 该次求解抛异常，结果行保留错误原因 | 0 |

三个成功状态**都不自动等于 `OPTIMAL`**：

- `BUDGET` 只说明「到达上限停下来」，与解的质量无关。本批次四条 `best-known` 参考**全部由敏感性组的运行取到**（见 4.2），主实验里跑满 150 次评价的运行一次都没拿到参考值——「用满预算」不是「解更好」的同义词。
- `LOCAL_OPTIMUM` 只说明「**在这个邻域里**没有严格更优的邻居」。换邻域、换初始解、换接受准则，都可能有改善空间。
- `BASELINE` 只说明「规则跑完了」。本批次 18 条 `BASELINE` 全部来自 `lpt` 的一次评价，值是 45.0 / 54.0 / 95.0 这样的基线值，与「最优」没有关系。

12 条 `LOCAL_OPTIMUM` 全部出现在 tiny 实例的 `first` / `best` 上（`tiny_single` 的 23 / 37 次评价，`tiny_parallel` 的 17 次评价）。停机早不等于解得差：这 12 条的目标值都等于该实例的 `optimum`。

### 4.2 `optimum` 与 `best-known`

**只有适用范围内完整枚举得到的参考才叫 `optimum`。** 本批次只有两个：

```text
tiny_single    exact: true → exhaustive_optimum 完整枚举 → 36   reference_type = optimum
tiny_parallel  exact: true → exhaustive_optimum 完整枚举 → 38   reference_type = optimum
```

其余四个实例的参考是**本批次全部成功主实验 + 敏感性运行的最小值**，必须标 `best-known`：

```text
single_12    250   ← single_12__sa_t10.0_c0.9__sa__1    组 sa_t10.0_c0.9，seed 1
parallel_12   43   ← parallel_12__sa_t10.0_c0.9__sa__0  组 sa_t10.0_c0.9，seed 0
parallel_24   90   ← parallel_24__sa_t10.0_c0.9__sa__0  组 sa_t10.0_c0.9，seed 0
routes_12     40   ← routes_12__sa_t0.1_c0.98__sa__0    组 sa_t0.1_c0.98，seed 0
```

四条参考**全部**由敏感性组的运行取到，没有一条来自 `main` 组。这带来一个必须记住的循环论证风险：

> 参考值取自本批次，所以「贡献参考的那条运行的 `gap` 恒等于 0」——这不是「它命中了最优解」，而是「它就是参考本身」。把这条运行的 `gap=0` 当作质量优势来引用，等于用定义代替证据。

`best-known` 与 `optimum` 的差别不是措辞：`best-known` 是「**这一批数据里**已知的最好记录」。将来跑出更好的解，参考值和所有 `gap` 都会跟着变——这正说明它不是最优性证书。

### 4.3 `gap` 约定

```text
gap = (value - reference) / max(1, |reference|)     最小化问题
```

- **参考为 0 时退化为绝对差**：`(value - 0) / max(1, 0) = value`。此时 `gap` 是「差了多少单位」，**不能当作百分比**；本批次参考最小为 36，没有触发退化。
- **对 `best-known` 的 gap 不是真正的最优性差距**。若把 `single_12` 的 250 当成最优值，`gap = (261.67 - 250)/250 = 0.0467` 会被误读成「只差 4.67%」，而没人证明过 250 是最优解。
- 分母的 `max(1, |·|)` 同时保证：小参考值不会把 `gap` 放大成天文数字；参考为 0 时不会除零。

### 4.4 失败行的语义

失败时 `objective` 存**空值**（CSV 里是空字段，JSON 里是 `null`），原因很直接：

> 这是一个最小化目标。**0 会被当成「最好的解」**——它比任何真实目标值都小，会把均值、`best`、以及 `reference`（取最小值）全部污染。

正确的做法是保持三个约定：

1. `objective` 与 `gap` 留空，绝不填 0，也绝不填 `1e9` 之类的「伪大数」。
2. `failure_reason` 保留异常类型与消息，作为诊断证据。
3. 失败行**留在总次数里**：批次是 162 行，不是「成功了多少行」。`summary.csv` 里 `successful` 与 `failed` 分列统计，失败不会被悄悄抹掉。

---

## 5. 示例：一条真实记录的重算（`routes_12__main__sa__0`）

选这条运行的理由：它是多工序实例（作业内有 precedence），是 150 次评价跑满的 SA 运行，而且它的目标值 42.0 与参考值 40.0 不相等——正好可以顺带演示 `gap`。

### 5.1 `results.csv` 里的一行

| 列 | 值 |
|---|---|
| `run_id` | `routes_12__main__sa__0` |
| `instance` | routes_12 |
| `input_sha256` | `ed8b606f720337b89df97898c7ab6168abf514416d8e3b1d0d97e2a7a07ad58c` |
| `group` / `algorithm` / `seed` | `main` / `sa` / `0` |
| `objective_name` | `makespan` |
| `budget` / `temperature` / `cooling` | 150 / 10.0 / 0.98 |
| `status` | `BUDGET` |
| `objective` / `evaluations` | 42.0 / 150 |
| `reference_type` / `reference` / `gap` | `best-known` / 40.0 / 0.05 |

### 5.2 重开保存的 run JSON

```text
config     : algorithm=sa, objective=makespan, budget=150, seed=0,
             temperature=10.0, cooling=0.98, restart_interval=40
candidate  : order        12 个工序 ID（每道工序恰好一次）
             assignments  12 个机器 ID（与 instance.operations 逐位对齐）
schedule   : operations   12 道已排定工序
```

排程（按机器分组，`machine_id` 与起止时刻来自保存的 JSON）：

```text
M0：J005_O0 0-16   J001_O0 16-26   J001_O1 26-40   J003_O1 40-41   负载 41
M1：J000_O0 0-10   J002_O0 10-22   J000_O1 22-25   J003_O0 25-40   负载 40
M2：J004_O0 1-16   J002_O1 22-27   J004_O1 27-28   J005_O1 28-42   负载 35

Σp = 41 + 40 + 35 = 116（= 13+24+17+16+16+30，与实例文件一致）
makespan = max(end_time) = 42
```

三个可以直接肉眼检查的约束：`J001_O0` 在 26 结束、`J001_O1` 在 26 开始（precedence 满足，允许相接）；每台机器上的区间两两不重叠；每道工序 `start ≥ r`（`J004_O0` 的 `r=1`，所以它从 1 开始）。

### 5.3 重开保存的 trace

```text
第 1 行    evaluation=1    proposed=54.0  current=54.0  best=54.0  accepted=True   temperature=
第 150 行  evaluation=150  proposed=62.0  current=45.0  best=42.0  accepted=False  temperature=0.5028740237764237
```

- 第 1 行的 `best=54.0` 是**初始解（LPT）**的目标值，与同一实例的 `routes_12__main__lpt__0` 那一行的 `objective=54.0` 完全一致——这是初始解口径的交叉验证。
- 第 150 行的 `best=42.0` 等于结果行里的 `objective`，而 `current=45.0`：搜索结束时手上的解比历史最好解差，说明 SA 在后期仍接受过更差的解。

### 5.4 四个出处给出同一个数

| 来源 | 取什么 | 值 |
|---|---|---|
| `results.csv` | `objective` 列 | 42.0 |
| `runs/<run_id>.json` 的 `schedule` | `max(end_time)` | 42 |
| 重算（`validate_schedule` + `makespan`） | `OBJECTIVES["makespan"]` | 42.0 |
| trace 末行 | `best` 列 | 42.0 |

外加参考侧的复算：`gap = (42 - 40) / max(1, |40|) = 2 / 40 = 0.05`，与 `results.csv` 的 `gap` 列一致；而 40 来自本批次 `routes_12` 全部成功运行的最小值（由敏感性组的 `routes_12__sa_t0.1_c0.98__sa__0` 取到），不是枚举结果，故标 `best-known`。

**结论**：数字 42.0 不是「记下来的」，而是「算出来的」——它的输入（那份排程）、参数（`objective_name=makespan`）和过程（trace）三样都在，任何一次重算都能复现它。

---

## 6. 实现：`benchmark.py` 的行构造与落盘

对应文件 [benchmark.py](../../projects/01_scheduling_core/scheduling_experiments/benchmark.py)。

结果行的构造顺序刻意写成「先给失败值，成功后覆盖」：

```python
row = {
    "run_id": run_id,                          # {instance}__{group}__{algorithm}__{seed}
    "instance": name,
    "input_sha256": input_hash,
    "group": group, "algorithm": algorithm, "seed": seed,
    "objective_name": settings.objective, "budget": settings.budget,
    "temperature": settings.temperature, "cooling": settings.cooling,
    "status": "FAILED",                        # 默认就是失败形态
    "objective": None, "evaluations": 0, "elapsed_seconds": None,
    "reference_type": "optimum" if optimum is not None else "best-known",
    "reference": optimum, "gap": None, "failure_reason": "",
}
```

四个设计点：

1. **默认值就是「失败形态」**（`status="FAILED"`、`objective=None`）。成功才覆盖；万一忘了赋值，得到的是一个显式的失败行，而不是看起来成功的空行。
2. **参考值与 `gap` 在整批结束后回填**。两者都依赖「本批次所有成功运行」这一跨行信息，必须跑完才能算：

```python
for row in rows:
    if row["reference"] is None:
        scores = [other["objective"] for other in rows
                  if other["instance"] == row["instance"] and other["objective"] is not None]
        row["reference"] = min(scores) if scores else None
    reference = row["reference"]
    if reference is not None and row["objective"] is not None:
        row["gap"] = (row["objective"] - reference) / max(1.0, abs(reference))
```

3. **`objective is not None` 这一条把失败行挡在参考值与 `gap` 之外**，它们的 `gap` 保持为空。
4. **`write_json` 用 `allow_nan=False`**：NaN 不是合法 JSON，宁可在写盘时直接报错，也不要产出一个读不回来的文件。

`summary.csv` 的统计只取成功行，但失败计数单独留列：

```python
good = [row for row in selected if row["objective"] is not None]
scores = [row["objective"] for row in good]
...
"successful": len(good),
"failed": len(selected) - len(good),
```

**失败会出现在分母里，只是不会被塞进均值里**——这就是第 4.4 节那三条约定的代码实现。

---

## 7. 实验：`m1w4d3_schema`

对应脚本 [m1w4d3_schema.py](../../projects/01_scheduling_core/examples/m1w4d3_schema.py)。脚本**只读** `artifacts/`，不写任何文件。在项目目录下运行：

```bash
python examples/m1w4d3_schema.py
```

脚本做四件事：列字段清单、重开一条运行重新验证并重算目标、统计 `status` 词表、复算全部 162 行的 `gap`。实际输出：

```text
=== 1. 三种粒度与字段清单 ===
粒度 1：results.csv（162 行，每次运行一行，批次层唯一入口）
   1. run_id
   2. instance
   3. input_sha256
   4. group
   5. algorithm
   6. seed
   7. objective_name
   8. budget
   9. temperature
  10. cooling
  11. status
  12. objective
  13. evaluations
  14. elapsed_seconds
  15. reference_type
  16. reference
  17. gap
  18. failure_reason

粒度 2：runs/<run_id>.json（一次运行的配置、最好候选与完整排程）
   1. config
   2. candidate
   3. schedule
     config     → algorithm, objective, budget, seed, temperature, cooling, restart_interval
     candidate  → order, assignments
     schedule   → operations[{operation_id, machine_id, start_time, end_time}]

粒度 3：runs/<run_id>.trace.csv（162 个文件，每次评价一行）
   1. evaluation
   2. proposed
   3. current
   4. best
   5. accepted
   6. temperature

附：summary.csv（实例 × 组 × 算法，跨 seed 汇总）
    instance, group, algorithm, successful, failed, mean, median, stdev, best, mean_gap, mean_evaluations, mean_seconds
附：metadata.json（批次级环境与版本证据）
    schema_version, created_utc, python, platform, git_commit, working_tree_dirty, source_sha256, config_sha256, budget_unit

三种粒度不能混进一张表：results.csv 是运行层，run JSON 是解层，trace 是过程层；
把逐评价的 trace 与逐运行的 results 拼在一起，行数就对不上了。

=== 2. 重开一条保存的运行，重新验证排程并重算目标 ===
run_id            : routes_12__main__sa__0
输入              : instances/routes_12.json，sha256 与结果行一致
参数              : algorithm=sa, objective=makespan, budget=150, seed=0, temperature=10.0, cooling=0.98, restart_interval=40
重算输入          : 6 作业 / 3 机器 / 12 工序
重算排程          : 12 道已排定工序，validate_schedule 无错误
机器负载          : M0=41, M1=40, M2=35
重算目标(makespan): 42.0
results.csv 记录   : 42.0
两者相等           : True；max(end_time) = 42
复算函数           : makespan（按 objective_name 反查指标函数，不重新求解）

=== 3. status 词表与本批次实际计数 ===
  BASELINE        18  规则基线完成，未进入搜索循环
  BUDGET         132  评价预算用尽，搜索被上限截断
  LOCAL_OPTIMUM   12  邻域内已无严格改善的邻居，提前停机
  FAILED           0  该次求解抛异常，结果行保留错误原因
  failures.json 内容: []
BASELINE/BUDGET/LOCAL_OPTIMUM 都不是最优性声明；本批次只有两个 tiny 实例的参考由枚举给出。
LOCAL_OPTIMUM 出现在: tiny_parallel__main__best__0, tiny_parallel__main__best__1, tiny_parallel__main__best__2, tiny_parallel__main__first__0, tiny_parallel__main__first__1, tiny_parallel__main__first__2, tiny_single__main__best__0, tiny_single__main__best__1, tiny_single__main__best__2, tiny_single__main__first__0, tiny_single__main__first__1, tiny_single__main__first__2

=== 4. gap 公式 gap=(value-reference)/max(1,|reference|) 复算 ===
  tiny_single__main__lpt__0    (57.0-36.0)/max(1,36.0) = 0.5833333333333334   记录值 0.5833333333333334
  parallel_24__main__lpt__0    (95.0-90.0)/max(1,90.0) = 0.05555555555555555  记录值 0.05555555555555555
  全部 162 行复算一致；reference 取值集合 = [36.0, 38.0, 40.0, 43.0, 90.0, 250.0]
  本批次 reference 最小为 36，没有参考为 0 的行；代入 0 时 (value-0)/max(1,0)=value，退化为绝对差而不是百分比。
```

**实验观察**：

1. 第 2 段把保存的排程重新过了一遍 `validate_schedule`（不调用 decoder 的独立验证器），再用 `OBJECTIVES[objective_name]` 重算目标，**没有重新求解**；`42.0 == 42.0` 把结果行的值、保存的排程、目标函数三者钉在一起。
2. 机器负载 41 / 40 / 35 与 `max(end_time)=42` 的差值 1 不是错误：`J003_O1` 必须等 `J003_O0` 在 25–40 完成后才能开始。**makespan 是作业完工时间的最大值，不是机器负载的最大值**，两者在带 precedence 时可以不相等。
3. 第 3 段把 `status` 词表与真实计数并排打印：`FAILED` 为 0、`failures.json` 为空数组 `[]`。**零失败只说明这次没失败**，失败路径是否被覆盖是 Day 4 的话题。
4. 第 4 段对全部 162 行复算 `gap`（脚本内断言），参考取值集合是 `[36.0, 38.0, 40.0, 43.0, 90.0, 250.0]`——正是第 4.2 节的六个数。

---

## 8. 今日练习

1. **练习 1（字段归属）**：不查第 3.1 节，把 `results.csv` 的 18 列按「标识 / 参数 / 结果 / 参考 / 诊断」分类，再逐列对照。
2. **练习 2（换一条重算）**：把脚本里的 `CHECKED_RUN` 换成 `single_12__main__sa__0`，先手算它的 `gap`，再跑脚本核对。
3. **练习 3（失败语义）**：阅读 `tests/test_month1.py` 里的 `test_benchmark_failure_is_recorded`，说明它为什么断言失败行的 `gap` 为空，以及为什么失败行必须留在总次数里。
4. **练习 4（最优性声明）**：为 tiny_single 与 parallel_12 各写一句「可以怎么说」和「不可以怎么说」。
5. **练习 5（粒度混用）**：写出一种「把三种粒度混进一张表」的错误做法，并说明它会导出什么错误结论。

---

## 9. 验收清单

- [ ] 能说出三种结果粒度的文件名、行数与各自回答的问题，并能解释为什么不能混用。
- [ ] 能默写 `results.csv` 的 18 列，并说出 `summary.csv` 与 trace 的列清单。
- [ ] 能说出 `runs/<run_id>.json` 的三段结构与每段的字段。
- [ ] 能说出 `metadata.json` 的九项内容，并解释 `source_sha256` 与 `config_sha256` 的分工。
- [ ] 能解释 `budget_unit` 的口径，以及为什么「150 次预算」需要口径说明。
- [ ] 能解释四个 `status` 的含义，并说明它们为什么都不是最优性声明。
- [ ] 能区分 `optimum` 与 `best-known`，并指出本批次哪两个实例是前者。
- [ ] 能解释失败行 `objective` 存空值而不是 0 的两个后果（误判最好解、污染参考值）。
- [ ] `python -m examples.m1w4d3_schema` 重算目标与全部 `gap`，无断言失败。
- [ ] `python -m pytest -q` 全部通过（本日不新增测试，仍为 127 条）。

---

## 10. 自测题

不看上文回答：

- Q1：三种结果粒度分别是什么？各自「一行」代表什么？
- Q2：`results.csv` 有多少列？`input_sha256`、`reference`、`failure_reason` 各属于哪一类？
- Q3：`runs/<run_id>.json` 有哪三段？每段回答什么问题？
- Q4：trace 的六个字段是什么？为什么第 1 行的 `temperature` 为空？
- Q5：`metadata.json` 记录哪些内容？为什么源码哈希与配置哈希要分开记？
- Q6：四个 `status` 各是什么含义？哪一个能支持「已经最优」的说法？
- Q7：`optimum` 与 `best-known` 的区别是什么？本批次哪些实例的参考是 `optimum`？
- Q8：`gap` 公式是什么？参考为 0 时会发生什么？
- Q9：为什么失败行的 `objective` 存空值而不是 0？
- Q10：为什么 `BUDGET` 状态不能说明算法已经收敛？

### 参考答案

- A1：`results.csv`（一行 = 一次运行）、`runs/<run_id>.json`（一个文件 = 一次运行的配置、最好候选与完整排程）、`runs/<run_id>.trace.csv`（一行 = 一次评价）。
- A2：18 列；`input_sha256` 属于标识，`reference` 属于参考，`failure_reason` 属于诊断。
- A3：`config`（怎么搜的：算法、目标、预算、seed、温度、冷却、重启间隔）、`candidate`（决策：`order` 排序 + `assignments` 选机）、`schedule`（结果：每道工序的机器与起止时刻）。
- A4：`evaluation, proposed, current, best, accepted, temperature`；第 1 行是初始解，不经过接受判定，因此温度为 `None`、`accepted=True`。
- A5：`schema_version, created_utc, python, platform, git_commit, working_tree_dirty, source_sha256, config_sha256, budget_unit`；源码哈希锁定算法实现，配置哈希锁定实验设置与输入生成参数，两者任一变一都会让复现失去意义。
- A6：`BASELINE` 规则基线完成、`BUDGET` 预算用尽、`LOCAL_OPTIMUM` 邻域内无严格改善、`FAILED` 求解抛异常；**四个都不能**支持「已经最优」。
- A7：`optimum` 由适用范围内的完整枚举得到；`best-known` 只是本批次成功运行的最小值。本批次 tiny_single（36）与 tiny_parallel（38）的参考是 `optimum`。
- A8：`gap=(value-reference)/max(1,|reference|)`；参考为 0 时退化为绝对差 `value`，只能报「差了多少单位」，不能当作百分比。
- A9：因为目标是最小化，0 比任何真实目标值都小，会被当成最好解，污染均值、`best` 与 `reference`；正确做法是留空并保留 `failure_reason`。
- A10：`BUDGET` 只说明「到达评价上限停下来」，与解的质量无关；本批次有参考值来自敏感性运行，正说明跑满预算不等于收敛。

---

## 11. 今日一句话总结

> **一个目标值要有三个出处才算证据：批次层的记录、解层的排程、过程层的轨迹；让它们对得上，比多跑一百次实验更能证明结果可信。**
