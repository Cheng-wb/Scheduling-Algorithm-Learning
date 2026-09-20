# Day 5：多目标 KPI 与完整 JSON 输入输出

> 当日主题：把一条排程翻译成一页业务方能读的 KPI，并让「实例 + 结果 + KPI」能完整地存下来、读回来
> 当日产出：**`fjsp_io/kpi.py` 的 KPI 报表 + `fjsp_io/json_bundle.py` 的往返契约 + 七个数的手工核对 + 可运行脚本 `m3w4d5_kpi_bundle.py`**
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 说出 KPI 报表里每个字段的定义，并说明它是从**排程**算出来的还是从**实例**算出来的。
2. 手算 `Cmax`、`total_tardiness`、`max_lateness`、`mean_flow_time`、`setup_share` 五个数。
3. 说清 `utilization` 的分子与分母各是什么，并解释为什么它**不是**「各资源利用率的平均值」。
4. 区分 `load` 与 `span`，并说出一个 `load < span` 的具体含义。
5. 说清 `normalize` 的零分母约定（返回 `1.0`）为什么是约定而不是计算结果，以及调用方必须做什么。
6. 复述一个 JSON bundle 里包含哪三样东西，以及「往返相等」这件事是谁在检查、检查了哪些字段。
7. 解释 `bundles_equal` 为什么返回**差异清单**而不是布尔值。
8. 说清 bundle 里的 KPI 为什么不重算 —— 以及重算会带来什么后果。

---

## 2. 为什么 Day 5 要做 KPI 与完整输入输出

前四天做的是**可行性与目标值**：一个排程合法不合法、它的 `makespan` 或加权迟期是多少。
这些是求解器之间比较用的语言，不是车间主任用的语言。车间主任要问的是另一组问题：

```text
这个排程让多少订单准时？         ->  准时率
机器有多少时间是闲着的？         ->  utilization
有多少时间花在换型上？           ->  换型占比
哪个人最忙？忙到什么程度？       ->  人员负载
最迟的那张单子迟了多少？         ->  max lateness
```

同一份排程可以回答这两组问题，但**它们的口径必须写下来**。
「利用率」这个词在不同厂里可以指三种不同的东西：

```text
口径一   各资源利用率的算术平均
口径二   总占用时间 / 总可用时间
口径三   瓶颈资源的利用率
```

三种口径在同一份排程上可以差出一倍。如果不写清用的是哪一种，
一页 KPI 报表就是一份**不能复核**的文档 —— 而不可复核的报表比没有报表更危险，
因为它看起来很权威。

然后是完整输入输出。前四天的产物都是「内存里的一份 `ShopResult`」：

```text
跑一次 -> 得到排程 -> 打印几行 -> 进程结束 -> 排程没了
```

这在实验阶段够用，但它有两个问题。第一，**报表里引用的排程无法被第三方复核** ——
别人只能相信打印出来的那几行字。第二，**KPI 与排程可能不一致** ——
如果 KPI 是另一次运行算的，两份数字对不上时无法判断谁错了。

今天的做法是把三样东西封成一个 JSON：

```text
instance   完整的输入（含全部约束数据）
result     完整的输出（求解器读数 + 每道工序的机器/时刻/资源指派）
kpi        从 result.schedule 算出的 KPI（含口径说明）
```

一份 bundle 就是一个**自足的档案**：拿到它的人不需要跑任何求解器，
就能复核 KPI 是不是从这份排程算出来的，也能把实例重新解一遍看结果是否可复现。
这就是本周「完整 JSON 输入输出」这条交付的实质。

---

## 3. 概念：一页 KPI 的口径

### 3.1 三组字段

`KPIReport` 的字段按来源分三组：

| 来源 | 字段 | 说明 |
|---|---|---|
| 排程的时刻 | `cmax`、`total_tardiness`、`weighted_tardiness`、`max_lateness`、`mean_flow_time` | 全部由工序的 `start` / `end` 推出 |
| 实例与排程一起 | `jobs_with_due_date`、`jobs_on_time`、`on_time_rate` | 先查实例里的 `due_date`，再与完工时刻比 |
| 资源占用 | `setup_time`、`setup_share`、`machine_kpi`、`worker_kpi`、`machine_utilization`、`worker_utilization`、`worker_load` | 由「谁在什么时间段占用了哪个资源」推出 |

三组的共同点是：**全部只依赖 `(instance, schedule)` 这两个入参**。
所以 KPI 计算不需要求解器，也不需要 `ShopResult` —— 一份存下来的排程同样能算。
这一点是 bundle 能成立的前提：KPI 是排程的函数，不是运行过程的函数。

### 3.2 `Cmax`、迟期与流经时间

```text
C_j         订单 j 的完工时刻 = 它最后一道工序的 end（各工序 end 的最大值）
Cmax        max_j C_j（所有订单完工时刻的最大值）
T_j         max(0, C_j - d_j)                       迟期
ΣT          Σ_j T_j（不带权）
ΣwT         Σ_j w_j · T_j（带权，注意这里**不含** priority，见 Day 4 第 6.2 节）
max lateness max_j (C_j - d_j)                      可以为负 —— 提前就是负数
mean flow time  Σ_j C_j / |J|                       平均完工时刻（释放时间都是 0 时等于平均流经时间）
```

`max_lateness` 与 `total_tardiness` 的区别值得单独记：

```text
T_j 在 0 处被截断    ->  ΣT 只统计「迟了多少」，不奖励提前
lateness 不截断      ->  max lateness 可以是负数，表示「所有订单都提前」，且能报出提前多少
```

本实例的 `max_lateness = 15`，与 `ΣT = 15` 数值相同 —— 因为订单 `J0` 提前（`9 <= 14`）贡献 `0`，
只有 `J1` 迟到 `15` 分钟。这不是巧合，是「只有一个订单迟到」时的必然。

### 3.3 `utilization`：分子与分母

这是今天最容易被误读的一个数，必须把口径写死：

```text
单个资源 r：
  load(r)   = Σ 该资源上各段占用的时长                       （真正在干活的时间）
  span(r)   = max(end) - min(start)   （首次占用开始到末次占用结束的墙钟跨度）
  utilization(r) = load(r) / span(r)  （span = 0 时定义为 0）

报表里的汇总：
  machine_utilization = Σ_r load(r) / Σ_r span(r)     <- 总负载 / 总跨度
  worker_utilization  = Σ_r load(r) / Σ_r span(r)
```

**它不是「各资源利用率的算术平均」。** 两者在本实例上差得很远：

```text
各资源利用率         M0: 0/0 = 0     M1: 20/27 = 0.740741        算术平均 = 0.370371
总负载 / 总跨度      20 / (0 + 27) = 20 / 27 = 0.740741          <- 报表用的是这一个
```

差在 `M0` 那一台闲置的机器上：算术平均让「没被用到的机器」拉低整体利用率，
而总负载 / 总跨度只看「实际被占用的那些资源在它们的时间窗里有多忙」。
两种口径都不错，但**必须知道自己看的是哪一种**：本报表用的是后者，
名字却叫 `machine_utilization`，读的时候要按定义读，不能按直觉读。

### 3.4 `load` 与 `span` 的差

```text
load  = 20    W1 实际看机器的总时长（4 + 5 + 6 + 5）
span  = 27    从 W1 第一段开始（0）到最后一段结束（27）
差    = 7     工人「在位但没事干」的时间：等机器、等换型
```

`load < span` 是所有「人跟着机器走」的排程的常态。真正要盯的是两个极端：

```text
load == span   这个人从头忙到尾 —— 他很可能就是瓶颈
load << span   这个人被叫来了但大部分时间在等 —— 排班可以更省
```

所以报表里同时给 `load` 与 `span` 是有意的：只给 `utilization` 一个比值，
看不出来是「忙但时间窗短」还是「闲但时间窗长」。

### 3.5 `setup_share`

```text
setup_share = setup_time / cmax
```

`setup_time` 来自 `fjsp_core.objective.total_setup_time`（按相邻对的族查表求和，见 Day 2 第 7.1 节），
它是**代价口径**而不是空闲口径。本实例：

```text
setup_time = 3      一次 F0 -> F1 换型（A、B 是 F0，C、D 是 F1）
setup_share = 3 / 27 = 0.111111
```

### 3.6 归一化

`normalize(report, reference)` 把当前报表与一个**参考排程**的报表相除，返回三个比值：

```text
{'cmax': 当前/参考, 'total_tardiness': 当前/参考, 'setup': 当前/参考}
比值 < 1 表示当前更好
```

零分母的处理是一条**约定**，必须写进文档：

```text
参考值为 0 时返回 1.0，并说明「无法区分」——
不返回 inf（比值无界）、不返回 nan（不可比较）、也不省略这一项（会让人以为漏了）。
返回 1.0 的含义是「在这个分量上参考排程是完美的，任何实数都是错的答案」，
所以调用方**必须**回去看原值才知道发生了什么。
```

这条约定的重要性在于：它是一个**会掩盖信息**的选择。选择它的理由是会掩盖得最少 ——
`inf` 会让下游的排序、平均、画图全部崩掉，`nan` 会让 `!=` 比较静默失效，
而 `1.0` 至少是一个能参与运算、并且能被显式检查的数。

---

## 4. 推导：bundle 的往返契约

### 4.1 三样东西与一个版本号

```python
@dataclass(frozen=True, slots=True)
class Bundle:
    instance: FJSPInstance
    result: ShopResult
    kpi: KPIReport
    schema: int = BUNDLE_SCHEMA      # 当前是 1
```

`to_dict()` 把它摊成三层 JSON，`from_dict()` 读回来。往返要保住的相等性是逐字段的：

```text
instance        全部字段（订单、工序、机器、日历、维护、资质、工人、换型矩阵、meta）
result          方法名、状态、目标值、下界、建模型/求解耗时、分支数、breakdown、detail
                schedule：每道工序的机器、开工、完工、资源
kpi             全部字段（含 normalization_note 这段文字）
```

`schema` 是给未来的自己留的：如果哪一天 bundle 的字段改了，
读旧文件时至少知道它是哪个版本写的，而不是把一份缺字段的 JSON 读成一堆默认值。

### 4.2 为什么要有一个独立的相等性函数

`bundles_equal(left, right) -> list[str]` 返回的是**差异清单**，
空列表才表示完全相等。为什么不返回 `bool`？

```text
返回 False 的信息量是 0：它只说「不一样」，不说「哪里不一样」。
排查一个往返 bug 时，你需要的恰恰是「哪个字段丢了」——
是 result.schedule 少了一道工序？还是 kpi 的某个浮点末位变了？
```

所以它按字段分组检查，并把命中的组名放进清单：

```text
JSON 结构层   instance / result / kpi 三个顶层块的原始字典是否相等
dataclass 层  instance 与 kpi 两个 dataclass 是否逐字段相等
排程层        schedule 是否存在、以及逐段是否相等
读数层        method / status / objective / best_bound / iterations / breakdown
耗时层        build_time / solve_time 按 6 位小数比（JSON 的精度就是 6 位）
```

最后一行是一个刻意的折中：wall-clock 耗时是观测值，每次运行都会变，
所以库里存的是 6 位小数；比较时也按 6 位比，避免「第 17 位不同」导致往返被误判为不相等。

### 4.3 为什么 KPI 不做重算

`Bundle.from_dict` 读回 KPI 时**不重算**，直接取 JSON 里的值。这个选择需要辩护，
因为「重算一遍更保险」听起来很对：

```text
如果读回来重算，那么 bundle 里的 kpi 块就是冗余的 —— 它可以被删掉，
反正读的时候会重新算。留一个冗余块会让人以为它有意义。
更要紧的是：重算会掩盖**写的时候**算错了这件事。往返相等本来是为了验证
「存档与原件一致」，重算会把「存档里的 KPI 错了」这个错误洗掉 ——
读回来的 KPI 永远是对的（因为它是刚算的），而原来那份错的被静默丢弃。
```

所以正确做法是：**写的时候算一次、验一次；读的时候一个字节都不改。**
KPI 是档案的一部分，不是缓存。

### 4.4 打包前先验证

`make_bundle(instance, result, *, verify=True)` 在默认情况下先跑一遍
`validate_result(instance, result)`，排程不合法就直接抛错，不产出 bundle。

```text
理由：一份不合法的排程被存成档案，会比没有被存下来更糟 ——
它会被当成「求解器的产物」引用，而它的每道工序的时刻都可能是错的。
```

把验证放在**入口**而不是出口，是本周反复出现的同一条纪律：
`ShopResult` 一旦离开求解器就要过独立验证，bundle 只是它离开内存之前的最后一站。

---

## 5. 手算：七个数的逐个核对

实例是 Week 4 实验驱动里分层实例构造函数的 `+worker` 层，
用 `fjsp_cpsat_full` 在 `15` 秒预算下求解（状态 `OPTIMAL`，`Cmax = 27`）。
求解器给的排程：

```text
A  M1  [0,4)    W1        J0 = (A, B)，due = 14
B  M1  [4,9)    W1
C  M1  [16,22)  W1        J1 = (C, D)，due = 12
D  M1  [22,27)  W1
```

**核对一：完工时刻与 `Cmax`。**

```text
C_J0 = max(A.end, B.end) = max(4, 9) = 9
C_J1 = max(C.end, D.end) = max(22, 27) = 27
Cmax = max(9, 27) = 27                                与报表一致
```

**核对二：迟期。**

```text
T_J0 = max(0, 9 - 14)  = 0        提前 5 分钟
T_J1 = max(0, 27 - 12) = 15       迟 15 分钟
total_tardiness  = 0 + 15 = 15                        与报表一致
max_lateness     = max(9-14, 27-12) = max(-5, 15) = 15 与报表一致
```

**核对三：准时率。**

```text
两张单子都有 due_date -> jobs_with_due_date = 2
J0 准时（9 <= 14）、J1 迟到 -> jobs_on_time = 1
on_time_rate = 1 / 2 = 0.5                            与报表一致
```

**核对四：平均完工时刻。**

```text
mean_flow_time = (9 + 27) / 2 = 18                    与报表一致
```

**核对五：换型。**

```text
M1 上的加工顺序是 A(F0) -> B(F0) -> C(F1) -> D(F1)
相邻对的换型：setup(F0,F0) + setup(F0,F1) + setup(F1,F1) = 0 + 3 + 0 = 3
setup_share = 3 / 27 = 0.111111...                   与报表一致（6 位小数取 0.111111）
```

**核对六：机器与工人的负载。**

```text
W1 看管的四段：4 + 5 + 6 + 5 = 20
W1 的跨度：max(end) - min(start) = 27 - 0 = 27
utilization(W1) = 20 / 27 = 0.740741                  与报表一致
W0、W2 一段都没有：load = 0、span = 0、utilization = 0
```

**核对七：汇总口径。**

```text
machine_utilization = Σload / Σspan = 20 / (0 + 27) = 0.740741    与报表一致
worker_utilization  = Σload / Σspan = 20 / (0 + 0 + 27) = 0.740741
```

第七项是第 3.3 节那个陷阱的实证：如果把 `machine_utilization` 理解成
「各机器利用率的算术平均」，会算出 `(0 + 0.740741) / 2 = 0.370371`，
与报表的 `0.740741` 差一倍。**报表没写错，是名字容易让人读错。**

---

## 6. 实现：KPI 与 bundle 的两处关键约定

### 6.1 KPI 的调度位置

[fjsp_io/kpi.py](../../projects/03_industrial_fjsp/fjsp_io/kpi.py) 里的函数只吃 `(instance, schedule)`：

```python
def kpi_report(instance: FJSPInstance, schedule: Schedule) -> KPIReport
def normalize(report: KPIReport, reference: KPIReport) -> dict[str, float]
def format_kpi(report: KPIReport) -> str
```

三个函数的层次很清楚：`kpi_report` 是计算、`normalize` 是相对比较、`format_kpi` 是排版。
**`format_kpi` 刻意只用 ASCII 排版符号**，理由写在了它的 docstring 里：
示例脚本的 stdout 要能在 GBK 控制台上打印，破折号与上标都会炸。
这与本周所有脚本「不打印非 GBK 字符」的纪律是同一条 —— 区别只在
KPI 这一层把纪律固化进了代码，而不是靠调用方自觉。

`ResourceKPI` 只记四个数（`load`、`span`、`capacity`、`operations`）加一个比值。
`operations` 是段数（本实例 `W1` 是 `4`），它让「利用率高」这件事可以进一步拆：
`4` 段 20 分钟与 `1` 段 20 分钟的利用率一样，但前者切了三次，换型/上下料的机会更多。

### 6.2 bundle 的读写

[fjsp_io/json_bundle.py](../../projects/03_industrial_fjsp/fjsp_io/json_bundle.py) 提供四个入口：

```text
make_bundle(instance, result, *, verify=True) -> Bundle      打包（先验证排程）
save_bundle(path, instance, result, *, verify=True) -> Bundle 打包并落盘
load_bundle(path) -> Bundle                                   读盘
bundles_equal(left, right) -> list[str]                       逐字段比对，返回差异清单
```

`_instance_to_dict` 走的是 `dataclasses.asdict`：**没有手写字段映射**。
这样做的理由是避免「模型加了新字段、序列化忘了跟上」这类静默丢字段的 bug ——
`asdict` 会把新增字段一起带走。反过来，它要求模型里的所有字段都是可 JSON 化的
（`tuple` 会被摊成 `list`，读回来再转回 `tuple`），这是加字段时要一起考虑的成本。

---

## 7. 实验：`m3w4d5_kpi_bundle`

脚本：[m3w4d5_kpi_bundle.py](../../projects/03_industrial_fjsp/examples/m3w4d5_kpi_bundle.py)。

在项目目录 `projects/03_industrial_fjsp` 下运行：

```bash
python examples/m3w4d5_kpi_bundle.py
```

实际输出（原样粘贴）：

```text
=== 1. 先解一条排程（status=OPTIMAL，Cmax=27）===
  A  M1  [0,4)  W1
  B  M1  [4,9)  W1
  C  M1  [16,22)  W1
  D  M1  [22,27)  W1

=== 2. KPI 报告 ===
== KPI ==
  Cmax (makespan)          : 27
  total tardiness          : 15
  weighted tardiness       : 15
  max lateness             : 15
  on-time                  : 1/2  (rate 0.5)
  mean flow time           : 18
  setup time               : 3  (share of Cmax 0.111111)
  machine utilization      : 0.740741
  worker utilization       : 0.740741
  -- workers --
    W0: load=0 span=0 cap=1 ops=0 utilization=0
    W1: load=20 span=27 cap=1 ops=4 utilization=0.740741
    W2: load=0 span=0 cap=1 ops=0 utilization=0

=== 3. 抽三个数手工核对 ===
  完工时刻：{'J0': 9, 'J1': 27}
  迟期项：J0: max(0,9-14)；J1: max(0,27-12)
  报告里的 total_tardiness = 15（上式的和）
  换型：独立函数 total_setup_time = 3　报告里的 setup_time = 3
  工人负载：
    W0 load=0 span=0 utilization=0
    W1 load=20 span=27 utilization=0.740741
    W2 load=0 span=0 utilization=0
  注意 span 不是 load：工人可能闲着等机器。utilization = load / span。

=== 4. JSON bundle 往返 ===
  序列化长度：3976 字符
  bundles_equal(原件, 读回来) = [] 完全相等
  往返比的是：实例、排程（每道工序的机器/时刻/资源）、KPI 每个字段。

=== 5. 改一个数字，看差异清单能不能指出位置 ===
  bundles_equal(原件, 被改过) = ['result', 'result.schedule']
  返回的是**差异清单**而不是 True/False，就是为了这一刻。

=== 6. 归一化：相对参考排程打分 ===
  cmax                   0.870968
  setup                  1
  total_tardiness        0.789474
  Cmax 复核：27 / 31 = 0.870968
```

### 7.1 怎么读这段输出

**第 2 节的十行里只有两行是「目标值」，其余八行是「业务读数」。**
`Cmax` 与 `weighted tardiness` 是求解器优化过的；`on-time`、`mean flow time`、
`setup time`、两个 `utilization` 都不是 —— 求解器完全不知道它们的存在。
所以**一个排程可以在被优化的指标上最优，同时在没被优化的指标上很差**：
本实例 `Cmax = 27` 是最优的，准时率却只有 `0.5`（两张单子一张迟到）。

**第 3 节是今天最该动手的一节**，它把第 5 节的七项手算挑了四项用独立方式再算一遍：
完工时刻从排程取 `max(end)`，迟期自己写 `max(0, C - d)`，
换型调 `fjsp_core.objective.total_setup_time`（与 KPI 模块内部是两条路径），
工人负载从 `worker_kpi` 读出来与手算的 `20` 对。

```text
完工时刻：{'J0': 9, 'J1': 27}        <- 手算核对一
报告里的 total_tardiness = 15         <- 手算核对二
换型：独立函数 total_setup_time = 3　报告里的 setup_time = 3    <- 手算核对五
W1 load=20 span=27 utilization=0.740741                        <- 手算核对六
```

四项全部吻合。最后一行那句提醒（`注意 span 不是 load`）是本节唯一一个「不是数字」的结论，
但它比数字重要：它说明 `0.740741` 是怎么来的，以及同一个工人为什么在另一份排程上
可能 `load = 20` 而 `utilization = 0.5`（跨度变成 40）。

**第 4 节的 `3976 字符` 是观测值，不是规格值。** 它随实例与排程变化，
而且同一个实例重跑也会差一两个字符：bundle 里记了 `build_time` 与 `solve_time` 两个浮点数，
它们的位数会变（实测过 `3976` / `3977` / `3978` / `3979` 四种长度），而**排程那一段逐字不变**
（工序的机器、时刻、`worker_id` 全部相同）。它的用处只给「一份 bundle 有多大」一个量级感：
不到 4 KB，可以塞进工单、邮件、日志。真正要核的是下一行：

```text
bundles_equal(原件, 读回来) = [] 完全相等
```

空列表的语义是「逐字段全部相等」，覆盖实例（含换型矩阵、日历、资质、工人）、
结果（含每道工序的机器/时刻/资源与全部读数）、KPI（含 `normalization_note` 那段文字）。
**这是一次真正的往返**：`to_dict -> json.dumps -> json.loads -> from_dict` 走完一整套。

**第 5 节是刻意保留的负例。** 把序列化结果里第一道工序的 `end_time` 加 `1` 再读回来比对：

```text
['result', 'result.schedule']
```

两层同时命中：`result` 是 JSON 结构层的比较，`result.schedule` 是排程层的比较。
**这就是返回差异清单而不是 `True/False` 的价值** —— 返回 `False` 只知道「不相等」，
不知道问题在 `instance`、`result` 还是 `kpi`；返回清单就一眼看出「排程被改了，
实例与 KPI 都没动」。两层同时出现不是冗余：它们用的是两套独立读法
（原始 JSON 与解析后的对象），**只有一层命中才说明序列化或反序列化有一侧丢了东西。**

**第 6 节展示归一化的用法与边界。**

```text
cmax                0.870968       27 / 31
setup               1              3 / 3
total_tardiness     0.789474       15 / 19

Cmax        27 / 31 = 0.870968     好 12.9%
setup       3 / 3  = 1             一样
ΣT          15 / 19 = 0.789474     好 21.1%
```

参考排程是同一实例在 `+locked` 层（`C` 锁定到 `M1` 开工 `20`）的最优解，`Cmax = 31`。
三个比值都 `<= 1`，读作「当前排程在这三个分量上不差于参考排程」。最后一行是脚本自己做的
**分子分母复核** —— 它看起来多余，却是唯一能发现「分子分母写反」的手段：
归一化表里最容易出的错就是颠倒，而颠倒之后所有数仍然「看起来合理」（都在 0～1 之间）。

`setup` 那一项等于 `1` 值得注意：两份排程的换型总量都是 `3` 分钟。它说明
**归一化是逐分量的**，不能把三个比值再加权成一个总分 ——
`(0.870968 + 1 + 0.789474) / 3 = 0.886814` 这个数没有任何含义，
因为三个分量的业务含义完全不同。

---

## 8. 今日练习

1. **练习 1（手算）**：本实例的 `weighted_tardiness` 与 `total_tardiness` 都是 `15`。
   请说明它们在什么参数下会不同，并给出一个最小的改动（改哪个字段、改成多少）。
2. **练习 2（判读）**：报表里 `machine_utilization = 0.740741`。
   请算出「各机器利用率的算术平均」是多少，并说明读报表的人为什么会算错。
3. **练习 3（推导）**：`W1` 的 `load = 20`、`span = 27`。请问这个工人有没有可能
   在同一条排程里 `load = 20` 而 `span = 20`？要满足什么条件？
4. **练习 4（编码）**：把 `bundles_equal` 改成返回 `bool`，第 5 节那个负例的输出会变成什么？
   请写出改后的输出，并说明你因此丢了什么信息。
5. **练习 5（工程）**：`normalize` 在参考值为 `0` 时返回 `1.0`。
   请构造一个实例让 `total_tardiness` 的参考值为 `0`，并说明这时调用方该怎么写代码才不会误判。

---

## 9. 验收清单

- [ ] 能说出 KPI 报表里每个字段是从排程推出来的还是从实例推出来的。
- [ ] 能手算 `Cmax`、`total_tardiness`、`max_lateness`、`mean_flow_time`、`setup_share`。
- [ ] 能说清 `utilization` 的分子分母，并指出它**不是**各资源利用率的平均值。
- [ ] 能解释 `load < span` 的差额是什么，以及为什么报表要同时给这两个数。
- [ ] 能说清 `normalize` 的零分母约定为什么是约定，以及调用方必须回去看原值。
- [ ] 能说出一个 bundle 里的三样东西，以及 `schema` 字段的用途。
- [ ] 能解释 `bundles_equal` 为什么返回差异清单，并说出它会命中哪几层。
- [ ] 能说清 bundle 里的 KPI 为什么不重算，以及重算会掩盖什么错误。
- [ ] 在项目目录下运行 `python examples/m3w4d5_kpi_bundle.py`，输出与本日第 7 节一致（KPI 十行与往返结果必须一致，序列化长度可微变）。
- [ ] 在项目目录下运行 `python -m pytest tests/test_week4.py -q`，与本日相关的用例（KPI 与 bundle）全部通过。

---

## 10. 自测题

- Q1：`total_tardiness` 与 `max_lateness` 都能回答「迟得厉害吗」，为什么要两个都给？
- Q2：`weighted_tardiness` 在本实例上等于 `total_tardiness`。它们是同一个东西吗？
- Q3：报表的名字叫 `machine_utilization`，本实例上它是 `0.740741`。请写出它的算式。
- Q4：`W0` 与 `W2` 的 `utilization` 都是 `0`（`load = span = 0`）。这是不是说明它们被浪费了？
- Q5：`setup_share = 0.111111`。这个数大不大？判断它需要什么额外信息？
- Q6：`normalize` 为什么返回比值而不是差值？两组数各自适合回答什么问题？
- Q7：一份 bundle 里的 `kpi` 块能不能删掉、读的时候重算？为什么不这么做？
- Q8：`bundles_equal` 在往返正常时返回空列表。空列表与「函数没执行成功」怎么区分？
- Q9：`make_bundle(verify=True)` 在打包前跑一遍验证。为什么不把它放在 `load_bundle` 那一侧？
- Q10：KPI 报表把 `Cmax` 与 `on_time_rate` 并列放在同一页里。这两个数被优化过吗？

### 参考答案

- A1：因为它们回答不同的问题。`ΣT` 是总量：它会把「一张单子迟 100 分钟」与
  「100 张单子各迟 1 分钟」算成同一个数；`max_lateness` 是极值：它盯住最坏的那一张。
  只看 `ΣT` 会漏掉「总量不大但有一张单子迟得离谱」的情形，只看 `max` 会漏掉「大家都迟一点」。
  两者并列才看得出分布的形状。
- A2：不是，只是在本实例上数值相同。`ΣT = Σ_j T_j`，`ΣwT = Σ_j w_j T_j`；
  当所有涉及迟期的订单权重都是 `1.0` 时两者相等。把任意一张迟到订单的 `weight` 改成 `2.0`
  （本实例只有 `J1` 迟到），`weighted_tardiness` 就变成 `30`，而 `total_tardiness` 仍是 `15`。
- A3：`Σ_r load(r) / Σ_r span(r) = (0 + 20) / (0 + 27) = 20 / 27 = 0.740741`。
  即总负载除以总跨度。`M0` 的 `span` 是 `0`，所以它对分子分母都没有贡献。
- A4：不能这么说。它们 `utilization = 0` 是因为**这一段没被用**，
  而不是因为它们「效率低」。本实例只需要一个人看 `M1`（`A`、`B`、`C`、`D` 全在 `M1` 上），
  所以 `W1` 就够了。`W0` 与 `W2` 的存在是**可选性**：如果排程换了（例如 `M0` 上有活），
  它们就能顶上。报表只能报「这一段用没用」，不能报「这个资源该不该留」。
- A5：判断它大不大需要两样信息：一是**同实例的历史值或基线值**（例如上一版排程的
  `setup_share` 是多少），二是**换型矩阵的量级**（本实例一次换型 3～4 分钟，
  而 `Cmax` 是 27 分钟，所以 11% 属于「有换型但没失控」）。
  单看 `0.111111` 这个数无法判断 —— 换型时间占 11% 在有些车间是优秀，在有些车间是失控。
- A6：返回比值是因为三个分量的量纲相同（都是分钟）但**量级不同**：
  `Cmax` 是 27、`ΣT` 是 15，直接减会得到 `27 - 31 = -4` 与 `15 - 19 = -4` 这样
  「差值相同但相对变化差一倍」的结果。比值回答「相对改善了多少」，
  差值回答「绝对省了多少分钟」—— 报给车间主任时两个都要，所以原值也要一起给出。
- A7：能删，但不应该删。删掉之后读回来的 KPI 是**刚算的**，
  于是「写的时候算错了 KPI」这个错误在往返检查里被洗掉了 ——
  读回来永远是对的，原来那份错的被静默丢弃。往返相等要验证的是
  「存档与原件一致」，不是「KPI 算法正确」；后者要靠手工核对（第 5 节那样）。
- A8：靠调用方式的约定区分：它返回一个列表，`[]` 是「全部相等」这一种确定的结果，
  而「没执行成功」会抛异常或返回 `None`（`None` 与 `[]` 在 Python 里是两回事）。
  这也是为什么它不返回 `bool`：`False` 与「函数出错」在布尔语义下不好区分，
  而列表能同时表达「相等」与「哪些字段不等」。
- A9：因为验证是**入口检查**：`make_bundle` 是排程离开内存前的最后一站，
  在这里拦住不合法排程，坏的档案根本不会产生。放到 `load_bundle` 那一侧的话，
  不合法排程已经落盘了 —— 它会在磁盘上存在、被引用、被转发，
  只在读的时候报错，而那时已经晚了。
- A10：只有 `Cmax` 被优化过（本实例的目标函数是 `makespan`）。
  `on_time_rate`、`mean_flow_time`、`setup_time`、两个 `utilization` 都不是目标的组成部分，
  求解器完全不知道它们的存在。所以一页 KPI 里可以出现「被优化到最优」与
  「顺带算出来的」两类数 —— 读报表的人必须知道哪一行是前者。

---

## 11. 今日一句话总结

> **KPI 是 `(instance, schedule)` 的函数，不是运行过程的函数 —— 所以它能被存进档案、被第三方复核；而每一个 KPI 都必须带着自己的口径：`utilization` 是「总负载 / 总跨度」（本实例 `20 / 27`）而不是「各资源利用率的平均」（那是 `0.370371`），`load` 与 `span` 要一起给才知道「忙」是忙在时间窗短还是真的在干活；bundle 把实例、结果、KPI 封成一个自足档案，往返逐字段相等，差异以清单形式返回而不是布尔值，`kpi` 块读回来一个字节都不改 —— 因为档案不是缓存。**
