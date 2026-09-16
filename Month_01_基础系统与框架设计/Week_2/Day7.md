# Day 7：表示、验证与测试边界复盘

> 当日主题：为所有搜索方法固定共同的接口，汇总 Week 2 的证据与边界
> 当日产出：**共享接口契约 + 证据表 + 已知局限清单 + 表示冗余/追加解码实验脚本**
> 建议投入：1.5 小时复盘 ＋ 2 小时数学（合计 3～4 小时）

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 写出本周固定的接口链 `Instance → Candidate → decode → Schedule → validate_schedule → objective`，并说明为什么每一环都不能省。
2. 说清楚「输入不可变、邻域返回新 `Candidate`、每次完整评价走同一条链」这三条约定各自的用途。
3. 把 Week 2 的每一项要求对应到**具体的测试名**，而不是笼统地说「都测过了」。
4. 用具体例子解释**表示冗余**：两个不同的 `Candidate` 可以解码出同一个 `Schedule`。
5. 解释**追加式解码**为什么不会把后面的工序填进已经出现的机器空隙。
6. 说清楚四条已知局限（表示冗余、追加解码、生成器全资格、Oracle 只证单工序极小实例），并知道它们**不能靠更多同分布测试消除**。
7. 用有向无环图的语言说明：为什么当前作业链结构不可能出现环，以及未来换成任意 precedence 边集时必须补什么。

**Day 7 不新增任何算法。** 今天的任务是：把 Week 2 的表示层、解码层、验证层与测试约定钉成一份后面 10 个月都要复用的契约。

---

## 2. 为什么要有「固定接口」的复盘日

Week 2 六天加进来的东西，单独看都成立：

```text
Day 1  Candidate：把「决策」和「结果」分开
Day 2  decode：把决策变成可行排程
Day 3  swap / insert / reassign：定义能走到哪里
Day 4  独立验证器：不信任任何算法产出的排程
Day 5  生成器与输入质量：可复现的测试数据
Day 6  枚举对拍：单工序极小实例上证明最优
```

拼在一起却有一类危险：**每个模块都「各按自己的理解」产生或消费排程**。典型症状：

- 某个算法为了快，跳过 `validate_schedule` 直接算目标；
- 某个算法自己写了一份目标公式，和 `objective.py` 有一点点差别；
- 某个搜索方法改动 `Candidate` 的字段而不是返回新对象；
- 某个实验直接用「跑了多少轮」当预算，和别的实验没法比。

这些都不是「写错了」，而是**没有契约**。Day 7 的产出因此不是更长的解释，而是三样更硬的东西：

> **一份接口链、一张证据表、一张边界清单。**

它们的作用是：Week 3 的 SearchConfig / SearchResult 与完整评价计数，会**直接挂在这条链上**——把「运行几轮」正式换算成可比较的**计算预算**。

---

## 3. 固定接口链

```text
Instance ──> Candidate ──decode──> Schedule ──validate_schedule──> 可信排程 ──objective──> 数值
   ↑            ↑
 不可变      不可变（邻域只返回新对象）
```

三条约定，逐一说明：

### 3.1 输入与候选都不可变

`Instance` / `Job` / `Operation` / `Machine`（[models.py](../../projects/01_scheduling_core/scheduling_core/models.py)）和 `Candidate`（[solution.py](../../projects/01_scheduling_core/scheduling_core/solution.py)）都是 `@dataclass(frozen=True, slots=True)`，集合字段一律用 `tuple`。

**为什么必须不可变**：同一个 `Instance` 要同时被 SPT、解码器、局部搜索、SA、MILP 复用。任何一个环节能改输入，后面所有实验的结果都不可信。`Candidate` 同理——邻域一旦能就地修改父解，「当前解」会在你不知情的地方被改掉，`trace` 也无法复现。

### 3.2 邻域返回新 Candidate

`swap` / `insert` / `reassign` 全部通过 `dataclasses.replace` 返回**新对象**。这条约定让「扫描邻域」与「更新当前解」在内存层面天然分离：扫描期间无论产出多少邻居，当前解一个字节都不会变。

### 3.3 每次完整评价必须走同一条链

**定义**：一次完整评价 = `decode` + `validate_schedule` + `objective`。

```text
decode(instance, candidate)         -> Schedule      构造（假设候选合法）
validate_schedule(instance, sched)  -> None 或 ValueError   独立检查
objective(instance, sched)          -> 数值          统一公式
```

**禁止的两件事**：

1. 某个算法略过验证。这会同时丢掉两层保险：既不能发现实现错误，也不能校验从外部导入的排程。
2. 某个算法使用另一套目标公式。这样「谁更好」会变成「谁的公式更宽松」。

**唯一例外**是实验设计本身：如果要把「带验证的评价」与「不带验证的评价」当成两个性能设置来对比，必须**显式**写成两组实验，而不是让某个算法偷偷省掉一步。

---

## 4. 本周证据表

把要求逐条对到测试名（测试代码在 [test_month1.py](../../projects/01_scheduling_core/tests/test_month1.py)）：

| 要求 | 证据（测试名） | 实际覆盖 |
|---|---|---|
| 三类解表示 / 解码轨迹 | `test_three_decoder_traces` | 3 条参数化编码 → 3 条精确时间轨迹 |
| swap / insert / 指派与边界 | `test_moves_and_boundaries` | 交换两次复原、插入方向、越界、非法资格 |
| 至少五类非法排程 | `test_independent_validator_corruption` | **实际九类**破坏 |
| 可复现输入、CSV / JSON | `test_roundtrip_and_csv` | JSON 往返相等 + CSV 三表读取 |
| 至少五个小例枚举 | `test_five_independent_enumerations` | **5 个种子** × 384 个组合 |

逐条展开：

### 4.1 `test_three_decoder_traces`（3 条）

固定实例 `route_instance`（J0 = A→B，J1 = C；A 只能上 `M0`，B、C 各有 `M0`/`M1` 资格），三条编码各自要求**精确的起止时刻**：

| 编码 | 期望时间轨迹 |
|---|---|
| `order=ABC, assign=M0/M1/M0` | A:`M0`[2,5)、B:`M1`[5,7)、C:`M0`[5,6) |
| `order=BCA, assign=M0/M1/M0` | C:`M0`[0,1)、A:`M0`[2,5)、B:`M1`[5,7) |
| `order=BCA, assign=M0/M0/M1` | C:`M1`[0,1)、A:`M0`[2,5)、B:`M0`[5,7) |

三条都额外要求：`validate_schedule` 通过，且**重复解码得到完全相同的 `Schedule`**（`decode(instance, c) == decode(instance, c)`）。这是确定性的最小证据。

### 4.2 `test_moves_and_boundaries`（1 条，覆盖 7 组断言）

```text
insert(candidate, 0, 2).order == ("B", "C", "A")     插入的 j 是「移除后的最终位置」
swap(swap(c, 0, 2), 0, 2) == c                        交换两次复原
len(set(moved)) == len(moved) and candidate not in moved    去重且不含自身
每个邻居都能 decode 且通过 validate_schedule          邻域不制造非法解
swap(candidate, -1, 0)  -> IndexError                 负索引被拒绝
reassign(..., "M1")     -> ValueError                 A 只能上 M0
decode(..., order=("A","A","C")) -> ValueError        重复工序被拒绝
```

### 4.3 `test_independent_validator_corruption`（9 类）

从一条合法排程出发，每次只破坏一处，断言 `schedule_errors` 报告里出现对应类别、且 `validate_schedule` 抛 `ValueError`：

| # | 破坏类别 | 怎么破坏 |
|---:|---|---|
| 1 | `precedence` | 把 B 改成 [2,4)，早于 A 完工 |
| 2 | `overlap` | 把 C 挪到 `M0` [3,4)，与 A 重叠 |
| 3 | `illegal assignment` | 把 A 放到 `M1` |
| 4 | `missing` | 删掉 C |
| 5 | `duplicate` | 再追加一次 A |
| 6 | `release` | 把 A 提到 [0,3)，早于 `r=2` |
| 7 | `duration` | 把 A 的 `end_time` 改成 6，不再等于 `start + p` |
| 8 | `unknown operation` | 把 `operation_id` 改成 `"X"` |
| 9 | `invalid time type` | 把 `start_time` 改成 `NaN` |

**要求只写了「至少五类」，实际做到九类。** 一个坏排程可以同时触发多条诊断，测试只要求「至少命中对应类别」。

### 4.4 `test_roundtrip_and_csv`（1 条）

`save_json_instance` 再 `load_json_instance` 必须**等于原对象**；CSV 走三张表（`machines.csv` / `jobs.csv` / `operations.csv`），并确认空的 `due_date` 字段被解析成 `None`、`processing_time` 被解析成整数 3。

### 4.5 `test_five_independent_enumerations`（5 个种子）

对 `generate_instance(seed, jobs=4, machines=2)`、`seed = 0..4`：

```text
exhaustive_optimum 的计数必须是 384（4! × 2^4 = 24 × 16）
测试自己再用 Candidate + decode 遍历同一个决策空间，最小值必须与 oracle 相同
六个算法在 budget=30 下返回的目标值都必须 >= optimum
```

第二条是关键：**oracle 不调用 decoder，测试用 decoder 再算一遍**。两条独立路径给出同一个最小值，才算对拍成功。

---

## 5. 手算 / 示例：`route_instance` 的 24 个编码

### 5.1 输入

| Job | 工序链 | `ri` | 工序 | `p` | 合格机器 |
|---|---|---|---:|---:|---|
| J0 | A → B | 2 | A | 3 | `M0` |
| J0 | A → B | 2 | B | 2 | `M0`, `M1` |
| J1 | C | 0 | C | 1 | `M0`, `M1` |

### 5.2 三条已由测试固定的轨迹

```text
order = ABC，assign = A:M0  B:M1  C:M0
  扫描 ABC：A 的前驱为空 -> 先排 A
    A: start = max(M0 ready 0, 0, r(J0)=2) = 2   -> M0 [2,5)
  接着 B：前驱 A 已排定
    B: start = max(M1 ready 0, end(A)=5, r(J0)=2) = 5 -> M1 [5,7)
  最后 C：
    C: start = max(M0 ready 5, 0, r(J1)=0) = 5 -> M0 [5,6)

order = BCA，assign = A:M0  B:M1  C:M0
  扫描 BCA：B 的前驱 A 还没排定 -> 跳过 B；C 的前驱为空 -> 先排 C
    C: start = max(M0 ready 0, 0, 0) = 0 -> M0 [0,1)
  回头排 A：
    A: start = max(M0 ready 1, 0, 2) = 2 -> M0 [2,5)
  最后 B：
    B: start = max(M1 ready 0, end(A)=5, 2) = 5 -> M1 [5,7)

order = BCA，assign = A:M0  B:M0  C:M1
  C 改到 M1：C -> M1 [0,1)；A -> M0 [2,5)；B -> M0 [5,7)
```

三条轨迹说明两件事：

1. **`order` 是优先级，不是时间顺序。** BCA 里的 B 排在第一位，却**最后一个**被加工——因为它必须等 A。
2. **`start` 取三个量的最大值**：机器什么时候空、前驱什么时候完工、作业什么时候释放。三者缺一不可。

### 5.3 表示冗余：24 个编码 → 12 个不同排程

这个实例的编码总数是 `3! × 1 × 2 × 2 = 24`（A 只有一种机器，B、C 各两种）。把 24 个编码全部解码后去重，只剩 **12 个不同 `Schedule`**。

最干净的一对：

```text
Candidate 1: order=(B, C, A)，assignments=(M0, M1, M0)
Candidate 2: order=(C, B, A)，assignments=(M0, M1, M0)

两个 Candidate 不相等（order 不同）
但 decode 结果完全相等：C:M0[0,1)  A:M0[2,5)  B:M1[5,7)
```

**原因**：解码器每一步只找「第一道前驱已排定的工序」。在 BCA 里 B 会被跳过，实际构造顺序是 C → A → B；在 CBA 里 C 先被排，B 依然被跳过，构造顺序还是 C → A → B。**两个优先级排列被解码器折叠成了同一个构造顺序。**

这条冗余有三个后果，必须记清：

1. **搜索空间 ≠ 可行时间表的数量。** 「我枚举了 24 个解」不等于「我考察了 24 种排程」。
2. **在编码空间均匀抽样（Random Search、SA 的随机移动）不等于在时间表空间均匀抽样。** 某些时间表被多个编码指向，被抽中的概率天然更高。
3. 这是**模型与实现边界**，不是 bug。要消除它需要更紧的表示（例如直接以构造顺序为编码），那会牺牲邻域移动的表达力。**Week 2 的选择是显式接受冗余**。

### 5.4 追加式解码：不填已有空隙

```text
order = ABC，assign 全为 M0
  A: start = max(0, 0, 2) = 2 -> M0 [2,5)      ← M0 在 [0,2) 全程空转
  B: start = max(5, 5, 2) = 5 -> M0 [5,7)
  C: start = max(7, 0, 0) = 7 -> M0 [7,8)      ← C 的 r=0，本该可以更早
  Cmax = 8，ΣCj = max(5,7) + 8 = 7 + 8 = 15

order = CAB，assign 仍全为 M0
  C: start = max(0, 0, 0) = 0 -> M0 [0,1)
  A: start = max(1, 0, 2) = 2 -> M0 [2,5)
  B: start = max(5, 5, 2) = 5 -> M0 [5,7)
  Cmax = 7，ΣCj = max(5,7) + 1 = 8
```

对比表：

| 编码 | `M0` 时间轴 | `Cmax` | `ΣCj` |
|---|---|---:|---:|
| `ABC`（全 `M0`） | [2,5)A、[5,7)B、[7,8)C | 8 | 15 |
| `CAB`（全 `M0`） | [0,1)C、[2,5)A、[5,7)B | **7** | **8** |

**追加式解码（append-only）的定义**：按优先级列表逐道工序处理，每道工序排在「它被处理时」机器的可选时刻上；**已经过去的空闲区间不会再被打开**。

于是 `ABC` 里 [0,2) 这段空转被永久保留——尽管 C 的释放时间是 0、加工时间只有 1，完全放得进去。**这不是解码器「算错了」，而是它的语义选择**：`order` 是优先级，解码器不假装自己会重排。要利用这段空隙，只能靠**换一个编码**（`CAB`），也就是靠**搜索**。

> **结论**：追加式解码把「填空隙」的责任从解码器转移给了搜索。代价是解质量可能受损，收益是解码逻辑简单、确定、可验证。

---

## 6. 实现：三个模块的分工

### 6.1 `solution.py`：候选解与它的合法性

```python
@dataclass(frozen=True, slots=True)
class Candidate:
    order: tuple[str, ...]          # 所有工序 ID 的优先级排列，恰好各出现一次
    assignments: tuple[str, ...]    # 位置对应 instance.operations，不是 order
```

`validate_candidate` 三条检查：

```text
order 长度与集合必须与 instance.operations 的 id 集合完全一致  -> 否则 "order must contain every operation exactly once"
assignments 长度必须等于工序数                                -> 否则 "assignment length mismatch"
每台被指派的机器必须在对应工序的 eligible_machine_ids 里        -> 否则 "illegal assignment: <op> -> <machine>"
```

**`assignments` 的位置对齐关系是最容易出错的地方**：它对齐的是 `instance.operations`，不是 `order`。这样 `order` 怎么变都不需要动 `assignments`——Day 1 的练习里那个问题（「交换优先级时要不要一起交换机器指派」）的答案就是：**不要**，那会把两件事绑死。

### 6.2 `decoder.py`：一个有前置条件的构造过程

对应文件 [decoder.py](../../projects/01_scheduling_core/scheduling_algorithms/decoder.py)。

```python
predecessors = {
    oid: (job.operation_ids[i - 1] if i else None)
    for job in instance.jobs
    for i, oid in enumerate(job.operation_ids)
}
```

前驱是**按位置**定义的：链上第 i 道工序的前驱就是第 i−1 道。整个实例的前驱表在函数开头一次性建好。

主循环：

```python
while remaining:
    oid = next(oid for oid in remaining
               if predecessors[oid] is None or predecessors[oid] in ends)
    remaining.remove(oid)
    start = max(
        machine_ready[machine],
        ends[predecessor] if predecessor is not None else 0,
        jobs[op.job_id].release_time,
    )
```

三个要点：

1. **`next(...)` 不会抛 `StopIteration`**（第 8 节给证明），所以不需要默认值。
2. `machine_ready[machine]` 在 `r = 0` 时就是该机器已排任务的总加工量；`r > 0` 时它仍然只记录「机器空了没有」，释放时间由第三项单独管。
3. 复杂度：每步线性扫描 `remaining` 并 `remove`，总体约 O(n²)。M1 优先选择「可验证」而不是「增量高效」，增量评估留给后面的月份。

`initial_candidate` 是同一文件的另一半：`p` 降序 + 平局按 `op.id` 升序排优先级，再为每道工序贪心选 `(max(load, release), machine.id)` 最小的机器。它既是 Week 1 的 LPT 基线，也是 Week 3 所有搜索算法的**共享初始解**。

### 6.3 `schedule_validation.py`：独立验证器

对应文件 [schedule_validation.py](../../projects/01_scheduling_core/scheduling_core/schedule_validation.py)。

**验证器信任什么？** 只信任 `instance`，不信任排程的来源：

```text
不调用 decoder                -> 避免共用构造逻辑把同一处错误掩盖两次
不假设工序按时间排序           -> 每台机器自己按 start 排序后再查重叠
不依赖任何算法的内部状态       -> 换任何算法产出的 Schedule 都一视同仁
```

它检查九类问题（对应 4.3 节的九类破坏），其中两类值得单独说：

- **重叠检查用的是「历史最大结束时间」而不是「相邻区间比较」**：维护 `frontier = max(frontier, end)`，只要 `start < frontier` 就报重叠。这样「一个长区间包住多个短区间」这种相邻比较看不出来的情况也能被抓住。
- **时间区间是 `[start, end)`**：所以 [0,3) 与 [3,5) 相接是合法的。这一个约定同时决定了解析、生成、导出和验证的行为，写在契约里而不是散落在各处。

`schedule_errors` 返回诊断列表，`validate_schedule` 在有错误时抛 `ValueError("; ".join(errors))`。**先看诊断、再看异常**：调试时列表比异常信息更有用。

---

## 7. 实验：`m1w2d7_review`

对应脚本 [m1w2d7_review.py](../../projects/01_scheduling_core/examples/m1w2d7_review.py)，在项目目录下运行：

```bash
python examples/m1w2d7_review.py
```

脚本打印接口链与证据表，实机验证三条解码轨迹、统计编码冗余、对比追加式解码的两种编码，并现场制造一条 `precedence` 违规交给独立验证器。实际输出（节选）：

```text
== 1. 固定接口链 ==
Instance -> Candidate -> decode -> Schedule -> validate_schedule -> objective
  Instance / Candidate / Schedule 都是 frozen dataclass + tuple，不可变
  邻域只返回新 Candidate；每次完整评价都必须走完这条链
  禁止：某个算法略过 validate_schedule，或私自使用另一套目标公式

== 2. 本周证据表 ==
  三类解表示/解码轨迹   test_three_decoder_traces     3 条编码 → 3 条精确时间轨迹
  swap/insert/指派与边界 test_moves_and_boundaries      交换两次复原、越界与非法资格
  至少五类非法排程       test_independent_validator_corruption  实际覆盖 9 类破坏
  可复现输入、CSV/JSON   test_roundtrip_and_csv         JSON 往返 + CSV 三表读取
  至少五个小例枚举       test_five_independent_enumerations  5 个种子 × 384 组合

== 3. 三条解码轨迹（test_three_decoder_traces）==
  order=A/B/C      assign=M0/M1/M0     -> A:M0[2,5)  B:M1[5,7)  C:M0[5,6)
  order=B/C/A      assign=M0/M1/M0     -> C:M0[0,1)  A:M0[2,5)  B:M1[5,7)
  order=B/C/A      assign=M0/M0/M1     -> C:M1[0,1)  A:M0[2,5)  B:M0[5,7)
```

冗余与追加解码两节：

```text
== 4. 表示冗余：不同 Candidate 解码到同一个 Schedule ==
  编码总数 24，解码后不同排程 12 个
  ('B', 'C', 'A') vs ('C', 'B', 'A')：Candidate 相等？False
  decode 结果相等？True
  两个排程：C:M0[0,1)  A:M0[2,5)  B:M1[5,7)

== 5. 追加解码的限制：不填已有空隙 ==
  order=ABC  A:M0[2,5)  B:M0[5,7)  C:M0[7,8)
  order=CAB  C:M0[0,1)  A:M0[2,5)  B:M0[5,7)
  order=ABC：ΣCj=15, Cmax=8；M0 在 [0,2) 全程空转
  order=CAB：ΣCj=8, Cmax=7；C(r=0) 被追加解码拒绝提前填隙

== 6. 独立校验器与已知局限 ==
  人为制造 precedence 违规 -> ['precedence: A -> B']
```

**实验观察**（全部来自上面的真实输出）：

1. 24 个编码折叠成 12 个排程，**冗余率正好一半**——但要注意这是这一个实例上的数字，不能外推成「冗余率总是 50%」。
2. 同一个 `Schedule` 可以由 `(B,C,A)` 和 `(C,B,A)` 两个不同编码产生，直接验证了「搜索空间不等于时间表空间」。
3. 追加式解码在 `order=ABC` 下让 `ΣCj` 从 8 涨到 15，几乎翻倍；而解码器本身没有任何错误——**代价来自编码，不来自解码**。
4. 独立验证器对人为制造的 precedence 违规给出了类别名 `precedence: A -> B`，而不是笼统的「不可行」。

复跑测试（在项目目录下运行）：

```bash
python -m pytest tests/test_month1.py -k 'decoder or moves or corruption or roundtrip or enumeration' -v
```

---

## 8. 数学补充：作业链 DAG 与环检测

### 8.1 当前结构是一个「不相交路径的并集」

把每道工序看成一个节点，把「前驱 → 后继」看成有向边。当前模型的 precedence 结构是：

```text
J0: A ──> B ──> C          （一条链）
J1: D ──> E                （另一条链）
```

它是由若干条**简单路径**组成的有向图。**理论结论：这样的图不可能有环。** 证明用三步：

1. `validate_instance` 要求每个 Job 的 `operation_ids` 内部**无重复**（`duplicate operation ids`）。
2. 它还要求所有 `Operation.id` **全局唯一**（`duplicate operation ids`），并要求 `operation.job_id == job.id`，所以每道工序**只属于一条链**。
3. 链上的前驱是按位置取的（第 i 位的前驱是第 i−1 位），边只能从小下标指向大下标。一个「下标严格递增」的有向图不可能有环。

顺带得到一个有用的推论：

> **`decode` 主循环里的 `next(...)` 永远不会失败。**

因为 `remaining` 非空时，取任意一条链上**还没被排定的最靠前的那道工序**，它的前驱要么不存在、要么已经在 `ends` 里。所以「第一道前驱已排定的工序」必然存在。这解释了为什么代码里 `next(...)` 没有默认值也不会抛异常。

### 8.2 换掉前提就必须补的东西

把前提改一个字，上面的结论立刻失效：

```text
现在的 precedence：按位置推导的链内前驱（单入边、单出边）
未来的 precedence：任意边集合 (u, v)
```

任意边集合会出现三类新问题：

| 新问题 | 例子 | 必须新增的能力 |
|---|---|---|
| **有环** | A→B→C→A | **环检测**，并在建图时直接拒绝 |
| **多入边** | A→C 且 B→C | 前驱必须是「一组」而不是「一个」，`max(...)` 要改成对集合取最大 |
| **多出边** | A→B 且 A→C | `decode` 的「后续工序等待前驱」逻辑不变，但作业完成时间要重新定义 |

**关键认识**：当前结构合法，**不意味着未来任意图都合法**。这正是复盘日要写下来的东西——不是要现在去实现环检测，而是要知道「这个简化假设在哪一行被用到了」，将来改模型时不会漏。

同类问题还有一处：Week 1 Day 7 记过的「字符串 ID 的字典序不等于自然数字序」（`J1, J10, J2`）。当前所有平局决胜都用字符串序，Month 1 只要求确定性，所以它是可接受的；一旦业务要求自然序，就必须引入 `sequence_index`。

### 8.3 自测

**问：解码器已经保证产出可行解，为什么还要独立验证？**

答：因为「保证」只是当前实现的主张，不是独立证据。独立模块能在**实现写错**时发现错误；同时它还能验证**从外部导入**的排程（它们不是解码器产生的）。这与「手算 expected 不能由被测函数生成」是同一个思想：**不能让 decoder 自己证明自己。**

**问：所有测试通过，是否说明算法最优？**

答：不。测试通过说明**实现符合预期、排程可行、结果可复现**；这些是**正确性**问题。而「解有多好」是**解质量**问题——它需要下界、精确求解或对手比较才能回答。正确性和解质量是两种问题，不能用同一个结论覆盖。

---

## 9. 已知局限：本周还没有做什么

四条边界（**必须与「已完成的证据」分开写**）：

| 局限 | 具体表现 | 为什么不能靠更多同分布测试消除 |
|---|---|---|
| 优先级表示有冗余 | 24 个编码 → 12 个排程（第 5 节） | 这是**表示的选择**，测试再多也不会变少；要么改表示，要么显式接受 |
| 追加解码不填空隙 | `order=ABC` 的 [0,2) 空转只能靠换编码消除 | 这是**解码语义的选择**；修它要改解码器，不是加测试 |
| 生成器默认全机器资格 | `generate_instance` 给每道工序全部机器 | 资格受限的实例**根本不在生成分布里**；只能手工构造（见 `test_invalid_inputs_and_rule_eligibility`） |
| Oracle 只能证明单工序极小实例 | 多工序输入直接 `ValueError`，组合数超过 100000 也拒绝 | 这是**枚举的成本边界**；`4! × 2^4 = 384` 可以，`8! × 2^8 ≈ 10^7` 不行 |

还要明确写上「这周没做，也不打算在这周做」的东西：

```text
没有换型时间（setup）、维护日历、工人容量
没有抢占（preemption）、没有批量（batching）
没有随机加工时间、没有动态到达
没有增量评估、没有多进程并行实验框架
```

这些不是缺陷，而是**分阶段推进**：先把「表示 + 解码 + 验证 + 对拍」做可信，后面的搜索算法才有公平的落脚点。现在急着上 SA 或 MILP，最大的问题是「排程不可信，好坏无从判断」。

---

## 10. 遗留问题（Open Questions）

| # | 问题 | 状态 |
|---:|---|---|
| 1 | 候选解与 Schedule 如何分离？ | 已由 `solution.py` 的 `Candidate` 落地 |
| 2 | 解码器保证可行，还是验证器负责发现错误？ | **两者独立**：`decoder.py` 构造，`schedule_validation.py` 独立检查 |
| 3 | 有释放时间时，静态排列如何解码？ | `start = max(machine_ready, predecessor_end, release)`（第 6.2 节） |
| 4 | 并行机排列是否足以表示机器指派？ | **不足**，所以 `Candidate` 同时含 `order` 与 `assignments` |
| 5 | 邻域如何保证不制造非法解？ | `neighborhoods.py` 只产生新 `Candidate`，由 `validate_candidate` 把关 |
| 6 | 如何做小规模枚举对拍？ | `oracle.py` 独立穷举；`test_five_independent_enumerations` 覆盖 5 个种子 |
| 7 | 随机实例从哪来？ | `scheduling_io/generator.py`，用局部 `Random(seed)`，不改全局随机状态 |
| 8 | 表示冗余会让搜索结果不可比吗？ | 目前只影响「抽样分布」，不影响可行性；**Week 3 起用统一评价预算把可比性钉在成本上** |

第 8 条是本周与下周的接缝：**下周（Week 3）会统一 `SearchConfig` / `SearchResult` 与完整评价计数，把「运行几轮」正式换算成可比较的计算预算。** 那个「一次评价」里包含的正是今天这条链上的三步——所以今天把链接死，下周才有账可算。

---

## 11. 今日练习

1. **练习 1（复述）**：不看笔记写出接口链的五个环节，并给每一环写一句「如果省掉它会怎样」。
2. **练习 2（手算）**：对 `route_instance` 的编码 `order=CBA, assign=A:M0 B:M1 C:M0`，独立推出每条工序的机器与起止时刻，再与脚本第 4 节的输出对照。
3. **练习 3（冗余）**：在同一个实例上再找一对不同的 `Candidate`，使它们解码出同一个 `Schedule`（提示：试着让 `order` 里出现「前驱在后、后继在前」的相邻对）。
4. **练习 4（验证器）**：不用 `decoder`，手工构造一个含**机器重叠**、但每条工序的时长为正且机器合法的 `Schedule`，解释验证器为什么仍然拒绝它。
5. **练习 5（数学）**：把某个 Job 的 `operation_ids` 改成 `("A", "B", "A")`，指出 `validate_instance` 会在哪一行拒绝；再说明如果允许重复 ID，第 8 节的「不可能有环」证明会在哪一步失效。

---

## 12. 验收清单（Week 2 Exit Checklist）

**表示**

- [ ] 能写出 `Candidate` 的两个字段，并说明 `assignments` 对齐的是 `instance.operations`。
- [ ] 能解释为什么输入与候选都必须不可变，邻域为什么只返回新对象。
- [ ] 能用 `(B,C,A)` 与 `(C,B,A)` 这一对说明「表示冗余」。

**解码**

- [ ] 能写出 `start = max(machine_ready, predecessor_end, release)` 三项的来源。
- [ ] 能解释 `order` 是优先级而不是时间顺序，并推出三条测试轨迹。
- [ ] 能说明追加式解码为什么不会填空隙，以及代价由谁承担。

**验证**

- [ ] 能说出独立验证器「不信任什么」，并能复述九类破坏中的至少五类。
- [ ] 能解释 `[start, end)` 区间约定与「历史最大结束时间」查重叠的做法。
- [ ] 能用有向无环图论证当前结构不可能有环，并说出换任意边集时必须补环检测。

**测试与证据**

- [ ] 能把 Week 2 的五项要求分别对到 `test_three_decoder_traces`、`test_moves_and_boundaries`、`test_independent_validator_corruption`、`test_roundtrip_and_csv`、`test_five_independent_enumerations`。
- [ ] 在项目目录下运行 `python examples/m1w2d7_review.py` 无报错，输出与第 7 节一致。
- [ ] 在项目目录下运行 `python -m pytest tests/test_month1.py -k 'decoder or moves or corruption or roundtrip or enumeration' -v` 全部通过。

---

## 13. 自测题

不看上文回答：

- Q1：写出本周固定的接口链，并说明「一次完整评价」包含哪些步骤。
- Q2：`Candidate.assignments` 的位置对齐的是 `order` 还是 `instance.operations`？
- Q3：什么叫表示冗余？举一个本周实例上的具体例子。
- Q4：追加式（append-only）解码的定义是什么？它为什么会让 `ΣCj` 变差？
- Q5：`decode` 的 `start` 为什么必须取三个量的最大值？三项分别是什么？
- Q6：独立验证器与输入验证器分别检查什么？为什么不能合并成一个？
- Q7：为什么说「24 个编码 → 12 个排程」意味着搜索空间不能等同于时间表数量？
- Q8：随机生成器默认给每道工序全部机器资格，这个默认值在什么情况下会成为实验的盲区？
- Q9：Oracle 能证明什么？为什么它拒绝多工序输入，也拒绝超过 100000 个组合？
- Q10：为什么当前作业链结构不可能出现环？换成任意 precedence 边集后必须新增什么？

### 参考答案

- A1：`Instance → Candidate → decode → Schedule → validate_schedule → objective`。一次完整评价 = `decode` + `validate_schedule` + `objective` 三步，任何算法都不得省略或替换其中任何一步。
- A2：对齐 `instance.operations`，与 `order` 无关。这样改变优先级时不需要同步改动机器指派。
- A3：两个不同的 `Candidate` 解码到同一个 `Schedule`。例子：`order=(B,C,A), assignments=(M0,M1,M0)` 与 `order=(C,B,A), assignments=(M0,M1,M0)`，解码结果都是 `C:M0[0,1) A:M0[2,5) B:M1[5,7)`。
- A4：按优先级列表逐道追加，每道工序只排在「它被处理时」机器可用的时刻，**不回头填已经过去的空闲区间**。当优先级第一位的工序被释放时间挡住时，机器在开头空转，后面的工序无法提前，于是每个 job 的完工时间整体后移，`ΣCj` 变差。
- A5：`start = max(machine_ready[machine], ends[predecessor], job.release_time)`。三项分别是「机器何时空出」「前驱何时完工」「作业何时释放」，任何一个都可能成为下界。
- A6：输入验证器（`validate_instance`）检查**问题数据**是否合法：ID 唯一、引用完整、`p > 0`、`weight` 有限且为正、`r >= 0` 等。独立验证器（`validate_schedule`）检查**求解结果**是否可行：机器不重叠、precedence、合法指派、工序缺失或重复、释放时间与时长。两者对象不同，合并会让「数据错」和「结果错」混在一起。
- A7：因为多个编码指向同一个排程，所以「扫描了多少个解」与「考察了多少种不同的时间表」不是一回事；在编码空间均匀抽样不等于在时间表空间均匀抽样。
- A8：当问题**本身**存在资格限制（某道工序只能上部分机器）时。这类实例不在生成分布里，只能手工构造，因此与 `generate_instance` 相关的实验结论不能推广到资格受限场景。
- A9：它能在**单工序、极小实例**上遍历全部「排列 × 指派」组合，给出**可证明的全局最优值**（`下限 = 上限`）。拒绝多工序是因为它的枚举模型只有一道工序一层；拒绝超 100000 组合是为了避免阶乘爆炸（`8! × 2^8` 已经超过一千万）。
- A10：因为 `validate_instance` 要求链内 `operation_ids` 无重复、要求 `Operation.id` 全局唯一且 `operation.job_id == job.id`，所以每道工序只属于一条链，而链上的边只能从小下标指向大下标——严格递增的图不可能有环。换成任意边集后必须新增**环检测**，并处理多入边（前驱成一集合）与多出边（作业完成时间的定义）。

---

## 14. 今日一句话总结

> **Week 2 的真正成果不是多了一个解码器或验证器，而是把「输入不可变、邻域返回新对象、每次评价都要走完整链路」钉成了契约；同时诚实地记下四条边界——表示有冗余、追加解码不填空隙、生成器只有全资格实例、Oracle 只能证明单工序极小实例——下周的搜索算法才有可比的成本账本和可信的落脚点。**
