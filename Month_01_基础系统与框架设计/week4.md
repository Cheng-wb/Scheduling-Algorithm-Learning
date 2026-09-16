# M1 Week 4 周总结：Benchmark 与科研式实验

> 笔记：[Day1](Week_4/Day1.md) · [Day2](Week_4/Day2.md) · [Day3](Week_4/Day3.md) · [Day4](Week_4/Day4.md) · [Day5](Week_4/Day5.md) · [Day6](Week_4/Day6.md) · [Day7](Week_4/Day7.md)

## 1. 本周目标与成果

前三周做出了**算法**与**验证器**，但「我跑过一次，结果不错」在算法研究里几乎没有价值——因为它不可核查、不可复现、也无法回答「和什么比、在什么条件下比」。

本周把「一次运行」升级为**可审计的实验批次**：

1. **一条命令的实验入口**：JSON 配置驱动，数据规模、目标、种子、预算与敏感性参数都不写死在算法里。
2. **六个保存的基准输入**：先落盘输入再求解，并记录 SHA-256。
3. **三层结构化结果**：`results.csv`（每次运行一行）、`runs/*.json`（配置 + 最好候选 + 完整排程）、`runs/*.trace.csv`（每次评价一行）。
4. **统计表与三张图**：均值/中位数/样本标准差/最好值/平均 gap/平均评价数/平均耗时。
5. **失败留痕与故障注入**：失败行保留在记录中，且失败路径本身被测试覆盖。
6. **SA 敏感性实验**：只改初温或只改冷却率，分开观察两个因素。
7. **逐运行复现脚本**：重算并核对目标、状态、评价数、候选、排程与全部轨迹。

## 2. 实验配置

对应文件 [month1.json](../projects/01_scheduling_core/configs/month1.json)。

```json
{
  "seeds": [0, 1, 2],
  "algorithms": ["lpt", "random", "first", "best", "multistart", "sa"],
  "search": {"budget": 150, "temperature": 10.0, "cooling": 0.98, "restart_interval": 40},
  "sensitivity": [
    {"temperature": 0.1,   "cooling": 0.98},
    {"temperature": 100.0, "cooling": 0.98},
    {"temperature": 10.0,  "cooling": 0.9}
  ]
}
```

```text
主实验:     6 实例 × 6 方法 × 3 算法 seed          = 108 次
敏感性实验: 3 个 SA 设置 × 6 实例 × 3 算法 seed    =  54 次
合计:                                                162 次
```

**运行顺序**（顺序本身是设计的一部分）：

```text
读取配置 → 生成并保存输入 → 对 tiny 实例算精确参考
        → 按 算法/种子 运行 → 保存候选与排程 → 保存轨迹
        → 补参考值与 gap → 生成统计表与 PNG
```

**先保存输入再求解**，让同一个实例上的所有算法共享**逐字节相同**的输入。

**输出目录必须为空或不存在**——否则报 `ValueError`。理由很实际：同名输出被覆盖后，旧报告就**失去证据**了。

## 3. 基准实例集

所有实例：`p ∈ [1,20]`、`r ∈ [0,10]`、`due_factor = 1.5`、`w ∈ [1,5]`、**全部机器资格**。

| 名称 | 输入 seed | 作业数 | 机器数 | 每作业工序数 | 目标 | 参考 |
|---|---:|---:|---:|---:|---|---|
| `tiny_single` | 10 | 4 | 1 | 1 | 总迟交 | 枚举 `optimum` |
| `tiny_parallel` | 11 | 4 | 2 | 1 | Cmax | 枚举 `optimum` |
| `single_12` | 20 | 12 | 1 | 1 | 总迟交 | 本批次 best-known |
| `parallel_12` | 21 | 12 | 3 | 1 | Cmax | 本批次 best-known |
| `parallel_24` | 22 | 24 | 3 | 1 | Cmax | 本批次 best-known |
| `routes_12` | 23 | 6 | 3 | 2 | Cmax | 本批次 best-known |

三个必须说清的细节：

- **`routes_12` 的 12 指总工序数**（6 作业 × 2 工序），**不是 12 个作业**。它检验多工序链能否贯穿整条搜索流水线，**不代表**已经完成工业级 JSP/FJSP 建模。
- **实例 seed 与算法 seed 是两种东西**：实例 seed 决定数据，算法 seed（0/1/2）决定搜索的随机动作。
- **确定性方法在三个 seed 下重复，只在验证接口与记录格式**，**不提供三个独立的随机样本**。

**实例版本管理**：每个实例保存为 JSON 并计算 SHA-256，结果行记录 `input_sha256`。这样即使生成器将来改动、相同 seed 不再产生旧实例，**已保存的 JSON 仍然可审计**。

> **保存 seed 不能代替保存输入。** 前者依赖生成器实现不变，后者是**证据本身**。

## 4. 结果 schema：三层粒度

```text
results.csv              每次运行一行
runs/<run_id>.json       该次的配置 + 最好 Candidate + 完整 Schedule
runs/<run_id>.trace.csv  每次评价一行
```

**不要把三种粒度混在一张表里。**

`results.csv` 列：

```text
run_id, instance, input_sha256, group, algorithm, seed,
objective_name, budget, temperature, cooling, status,
objective, evaluations, elapsed_seconds,
reference_type, reference, gap, failure_reason
```

`summary.csv` 列：

```text
instance, group, algorithm, successful, failed,
mean, median, stdev, best,
mean_gap, mean_evaluations, mean_seconds
```

`runs/<run_id>.trace.csv` 列：

```text
evaluation, proposed, current, best, accepted, temperature
```

`metadata.json` 记录 `schema_version`、`created_utc`、Python 版本、平台、Git commit、工作区 dirty 标记、**源码 SHA-256**、**配置 SHA-256**，以及预算单位的定义。

**`run_id` 的格式是 `{实例}__{实验组}__{算法}__{seed}`**，因此每一条结果都能被唯一定位。

## 5. 状态语义：状态不是最优性声明

| 状态 | 含义 |
|---|---|
| `BASELINE` | 规则基线完成（`lpt`，1 次评价） |
| `BUDGET` | 达到评价上限 |
| `LOCAL_OPTIMUM` | 完整扫描邻域后无严格改善 |
| `FAILED` | 该次求解抛异常 |

> **任何一个「成功」状态都不自动等于 `OPTIMAL`。**

**参考值的两档分野**：

```text
optimum      仅当在适用范围内做完整枚举得到（本批次只有两个 tiny 实例）
best-known   本批次所有成功的主实验 + 敏感性运行中的最小值
```

**gap 约定**：

```text
gap = (value − reference) / max(1, |reference|)
```

两条边界：

- 参考值为 0 时**退化为绝对差**，**不能当百分比**；
- 对 **best-known** 的 gap **不是**真正的最优性差距——将来发现更好解，参考值与 gap 都会更新。

**失败行为什么用空值而不是 0？** 因为在**最小化**目标下，0 会被误判成「最好解」，污染均值和参考值。`failure_reason` 是**诊断证据**，失败行也**不能从总次数中消失**。

## 6. 主实验结果

三个 seed 的**均值**，越小越好。

| 实例 / 目标 | LPT | Random | First | Best | Multi-start | SA |
|---|---:|---:|---:|---:|---:|---:|
| `tiny_single` / ΣT | 57 | 36 | 36 | 36 | 36 | 36 |
| `tiny_parallel` / Cmax | 38 | 38 | 38 | 38 | 38 | 38 |
| `single_12` / ΣT | 719 | 313 | 575 | 529 | 373 | 261.67 |
| `parallel_12` / Cmax | 45 | 44.33 | 45 | 45 | 45 | 44.67 |
| `parallel_24` / Cmax | 95 | 94.33 | 92 | 94 | 94 | 93.33 |
| `routes_12` / Cmax | 54 | 45.33 | 41 | 41 | 45 | 42 |

```text
tiny_single   optimum = 36   ← 枚举证明
tiny_parallel optimum = 38   ← 枚举证明

single_12     best-known = 250
parallel_12   best-known = 43
parallel_24   best-known = 90
routes_12     best-known = 40
```

三条读表纪律：

1. **不存在在所有实例上领先的方法**：SA 在单机迟交案例更好，First/Best 在多工序 Cmax 案例更好。
2. **确定性方法重复运行不算三个独立随机样本**，其标准差为 0 不代表它更优。
3. **排名同时反映邻域扫描顺序与预算大小**：First/Best 在 tiny 实例上提前停机（分别用 23/37 和 17 次评价），在较大实例上用满 150 且部分扫描被截断。

## 7. 敏感性结果

三个 seed 的 SA 均值；**只比较同一行**。

| 实例 | 主配置 10/0.98 | 低温 0.1/0.98 | 高温 100/0.98 | 快冷却 10/0.9 |
|---|---:|---:|---:|---:|
| `single_12` | 261.67 | 262.00 | 282.67 | **255.33** |
| `parallel_12` | 44.67 | 44.67 | 44.33 | 44.33 |
| `parallel_24` | 93.33 | **91.67** | 94.33 | 92.00 |
| `routes_12` | 42.00 | 41.67 | 46.33 | 42.67 |

**理论预期**（由接受公式直接读出）：

```text
低温   → 更少接受坏解
高温   → 更常接受坏解
快冷却 → 较早趋向贪心
```

**实际结果**：**没有跨全部实例统一最好的设置**。快冷却在 `single_12` 均值较好；低温在 `parallel_24` 均值较好；高温在 `routes_12` 明显变差。

> **理论预期 ≠ 实际结果。** 最终质量是否改善**必须读数据**，不能由公式推出；反过来，在两个 tiny 实例上四种设置**全部追平 `optimum`**，这个「同分」也**不能**说明温度永远不重要——它只说明这个实例太容易，或预算还没到体现后期低温效果的阶段。

**方法学纪律**：如果从这四组里挑最好的当默认值，那就是**在本批数据上调参**；要这样做必须另留**独立测试集**，且此后不能把同一批数据当作未见数据。本项目**保留原教学默认值**，不宣称完成参数优化。

## 8. 图表：各自回答什么

| 文件 | 回答的问题 | **不能**据此断言 |
|---|---|---|
| `quality.png` | 本批次参考 gap 的分布如何 | 显著胜过所有方法 |
| `convergence.png` | 一个实例一个 seed 的最好值何时改善 | 平均收敛速度普遍最快 |
| `gantt.png` | 一个最好排程的机器占用与空闲如何 | 图看起来紧凑就一定可行 |

四条图表审计要点：

1. `quality.png` 合并了不同实例的**归一化** gap，**只作描述性展示**；**不同目标的原始值不合并求平均**。
2. `convergence.png` 横轴是**评价数**；不同算法可能提前停止，所以**曲线长短不同**——不能把提前停止误画成「完成了全部预算」。
3. `gantt.png` 的 `best` 应**单调不增**；若反向上升，先检查画的是 `current` 还是 `best`。
4. 甘特图用 `[start, end)` 长度绘制，**每条工序宽度应等于其工时**；**验证器先检查可行性，图只帮助理解**——「看起来紧凑」不是可行性证据。
5. **图不等于「本批最优」。** 本月 `gantt.png` 画的是 `routes_12__main__first__0`（`Cmax = 41`），而敏感性批次在**同一个实例**上到过 40。所以这张图可以拿来讲「一个可行排程长什么样」，**不能**拿来当「本批最好解」的证据。

## 9. 可复现性的三个层次

```text
第一层  同输入/配置/种子重跑 → 目标与评价数一致
第二层  最好 Candidate、Schedule、逐评价 trace 完全一致
第三层  环境、源码与输入均有记录 → 能解释版本差异
```

```text
时间戳、elapsed_seconds 不要求逐字节一致
   ↓ 但
忽略这些字段 ≠ 忽略算法结果
```

复现脚本 [m1w4d4_reproduce.py](../projects/01_scheduling_core/examples/m1w4d4_reproduce.py) 做三件事：

1. 先核对**当前源码 hash** 与 `metadata.json` 中记录的 `source_sha256`，不一致直接拒绝（提示使用原始源码版本）；
2. 逐行核对每个实例 JSON 的 SHA-256 与记录中的 `input_sha256`；
3. 重新求解并比较**目标、状态、评价数、最好候选、排程与完整轨迹**。

### 9.1 一个必须如实说明的当前状态

**第 1 道闸门今天会拒绝。** 实测：

```text
metadata.json 记录   source_sha256 = 025ed469c2621c03…
当前工作区           source_hash() = 4d6d74ea57637b7c…
                     → ValueError: source hash differs from recorded run
```

原因在 `metadata.json` 自己记着：`working_tree_dirty: true`。该批次产自一个**尚未提交的工作区**（记录的 `git_commit` 是 `538886b`，已不是当前 HEAD），而记录 commit 对应源码的 hash（`4f2c6d1e…`）与记录值也不相等。也就是说：**记录值既不是「记录 commit 的源码」，也不是「当前源码」，而是「当时那个 dirty 工作区」的源码。**

这不是脚本的缺陷，恰恰是它按设计工作：**它拒绝在一个无法证明是同一份源码的代码上宣称复现成功。** 三条结论：

1. **要复现 `month1_refactored` 这一批**，必须找回当时那份源码（`source_hash() == 025ed469…`）；
2. **要在当前源码上做可复现实验**，应新建一个批次目录重跑 benchmark，此后 `source_sha256` 就能对得上；
3. 这正是第三层复现（记录环境/源码/输入）存在的理由——**没有它，你连「对不上」都发现不了**。

**失败注入**（`test_benchmark_failure_is_recorded`）：把求解器替换成抛异常的函数，**只在测试临时目录中执行**，验证 `FAILED` 被记录、失败 gap 留空、统计表计入失败次数。

> **真实批次零失败只能说明「这一次成功了」；只有故障注入才能说明失败路径也被测试。**

**不要故意损坏正式实验文件来模拟失败。**

## 10. 测试与验收证据

| 月末要求 | 对应内容 |
|---|---|
| ≥10 个手算规则与指标案例 | `test_ten_hand_calculations`（Week 1） |
| 独立拒绝五类违规 | `schedule_validation.py` + `test_independent_validator_corruption`（**九类**） |
| 统一五种搜索比较 | `search.py` + `SearchConfig` + 完整评价预算 |
| ≥5 个小实例枚举 | `oracle.py` + `test_five_independent_enumerations`（5 个种子） |
| 一条命令生成表和图 | benchmark CLI + `configs/month1.json` |
| 参数、状态、失败与 gap 留痕 | `results.csv` / `metadata.json` / `runs/` / `failures.json` |
| 每周七天记录与周报 | 28 篇 Day 笔记 + `week1.md` … `week4.md` |

**复跑命令**（仓库根目录）：

```bash
python projects/01_scheduling_core/examples/m1w4d1_benchmark.py --output projects/01_scheduling_core/artifacts/my_run
python projects/01_scheduling_core/examples/m1w4d4_reproduce.py projects/01_scheduling_core/artifacts/month1_refactored
python -m pytest projects/01_scheduling_core -q
```

## 11. 已知局限

```text
规模:        小规模、六个合成实例、三 seed
分布:        所有生成实例全机器资格 → 未检验资格受限对搜索的影响
测试集:      没有把「调参集」与「最终测试集」分开
解码:        追加式 decoder 有构造偏置，且表示冗余
扫描顺序:    First/Best 先排列后指派 → 小预算可能到不了指派邻域
SA:          允许 no-op → 接受率不能直接当作有效探索率
统计:        不做显著性声明；三 seed 小样本不足以稳定估计小差异
复现:        忽略墙钟时间；不要求逐字节一致
```

**`artifacts/` 中三个批次的角色**：`month1_refactored` 是当前正式批次（月度报告与复现命令指向它）；`month1` 是重构前的正式批次（源码 hash 对应旧结构）；`month1_initial` 是首轮开发归档，不用于最终验收。

一个值得记录的**过程性局限**：当前批次的 `metadata.json` 记录 `working_tree_dirty: true`，即它是在**未提交的工作区**上产生的。这正是为什么必须同时记录 `source_sha256` 与 `config_sha256`——**当源码未提交时，用 dirty 标记 + 源码 hash 明确版本状态**。

## 12. 遗留问题

| # | 问题 | 状态 |
|---|---|---|
| 1 | 邻域消融（禁用 reassign）会怎样？ | **未执行**，列为后续工作 |
| 2 | 更大规模、资格受限实例的表现？ | **未执行**，列为后续工作 |
| 3 | 参数如何在独立留出集上选择？ | 需要新数据集 + 配对分析，本月未做 |
| 4 | 如何给出真正的最优性 gap？ | 需要**精确求解器**提供 bound/optimum（Month 2 的 MILP / CP-SAT） |
| 5 | 三个 seed 的均值差是否显著？ | **不做显著性声明**；需要更多实例与不确定性估计 |
| 6 | 追加解码器的构造偏置有多大？ | **未量化**，需要与「允许插空隙」的解码器对拍 |

## 13. 待个人完成

建议**闭卷**自测（答不出就回到对应日笔记补练，不必重搭整个工程）：

1. 重写两任务相邻交换证明（Week 1）。
2. 手推一条 decoder 轨迹（Week 2）。
3. 解释一个验证器错误从哪来、为什么被拒绝（Week 2）。
4. 从一条 trace 解释一次 SA 接受（Week 3）。
5. 复现一条结果：从 `results.csv` 找到 `run_id`，打开对应 JSON，重新验证并计算目标（Week 4）。

**周报中的「待学习练习」不假装已经由你完成。**

## 14. 接入 Month 2

```text
复用:  Instance、Schedule、独立验证器、Objective   ← 一行都不用改
新增:  MILP / CP-SAT 求解器，扩展 status、bound 与真实求解 gap
对照:  在同一输入上比较精确方法与本月基线
```

> **不要把本月的 best-known gap 直接当作求解器证明的 gap。** 前者是「与本批最好记录的差异」，后者是「相对可证明界或已证明最优值的差异」——两者含义完全不同。
