# Day 1：候选解表示与接口约定

> 当日主题：区分 Instance、Candidate、Schedule，定下搜索层的第一套接口
> 当日产出：**Candidate 表示与 `validate_candidate` 校验**（`solution.py` + 实验脚本）
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 说清楚 Instance、Candidate、Schedule 三种对象各自的角色，以及为什么不能合并成两种。
2. 解释为什么搜索算法不应该直接修改 Schedule 里的 `start_time` / `end_time`。
3. 写出 `Candidate(order, assignments)` 的定义，并说出它为什么是 frozen dataclass。
4. 说清 `order` 与 `assignments` 的对齐关系：前者是工序 ID 的排列，后者按 `instance.operations` 的位置对齐。
5. 理解 `order` 是**优先级列表**而不是拓扑序，并解释 decoder 为什么能容忍「后继排在前面」。
6. 手算三条编码例子，写出每道工序的机器与开始/结束时刻。
7. 用「不同 `order` → 同一个 Schedule」举出表示冗余（representation redundancy）的例子，并会数冗余倍数。
8. 说出 `validate_candidate` 拒绝的五类坏候选解，以及为什么不在邻域里偷偷修复它们。

---

## 2. 为什么 Day 1 要引入第三种对象

Week 1 的流水线是「输入直接进规则、规则直接出排程」：

```text
JSON → Parser → Instance → Validator → 可信输入
                                     ↓
                              Rules → Schedule → Objective → 数字
```

这条流水线只服务一件事：**给定一个实例，一次性产出一个答案**。从今天起要接上搜索，它需要反复试探同一个实例的许多个「中间决策」，于是流水线多出一环：

```text
                                        可信输入
                                            ↓
                              Candidate → decode → Schedule → Objective → 数字
                                  ↑                                     ↑
                            今天新增的一环                       Week 1 已经有的环节
```

三个理由说明为什么必须有 Candidate：

1. **规则只有一个决策点，搜索有很多个。** SPT/EDD/WSPT 是「排完序就结束」，而 swap、insert、reassign 这些移动作用的对象不是 Schedule，而是「决策本身」。必须先把决策抽出来，才谈得上「在决策空间中移动」。
2. **时间戳是算出来的，不是改出来的。** `Schedule` 里只有 `start_time` / `end_time` 两个数字。如果搜索直接去改 B 的开始时间，很可能就违反了「B 不早于 A 完工」「B 不早于作业释放时间」这两条约束。让时间由决策**重新推导**，比让搜索**直接改写**安全得多。
3. **搜索需要一个可比较、可去重、可复制的对象。** 邻域要判断「这个邻居是不是已经见过」，`Candidate` 用 frozen dataclass + `tuple` 实现，天生可哈希、可相等比较、可放进 `set`。

一句话：**Instance 是「不许变的问题」，Schedule 是「算出来的答案」，Candidate 是「可以反复试探的决策」。**

---

## 3. 三种对象的分工

| 对象 | 所在层 | 可变性 | 谁产生 | 谁消费 |
|---|---|---|---|---|
| `Instance` | 输入模型 | 不可变 | Parser / generator | 所有算法 |
| `Candidate` | 决策层 | 不可变 | 构造式启发式 / 邻域算子 | `decode`、`validate_candidate` |
| `Schedule` | 结果层 | 不可变 | `decode` | objective、`validate_schedule`、Gantt 导出 |

三者的字段对照：

| 对象 | 字段 |
|---|---|
| `Instance` | `jobs` / `operations` / `machines` |
| `Candidate` | `order`（工序 ID 的排列）+ `assignments`（机器 ID 序列） |
| `Schedule` | `operations`（`ScheduledOperation` 元组，每项含 `operation_id` / `machine_id` / `start_time` / `end_time`） |

注意三者都**不可变**。这看起来矛盾——搜索难道不需要「变」吗？搜索的「变」体现为**不断产生新的对象**：邻域算子读一个 `Candidate`，产出一个新的 `Candidate`，原来的那个原封不动。这和 Day 5 里「`machine_ready` 必须是算法内部局部字典、不能塞进输入 `Machine`」是同一条原则。

时间只有 `decode` 一处产生，所以「时间对不对」只需要审一个函数；决策只有 `Candidate` 一处表达，所以「决策变没变」只需要比一个元组。**把变化集中到一个最小的对象上，是这一周所有接口设计的出发点。**

### 3.1 决策的粒度：为什么是「排列 + 指派」而不是别的

`Candidate` 的两个字段正好对应并行机调度的两类决策：

```text
sequencing   谁先做      → order
assignment   在哪台做    → assignments
```

Week 1 第 5 天已经论证过 `P||Cmax` 的决策「排序 + 选机，缺一不可」；`Candidate` 就是把那句话直接落成两个字段。**注意它不包含时间**：时间是这两类决策的**后果**，一旦存进 `Candidate`，就会出现「决策说 B 在 M1 而时间是 M0 的时刻」这种自相矛盾的对象。

### 3.2 本周后面六天都在围绕 `Candidate` 展开

```text
Day 2  Candidate → Schedule          把决策变成时间（decode）
Day 3  Candidate → Candidate         在决策空间里移动（swap / insert / reassign）
Day 4  Schedule  → 诊断列表           不信任任何算法输出的独立检查
Day 5  Param     → Instance          可复现地造出更多输入
Day 6  Instance  → optimum           极小实例的独立枚举对拍
Day 7  全链路复盘                     固定接口与已知局限
```

今天定下的接口一旦松动（例如允许 `Candidate` 携带时间、或允许 `order` 缺工序），后面六天全部要跟着改。**所以今天花在「把接口压到最小」上的时间，是本周最划算的投入。**

---

## 4. Candidate 的定义与三条不变量

定义见 [solution.py](../../projects/01_scheduling_core/scheduling_core/solution.py)：

```python
@dataclass(frozen=True, slots=True)
class Candidate:
    order: tuple[str, ...]
    assignments: tuple[str, ...]
```

```python
Candidate(order=("A", "B", "C"), assignments=("M0", "M1", "M0"))
```

`order` 是所有工序 ID 的优先级排列，必须恰好出现一次；`assignments` 的位置始终对应 `instance.operations`，**不是** `order` 的位置。`frozen=True` 保证邻域操作不会意外修改父解，`slots=True` 让对象更小，`tuple` 而非 `list` 保证可哈希。

### 4.1 三条不变量

`validate_candidate` 检查三件事：

```python
def validate_candidate(instance: Instance, candidate: Candidate) -> None:
    ids = {op.id for op in instance.operations}
    if len(candidate.order) != len(ids) or set(candidate.order) != ids:
        raise ValueError("order must contain every operation exactly once")
    if len(candidate.assignments) != len(instance.operations):
        raise ValueError("assignment length mismatch")
    for op, machine in zip(instance.operations, candidate.assignments, strict=True):
        if machine not in op.eligible_machine_ids:
            raise ValueError(f"illegal assignment: {op.id} -> {machine}")
```

| 不变量 | 检查方式 | 违反后的后果 |
|---|---|---|
| `order` 恰好含每道工序一次 | 长度比较 + `set` 比较 | 工序被漏排或重复排，解码结果不完整 |
| `assignments` 长度 = `len(instance.operations)` | 长度比较 | 指派与工序错位，`zip` 静默截断 |
| 指派机器在 `eligible_machine_ids` 里 | 逐项 `in` 检查 | 产出「在不合格机器上加工」的非法排程 |

三点补充：

- **`len(...)` 与 `set(...)` 必须同时比。** 只比 `set` 会漏掉「`order` 长度不对但集合相同」的重复情形（例如 `("A","B","C","C")`）。
- **「不合格机器」是输入约束，不是算法决策。** `eligible_machine_ids` 在 `Operation` 上（Day 5 第 6 节），`assignments` 只是「挑了哪一台」，挑错了就是违反约束。
- **坏输入要当场报错，不要偷偷修复。** 如果邻域算子遇到坏候选就「顺便修一下」，错误会被埋进搜索过程，最后表现为「结果莫名其妙变差」，极难定位。宁可抛 `ValueError`。

### 4.2 `order` 是优先级列表，不是拓扑序

这是今天最容易误解的一点。

> **`order` 只承诺「谁更优先」，不承诺「谁在时间上前」。**

例子：`order = ("B", "C", "A")`，其中 A 是 B 的前驱。B 排在第一位，看起来「B 应该先做」，但 B 必须等 A 完工，所以实际构造顺序是 C → A → B（见第 5 节编码 2）。decoder 扫描时**跳过前驱尚未排定的工序**，所以「前驱排在后面」不是错误，只表示「这道工序的优先级暂时无效」。

这样设计的好处：`order` 永远是一个干净的排列（只要是 ID 的全排列就合法），不需要额外检查它是不是拓扑序。代价是**表示冗余**：不同的 `order` 可能给出同一个 Schedule。这一点在第 5.4 节量化。

---

## 5. 手算：三条编码的时间线

用与 Week 1 连续性实例同构的两作业三工序输入：

| 工序 | 所属 Job | `pj` | Job 的 `rj` | `eligible_machine_ids` |
|---|---|---:|---:|---|
| A | J0 | 3 | 2 | `("M0",)` |
| B | J0 | 2 | 2 | `("M0", "M1")` |
| C | J1 | 1 | 0 | `("M0", "M1")` |

注意 `release_time` 是**作业级**字段，J0 的 `r=2` 对 A、B 同时生效。`instance.operations` 的顺序是 `(A, B, C)`，这决定了 `assignments` 的位置语义。

### 5.1 编码 1：`ABC` / `M0,M1,M0`

```text
t=0   M0、M1 都空闲，但 A 的作业在 t=2 才释放 → 不能开工
t=2   A 指派 M0：start = max(machine_ready[M0]=0, 无前驱=0, r=2) = 2，end = 2+3 = 5
t=5   B 的前驱 A 已完工；B 指派 M1：start = max(0, end(A)=5, r=2) = 5，end = 7
t=5   C 指派 M0：start = max(machine_ready[M0]=5, 无前驱=0, r=0) = 5，end = 6
```

```text
M0: A[2,5)  C[5,6)      空闲 [0,2)
M1: B[5,7)              空闲 [0,5)
```

### 5.2 编码 2：`BCA` / `M0,M1,M0`

```text
t=0   order 第一位是 B，但前驱 A 尚未排定 → 跳过 B
t=0   下一位 C 无前驱 → C 指派 M0：start = max(0, 0, 0) = 0，end = 1
t=1   剩下 B、A；B 仍不可行 → 跳过；A 被选中
      A 的作业 r=2，此刻 t=1 → start = max(machine_ready[M0]=1, 0, 2) = 2，end = 5
t=5   B 指派 M1：start = max(machine_ready[M1]=0, end(A)=5, 2) = 5，end = 7
```

```text
M0: C[0,1)  A[2,5)      空闲 [1,2)
M1: B[5,7)              空闲 [0,5)
```

A 被 t=1 选中却仍从 2 开工，这是「释放时间不是改优先级，而是限制开工时刻」的第二次出现（第一次见 Day 4 第 5 节）。

### 5.3 编码 3：`BCA` / `M0,M0,M1`

只改了 `assignments`：B 从 M1 挪到 M0，C 从 M0 挪到 M1。

```text
t=0   B 跳过；C 指派 M1：start = max(0, 0, 0) = 0，end = 1
t=2   A 指派 M0：start = max(machine_ready[M0]=0, 0, 2) = 2，end = 5
t=5   B 指派 M0：start = max(machine_ready[M0]=5, end(A)=5, 2) = 5，end = 7
```

```text
M0: A[2,5)  B[5,7)      空闲 [0,2)
M1: C[0,1)              无空闲
```

### 5.4 对比表

`ΣCj` 是**作业级**指标，`Cj` 取该作业最后完工的工序：

| 编码 | 构造顺序 | A | B | C | `Cmax` | `ΣCj` |
|---|---|---|---|---|---|---|
| `ABC` / `M0,M1,M0` | A,B,C | M0[2,5) | M1[5,7) | M0[5,6) | 7 | 13 |
| `BCA` / `M0,M1,M0` | C,A,B | M0[2,5) | M1[5,7) | M0[0,1) | 7 | **8** |
| `BCA` / `M0,M0,M1` | C,A,B | M0[2,5) | M0[5,7) | M1[0,1) | 7 | **8** |

```text
编码 1：C_J0 = max(end(A), end(B)) = max(5, 7) = 7；C_J1 = end(C) = 6
        ΣCj = 7 + 6 = 13
编码 2：C_J0 = max(5, 7) = 7；C_J1 = 1
        ΣCj = 7 + 1 = 8        （比编码 1 少 5，全部来自 C 提前完工）
编码 3：C_J0 = max(5, 7) = 7；C_J1 = 1
        ΣCj = 7 + 1 = 8
```

**结论**：三个编码的 `Cmax` 都是 7（总工作量 6，最长链 A→B 占 5），差别全在 `ΣCj` 上。编码 2 与编码 3 的 `ΣCj` 相同，但 C 的机器不同——**同一个目标值可以由不同的排程达到**，这也是「目标不是排程的唯一描述」的一个小例子。

顺带记住编码 1 的画面：`M0` 在 `[0,2)` 是空的，而 C 明明指派在 M0 却没有被塞进去。这是 decoder 的 **append-only** 行为，Day 2 第 6 节专门讲。

### 5.5 表示冗余：24 个候选解只有 12 个不同 Schedule

固定 A 只能上 M0，B、C 各有两台资格，于是：

```text
order         : 3! = 6 种
assignments   : 1 × 2 × 2 = 4 种（A 必须 M0；B、C 各两种）
合法候选解总数 = 6 × 4 = 24
```

把 24 个候选解全部解码，去重后只有 **12 个不同的 Schedule**。两个具体的冗余对：

```text
(A,B,C)/(M0,M1,M0)  与  (B,A,C)/(M0,M1,M0)   → 同一个 Schedule
(B,C,A)/(M0,M1,M0)  与  (C,A,B)/(M0,M1,M0)   → 同一个 Schedule
```

原因很直白：B 的优先级再高也要等 A，所以 `ABC` 和 `BAC` 的实际构造顺序都是 A,B,C；而 `BCA`、`CBA`、`CAB` 三种都先挑中无前驱的 C。

> **表示冗余的直接后果：搜索空间的「候选解个数」不能直接当作「不同可行时间表个数」。** 统计评价次数、计算去重率时，必须先解码再比较，不能只比较 `Candidate`。

### 5.6 决策空间大小的公式

对单工序、每道工序可选 `m` 台机器的实例，决策空间的规模有一个干净的公式：

```text
候选解个数 = n!  ×  Π|eligible_machine_ids(op)|
             ↑      ↑
          排列数      每道工序的资格数乘积

本实例：3! × (1 × 2 × 2) = 6 × 4 = 24        与脚本输出一致
不同 Schedule = 12                            需要解码去重才能得到
```

**结论**：`n!` 只描述 `order` 的自由度；`assignments` 的贡献是「资格数连乘」。Week 1 第 6 天枚举 384 个组合用的就是这条公式（`4! × 2^4 = 24 × 16 = 384`），只是那时还没有 `Candidate` 这个显式对象。两条线索到这里合上了。

---

## 6. 实现：`solution.py`

对应文件 [solution.py](../../projects/01_scheduling_core/scheduling_core/solution.py)，整个文件只有 22 行，是刻意压到最小的：

```python
"""候选解的不可变表示与合法性校验；不负责解码或搜索。"""

@dataclass(frozen=True, slots=True)
class Candidate:
    order: tuple[str, ...]
    assignments: tuple[str, ...]
```

三个设计点：

1. **只存决策，不存时间。** `Candidate` 里没有 `start_time`，因为时间是 `decode` 的产物。这样「同一个 `Candidate` 永远对应同一个 `Schedule`」是显然的，不需要额外一致性检查。
2. **`tuple` 而不是 `list`。** `Candidate` 要能放进 `set`（邻域去重）、能当 `dict` 的键（搜索的记忆表），`list` 不可哈希会立刻破坏这两件事。
3. **`validate_candidate` 与 `decode` 分开。** 校验是纯检查，不产出任何东西；`decode` 先校验 `Instance`、再校验 `Candidate`、最后才计算时间。分开写的好处是：邻域算子可以在**不付解码代价**的前提下先筛掉坏候选解。

`decode` 的第一件事就是调用 `validate_candidate`，所以任何算法只要走 `decode`，就自动获得这一层保护。细节留给 Day 2。

校验链的顺序是**先输入、后决策、再计算**：

```text
decode(instance, candidate)
  ├─ validate_instance(instance)      输入本身的合法性（Week 1 Day 3）
  ├─ validate_candidate(instance, candidate)   决策的合法性（今天）
  └─ 计算时间 → Schedule              从这里开始才可能产生新信息
```

这样安排的好处是：**任何一个坏对象都在它第一次被使用的地方立刻停下**，错误信息指向具体工序或具体机器，而不是等到最后 objective 给出一个奇怪的数字再回头猜。

注意 `validate_candidate` 的第一个参数是 `instance` 而不是 `candidate` 单独的检查——因为「机器是否合格」这条不变量必须对照输入才能判断。**校验函数需要什么就传什么，不要为了「看起来通用」而拆掉必要参数。**

---

## 7. 实验：`m1w2d1_candidate`

对应脚本 [m1w2d1_candidate.py](../../projects/01_scheduling_core/examples/m1w2d1_candidate.py)，在项目目录下运行：

```bash
python examples/m1w2d1_candidate.py
```

脚本做五件事：打印三个编码例子、验证「`order` 不是拓扑序」、验证表示冗余、验证 `assignments` 的对齐方向、验证 `validate_candidate` 的拒绝边界。实际输出：

```text
instance.operations 顺序 = ('A', 'B', 'C')
A 的资格 = ('M0',)  B 的资格 = ('M0', 'M1')  C 的资格 = ('M0', 'M1')

[1] 三个编码例子
- A->M0, B->M1, C->M0
  order=A,B,C  assignments=M0,M1,M0
    构造顺序 = ['A', 'B', 'C']
    A: M0[2,5)
    B: M1[5,7)
    C: M0[5,6)
- 只改优先级，指派不变
  order=B,C,A  assignments=M0,M1,M0
    构造顺序 = ['C', 'A', 'B']
    C: M0[0,1)
    A: M0[2,5)
    B: M1[5,7)
- B 改到 M0、C 改到 M1
  order=B,C,A  assignments=M0,M0,M1
    构造顺序 = ['C', 'A', 'B']
    C: M1[0,1)
    A: M0[2,5)
    B: M0[5,7)

[2] order 是优先级列表，不是拓扑序
  B 的前驱 A 排在 B 之后，order = ('B', 'C', 'A')
  decode 仍产出可行排程，构造顺序 = ['C', 'A', 'B']
  B 排在第一位，但 A 未排定前不会被选中，B 的 start = 5

[3] 表示冗余：不同 order 得到同一个 Schedule
  (A,B,C)/(M0,M1,M0) == (B,A,C)/(M0,M1,M0) ? True
  原因：B 的优先级再高也排在 A 之后，两者构造顺序都是 A,B,C
  (B,C,A)/(M0,M1,M0) == (C,A,B)/(M0,M1,M0) ? True
  合法候选解 = 24  不同 Schedule = 12

[4] assignments 对齐 instance.operations，不随 order 重排
  order         = ('C', 'A', 'B')
  assignments   = ('M0', 'M0', 'M1')
    A -> M0   （第 1 位）
    B -> M0   （第 2 位）
    C -> M1   （第 3 位）

[5] validate_candidate 的拒绝边界
  缺失工序     -> ValueError: order must contain every operation exactly once
  指派长度不符   -> ValueError: assignment length mismatch
  不合格机器    -> ValueError: illegal assignment: A -> M1
```

**实验结论**：

1. 三个编码的机器与时刻与第 5 节手算逐位一致，说明「表示 → 时间」这一步是可以离线预测的。
2. `order` 第一位的 B 在编码 2、3 中都最后一个完工于 M 上，`start = 5`——**优先级不等于时间顺序**。
3. 24 个合法候选解只对应 12 个不同 Schedule，**冗余倍数 2.0**；这提醒我们任何「搜索空间大小」的说法都要说明是在哪一个层面上数的。
4. 三个非法候选解分别命中三类不变量，错误信息里带上了具体工序与机器（`illegal assignment: A -> M1`），便于定位。

配套测试在项目目录下运行：

```bash
python -m pytest tests/test_month1.py -k 'decoder or moves' -v
```

三个精确解码轨迹测试（`test_three_decoder_traces`）加上 `test_moves_and_boundaries`，共 4 条，覆盖了今天定义的表示与边界。

---

## 8. 今日练习

1. **练习 1（手算）**：把编码 2 的 `assignments` 改成 `("M0", "M1", "M1")`，重新手算三条时间线，并算出 `ΣCj`。
2. **练习 2（表示冗余）**：在 A 只能上 M0、B 只能上 M1、C 有 M0/M1 两台资格时，数一数合法候选解个数与不同 Schedule 个数，看看冗余倍数变成多少。
3. **练习 3（不变量）**：构造一个 `order` 长度正确、集合正确、但含重复 ID 的候选解（例如 `("A","A","C")`），确认 `validate_candidate` 抛出的错误信息是什么。
4. **练习 4（接口设计）**：如果允许 `Candidate` 直接携带 `start_time`，举出至少两个会出问题的地方（提示：释放时间、机器不重叠、同一个候选解两种解释）。
5. **练习 5（代码阅读）**：不看 [solution.py](../../projects/01_scheduling_core/scheduling_core/solution.py)，自己写出 `validate_candidate` 的三条检查，再与实现对照，特别留意哪一条用了 `zip(..., strict=True)`。

---

## 9. 验收清单

- [ ] 能说出 Instance / Candidate / Schedule 三者的角色，以及为什么搜索不能直接改 `Schedule` 的时间戳。
- [ ] 能默写 `Candidate` 的两个字段，并解释 `frozen=True` 与 `slots=True` 各自的作用。
- [ ] 能说出 `assignments` 对齐的是 `instance.operations` 的位置，不是 `order` 的位置。
- [ ] 能解释「`order` 是优先级列表而不是拓扑序」，并给出 B 排第一仍不能先加工的例子。
- [ ] 能手算出三条编码每道工序的机器、开始时刻、结束时刻。
- [ ] 能举出两组「不同 `order` → 同一个 Schedule」的冗余例子，并说明 24 与 12 是怎么来的。
- [ ] 能列出 `validate_candidate` 拒绝的三类问题，并说明为什么不在邻域里默默修复。
- [ ] 知道坏候选解在 `decode` 入口会被自动拦截（`decode` 内部先调 `validate_candidate`）。
- [ ] `python examples/m1w2d1_candidate.py` 输出与第 5 节手算一致。
- [ ] `python -m pytest tests/test_month1.py -k 'decoder or moves' -q` 全部通过（4 条）。

---

## 10. 自测题

不看上文回答：

- Q1：为什么需要 Candidate，不能直接用 Schedule 做搜索？
- Q2：`Candidate.assignments` 的位置对应什么？对应 `order` 还是 `instance.operations`？
- Q3：`order` 是不是拓扑序？举一个「后继排在前面」的例子并说明结果。
- Q4：`validate_candidate` 检查哪三件事？
- Q5：为什么 `order` 的检查要同时比较长度和集合？
- Q6：什么是表示冗余？本文实例中 24 个候选解对应多少个不同 Schedule？
- Q7：为什么 `Candidate` 用 `tuple` 而不是 `list`？
- Q8：如果邻域算子遇到坏候选解，正确做法是什么？
- Q9：编码 1（`ABC` / `M0,M1,M0`）里 M0 的 `[0,2)` 为什么是空的？
- Q10：三个编码的 `Cmax` 分别是多少？为什么？

### 参考答案

- A1：因为搜索要反复试探「决策」而不是「结果」；直接改 Schedule 的时间戳会破坏释放时间与机器不重叠约束，而且时间本该由决策重新推导。
- A2：对应 `instance.operations` 的位置；与 `order` 无关。
- A3：不是拓扑序，只是优先级列表。例：`order=("B","C","A")` 而 A 是 B 的前驱，解码时 B 被跳过，实际构造顺序是 C → A → B。
- A4：① `order` 恰好含每道工序一次；② `assignments` 长度等于 `len(instance.operations)`；③ 每个指派机器属于该工序的 `eligible_machine_ids`。
- A5：只比集合会漏掉重复 ID（集合相同、长度不同）的情形。
- A6：不同 `order`/`assignments` 得到同一个 `Schedule`；本实例 24 个合法候选解对应 12 个不同 Schedule。
- A7：`tuple` 可哈希，能放进 `set`（邻域去重）、当 `dict` 键（记忆表）；`list` 不行。
- A8：当场抛 `ValueError`，不要默默修复——否则错误会被埋进搜索过程，最后表现为结果莫名变差。
- A9：A 所属作业 J0 的 `release_time = 2`，机器此刻空闲也不能开工；这是释放时间约束，不是排序问题。
- A10：都是 7。总工作量 `Σp = 3+2+1 = 6`，关键路径 A→B 占 5，`Σp` 才是下界来源；`Σp=6` 与 `Cmax=7` 的差来自释放时间造成的等待。

---

## 11. 今日一句话总结

> **搜索不该去改答案，而该去改决策；`Candidate(order, assignments)` 用两个元组承载全部决策，`order` 是优先级不是拓扑序，`assignments` 跟着 `instance.operations` 走——这三条约定是 Week 2 所有邻域与算法的公共地基。**
