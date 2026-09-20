# Month 3 报告：Industrial FJSP Solver

## 1. 研究范围

本月从「经典调度问题」走进「真实车间」：先补上 Flow Shop 与 JSP 的基线（Johnson、NEH、优先级派工、析取图与关键路径），再进入 FJSP 的定义特征——**工时不只依赖工序，还依赖选哪台机器**（`p_ij`）——最后逐条加上工业约束：sequence-dependent 换型、机器日历、计划维护、资质、次生资源（工人）、WIP 锁定、紧急订单。

全部求解只依赖 **OR-Tools 9.15**。与 M2 最大的差别是：**M3 不打算复用 M1/M2 的问题定义。** M1 的 `Operation.processing_time` 是单个整数，语义是「在所有合格机器上耗时相同」；FJSP 的定义特征恰恰是 ``p_ij``。这不是加个可选字段能兼容的——目标函数、解码器、独立验证器、CP-SAT 模型全都要按「工时依赖机器」重写。改 M1 会同时破坏 M1/M2 已封存批次的 `source_sha256`，所以 M3 自带更丰富的领域核心，复用的是**纪律**而不是代码：统一结果接口、半开区间语义、独立验证器、参考值分档。

验证包含 **181 项测试**、一次 38 次运行的正式批次（零失败）、三周各自的独立实验驱动，以及 4 个小实例上与**独立穷举**的对拍。每个返回的排程都过 11 项独立检查。

## 2. 模型

### 2.1 Flow Shop 与 JSP（Week 1）

Johnson 规则（两机器最优）与 NEH（多机器构造式启发式）；优先级派工按 SPT/EDD 等规则逐槽位选工序。JSP 用 CP-SAT：每道工序一个区间变量，作业内 precedence，机器上一串 `AddNoOverlap`。析取图给出关键路径与关键块，是瓶颈分析的依据。

### 2.2 FJSP（Week 2）

机器选择 + 排序的联合决策。三种指派启发式（`random` / `shortest` / `loadbalance`）先定机器，再由解码器在固定指派上做活动调度；CP-SAT 则把指派与排序放进同一个模型。**`oracle.py` 对极小实例穷举全部「机器指派 × 机器上顺序」**，是与被测求解器无关的参考值来源——这是本月唯一不依赖求解器自证的证据。

### 2.3 工业约束（Week 3–4）

| 约束 | 建模要点 |
|---|---|
| sequence-dependent setup | 换型时间依赖**前一工序的族**，不是常数 |
| 机器日历 | 可用窗口集合；`windows == ()` 表示**不受限**，不是「永远不可用」 |
| 计划维护 | 机器上的禁排区间 |
| 资质 | 「哪台机器能做哪个族」的白名单，与「工时表」是两回事 |
| 次生资源 | 工人能力 + 容量，采用**强制占用**语义：给了工人则每道工序必须占一名 |
| WIP 锁定 | 工序被钉死在指定机器（可选钉死开始时刻） |

## 3. 实现与算法

```text
03_industrial_fjsp/
├── fjsp_core/         领域模型 / 输入校验 / 11 项独立验证器 / 目标 / 统一结果
├── fjsp_shop/         Flow Shop、JSP、析取图、FJSP、CP-SAT、oracle、工业约束
├── fjsp_io/           生成器 / JSON / 标准格式解析 / KPI
└── fjsp_experiments/  跨方法批次与各周驱动
```

依赖方向单向：`fjsp_shop → fjsp_core / fjsp_io`，`fjsp_core` 不依赖任何上层。**周模块之间尽量不互相导入**——四周共享的是注册表、领域模型与结果接口。

**统一结果接口**（`fjsp_core/result.py`）沿用 M2 的三条纪律，并新增一条：

1. **没有 bound 就写 `None`**，绝不填 0 或目标值。启发式的 `best_bound` / `gap` 落表为**空**。
2. **`build_time` 与 `solve_time` 分开记。**
3. **求解器说 `OPTIMAL` 不等于解可行。** 每个返回排程都过 11 项独立检查，诊断落在 `validation` 列。
4. **每次求解都要填 `breakdown`**（`cmax` / `total_tardiness` / `setup`）。目标可能是加权和，只报一个数会让分量取舍不可见。

本批共注册 13 个方法，13 个全部进入配置。

## 4. 正确性证据

| 检查 | 已执行内容 |
|---|---|
| 单元与回归测试 | 181 项：foundation 40、Week 1 51、Week 2 33、Week 3 23、Week 4 34 |
| 独立穷举对拍 | 4 个小实例（2–4 道工序）上 `fjsp_cpsat` 的最优值与 oracle **全部相等**（2 / 10 / 10 / 7） |
| 独立验证器 | 正式批次 38 次运行，**0 次**被拒绝（`validation` 全空） |
| 验证器有效性 | 对 `ind_qualified` 的实解**注入**八类违反（重叠、提前开工、缺工序、未知机器、改坏时长、日历、维护、锁定）——**八次全部被捕获**，另带出 release / precedence / worker 三类派生诊断（见 §4.1） |
| 约束消融单调性 | 两条消融链**六段全部单调不减**；违反单调性的行一定是建模方向写错 |
| 两种编码交叉验证 | 保守编码的目标值在**每一段都不低于**精确编码——正是「可行域子集」所要求的序关系（见 §6.3） |
| 边界纪律 | 批次 0 次 `best_bound > objective`；启发式的 bound / gap 落表为**空**而非 0 |

### 4.1 验证器不是「跑过就算」

「38 次运行零诊断」只有在验证器**确实会报错**时才有意义。所以本节做了一个正向对照：取最难的 `ind_qualified`（setups 6、日历 1、维护 2、资质 15、工人 3、锁定 1）的实解，逐类注入违反，确认每一类都被点名——

```text
CLEAN             = []
注入重叠          = ['duration: J001_O0', 'release: J001_O0', 'overlap: M4/J001_O0',
                     'overlap: M4/J005_O1', 'worker: W1 double-booked']
注入提前开工      = ['duration: J007_O2', 'release: J007_O2',
                     'precedence: J007_O1 -> J007_O2', 'overlap: M4/J007_O2', ...]
删掉一道工序      = ['missing: J001_O0']
换成不存在的机器  = ['illegal assignment: J000_O0 -> M99']
改坏时长          = ['duration: J000_O0']
推入日历窗口间隙  = ['calendar: J003_O2 on M0', ...]
推入维护区间      = ['maintenance: J003_O2 on M0', ...]
换掉锁定机器      = ['duration: J004_O2', 'locked: J004_O2 machine M1 != M2']
```

八次注入覆盖了「排程本身是否合法」的全部维度。**没有这一节，「零诊断」只证明脚本没崩。**

## 5. 实验设置与原始记录

配置见 [configs/month3.json](../projects/03_industrial_fjsp/configs/month3.json)：10 个实例、13 个方法，**主实验 26 次 + 时间预算敏感性 12 次 = 38 次运行**，零失败。方法表按实例裁剪——基础模型 `fjsp_cpsat` 只建模机器选择 + precedence，遇到换型/日历/维护/资质/次生资源会在求解前**主动拒绝**，所以 `ind_*` 四个实例只列真正能处理对应约束的模型；拒绝行为本身由 Week 3/4 的消融驱动演示，不放进正式批次，免得多出无信息量的 `FAILED` 行。原始记录在 [artifacts/month3](../projects/03_industrial_fjsp/artifacts/month3)。

版本状态（这次是可信的）：

```text
git_commit          = 1380ba0dc52b      （真实提交，非「未提交工作区」）
working_tree_dirty  = False             （运行前工作区干净）
source_sha256       = 8c752073b1a47c8ec965ed69e0e9c64bc532e733e31780b8607e7272273338fb
                     └─ 与当前源码重算的 source_hash() 一致（已复核）
config_sha256       = 2db6ae393bfdbd1f764acbc7322c3cff3e6e7238d284da2c80cff2dbc610e34d
```

**整批确定性的实测结果（两次独立运行）**：

```text
38 个 run_id 在 (status, objective, best_bound, gap, validation) 上：
  36 个逐字节一致
   2 个不同 —— 且两个都是跑满墙钟的 FEASIBLE 行
     ind_setup__main__fjsp_cpsat_setup     61 -> 62
     ind_worker__main__fjsp_cpsat_full     97 -> 101
```

这与 M2 的结论一致但更精确：**固定种子 + 单线程让搜索「路径」确定，但「走多远」由墙钟决定。** 13 个 `OPTIMAL` 行与全部启发式行逐位复现；5 个限时行中 3 个复现、2 个不同。所以——

> **限时行的目标值是一次观测，不是常量。** 本批把 `best-known` 记在两次观测中**更好**的那次（61、97）。引用这两个数时必须带上这句话。

实例参考值分三档（见 [report.md](../projects/03_industrial_fjsp/artifacts/month3/report.md)）：

| 实例 | 参考类型 | 参考值 |
|---|---|---:|
| `flow_5x3` | `proven_by_solver` | 69 |
| `flow_8x4` | `proven_by_solver` | 126 |
| `jsp_6x4` | `proven_by_solver` | 67 |
| `jsp_8x5` | `proven_by_solver` | 84 |
| `fjsp_6x4_f2` | `proven_by_solver` | 42 |
| `fjsp_10x5_f3` | `proven_by_solver` | 56 |
| `ind_calendar` | `proven_by_solver` | 79 |
| `ind_setup` | `best-known` | 61 |
| `ind_worker` | `best-known` | 97 |
| `ind_qualified` | `best-known` | 75 |

**正式批次里没有一个 `optimum`。** 7 个由求解器在预算内自证，3 个只是「本批见过的最好可行解」。独立穷举只在 Week 2 的 4 个小实例上存在，且**没有进入正式批次**。这个分档本身就是结论的一部分：**在工业约束实例上，本月拿不出任何独立的最优性证书。**

## 6. 主实验结果

| 实例 | 最好启发式 | CP-SAT | 差距 |
|---|---|---|---|
| `flow_5x3` / Cmax | 70（`flow_neh`） | OPTIMAL **69** (0.02s) | 1.4% |
| `flow_8x4` / Cmax | 127（`flow_neh`） | OPTIMAL **126** (0.04s) | 0.8% |
| `jsp_6x4` / Cmax | 71（`jsp_priority`） | OPTIMAL **67** (0.01s) | 6.0% |
| `jsp_8x5` / Cmax | 86（`jsp_priority`） | OPTIMAL **84** (0.02s) | 2.4% |
| `fjsp_6x4_f2` / Cmax | 61（`fjsp_loadbalance`） | OPTIMAL **42** (0.04s) | **45%** |
| `fjsp_10x5_f3` / Cmax | 90（`fjsp_loadbalance`） | OPTIMAL **56** (4.13s) | **61%** |
| `ind_calendar` / Cmax | — | OPTIMAL **79** (0.14s) | — |
| `ind_setup` / 加权和 | — | FEASIBLE 61（无界） | — |
| `ind_worker` / Cmax | — | FEASIBLE 97，界 41，gap 0.577 | — |
| `ind_qualified` / 加权和 | — | FEASIBLE 75，界 36，gap 0.520 | — |

### 6.1 结论一：FJSP 的难点在「选机器」，不在「排顺序」

同一批实例上，启发式与精确解的差距从 JSP 的 2–6% 跳到 FJSP 的 **45–61%**。原因是启发式只做了一件事——**先按局部规则把机器定死，再排顺序**，而 FJSP 的收益恰恰来自「为一道工序选一台稍微慢一点、但不那么拥挤的机器」。局部贪心看不见这层权衡。

`fjsp_10x5_f3` 尤其能说明问题：CP-SAT 证最优花了 **4.13 秒、21259 个分支**，而最好的启发式还差 **61%**。**「精确方法慢」和「启发式够用」这两个直觉在这里都不成立**——精确方法慢，但它一次性把 61% 拿回来了。

### 6.2 结论二：Johnson 只对两机器最优，NEH 在多机器上稳赢

```text
flow_5x3   johnson 78  ->  neh 70   （-10.3%）
flow_8x4   johnson 151 ->  neh 127  （-15.9%）
```

Johnson 规则的最优性证明只覆盖 **2 台机器**。一旦机器数变成 3、4，它退化成普通启发式，而按「总加工时间降序」构造的 NEH 稳定更好。两者都输给 CP-SAT——**这是「教科书最优」必须带上适用条件的标准案例。**

### 6.3 结论三：两种换型编码互相验证，且保守编码在限时下反而赢

sequence-dependent setup 有两套编码，都用同一个实例族消融：

```text
fjsp_cpsat_full（精确：槽位链 + AddAllowedAssignments）
  base 9 -> +setup 9 -> +calendar 9 -> +qualification 27 -> +worker 27 -> +locked 31
fjsp_cpsat_qualified（保守：区间膨胀 + AddNoOverlap）
  base 9 -> +setup 13 -> +calendar 28 -> +qualification 29 -> +worker 29 -> +locked 35
```

两条链各自**单调不减**（每加一条约束可行域只会变小）。更有信息量的是**跨链比较**：保守编码把机器占用区间膨胀成 `[start, end + max_outgoing_setup)`，它禁止的排程严格多于精确编码，所以它的可行域是**子集**，目标值必须**逐段不低于**——实测 `13≥9, 28≥9, 29≥27, 29≥27, 35≥31`，**六段全部成立**。这是对一个数学论断的实测验证，而不是「跑通了」。

但到了限时的正式批次上，序关系**不再保证**：

```text
ind_qualified，15 秒
  fjsp_cpsat_qualified（保守，可行域更小）  FEASIBLE 75，界 36，gap 0.520
  fjsp_cpsat_full    （精确，可行域更大）  FEASIBLE 78，界 34，gap 0.564
```

保守编码返回的 75 是**精确模型的可行解**（独立验证器确认它满足真实换型间隔），精确模型只是**在 15 秒内没找到它**。可证明的序关系在预算充足时成立（消融链全部 `OPTIMAL`），在预算不足时会被搜索能力盖过。**这是 M2「换 formulation 比调 Big-M 重要」那节课在编码正确性维度上的重演：更忠实的编码不等于更好的结果。**

### 6.4 结论四：没有任何一个启发式规则在所有实例上更好

`fjsp_loadbalance` 在正式批次里全面赢过 `fjsp_shortest`（61 vs 67、90 vs 111），但在 Week 2 的小实例 `assign_2x3` 上**反过来输**：

```text
assign_2x3（2 作业 3 机器，最优 10）
  fjsp_shortest     11
  fjsp_loadbalance  13
  fjsp_random       14
```

差距不大，但方向明确。**「负载均衡」这条直觉在均衡本身就是瓶颈时会失效**——把工序摊到多台机器上会增加搬运与换型，而实例太小、机器太少时这笔账划不来。只报正式批次会得出「loadbalance 总是更好」这一错误信条。

## 7. 敏感性与边界

### 7.1 时间预算

`jsp_cpsat` / `fjsp_cpsat` 各扫 5 / 15 / 30 秒，**12 行全部无变化**（目标值与界逐位相同），因为它们在 5 秒内就已证最优。真正吃满预算的是工业约束实例：`ind_worker` 与 `ind_qualified` 的 `solve_time` 都是 15.00x 秒，界停在 41 / 36，gap 0.577 / 0.520——**约束一加，可证空间就掉下来了。**

### 7.2 目标归一化：`ind_setup` 为什么没有 bound

`ind_setup` 的两行 `best_bound` 都是**空**，看起来像漏填。实际是刻意的：该实例的目标是加权和，而**求解器优化的是归一化后的加权和，报告的 `objective` 是原始单位的加权和**。两者不同量纲，归一化尺度上的界**不能**当作报告目标的界——填进去就是伪证书。`runs/*.json` 的 `detail` 里写明了这一点：

```text
optimality_scope = "normalized weighted sum (not the reported objective)"
normalization_note = "求解器优化的是归一化后的加权和；报告的 objective 是原始单位的加权和"
```

**「没有可比的界」和「忘了取界」在表格上长得一模一样，区别只在有没有写清原因。** 这正是 M2 那条「没有 bound 就写 None」纪律的延伸：`None` 是诚实的，但要配上解释才算完整。

### 7.3 归一化口径会改变最优解的选择

归一化不是排版问题。同一个实例、同一组权重，换口径就换解（`tiny_tradeoff`，均 `OPTIMAL`）：

| 口径 | `tardiness_light`（α=1, β=0.25）选出的排程 | Cmax | ΣT |
|---|---|---:|---:|
| `none` / `trivial` | `M0:A@0-6,B@7-9;M1:C@0-5,D@6-8` | 9 | 9 |
| `ideal` | `M0:A@10-16,B@0-2;M1:C@0-5,D@6-8` | 16 | 2 |

`trivial`/`none` 口径下选短工期解，`ideal` 口径下选了**完全相反**的排程。原因是 `ideal` 的分母是三个分量各自的最优值，它内建了「一个单位的 ΣT 值多少钱」的定价——**这个定价不是业务给的，是实例给的。** 换一批实例，同一个 β 的含义就变了。

另有一处方法边界：`plant_batch` 上 setup 的单目标最优值为 **0**，`ideal` 口径的分母为 0，该分量**在该实例上无法定价**。两类「不可用」必须分开：**分成 0** 是理想点归一化的固有边界（换预算修不好），**没证明最优**只是预算不够（加时间就能修）。

## 8. 图与案例

**本月没有生成任何图。** 全部证据以表格与 CSV 呈现；Week 1 的甘特图数据落在 `artifacts/month3_w1/gantt_*.csv`（机器 × 时间的占用明细），瓶颈分析由 `machine_loads` 的利用率数字表达。

这与 M2 是**同一个缺口**，且值得指出：M1 批次有三张 PNG，M2/M3 都没有对应的绘图脚本。补一个只读 `artifacts/month3/` 的绘图脚本不会改变本批次的源码指纹（绘图代码不在被 hash 的包内），列为后续工作。

## 9. 修复与局限

本轮自查发现并修复的**三个真实缺陷**：

1. **`oracle.py` 的拒绝信息里有一条错误的数学论断。** 它声称活动调度族对「非正规目标」不一定包含最优解，但 ΣTj 恰恰**是**正规目标。已改为如实陈述「本模块只为 makespan 构建并检查证书」这一保守边界——**拒绝的理由必须是真理由**，否则读者会据此得出错误的一般结论。
2. **示例脚本与笔记里三处打印输出的前瞻引用**（含 Week 1 Day 7 脚本会打印其它周的方法名）。已在源头修正并重新粘贴 stdout。这类错误只靠肉眼读笔记发现不了，因此另写了 [tools/check_chronology.py](../tools/check_chronology.py) 常驻检查（详见 §10）。
3. **换型验证条件过严**：原实现只要实例里有工序族就强制要求换型矩阵，但「给族」也可能是为了资质或批处理分组。已改为只在 `instance.setups` 非空时检查。

当前限制：

```text
规模：        10 个合成实例，作业数 5–10、机器数 3–5，单 seed
参考值：      正式批次没有一个独立最优值，7 个靠求解器自证，3 个连自证都没有
独立枚举：    只在 4 个 2–4 工序的小实例上做过，未进入正式批次
调参：        未在独立留出集上验证任何权重/归一化结论
绘图：        无图（见第 8 节）
前端：        没有 lint / formatter / 类型检查——验证环境里没有 ruff / black / mypy
求解器：      只有 OR-Tools 一个后端，未与商业求解器交叉验证
确定性：      限时行的目标值是单次观测（实测 38 行中 2 行会变）
换型语义：    保守编码会切掉合法解，只在消融链上被证明「不改变最优值」，
              未在任何一批实例上量化它损失了多少
```

## 10. 复现与下一步

仓库根目录：

```powershell
python projects/03_industrial_fjsp/examples/m3_month3_benchmark.py --output projects/03_industrial_fjsp/artifacts/my_run
python -m pytest projects/03_industrial_fjsp -q
```

项目目录等价命令与各周驱动见 [PROJECT_GUIDE.md](../projects/03_industrial_fjsp/PROJECT_GUIDE.md)。输出目录必须为空或不存在；每次重跑换新目录名。

验证本批次是否可信，三步：

```text
1. metadata.json 的 source_sha256 是否等于当前源码重算的 source_hash()
2. working_tree_dirty 是否为 False，git_commit 是否指向一个真实提交
3. 重跑一次，比较 (status, objective, best_bound, gap, validation) 是否逐行一致
```

前两项本批次通过。**第 3 项要按 §5 的口径读**：36/38 逐行一致，2 个限时行不同——不同不等于批次有问题，但也不能声称「完全可复现」。

### 10.1 关于笔记的时间顺序

本月全部的日笔记遵守一条规则：**每天的内容不引用后续内容。** 允许向后引用（「上周的开放问题已由本周解决」），不允许向前引用（「这会在下周讲」）。这条规则的动机是读者的实际体验：提前出现的方法名会逼着人跳着读。

规则用 [tools/check_chronology.py](../tools/check_chronology.py) 常驻检查，覆盖三个月全部笔记：

```powershell
python tools/check_chronology.py            # 三个月，跳过代码块
python tools/check_chronology.py --fences   # 连代码块内一起查
```

两处易误伤的地方已在工具里显式处理：机器编号 `M1`/`M2`/`M3`（Flow Shop 举例）**不是**月份引用，必须带中文语境词才算；`Week 1 Day 4 第 5 节` 这类带周前缀的**向后**引用合法，只有裸 `Day 4` 在前一周里才算违规。最终三个月在两种模式下均为 **0 命中**。

### 10.2 下一步

进入 M4 后可以直接复用的：统一结果接口（含 `breakdown`）、半开区间语义、11 项独立验证器、「正向对照证明验证器会报错」的做法、单调性消融法、参考值分档。**要新补的是规模**——本月最大的实例只有 10 个作业，而限时行已经在 15 秒上给出 0.52 的 gap。「精确方法能处理多大」这个问题本月完全没有触及，M4 若走向分解或元启发式，第一件事应该是把实例规模推到本月的 10 倍以上，看看哪条结论先失效。
