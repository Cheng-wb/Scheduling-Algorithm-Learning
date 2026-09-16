# Day 5：统计表、收敛图与甘特图

> 当日主题：把 162 行逐次运行压缩成可信的统计表，并说清每张图只能回答什么问题。
> 当日产出：**统计复盘脚本 `examples/m1w4d5_stats.py` 与图表审计口径**
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 说出 `summary.csv` 的分组键 `(instance, group, algorithm)` 与十二个字段，并解释一行到底汇总了什么。
2. 用三个 `seed` 的原始 `objective` 手算 `mean` / `median` / `stdev`，并与 `summary.csv` 的记录对拍。
3. 用 10 / 10 / 13 这个三数样本说明：只报 `best`、只报 `mean`、三个都报，各自会得出什么结论。
4. 说清样本标准差（分母 n−1）与总体标准差（分母 n）的区别，以及这里为什么用前者。
5. 解释确定性算法 `stdev = 0` 的确切含义，以及它**不**代表的含义。
6. 说出 `quality.png` / `convergence.png` / `gantt.png` 各自回答什么、各自不能用来断言什么。
7. 从 `runs/<run_id>.json` 重建排程、用独立验证器复核，并逐条核对「甘特条宽度 == 加工时间」。
8. 解释 `convergence.png` 的 `best` 为什么必须单调不增，以及把 `current` 画成曲线会出现什么假象。

---

## 2. 为什么第 5 天要读统计与图

Day 3 解决「一个数字的出处」，Day 4 解决「一批运行的留痕」。今天要解决第三个问题：**162 行怎么变成一句别人能读、也不能被误读的结论。**

从原始记录到结论之间隔着三个动作，每个动作都可能引入错误：

```text
压缩：162 行逐次结果 ──► 54 行分组统计     （summary.csv 的 mean/median/stdev/best）
比较：同一分组键内跨 seed、跨算法、跨设置    （同一实例、同一 objective 才能比）
呈现：把分布与轨迹画成图                    （图只描述，不证明）
```

这三个动作都有同一个失败模式：**用更少的数字讲更强的结论。**

- 只报 `best`：读者会以为每次运行都能到那个值。
- 只报 `mean`：读者看不出运行之间的波动有多大。
- 只看图：箱线图的形状看起来「谁明显更好」，但图上没有任何检验，也没有样本量。

所以今天的目标不是「会画图」，而是**说得出每个统计量和每张图的边界**。本日不新增算法、不重跑基准、不生成新图，只对 Day 1 已经落盘的批次做只读复盘。

---

## 3. 统计单位：`summary.csv` 的一行是什么

### 3.1 分组键与字段清单

`summary.csv` 的一行 = **一个（实例，实验组，算法）组合在若干 `seed` 上的汇总**。本批次共 54 行：六个实例 × 六种算法的主实验 36 行，加上六个实例 × 三个敏感性设置 18 行。

| 字段 | 含义 | 属于哪一类 |
|---|---|---|
| `instance` | 实例名 | 分组键 |
| `group` | 实验组，主实验为 `main`，敏感性为 `sa_t…_c…` | 分组键 |
| `algorithm` | 算法名 | 分组键 |
| `successful` | 成功运行的次数 | 计数 |
| `failed` | 失败运行的次数 | 计数 |
| `mean` | 成功运行 `objective` 的算术平均 | 统计量 |
| `median` | 成功运行 `objective` 的中位数 | 统计量 |
| `stdev` | 样本标准差（分母 n−1） | 统计量 |
| `best` | 成功运行 `objective` 的最小值 | 统计量 |
| `mean_gap` | 各行 `gap` 的平均 | 统计量 |
| `mean_evaluations` | 平均评价次数 | 诊断 |
| `mean_seconds` | 平均耗时 | 诊断 |

**三个计数与统计量必须分开看**：`successful` / `failed` 是次数，`mean` / `median` / `stdev` / `best` 只由成功行计算。

### 3.2 每个数的来源与两个边界

`summary.csv` 的每个统计量都由 `results.csv` 的原始 `objective` 列算出（第 5 节会逐组复算）。两个必须记住的边界：

1. **失败行不参与统计量，但必须留在计数里。** `objective` 为空的行不会被当成 0 分计入 `mean`，否则 0 会被当成「最好的解」。失败行只出现在 `failed` 计数与总次数里。
2. **只有一个成功运行时，`stdev` 写 0.0，含义是「算不出来」。** 一个数没有离差，这不是「结果稳定」。本批次没有这种情况（每组三个 `seed` 全部成功），但读别人产出的表时必须先看 `successful` 再相信 `stdev`。

**结论**：读一行 `summary.csv` 的顺序是「先看 `successful`/`failed`，再看 `mean`/`median`/`best`，最后看 `stdev`」，跳过第一步就会把「样本太少导致的 0」读成「算法稳定」。

### 3.3 为什么同一实例内才能比较

一行只对**同一个 `instance`** 有意义。跨实例比较原始值是错的，原因有两个：

- 不同实例的 `objective` 尺度不同：`single_12` 的 ΣT 在 250 上下，`parallel_12` 的 Cmax 在 43 上下，直接比大小等于比较两个不同的量。
- 不同实例的 `objective_name` 可以不同：本批次两个实例用 `total_tardiness`，四个用 `makespan`。

跨实例想要一个可比数，只能用 `gap = (value - reference) / max(1, |reference|)` 这类归一化量——这只是把尺度统一，仍然不能把不同目标的原始值求平均。第 6 节会看到 `quality.png` 恰好做了这种归一化聚合，所以它只能当描述。

---

## 4. 三个统计量与两种标准差

### 4.1 10 / 10 / 13

假设某个算法在三个 `seed` 上的 `objective` 是 10、10、13：

```text
mean   = (10 + 10 + 13) / 3 = 33 / 3 = 11.0
median = 排序后正中间的值 = 10.0
样本标准差 = √(((10-11)^2 + (10-11)^2 + (13-11)^2) / (3-1))
           = √((1 + 1 + 4) / 2)
           = √3 ≈ 1.7320508075688772
best   = 10.0
```

三个统计量回答三个不同的问题：

| 统计量 | 回答的问题 | 在这组数据上 |
|---|---|---|
| `best` | 最好能到多少？ | 10 |
| `mean` | 平均如何？ | 11 |
| `stdev` | 运行之间差异多大？ | √3 ≈ 1.73（占了均值的 16%） |

只报 `best=10`，那一次 13 就完全消失了，读者会以为三次都一样好；只报 `mean=11`，10/10/13 与 11/11/11 完全无法区分，而后者根本没有波动。**结论**：三个数要一起给，样本量也要一起给。

### 4.2 分母为什么是 n−1

同一个样本，两种标准差：

```text
离差        = [-1.0, -1.0, 2.0]
离差平方    = [1.0, 1.0, 4.0]
离差平方和  = 6.0
样本标准差（分母 n-1 = 2）：√(6.0 / 2) = √3 ≈ 1.7320508075688772
总体标准差（分母 n   = 3）：√(6.0 / 3) = √2 ≈ 1.4142135623730951
```

这里把三个 `seed` 看成「所有可能运行」的一个**样本**，要估计的是运行之间的波动，所以用分母 n−1 的样本标准差（无偏方差）。把它们当成总体（分母 n）会系统性低估波动，还会让「只跑一次」这种极端情况看起来有定义。

`benchmark.summarize` 调用的是 `statistics.stdev`（分母 n−1），所以 `summary.csv` 里的 `stdev` 是样本标准差。报告里写「标准差」时必须说清是哪一种，否则 1.732 与 1.414 会被当成同一个数。

### 4.3 `stdev = 0` 说明「重复运行结果相同」

确定性算法（`lpt`）的三次重复不是三个独立随机样本，它的 `stdev = 0` 只说明**结果不随 `seed` 变化**，与解的好坏无关。本批真实数据：

```text
tiny_single  lpt  mean=57       median=57     stdev=0.000 best=57
single_12    lpt  mean=719      median=719    stdev=0.000 best=719
single_12    sa   mean=261.67   median=263    stdev=5.132 best=256
```

在 `single_12` 上对比最直观：`lpt` 的 `stdev = 0.000`、均值 719，而 `sa` 的 `stdev = 5.132`、均值 261.67——波动更大的那个反而好了 2.75 倍。反过来在 `tiny_single` 上，两者的 `stdev` 都是 0（`lpt` 停在 57，`sa` 追平枚举 `optimum = 36`），同一个 `stdev` 对应完全不同的质量。**结论**：`stdev` 小是「确定」，不是「更优」；这两个性质在本批数据里甚至方向相反。

### 4.4 三种常见的过度陈述

| 说法 | 为什么不行 | 可以怎么说 |
|---|---|---|
| 「SA 的最好值是 250，所以 SA 能稳定达到 250」 | 250 是三个 `seed` 里的一次结果 | 「SA 在本批三个 `seed` 上的最好一次是 250」 |
| 「LPT 标准差为 0，最稳定，所以最好」 | 确定性与质量是两个维度 | 「LPT 结果不随 `seed` 变化；它的均值离参考最远」 |
| 「均值 44.33 比 44.67 好，所以高温更好」 | 差 0.33，只有三个 `seed`，还可能是并列 | 「高温与快冷却在本批均值并列 44.33」（见 Day 6 第 6 节） |

---

## 5. 示例：复算 `single_12` 的 SA 组均值（真实数据）

任取一个分组：`instance = single_12`、`group = main`、`algorithm = sa`。从 `results.csv` 取出三行：

| `seed` | `objective` | `status` | `evaluations` |
|---|---|---|---|
| 0 | 263.0 | `BUDGET` | 150 |
| 1 | 266.0 | `BUDGET` | 150 |
| 2 | 256.0 | `BUDGET` | 150 |

手算（用精确分数，避免二次取整）：

```text
mean   = (263.0 + 266.0 + 256.0) / 3 = 785.0 / 3 = 261.6666666666667
median = 排序后 256, 263, 266 → 中间值 263
stdev  = 离差 4/3, 13/3, -17/3
         平方和 = 16/9 + 169/9 + 289/9 = 474/9 = 158/3
         除以 (n-1)=2 → 79/3
         stdev = √(79/3) ≈ 5.131601439446...
best   = min(263, 266, 256) = 256
```

与 `summary.csv` 的记录对拍：

| 统计量 | 手算 | `summary.csv` | 一致 |
|---|---|---|---|
| `mean` | 785.0 / 3 = 261.6666666666667 | 261.6666666666667 | 是 |
| `median` | 263 | 263 | 是 |
| `stdev` | √(79/3) ≈ 5.132 | 5.132 | 是 |
| `best` | 256 | 256 | 是 |

**实验观察**：`mean` 相等是在浮点意义上成立的（脚本用 `==` 断言通过），说明 `summary.csv` 直接来自 `results.csv` 的原始值，没有先四舍五入再平均。把这一步放大到全部 54 个分组、四个统计量（共 216 次对拍）全部一致，见第 7 节。

波动有多大？`mean = 261.67`、`stdev = 5.13`，一次运行之间的差异可以到 10 个单位（256 与 266），而三个 `seed` 的均值与 `best` 相差 5.67。**结论**：只报 `best = 256` 会把「同一配置下结果从 256 到 266」这件事藏起来，而这正是随机算法的关键性质。

---

## 6. 实现：`benchmark.py` 的 `summarize` 与 `plot`

对应文件 [benchmark.py](../../projects/01_scheduling_core/scheduling_experiments/benchmark.py)。`summarize` 与 `plot` 都由 `run` 在批次结束时调用，所以统计与图永远与刚跑出来的 `rows` 同源。

### 6.1 `summarize`：分组、统计、落盘

```python
for instance, group, algorithm in sorted(
    {(row["instance"], row["group"], row["algorithm"]) for row in rows}
):
    selected = [... 同键的行 ...]
    good = [row for row in selected if row["objective"] is not None]
    scores = [row["objective"] for row in good]
    ...
    "stdev": statistics.stdev(scores) if len(scores) > 1 else 0.0,
```

三处值得记住的实现细节：

1. **分组键来自数据本身**（对 `rows` 的元组集合去重再排序），不是硬编码的实例名或算法名。新增一个算法或一个敏感性组，表里自动多几行。
2. **`good` 用 `objective is not None` 过滤**：失败行不参与 `mean` / `median` / `stdev` / `best`，但 `failed` 计数保留了它。
3. **`stdev` 的 `len(scores) > 1` 分支**：0 个或 1 个成功运行时写 `0.0`。这是「不可计算」的占位，不是测出来的波动，第 3.2 节已经强调过。

`summarize` 同时写 `report.md`：一张 9 列的 markdown 表，表头写明 `gap=(value-reference)/max(1,abs(reference))` 的约定，脚注写明「同一实例跨种子汇总；不把不同目标的原始值求平均。LPT 只评价一次，LS 可提前停机；预算是共同上限」。**这些脚注是表格的一部分**，复制表格时不能只复制中间几行。

### 6.2 `plot`：三张图各自挑了哪些数据

| 文件 | 数据（挑了哪些行） | 画法 | 标题与坐标轴 |
|---|---|---|---|
| `quality.png` | `group == "main"` 且目标非空的行，共 108 个 `gap` | 按算法分组的箱线图 | 标题 `Mixed instances: descriptive distribution (not significance)`，纵轴 `Normalized reference gap` |
| `convergence.png` | `selected_instance = main[-1]["instance"]`（本批为 `routes_12`）、`seed = main[0]["seed"]`（本批为 0） | `step(where="post")` 画 `best` 随 `evaluation` 的轨迹；单点轨迹（`lpt`）加点标记 | 标题 `routes_12, seed=0`，横轴 `Evaluations`，纵轴 `Best objective` |
| `gantt.png` | 该实例 `main` 行中 `objective` 最小的一行（本批为 `routes_12__main__first__0`） | `barh(width=end-start, left=start)`，每个作业一个颜色，y 轴为机器 | 标题是 `run_id`，横轴 `Time` |

三张图都由 matplotlib（`Agg` 后端，`dpi=140`）生成，是独立文件，可以单独导出与分享；`report.md` 的结尾列出了这三个文件名，方便按图索骥。但**定量证据始终是原始 CSV**，图只用来帮助理解。

三条必须自己看出来的口径：

- `quality.png` 把**六个实例、两种 `objective`** 的归一化 `gap` 混在六只箱子里，每只箱子 18 个点。标题里的 `Mixed instances` 与 `not significance` 就是这个意思：它是描述，不是检验。它**没有**做任何显著性判断，箱子的高低差不构成「显著胜过」。
- `convergence.png` 只画**一个实例、一个 `seed`**的一条轨迹，不是三 `seed` 平均，也不是全批平均。`lpt` 只评价一次，因此在图上只是一个点。
- `gantt.png` 画的是**该实例主实验里最好的一次运行**，不是全批最好。本批 `routes_12` 上敏感性组出现过 40，而这张图画的是 41，所以不能拿这张图说「本批最优排程长这样」。

**结论**：图的标题就是它的适用范围。读图先读标题，再决定能说什么。

---

## 7. 实验：`m1w4d5_stats`

对应脚本 [m1w4d5_stats.py](../../projects/01_scheduling_core/examples/m1w4d5_stats.py)。脚本**只读** `artifacts/month1_refactored/`，不写文件、不重新出图、不重跑基准。在项目目录 `projects/01_scheduling_core` 下运行：

```bash
python examples/m1w4d5_stats.py
```

脚本做七件事：说明统计单位、复算一个分组的均值、演示 10/10/13、区分两种标准差、审计甘特数据的宽度与空闲、说明三张图的边界、审计收敛曲线的单调性。实际输出：

```text
== 1. 统计单位：summary.csv 的一行是什么 ==
  分组键 = (instance, group, algorithm)，一行汇总同一组内的三个 seed。
  字段：instance, group, algorithm, successful, failed, mean, median, stdev, best, mean_gap, mean_evaluations, mean_seconds
  results.csv 行数 = 162（逐次运行）；summary.csv 行数 = 54（逐组汇总）。
  successful/failed 分开计数，失败不会被当成 0 分写进均值。

== 2. 从 results.csv 手算均值，与 summary.csv 对拍 ==
  single_12 / main / sa 的三行 objective（seed 0,1,2）：
    seed=0  objective=263.0  status=BUDGET  evaluations=150
    seed=1  objective=266.0  status=BUDGET  evaluations=150
    seed=2  objective=256.0  status=BUDGET  evaluations=150
  手算：( 263.0 + 266.0 + 256.0 ) / 3 = 785.0 / 3 = 261.6666666666667
  summary.csv 的 mean = 261.6666666666667
  两者相等：summary.csv 的均值确实来自 results.csv 的原始 objective，没有二次取整。

  逐组复算：54 组的 mean / median / stdev / best 全部与 results.csv 一致。
  其中 stdev 由 statistics.stdev 计算，分母是 n-1（样本标准差），见第 4 节。

== 3. 10 / 10 / 13：只报一个数字会丢掉什么 ==
  示意样本（三个 seed 的 objective）：10, 10, 13
  均值   mean   = (10 + 10 + 13) / 3 = 33 / 3 = 11.0
  中位数 median = 排序后正中间的值 = 10.0
  样本标准差 = √(((10-11)^2 + (10-11)^2 + (13-11)^2) / (3-1)) = √(6/2) = √3 ≈ 1.7320508075688772
  最好值 best   = 10.0

  只报 best=10：这一次 13 完全消失，读者会以为三次都一样好。
  只报 mean=11：看不出 10/10/13 与 11/11/11 的区别，而后者根本没有波动。
  三个统计量回答三个不同问题：best 说「最好能到多少」，mean 说「平均如何」，
  stdev 说「不同 seed 之间差异多大」。少任何一个都会得出过强的结论。

  stdev = 0 的含义是「重复运行结果相同」，不是「解更好」。本批真实数据：
    tiny_single  lpt  mean=57       median=57     stdev=0.000 best=57
    single_12    lpt  mean=719      median=719    stdev=0.000 best=719
    single_12    sa   mean=261.67   median=263    stdev=5.132 best=256
  tiny_single 的枚举 optimum=36：lpt 的 stdev 是 0，但它离 optimum 比 SA 远得多。
  确定性与随机性在这里正好相反：stdev 小只说明算法更确定，不说明算法更优。

== 4. 分母为什么是 n-1：样本标准差不是总体标准差 ==
  离差 = [-1.0, -1.0, 2.0]，离差平方 = [1.0, 1.0, 4.0]，离差平方和 = 6.0
  样本标准差（分母 n-1 = 2）：√(6.0/2) = √3 ≈ 1.7320508075688772
  总体标准差（分母 n   = 3）：√(6.0/3) = √2 ≈ 1.4142135623730951
  这里把三个 seed 看作「可能运行集合」的一个样本，要估计的是运行之间的波动，
  所以用 n-1 的样本标准差（无偏方差），而不是把这三个数次运行当成总体。
  注意边界：确定性算法的三次重复不算三个独立随机样本，它的 stdev=0 只是「结果不变」。

== 5. 甘特数据审计：宽度必须等于加工时间 ==
  run_id = routes_12__main__first__0
  config = {'algorithm': 'first', 'objective': 'makespan', 'budget': 150, 'seed': 0, 'temperature': 10.0, 'cooling': 0.98, 'restart_interval': 40}
  独立验证器 validate_schedule 通过（不调用 decoder）；makespan = 41

  机器 M0（3 条）：
    工序       开始  结束  宽度(=结束-开始)  p   宽度==p
    J005_O0       0    16       16         16       是
    J000_O0      16    26       10         10       是
    J001_O1      26    40       14         14       是
  机器 M1（3 条）：
    工序       开始  结束  宽度(=结束-开始)  p   宽度==p
    J002_O0       3    15       12         12       是
    J001_O0      15    25       10         10       是
    J003_O0      25    40       15         15       是
  机器 M2（6 条）：
    工序       开始  结束  宽度(=结束-开始)  p   宽度==p
    J004_O0       1    16       15         15       是
    J004_O1      16    17        1          1       是
    J005_O1      17    31       14         14       是
    J002_O1      31    36        5          5       是
    J000_O1      36    39        3          3       是
    J003_O1      40    41        1          1       是

  M1 的空闲 [0,3)：J002 的 release_time=3 强制等待
  M2 的空闲 [0,1)：J004 的 release_time=1 强制等待
  M2 的空闲 [39,40)：job 内 precedence 强制等待（前驱工序刚结束）
  decoder 不会向已有空隙插入工序，所以图上的空闲都是被约束逼出来的，不是算法主动空等。
  图上每根条的绘制宽度就是 end-start（benchmark.plot 用 barh(width=end-start, left=start)），
  所以「宽度 == p」既是数据自检，也是「图与数据一致」的自检。
  但图本身不证明可行：可行性由独立验证器先判，图只帮助理解。

== 6. 三张图各自回答什么 ==
  quality.png       回答：本批次参考 gap 的分布怎样？
                    不能断言：显著胜过所有方法
                    文件 存在（36333 字节）
  convergence.png   回答：一个实例一个 seed 的最好值何时改善？
                    不能断言：平均收敛速度普遍最快
                    文件 存在（33588 字节）
  gantt.png         回答：一个最好排程的机器占用与空闲如何？
                    不能断言：图看起来紧凑就一定可行
                    文件 存在（30431 字节）

  读图前必须先读标题：quality.png 的标题写明 Mixed instances 且带 not significance；
  它把六个实例、两个不同 objective 的归一化 gap 混在一张箱线图上，只能当描述。
  不同 objective 的原始值（ΣT 与 Cmax）永远不合并求平均，详细比较回到每实例统计表。
  convergence.png 画的是 routes_12、seed=0（实例取自 rows 顺序的最后一行 main 记录，
  seed 取自第一行），是一条轨迹，不是三 seed 平均；lpt 只有一个初始点。
  gantt.png 的 run_id 是 routes_12__main__first__0（objective=41），
  而敏感性批次在同一实例上出现过 40 —— 这张图不代表全批最优。

== 7. 收敛曲线审计：best 必须单调不增 ==
  routes_12__main__sa__0 的轨迹：150 个评价点
  best 序列：首个 54.0 → 末个 42.0；上升次数 = 0
  current 序列：上升次数 = 6（SA 接受坏解时 current 会变差）
  best 单调不增是定义决定的：所谓最好，就是到此为止见过的最小值。
  若图上出现上升，先检查画的是不是 current —— current 允许上升，best 不允许。
  本轨迹最大一次 current 上升幅度 = 16.0

== 8. 结论 ==
  表格的数字必须能回到 results.csv 复算，图表只是描述性辅助。
  报告结论要同时给 best / mean / stdev，并说明样本量与失败计数。
  全部断言通过。
```

**实验观察**：

1. 第 2 段的手算与 `summary.csv` 在浮点意义上相等，第 2 段末尾的循环又对**全部 54 个分组**复算了 `mean` / `median` / `stdev` / `best`（共 216 次对拍）全部一致。**结论**：`summary.csv` 是 `results.csv` 的确定性函数，没有任何人工调整的空间。
2. 第 5 段的排程**重新过了一遍独立验证器** `validate_schedule`（不调用 decoder），`makespan = 41`；三台机器共 12 条工序的「宽度 == p」全部通过。**实验观察**：机器负载分别是 M0 = 40、M1 = 37、M2 = 39，而 `makespan = 41 = max(end_time)`，两者不等——空闲是 `release_time` 与 precedence 逼出来的，不是算法主动空等。
3. 第 5 段的三个空闲都给出了**具体原因**：两个来自作业释放时间（J002 的 `release_time=3`、J004 的 `release_time=1`），一个来自作业内先后顺序（M2 的 [39,40) 在等前驱工序结束）。**结论**：只要 decoder 是「追加到机器末尾」的，图上的每一段空闲都应该能这样归因；归因不了才需要怀疑 decoder 或数据。
4. 第 6 段把三张图的「回答什么」与「不能断言什么」并排打印，还打印了文件是否存在的自检。**实验观察**：`gantt.png` 画的那次运行 `objective = 41`，而敏感性组在同一实例上出现过 40，所以这张图**不是**本批最优排程。
5. 第 7 段验证了 `best` 的单调性：150 个评价点里 `best` 上升 0 次、`current` 上升 6 次（SA 接受坏解），最大一次上升幅度 16.0。**结论**：`convergence.png` 画的是 `best`，所以它必须单调不增；看到上升曲线就要先怀疑画的是 `current`。

---

## 8. 今日练习

1. **练习 1（手算对拍）**：不查第 5 节，从 `results.csv` 取 `routes_12` / `main` / `sa` 的三个 `objective`，手算 `mean` / `median` / `best`，再与 `summary.csv` 对照。
2. **练习 2（标准差约定）**：用上面三个数分别算样本标准差与总体标准差，说明报告里应该报哪一个、为什么。
3. **练习 3（甘特审计）**：换一条运行（例如 `routes_12__main__sa__0`），从 `runs/<run_id>.json` 重建排程，逐条核对宽度并给每段空闲标出原因。
4. **练习 4（图的边界）**：为三张图各写一句「可以怎么说」与「不可以怎么说」，要求每句话都带实例、`objective`、`seed` 或 `budget` 之一。
5. **练习 5（失败的读法）**：假设某组 `successful=2, failed=1`，说明为什么 `stdev` 的定义域只有两个点，以及这时报告里必须额外写出什么。

---

## 9. 验收清单

- [ ] 能说出 `summary.csv` 的十二个字段与分组键，并解释为什么分组键来自数据而不是硬编码。
- [ ] 能用三个 `seed` 的原始值手算 `mean` / `median` / `stdev` / `best`，并说明 `stdev` 的分母是 n−1。
- [ ] 能用 10 / 10 / 13 说明只报 `best` 与只报 `mean` 各自会掩盖什么。
- [ ] 能解释确定性算法 `stdev = 0` 的含义与它不代表的含义，并举出本批的一个反例。
- [ ] 能说出 `quality.png` / `convergence.png` / `gantt.png` 各自挑了哪些行、各自不能断言什么。
- [ ] 能从 `runs/<run_id>.json` 重建排程，核对「宽度 == 加工时间」，并给每段空闲标出 `release_time` 或 precedence 的原因。
- [ ] 能解释 `convergence.png` 的 `best` 为什么单调不增，以及画错成 `current` 会出现什么。
- [ ] 能说明为什么跨实例、跨 `objective` 的原始值不能求平均，只能比归一化的 `gap`；并会检查表格与图的三个细节（不用失败空值冒充零、坐标轴有名称、标题写明实例或汇总范围）。
- [ ] `python examples/m1w4d5_stats.py` 运行无断言失败，且不写入 `artifacts/` 任何文件。
- [ ] `python -m pytest -q` 全部通过（本日不新增测试，仍为 127 条）。

---

## 10. 自测题

不看上文回答：

- Q1：`summary.csv` 的分组键是什么？本批次共多少行？
- Q2：十二个字段里哪两个是计数、哪两个只作诊断、哪些是统计量？
- Q3：三个 `seed` 的目标值是 10、10、13，`mean` / `median` / 样本 `stdev` 各是多少？
- Q4：样本标准差与总体标准差的分母各是什么？报告里应该用哪一个？
- Q5：`stdev` 写 0.0 有哪两种完全不同的原因？
- Q6：为什么失败行不能计入 `mean`，也不能从总次数里删掉？
- Q7：`quality.png` 的数据是哪些行？标题里的 `not significance` 在提醒什么？
- Q8：`convergence.png` 画的是哪个实例、哪个 `seed`、哪条序列？
- Q9：`gantt.png` 画的是哪次运行？为什么它不能代表本批最优排程？
- Q10：`best` 序列为什么必须单调不增？出现上升应该先检查什么？

### 参考答案

- A1：`(instance, group, algorithm)`；本批次 `summary.csv` 共 54 行（主实验 36 行 + 敏感性 18 行）。
- A2：计数是 `successful` 与 `failed`；诊断是 `mean_evaluations` 与 `mean_seconds`；统计量是 `mean` / `median` / `stdev` / `best` / `mean_gap`。
- A3：`mean = 11.0`、`median = 10.0`、样本 `stdev = √3 ≈ 1.7320508075688772`（总体标准差则是 `√2`）。
- A4：样本标准差分母是 n−1，总体标准差分母是 n；这里把若干 `seed` 看成可能运行集合的一个样本，所以报 n−1 的样本标准差。
- A5：一是「只有一个成功运行」时的不可计算占位（`benchmark.summarize` 的 `len(scores) > 1` 分支）；二是确定性算法重复运行结果确实相同。
- A6：`objective` 是最小化的量，把失败填成 0 会让它变成「最好解」，污染 `mean` / `best` / `reference`；删掉失败行则会让失败的算法看起来从不失败。
- A7：`group == "main"` 且目标非空的全部行（本批 108 个 `gap`），按算法分箱；`not significance` 提醒它只是描述性分布，图上没有任何显著性检验。
- A8：实例 `routes_12`、`seed=0`，画的是各算法 `best` 随 `evaluation` 的阶梯轨迹（`lpt` 只有一个点）。
- A9：画的是 `routes_12__main__first__0`（`objective = 41`）；它是该实例主实验里最好的一次，而敏感性组在同一实例上出现过 40。
- A10：`best` 的定义就是「到此为止见过的最小值」，所以只可能下降或持平；出现上升先检查画的是不是允许上升的 `current`。

---

## 11. 今日一句话总结

> **统计量是压缩，图是描述：`mean` / `median` / `stdev` / `best` 必须一起给并带上样本量与失败计数，图的标题就是它能说的范围。**
