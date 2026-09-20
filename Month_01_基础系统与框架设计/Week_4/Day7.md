# Day 7：月度报告与复盘

> 当日主题：把一个月的工作整理成别人能重跑、能核查、能理解的 Scheduling Core & Search Lab，并把「已经做完」与「还没做」分清楚。
> 当日产出：**月度复盘脚本 `examples/m1w4d7_review.py` 与月末验收对应表**
> 建议投入：2 小时复盘 + 2 小时统计

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 说出 [MONTH1_REPORT.md](../MONTH1_REPORT.md) 的八段结构，并解释为什么按问题组织而不是按日期记录开发流水账。
2. 复述两条措辞规范：任何「最好」都要带实例、`objective` 与 `budget`；任何「最优」都要说明证据来自公式、界还是完整枚举。
3. 把月计划的每条验收要求对应到一个具体产物（文件、函数或测试名），而不是只写「已完成」。
4. 从 `summary.csv` 读出六个实例、六种方法的均值表，并区分 `optimum` 与 `best-known` 两类参考。
5. 说出复现命令清单、`metadata.json` 的九项版本证据，以及 `source_sha256` 闸门的作用。
6. 说出本月至少四条诚实局限，并解释为什么它们是边界而不是待办。
7. 说出精确方法会复用哪些既有模块、扩展哪些能力，以及为什么本月的 `best-known` gap 不能被当成求解器证明的 gap。
8. 用闭卷自测找出自己的知识缺口，并如实承认哪些练习还没做。

---

## 2. 为什么第 7 天要写报告，而不是继续跑实验

一个月的实验做完了，最诱人的选择是「再加一个算法」「再调一组参数」。但今天要回答的是更基础的问题：**这些数字能不能被别人使用？**

「被别人使用」有三个具体门槛：

```text
可重跑：别人拿到仓库，能用一条命令得到同一批表与图
可核查：别人不相信结论时，能沿着结论一路回到原始记录与代码
可理解：别人读完报告，知道问题是什么、方法是什么、结论的边界在哪里
```

这三条都不靠新实验解决。第 3 节的报告结构、第 6 节的证据链、第 8 节的验收对应表，做的都是这三件事。**报告不是装饰，它是把「跑过一次」变成「可复现的研究对象」的那一步。**

同时今天也是**诚实日**：把已经做完的、还没做的、做不动的分开写。一个只有「已完成」列表的项目，通常意味着作者没意识到自己的边界。

本日不重跑基准、不新增算法、不修改既有实验目录；只对 Day 1 已经落盘的批次做只读复盘。

---

## 3. 报告的八段结构

`MONTH1_REPORT.md` 按下面八段组织，顺序不是随意的：

| 段 | 回答的问题 | 本月的对应内容 |
|---|---|---|
| 1 问题与范围 | 到底解哪一类问题，不解决什么 | `α\|β\|γ` 记法下的 `1\|\|ΣCj` / `1\|\|Lmax` / `1\|\|ΣwjCj` / `P\|\|Cmax` / `1\|rj\|ΣCj` |
| 2 模型 | 输入与解用什么数据结构表达 | 不可变 `Instance`（Job / Operation / Machine）、`Candidate(order, assignments)`、`Schedule` |
| 3 方法 | 有哪些算法、各自怎么走一步 | 规则基线 `lpt` + `random` / `first` / `best` / `multistart` / `sa` |
| 4 正确性证据 | 凭什么相信结果是可行的、可比的 | 独立验证器九类破坏、十个手算案例、五个小实例枚举、统一 `Objective` |
| 5 运行设置 | 用什么配置跑出来的 | `configs/month1.json`：3 个 `seed`、`budget = 150`、四组 SA 设置 |
| 6 结果 | 数字是什么 | `results.csv`（162 行）、`summary.csv`（54 行）、三张图 |
| 7 局限 | 哪些结论不能下 | 见表 10 与表 11 |
| 8 复现 | 别人怎么重跑 | 三条命令 + `metadata.json` 的九项证据 |

**为什么不是按日期写**：按日期写会变成「周一做了什么、周二做了什么」的流水账，读者必须自己把八天的信息重新拼装才能回答「这个方法为什么可信」。按问题组织的意思是：**每一段都要能被单独引用**——引用第 4 段的人可以只关心验证方式，引用第 6 段的人可以只关心数字。

---

## 4. 措辞规范：两种最容易说过头的话

### 4.1 任何「最好」都要带三个限定

```text
可以说：在 routes_12 上、objective=makespan、budget=150 的六个方法里，
        低温 SA（T0=0.1, cooling=0.98）三个 seed 的均值最小（41.67）。
不可以说：低温 SA 是最好的。
```

一句话里的「最好」必须能回答：**哪个实例、哪个 `objective`、多少 `budget`、在哪些方法之间比。** 少了任何一项，这句「最好」就会被读者自动放大成全局结论。

同理，报 `mean` 必须同时报 `median` 与 `best`，报统计量必须同时报样本量与失败计数（Day 5 第 4.4 节）。

### 4.2 任何「最优」都要说明证据来源

`optimum` 这个词只有三种合法证据来源：

| 证据来源 | 本月是否使用 | 例子 |
|---|---|---|
| 公式（可证明的最优性条件） | 使用 | 单机 ΣCj 的 SPT 规则、`1\|\|Lmax` 的 EDD 规则 |
| 界（下界或松弛） | 本月未使用 | 需要 MILP / CP-SAT 给出 bound |
| 完整枚举 | 使用 | 两个 tiny 实例：24 与 384 个候选组合 |
| 算法集合内排名第一 | **不算证据** | 六种方法里的最小值只能说 `best-known` |

本批次六个实例里只有 `tiny_single`（36）与 `tiny_parallel`（38）的参考是 `optimum`，其余四个的参考是本批全部成功运行的最小值，标 `best-known`。**排第一不等于数学最优**，这是本月最重要的一条纪律。

### 4.3 接入精确方法：复用与扩展

MILP / CP-SAT 不需要重新发明输入与解：

```text
直接复用：Instance 模型、Candidate(order, assignments)、Schedule、
         独立验证器 validate_schedule、统一 Objective（Cmax / ΣCj / ΣTj / ΣwjCj / Lmax）
扩展：    bound 与真实求解 gap、status 词表（OPTIMAL / INFEASIBLE / TIME_LIMIT）、
         更大的实例规模与更一般的机器资格分布
```

关键纪律：**本月的 `best-known` gap 不能被当成求解器证明的 gap。** 本月的 `gap` 只是「与参考值的相对差异」，参考值本身是本批运行的最小值；只有在求解器给出 `bound` 与最优性证明之后，才允许写 `optimum`。

---

## 5. 示例：修正后的月度结果摘要（真实数据）

从 `summary.csv` 的 `main` 组读出六个实例、六种方法的均值（三个 `seed`）：

| 实例 | `objective` | 参考 | 参考类型 | `lpt` | `random` | `first` | `best` | `multistart` | `sa` |
|---|---|---|---|---|---|---|---|---|---|
| `tiny_single` | ΣT | 36 | `optimum` | 57 | 36 | 36 | 36 | 36 | 36 |
| `tiny_parallel` | Cmax | 38 | `optimum` | 38 | 38 | 38 | 38 | 38 | 38 |
| `single_12` | ΣT | 250 | `best-known` | 719 | 313 | 575 | 529 | 373 | 261.67 |
| `parallel_12` | Cmax | 43 | `best-known` | 45 | 44.33 | 45 | 45 | 45 | 44.67 |
| `parallel_24` | Cmax | 90 | `best-known` | 95 | 94.33 | 92 | 94 | 94 | 93.33 |
| `routes_12` | Cmax | 40 | `best-known` | 54 | 45.33 | 41 | 41 | 45 | 42 |

### 5.1 两个 `optimum` 是现场枚举出来的

脚本对两个 `tiny` 实例重新做了完整枚举，并与 `results.csv` 记录的参考值对拍：

```text
tiny_single   ΣT   枚举 24 个组合 → optimum = 36
tiny_parallel Cmax 枚举 384 个组合 → optimum = 38
```

组合数可以手算验证：

```text
tiny_single  ：4 个作业、1 台机器、每作业 1 道工序
               候选空间 = 4! 个 order × 1 种 assignments = 24
tiny_parallel：4 个作业、2 台机器、每作业 1 道工序
               候选空间 = 4! 个 order × 2^4 种 assignments = 24 × 16 = 384
```

**结论**：这两个数是可以举证的最优，任何人重跑 `exhaustive_optimum` 都能得到同一个值；它们支持「某方法追平了 `optimum`」这样的说法。

### 5.2 四个 `best-known` 为什么不能升级成 `optimum`

同样的候选空间计算，放到较大实例上就不可枚举：

```text
single_12  ：12 个作业、1 台机器 → 12! = 479001600 个 order
parallel_12：12 个作业、3 台机器 → 12! × 3^12
             12! = 479001600，3^12 = 531441
             乘积 ≈ 2.5 × 10^14
routes_12  ：12 道工序、3 台机器，且带作业内先序约束
             order 只保留合法拓扑序（6 条长度为 2 的链），assignments 仍有 3^12 种
```

枚举 2.5 × 10^14 个候选在任何教学预算下都不可行，所以这四个参考只能叫 `best-known`：**它是「本批运行里最小的那个」，换一批 `seed`、加一个算法，这个值本身就会变。**

这也解释了一个容易被忽略的事实：`routes_12` 的 `best-known = 40` 恰好由敏感性组的低温 SA 取到（`seed = 0` 那次）。**参考值来自被评价的方法之一**，所以「用 `gap` 评价低温 SA」在这个实例上等于自己给自己打分。这是引入独立 `bound` 的另一个理由。

### 5.3 这张表能说什么、不能说什么

| 能说 | 不能说 |
|---|---|
| 在 `single_12` 的 ΣT 上，`lpt` 的均值（719）远高于五种搜索方法 | 五种搜索方法「解决了」单机加权类问题 |
| 在两个 tiny 实例上，六种方法有五种追平枚举 `optimum` | 追平 `optimum` 说明这些方法在一般实例上也能最优 |
| 六个实例的 `mean` 已从 `results.csv` 复算一致（Day 5 第 7 节） | 均值差就是「显著更好」，本批只有三个 `seed` |

---

## 6. 实现：报告与证据链怎么对上

### 6.1 报告里每个数字的来源

```text
MONTH1_REPORT.md 的任何表格  ←  summary.csv        （统计层，可复算）
summary.csv 的任何一行       ←  results.csv        （运行层，一行=一次运行）
results.csv 的任何一行       ←  runs/<run_id>.json 与 runs/<run_id>.trace.csv （解层与过程层）
```

这条链上没有人工编辑的环节：`summary.csv` 由 [benchmark.py](../../projects/01_scheduling_core/scheduling_experiments/benchmark.py) 的 `summarize` 生成，`report.md` 与三张图由同一个函数的同一次调用生成（第 `run` 的最后一行），所以表和图不可能来自两次不同的运行。

### 6.2 三份证据文件的分工

| 文件 | 记录什么 | 本批次的值 |
|---|---|---|
| `metadata.json` | 环境与版本：`python`、`platform`、`git_commit`、`working_tree_dirty`、`source_sha256`、`config_sha256`、`budget_unit` 等九项 | `python 3.14.6`、`git_commit 538886b`、`working_tree_dirty true` |
| `failures.json` | 失败运行的清单与原因 | `[]`（本批零失败） |
| `verification.json` | 本月的验证证据 | `reproduced_runs 162`、`identical_candidates_schedules_and_traces 162`、`tests_passed 107` |

三份文件回答三个不同的问题：**批次是怎么跑出来的**（`metadata.json`）、**有没有失败**（`failures.json`）、**验证做过哪些**（`verification.json`）。

`verification.json` 里最值得引用的是两条 162：`reproduced_runs = 162` 说明 [m1w4d4_reproduce.py](../../projects/01_scheduling_core/examples/m1w4d4_reproduce.py) 把每一次成功运行都重新求解并核对过；`identical_candidates_schedules_and_traces = 162` 说明连完整轨迹都逐点相同（Day 4 第 2 节讲的第二层可复现性）。**这两条是把「可复现」从声明变成事实的关键证据。**

### 6.3 `source_sha256` 闸门与测试数量的口径

复现脚本的第一道闸门是源码哈希：源码版本对不上，它直接拒绝执行，而不是给出一批「看起来一样」的数字。本批次记录的是 `git_commit 538886b`，而仓库此后又发生了重构（HEAD 已经前进），所以**要在当前工作树上重跑复现，必须先用记录里那一版源码，不能默认「现在的代码还能重放当初的批次」**。这是设计意图，不是缺陷。

测试数量也要带口径：`verification.json` 记录 `tests_passed = 107`，那是**本批次**在它的源码版本上跑出的数；当前工作树用 `python -m pytest --collect-only -q` 收集到 **127** 条。两个数都对，但属于不同时点，引用时必须写明出处——这与 Day 3 第 7 节的处理方式一致。

---

## 7. 实验：`m1w4d7_review`

对应脚本 [m1w4d7_review.py](../../projects/01_scheduling_core/examples/m1w4d7_review.py)。脚本**只读** `artifacts/month1_refactored/`，不写文件、不重跑基准、不重新出图。在项目目录 `projects/01_scheduling_core` 下运行：

```bash
python examples/m1w4d7_review.py
```

脚本做七件事：打印验收证据表并现场核对批次产物、打印修正后的结果摘要（含两个 `optimum` 的现场重枚举）、给出复现命令清单与版本证据、列出局限、给出精确方法的复用与扩展、给闭卷自测建议、收尾。实际输出：

```text
=== Month 1 月度复盘 ===

== 1. 本月验收证据表：每条要求对应哪个具体产物 ==
  [≥10 个手算规则与指标案例]
    产物：tests/test_month1.py::test_ten_hand_calculations（HAND_CASES 10 组）
    说明：expected 全部来自手算时间线，不由被测函数生成
  [独立拒绝 ≥5 类违规]
    产物：scheduling_core/schedule_validation.py + test_independent_validator_corruption
    说明：9 类破坏：precedence / overlap / illegal assignment / missing / duplicate / release / duration / unknown operation / invalid time type
  [统一五种搜索比较]
    产物：scheduling_algorithms/search.py（ALGORITHMS、SearchConfig、统一评价预算）
    说明：lpt 基线 + random / first / best / multistart / sa 五种搜索，共用初始解与预算口径
  [≥5 个小实例枚举]
    产物：scheduling_algorithms/oracle.py + test_five_independent_enumerations
    说明：seed 0..4，每例 4 工序 / 2 机器，384 个组合，oracle 与 decoder 最小值对拍
  [一条命令生成表和图]
    产物：scheduling_experiments/benchmark.py + configs/month1.json
    说明：results.csv、summary.csv、report.md、quality/convergence/gantt 三张图
  [参数、状态、失败与 gap 留痕]
    产物：results.csv、metadata.json、runs/、failures.json、verification.json
    说明：每次运行留 config/candidate/schedule/trace，失败留 FAILED 与原因，参考标 optimum 或 best-known
  [每周七天记录与周报]
    产物：Week_1..Week_4 的 28 篇 Day 笔记 + week1..week4 周报
    说明：笔记按概念组织；周报汇总本周成果、局限与遗留问题

  现场核对（全部来自当前 artifacts/，只读）：
    results.csv 行数 = 162（main 108 + 敏感性 54）
    failures.json = []（长度 0）
    runs/*.json = 162 个；runs/*.trace.csv = 162 个；instances/*.json = 6 个
    status 计数 = {'BASELINE': 18, 'BUDGET': 132, 'LOCAL_OPTIMUM': 12}；FAILED = 0
    quality.png / convergence.png / gantt.png 三张图都存在
    verification.json: tests_passed = 107
    verification.json: ruff = passed
    verification.json: black = passed
    verification.json: mypy_source_files = 18
    verification.json: reproduced_runs = 162
    verification.json: pre_refactor_rows_equal_excluding_timing = 162
    verification.json: identical_candidates_schedules_and_traces = 162
    verification.json: documentation_links = passed
    verification.json: package_dependency_boundaries = passed
    verification.json: daily_examples = passed
    注：tests_passed=107 是**该批次**记录的数；当前工作树用
    python -m pytest --collect-only -q 收集到 127 条（Day 5/6 之后新增了测试）。
    两个数都对，但属于不同时点，引用时必须带上出处。
    笔记核对：28 篇 Day 笔记 + 4 篇周报（Month_01_基础系统与框架设计）

== 2. 修正后的月度结果摘要（读 summary.csv，三个 seed 均值） ==
  实例            目标         参考  参考类型               lpt     random      first       best multistart         sa
  parallel_12   Cmax       43  best-known          45      44.33         45         45         45      44.67
  parallel_24   Cmax       90  best-known          95      94.33         92         94         94      93.33
  routes_12     Cmax       40  best-known          54      45.33         41         41         45         42
  single_12     ΣT        250  best-known         719        313        575        529        373     261.67
  tiny_parallel Cmax       38  optimum             38         38         38         38         38         38
  tiny_single   ΣT         36  optimum             57         36         36         36         36         36

  optimum 与 best-known 的区别：
    tiny_single   ΣT   枚举 24 个组合 → optimum = 36（与 results.csv 的参考一致，属于可证明的最优）
    tiny_parallel Cmax 枚举 384 个组合 → optimum = 38（与 results.csv 的参考一致，属于可证明的最优）
    其余四个实例的参考是本批次全部成功运行的最小值，只能标 best-known：
      single_12 = 250、parallel_12 = 43、parallel_24 = 90、routes_12 = 40
    它们没有最优性证明：换一批数据、多跑几个 seed，参考值本身就会变。

  口径提醒（引用结果时必须一起说）：
    - 实例：六个合成实例，规模小，不代表工业规模。
    - 目标：tiny_single 与 single_12 是 ΣT，其余四个是 Cmax；两种目标不互相比较。
    - 预算：150 次「解码 + 独立验证 + 目标计算」，包含初始化、拒绝与 no-op。
    - 排名：只在「本批六种方法」内比较，排第一不等于数学最优。

== 3. 复现命令清单（在项目目录 projects/01_scheduling_core 下运行） ==
  1. 重跑整批（新目录必须不存在或为空，不覆盖已有实验）：
     python examples/m1w4d1_benchmark.py --output artifacts/my_run
  2. 逐次复现已保存的批次（核对目标、状态、评价数、候选、排程与完整 trace）：
     python examples/m1w4d4_reproduce.py artifacts/month1_refactored
  3. 全量测试：
     python -m pytest -q

  本批次的版本证据（metadata.json 记录）：
    python=3.14.6  platform=Windows-10-10.0.19045-SP0  created_utc=2026-09-15T08:50:38.290916+00:00
    git_commit=538886b  working_tree_dirty=True
    source_sha256=025ed469c2621c03...  config_sha256=8b126be787355ee7...
  复现脚本的第一道闸门是 source_sha256：源码版本对不上，它直接拒绝执行，
  而不是给出一批「看起来一样」的数字。所以复现要用记录里的那版源码，
  不能默认「现在的代码也能复现当初的批次」。

== 4. 诚实局限清单（这些不是待办，是当前的边界） ==
  1. 追加式 decoder 有表示偏置：它把工序依次追加到机器末尾，不会插入已有空隙，所以一部分可行排程永远搜不到。
  2. First/Best 先扫描排列邻域，再扫描机器指派邻域；小预算可能根本走不到指派邻域，排名里混着「邻域扫描顺序」而不只是算法本身。
  3. SA 允许 no-op（原地 swap/insert 或指派到同一台机器），仍计入一次评价，所以接受率不能当作有效探索率：接受里包含大量目标值不变的动作。
  4. 生成器产出的实例全部是「所有机器都能做所有工序」，机器资格受限的情形没有被覆盖。
  5. 三个 seed、六个合成实例只支持教学观察；没有统计显著性声明，也没有置信区间。
  6. 参数（T0=10、cooling=0.98）是教学默认值，没有在独立留出集上验证过；敏感性结果只说明「本批数据上不同设置有差异」，不构成推荐配置。

  另外两条口径上的限制：
    - best-known gap 只是「与本批最好记录的相对差异」，不是求解器证明的 gap。
    - 本月没有做邻域消融，也没有做更大规模实例，这些列为后续工作。

== 5. 接口的复用性与本月的边界 ==
  这些接口是为复用而设计的（不需要重新发明）：
    - 同一个 Instance 模型：Job / Operation / Machine，输入不可变、可被多算法公平复用。
    - 同一个 Schedule 与 Candidate 表示：order + assignments 仍然是解的载体。
    - 同一个独立验证器：validate_schedule 不调用 decoder，任何方法都要过同一道闸门。
    - 同一套 Objective：Cmax / ΣCj / ΣTj / ΣwjCj / Lmax 由同一个模块计算。
    - 同一批输入与同一批基线结果：新方法要在这批数据上对比，而不是换一批数据自证。

  本月没有做的（能力边界，不是缺陷而是分阶段推进）：
    - 没有 MILP / CP-SAT：给不出 bound，也报不出真实的求解器 gap。
    - status 词表只有搜索侧状态：BASELINE / BUDGET / LOCAL_OPTIMUM，
      没有 OPTIMAL / INFEASIBLE / TIME_LIMIT 这类求解器状态。
    - 参考口径只有 best-known：它只是「与本批最好记录的差异」，
      不是求解器证明的 gap，更不能写成 optimum。
    - 规模与资格分布有限：更大的实例、更一般的机器资格才有区分度。

== 6. 闭卷自测建议（答不出就回到对应日笔记，不必重搭工程） ==
  1. 重写两任务相邻交换证明，说清 ΣCj 与 ΣwjCj 的差别。
  2. 手推一条 decoder 轨迹：给定 order 与 assignments，写出每道工序的起止时刻。
  3. 解释一个验证器错误：例如 precedence 与 overlap 分别在检查什么。
  4. 从一条 trace.csv 解释一次 SA 接受：Δ、T 与接受概率的关系。
  5. 复现一条结果：从 results.csv 的 run_id 一路回到 run JSON 与 trace，数字对得上。
  周报里的「待学习练习」不假装已经由你完成；没做就是没做。

== 7. 结论 ==
  这个月的成果不是「某方法赢了」，而是一套可核对的工作方式：
  问题语言、不可变输入、独立验证、统一目标、可复现批次、明确标注的参考口径。
  全部断言通过。
```

**实验观察**：

1. 第 1 段现场核对了批次产物的全部计数：`results.csv` 162 行（`main` 108 + 敏感性 54）、`runs/*.json` 与 `runs/*.trace.csv` 各 162 个、`instances/*.json` 6 个、`failures.json` 为空数组、`status` 计数 18 / 132 / 12 / 0。**结论**：报告里的每个数字都能被一段只读脚本重新数一遍。
2. 第 2 段重新枚举了两个 tiny 实例并与 `results.csv` 的参考对拍（24 与 384 个组合），断言 `kind == "optimum" and value == reference`。**实验观察**：`optimum` 是可举证的，`best-known` 只是本批最小值——两类参考在脚本里被显式区分，不能混用词。
3. 第 3 段把三条复现命令与 `metadata.json` 的版本证据放在一起。**结论**：命令能否复现，取决于源码版本是否与记录一致；`source_sha256` 闸门就是这个判断的执行者。
4. 第 4 段的六条局限都是**边界陈述**，不是「还没做的任务」：它们说明本月的结论天然到哪一步为止（表示偏置、邻域扫描顺序、no-op、资格分布、样本量、参数未验证）。
5. 第 5 段明确了精确方法的交接纪律：复用 `Instance` / `Schedule` / 验证器 / `Objective`，扩展 `bound` 与 `status`，**不把本月的 `best-known` gap 当作求解器证明的 gap**。这条纪律决定了什么时候才能第一次合法写 `optimum`。

---

## 8. 月末验收对应表

| 月计划要求 | 对应内容 | 现场可否核对 |
|---|---|---|
| ≥10 个手算规则与指标案例 | Week 1 Day 6 与 `tests/test_month1.py::test_ten_hand_calculations`（10 组 `HAND_CASES`） | 可：测试名与用例数 |
| 独立拒绝五类违规 | [schedule_validation.py](../../projects/01_scheduling_core/scheduling_core/schedule_validation.py) 与九类破坏测试 | 可：九类破坏逐个断言 |
| 统一五种搜索比较 | [search.py](../../projects/01_scheduling_core/scheduling_algorithms/search.py) 的 `ALGORITHMS`、`SearchConfig` 与统一评价预算 | 可：`ALGORITHMS` 元组与 `budget` 列 |
| ≥5 个小实例枚举 | [oracle.py](../../projects/01_scheduling_core/scheduling_algorithms/oracle.py) 与五种子对拍 | 可：两个 tiny 实例现场重枚举 |
| 一条命令生成表和图 | `benchmark` CLI 与 `configs/month1.json` | 可：`results.csv` / `summary.csv` / `report.md` / 三张图 |
| 参数、状态、失败与 gap 留痕 | `results.csv`、`metadata.json`、`runs/`、`failures.json`、`verification.json` | 可：五处计数与词表 |
| 每周七天记录与周报 | 28 篇 Day 笔记与 `week1…week4` | 可：目录计数 28 + 4 |

**结论**：本月的七条验收要求都能落到一个具体文件名或测试名上，并且都能用只读命令重新数一遍；「已完成」三个字不是证据，可核对的具体产物才是。

---

## 9. 接入精确方法会复用什么

```text
复用（不重新发明）：
  Instance / Job / Operation / Machine     输入不可变，精确方法与启发式共用同一道题
  Candidate(order, assignments) / Schedule 解的载体不变，便于同解对比
  validate_schedule                        独立验证器，精确方法也要过同一道闸门
  Objective                                同一套指标函数，禁止两套定义
  本批输入与基线结果                        在同一输入上比精确方法，而不是换一批数据

扩展（本月没有的能力）：
  bound 与真实求解 gap                      MILP / CP-SAT 给出界与最优性证明
  status 词表                              增加 OPTIMAL / INFEASIBLE / TIME_LIMIT
  参考口径                                 只有拿到 bound 与证明之后才写 optimum
  规模与资格分布                            更大实例、更一般的机器资格，才拉得开区分度
```

**结论**：接入精确方法的目标不是「用求解器跑一遍」，而是**在同一道题上补上本月缺的那一半证据**——下界与最优性证明。

---

## 10. 本月还没有做什么

按「明确排除」而不是「忘了做」记录：

1. **没有做邻域消融**：`swap` / `insert` / `reassign` 三类动作各自贡献多少，本月没有分开测。
2. **没有更大规模实例**：最大是 24 个作业、3 台机器；工业规模（上千作业）没有触及。
3. **没有精确方法的界**：本月只有两个 tiny 实例的完整枚举，没有 LP/MILP 下界。
4. **没有统计显著性**：三个 `seed` 只能给描述性统计，没有置信区间，也没有配对检验。
5. **没有机器资格受限的实例**：生成器产出的实例都是「所有机器都能做所有工序」，`eligible_machine_ids` 的约束能力没有被数据覆盖。
6. **没有与其他公开基准对比**：全部实例由本项目生成器产出，不是标准测试集。

以上六条都在 `MONTH1_REPORT.md` 的局限段落里，属于**已知边界**，不是遗漏。

统计补充：三个 `seed` 的均值差只作**探索性**观察（Day 6 第 7 节已经看到并列与 1 个单位就能翻转排名的情况）；更正式的结论需要更多实例、独立测试集、配对分析与不确定性估计。项目最终的价值不是某一批表或某一组参数，而是**把这些步骤变成可重复的过程**——这也正是精确求解要接着做的事。

---

## 11. 遗留问题（Open Questions）

| 问题 | 现状 | 下一步 |
|---|---|---|
| `best-known` 参考由被评价的方法取到，评价会自我强化 | `routes_12` 的 40 来自低温 SA | 精确方法用 `bound` 取代本批最小值 |
| 源码版本与批次记录不一致 | 记录 `git_commit 538886b`，仓库此后重构，HEAD 已前进 | 复现前先取回记录版本；哈希闸门会拒绝不一致的源码 |
| 测试数量有两个口径 | 批次记录 107，当前树 127 | 引用时写明时点与来源，禁止混用 |
| `working_tree_dirty: true` | 批次在未提交的工作树上运行 | 正式批次建议在干净工作树上重跑并记录 |
| `gantt.png` 画的不是全批最优 | 图上 `objective = 41`，本实例 `best-known = 40` | 报告引用图时写明 run_id 与实例范围 |
| SA 参数与目标尺度相关 | `exp(-Δ/T)` 的 Δ、T 同量纲 | 接入精确方法前做尺度归一化或改用相对温度 |

---

## 12. 待个人完成

以下项目**没有**由本项目代做，属于个人练习清单：

- Week 1～Week 4 各日「今日练习」中尚未动手的部分（尤其是手算与换一条运行复算的练习）。
- 第 7 节的五条闭卷自测：能背概念不等于能在纸上推一遍。
- 周报中标注为「待学习 / 待练习」的条目——它们不是已完成项。
- 用自己的话把 `Month 1` 讲给一个不熟悉调度的同学听，看他能否复述「为什么需要独立验证器」。

**结论**：这些是「看懂了」与「会做」之间的差距，报告不替它们背书。

---

## 13. 今日练习

1. **练习 1（措辞改写）**：把「SA 最好」改成一句符合第 4.1 节规范的完整表述，要求带实例、`objective`、`budget` 与比较范围。
2. **练习 2（证据来源）**：为 `single_12` 的 `best-known = 250` 写两句：可以怎么说、不可以怎么说。
3. **练习 3（结果复算）**：不看脚本，从 `results.csv` 手算 `parallel_24` 上 `first` 的均值，与 `summary.csv` 对照，并说明它离参考 90 差多少。
4. **练习 4（验收对应）**：为「≥5 个小实例枚举」这条要求找出至少两个可核对的证据（一个在测试里、一个在产物里）。
5. **练习 5（交接）**：写出精确方法接手时最需要先确认的三件事（输入模型、验证器、参考口径），并说明为什么 `best-known` gap 不能直接当求解器 gap。

---

## 14. 验收清单

- [ ] 能说出报告的八段结构与每段回答的问题，并能解释为什么按问题而不是按日期组织。
- [ ] 能复述「最好」与「最优」两条措辞规范，并各举一个可以说/不可以说的例子。
- [ ] 能说出本批次哪些实例的参考是 `optimum`、哪些是 `best-known`，并给出各自的证据来源。
- [ ] 能说出 `metadata.json` / `failures.json` / `verification.json` 三份文件的分工。
- [ ] 能解释 `source_sha256` 闸门的作用，以及为什么复现要用记录里的源码版本。
- [ ] 能说出月末验收七条要求各自对应的产物，并知道怎么现场核对。
- [ ] 能说出至少四条诚实局限，并区分「边界」与「待办」。
- [ ] 能说出精确方法复用什么、扩展什么，以及 `best-known` gap 为什么不能当求解器 gap。
- [ ] `python examples/m1w4d7_review.py` 运行无断言失败，且不写入 `artifacts/` 任何文件。
- [ ] `python -m pytest -q` 全部通过（本日不新增测试；当前收集 127 条，批次记录为 107 条）。

---

## 15. 自测题

不看上文回答：

- Q1：报告的八段结构是什么？为什么不能按日期写？
- Q2：说「最好」时必须带上哪几个限定？说「最优」时必须说明什么？
- Q3：本批次哪两个实例的参考是 `optimum`？各自的组合数是多少？
- Q4：为什么 `routes_12` 的参考只能是 `best-known`？这个值由谁取到？
- Q5：`metadata.json`、`failures.json`、`verification.json` 各回答什么问题？
- Q6：`verification.json` 里「两条 162」分别是什么？它们证明了哪一层可复现性？
- Q7：`source_sha256` 闸门在什么情况下会拒绝执行？为什么这是设计而不是缺陷？
- Q8：本批次的测试数量为什么有两个数？引用时要注意什么？
- Q9：说出至少四条本月的诚实局限，并说明它们为什么是边界而不是待办。
- Q10：精确方法会复用哪些模块、扩展哪些能力？`best-known` gap 为什么不能被当作求解器证明的 gap？

### 参考答案

- A1：问题与范围 / 模型 / 方法 / 正确性证据 / 运行设置 / 结果 / 局限 / 复现；按日期写会变成开发流水账，读者必须自己重新拼装才能判断「结论是否可信」，而每一段都应该能被单独引用。
- A2：说「最好」要带实例、`objective`、`budget` 与比较的方法范围（还应同时给 `mean` / `median` / `best` 与样本量）；说「最优」要说明证据来自公式、界还是完整枚举。
- A3：`tiny_single`（ΣT，36）与 `tiny_parallel`（Cmax，38）；组合数分别是 4! = 24 与 4! × 2^4 = 384。
- A4：它的候选空间约为 2.5 × 10^14（12! × 3^12），不可枚举，所以参考只能是本批成功运行的最小值；40 这个值由敏感性组的低温 SA（`T0 = 0.1`，`seed = 0`）取到。
- A5：`metadata.json` 记录批次怎么跑出来的（环境与版本），`failures.json` 记录有没有失败及原因，`verification.json` 记录验证做过哪些项。
- A6：`reproduced_runs = 162`（每次成功运行都被重新求解并核对）与 `identical_candidates_schedules_and_traces = 162`（连完整轨迹都逐点相同）；后者证明的是可复现性的第二层。
- A7：当工作树重算出的源码哈希与 `metadata.json` 记录不一致时拒绝执行；它避免用不同版本的代码产出「看起来一样」的数字，把版本差异显式暴露出来。
- A8：`verification.json` 记录的是**该批次**源码版本上的 `tests_passed = 107`，当前工作树收集到 127 条；引用时必须写明时点与来源，不能把两个数混用。
- A9：例如追加式 decoder 的表示偏置、First/Best 的邻域扫描顺序影响排名、SA 的 no-op 使接受率不等于有效探索率、实例全是全机器可做、三个 `seed` 不支持显著性、参数未在独立留出集上验证；它们是当前方法能覆盖范围的上界，不是待补的作业。
- A10：复用 `Instance` / `Candidate` / `Schedule` / `validate_schedule` / `Objective` 与本批输入；扩展 `bound` 与真实求解 gap、`status` 词表、实例规模与资格分布；本月的 `gap` 只是与本批最小值的相对差异，参考值没有最优性证明，所以它不等于求解器给出的 gap。

---

## 16. 今日一句话总结

> **报告的价值不在于多写了一个算法，而在于让每个数字都能被重跑、被核查、被限定：能举证的才叫 `optimum`，只有本批最小值的只能叫 `best-known`。**
