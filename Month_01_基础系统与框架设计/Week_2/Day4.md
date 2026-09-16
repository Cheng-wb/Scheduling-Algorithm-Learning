# Day 4：独立排程验证器

> 当日主题：用一个不依赖 `decoder` 的独立验证器，把「求解器声称可行」变成「可复核的检查」
> 当日产出：**独立 `Schedule Validator` 的完整认识 + 九类破坏的诊断实验**（`schedule_validation.py` 解读 + 示例脚本）
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 说清楚「独立验证」独立在哪里：为什么不能调用 `decoder`，为什么不能信任工序列表的顺序。
2. 背出六项独立检查清单，并知道每一项对应哪一类错误。
3. 用 `[start,end)` 区间与 `frontier`（历史最大结束时间）手算出一台机器上的 `overlap`。
4. 解释为什么「只与相邻区间比较」不够，必须维护历史最大 `end`。
5. 手工构造九类破坏排程，并在运行前预测 `schedule_errors()` 会返回哪些诊断。
6. 区分 `schedule_errors`（返回诊断列表）与 `validate_schedule`（抛异常）的分工。
7. 说清楚「Objective 只算指标」，有效性由调用者负责。
8. 理解一个坏排程可能同时触发多条诊断，因此不能只检查第一条。

---

## 2. 为什么第 4 天要「独立验证」

前三天建立的流水线是这样一条链：

```text
Instance → Candidate → decode → Schedule → Objective → 数字
```

Day 1 定义了 `Candidate`（决策的表示），Day 2 用 `decode` 把它变成 `Schedule`（落到时间轴的结果），Day 3 的邻域不断产生新的 `Candidate`。到这里，「谁产生 `Schedule`」这个问题突然变得很多答案：规则、`decoder`、每一个邻居、每一个搜索算法、以及你手写的测试数据。

于是 Day 4 要接上的一环**不是链上的下一步，而是一条并行的分支**：

```text
Instance ──┬─→ Candidate ─→ decode ─→ Schedule ──┬─→ Objective ─→ 数字
           │                                     │
           └─────────────────────────────────────┴─→ Schedule Validator
                                                       ↓
                                                  诊断 / 异常
```

关键观察：**验证器与 Objective 是兄弟，不是父子。** 验证器只吃 `(Instance, Schedule)` 两个公开输入，不知道、也不关心这个 `Schedule` 是谁产生的。

为什么今天必须补上这一环？

1. **只有一个目标值，判断不出对错。** 把一条排程里最长的工序整条删掉，`Cmax` 会「变好」而不是变坏。目标函数只回答「多好」，从不回答「对不对」。
2. **`decoder` 不能给自己发合格证。** 如果验证的方式是「把 `Candidate` 再 `decode` 一次，看两次是否一致」，那么原始输出里的错误时间已经被新生成的排程覆盖掉了。这与 Week 1 手算测试坚持「`expected` 不由被测函数生成」是同一个原则：**不能让被测对象证明它自己。**
3. **搜索会放大错误。** 一个未被发现的非法排程会作为当前解留在搜索里，后续所有邻域都在一个不可行点上做局部改进，整条实验记录随之失效。

> **一句话：`Objective` 负责「多好」，`Validator` 负责「对不对」，两者都不能替对方签字。**

---

## 3. 验证器信任什么、不信任什么

**定义**：独立排程验证器是一个只接受 `(Instance, Schedule)` 两个参数、只依赖公开字段来判断可行性的函数，不读取任何算法内部状态。

对应文件 [schedule_validation.py](../../projects/01_scheduling_core/scheduling_core/schedule_validation.py)，模块 docstring 只有一行：

```text
独立验证结果，不调用 decoder，也不信任结果顺序。
```

这一行是四件具体的事：

| 不信任的对象 | 具体含义 | 如果违反了会怎样 |
|---|---|---|
| `decoder` | 验证过程不重新解码 `Candidate` | 检查的是新排程，不是被验证的那一份 |
| 列表顺序 | `Schedule.operations` 是**构造顺序**，不保证按 `start_time` 排序 | 只扫一遍相邻元素会漏掉反向重叠 |
| 列表长度 | 不假设条数等于 `instance.operations` 的条数 | 少排一道工序会被当成「没问题」 |
| 算法信誉 | 不因为某个算法「通常是对的」而放宽检查 | 错误在搜索中被传播，实验结论作废 |

再补一条容易忽略的：**验证器也不假设 `Schedule` 里的工序 ID 在输入中存在。** 遇到未知 ID 时它先记一条 `unknown operation`，然后 `continue`，而不是直接崩溃——诊断信息比异常栈更有用。

三类语句必须分开（沿用 Day 7 第 6 节的约定）：

| 内容 | 类型 |
|---|---|
| `schedule_errors(instance, schedule) -> list[str]` | **定义** |
| 被验证器接受的排程满足实现覆盖的全部约束 | **理论结论**（在实现覆盖范围内成立） |
| 在 `route_instance` 上注入的九类破坏全部被诊断捕获 | **实验观察**（见第 7 节实际运行） |
| 验证器覆盖了工业调度的全部约束 | **错误断言**（没有换型、日历、工人容量） |

---

## 4. 六项独立检查清单

验证器依次回答六个问题。这六项合起来才是「可行」，任何一项单独成立都不够。

| # | 检查内容 | 诊断标签 | 说明 |
|---|---|---|---|
| 1 | 每道输入工序恰好出现一次 | `missing` / `duplicate` / `unknown operation` | 用 `Counter` 统计出现次数；未知 ID 单独报 |
| 2 | 机器存在且属于该工序的资格集合 | `illegal assignment` | 同时检查「机器在实例中」与「机器在 `eligible_machine_ids` 中」 |
| 3 | 起止是整数、`start >= 0`、`end - start = p` | `invalid time type` / `duration` | 类型检查用 `type(x) is not int`，浮点与布尔都会被挡下 |
| 4 | 开工不早于所属作业的释放时刻 | `release` | `start_time >= job.release_time` |
| 5 | 同一作业内相邻工序 `end(before) <= start(after)` | `precedence` | 用 `Job.operation_ids` 的相邻二元组扫描 |
| 6 | 每台机器上区间两两不重叠 | `overlap` | 按 `start` 排序后维护 `frontier` |

### 4.1 第 3 项为什么用 `type(x) is not int`

`isinstance(True, int)` 为真，`isinstance(nan, int)` 为假但 `math.floor` 之类的写法容易误放行。实现选择最严格的一种：**类型必须恰好是 `int`**。于是 `1.5`、`float("nan")`、`True` 全部被归入 `invalid time type`。

注意这一项检查失败后会 `continue`：时刻不可信的工序不进 `valid_times`，因此不会在后面的 `precedence` / `overlap` 里产生二次误报。

### 4.2 第 6 项的 `frontier` 算法

`[start,end)` 是半开区间，所以 `[0,3)` 与 `[3,5)` **可以相接**，`start == frontier` 是合法的。伪代码：

```text
frontier = 0
for item in 该机器上按 start_time 升序排列的工序:
    if item.start_time < frontier:       # 严格小于才算重叠
        报告 overlap: <machine>/<operation>
    frontier = max(frontier, item.end_time)
```

**为什么必须是 `max` 而不是「上一个区间的 `end`」？** 因为按 `start` 排序后，`end` 未必单调递增。看这个结构：

```text
M0 上三条工序（按 start 排序）：
  A: [0,10)
  B: [1,2)
  C: [4,5)

若只与「上一条」比较：
  B.start=1  < A.end=10   →  抓到
  C.start=4  >= B.end=2   →  ★ 漏掉
若维护 frontier = max(历史所有 end)：
  frontier 依次为 10 → 10 → 10
  B.start=1 < 10 → 抓到；C.start=4 < 10 → 抓到
```

一个长区间**包住**多个短区间时，「相邻比较」只能抓到第一个被包住的区间，后面的全部漏报。`frontier` 记住的是「此前所有区间的最大 `end`」，等价于问「当前位置之前，这条机器总共被占用到了什么时候」。

> **`frontier = max(frontier, item.end_time)` 这一行是第 6 项检查的全部精髓。**

### 4.3 Objective 的位置

`objective.py` 的模块 docstring 写的是「统一的目标评估器：由 Schedule 计算指标」。它**不做任何可行性检查**：给定一个非法排程，`makespan` 照样返回一个数，只是这个数没有意义。

所以调用顺序永远是：

```text
Schedule → validate_schedule → Objective → 可比较的数字
```

`search.py` 里的 `solve` 就是这么写的——`decode` 之后立刻 `validate_schedule`，然后才计算目标值（见 [search.py](../../projects/01_scheduling_core/scheduling_algorithms/search.py) 的 `evaluate` 内部函数）。

---

## 5. 手算 / 构造：从一条可行排程出发

沿用 Day 2 的三条解码轨迹所使用的实例，它是本周所有实验的公共载体。

| Job | `rj` | `pj` | 工序链 |
|---|---:|---:|---|
| J0 | 2 | A=3, B=2 | `A → B` |
| J1 | 0 | C=1 | `C` |

| Operation | `job_id` | `p` | `eligible_machine_ids` |
|---|---|---:|---|
| A | J0 | 3 | `("M0",)` |
| B | J0 | 2 | `("M0","M1")` |
| C | J1 | 1 | `("M0","M1")` |

Day 2 第一条轨迹 `order=ABC, assignments=M0,M1,M0`：

```text
A on M0 [2,5)
B on M1 [5,7)
C on M0 [5,6)

M0 时间线：A[2,5) 然后 C[5,6)      frontier: 5 → 5
M1 时间线：B[5,7)                  frontier: 5 → 7
J0 链：end(A)=5 <= start(B)=5      相接，合法
J1 链：start(C)=5 >= r(J1)=0       合法
```

六个问题全部为「是」，所以 `schedule_errors` 返回空列表，`validate_schedule` 不抛异常。

### 5.1 九类破坏的预测与实测对照

每次只改一项，观察诊断如何变化。左半是**预测**，右半是第 7 节的**实测**（两者一致）。

| 破坏 | 改法 | 预测诊断 | 实测诊断条数 |
|---|---|---|---:|
| `precedence` | B 改成 `M1[2,4)` | `precedence: A -> B` | 1 |
| `overlap` | C 改成 `M0[3,4)` | `overlap: M0/C` | 1 |
| `illegal assignment` | A 改成上 `M1` | `illegal assignment: A` | 1 |
| `missing` | 删掉 C | `missing: C` | 1 |
| `duplicate` | 再附加一份 A | `duplicate: A` + `overlap: M0/A` | 2 |
| `release` | A 改成 `M0[0,3)` | `release: A` | 1 |
| `duration` | A 改成 `[2,6)` | `duration: A` + `precedence: A -> B` + `overlap: M0/C` | 3 |
| `unknown operation` | A 的 ID 改成 `X` | `missing: A` + `unknown operation: X` | 2 |
| `invalid time type` | A 的 `start=float("nan")` | `invalid time type: A` | 1 |

三处需要展开理解：

**`duplicate` 一定伴随 `overlap`。** 同一道工序出现两次，两次都在 M0 上、都占 `[2,5)`，第 1 项报 `duplicate`，第 6 项必然报 `overlap`。这不是重复检查，而是两个不同的问题：一个说「出现次数错了」，一个说「机器时间轴被占了两次」。

**`duration` 是三条诊断的连锁反应。** A 的 `end` 从 5 变成 6（`end-start=4 != p=3`），于是 `end(A)=6 > start(B)=5` 触发 `precedence`，同时 M0 上 A 的占用被拉长到 6，`C` 在 `[5,6)` 被覆盖触发 `overlap`。

**`unknown operation` 会一并报出 `missing`。** 把 A 的 ID 改成 `X` 后，「输入里的 A」出现 0 次（missing），而「排程里的 X」在输入中不存在（unknown operation）。**缺失与未知是同一件事的两个视角**，两个都要报。

### 5.2 相接合法的对照实验

单独造一个实例验证「相接不算重叠」：

| Job | `operation_ids` | `pj` |
|---|---|---:|
| J0 | `A → B` | A=3, B=2 |

A、B 都只能上 M0，`rj = 0`。

```text
A M0[0,3) 与 B M0[3,5)

第 6 项：frontier 从 0 更新到 3；B.start=3 不小于 frontier=3 → 不报
第 5 项：end(A)=3 <= start(B)=3 → 不报
实测 schedule_errors -> []
```

如果实现里把判断写成 `start_time <= frontier`，这一条合法排程就会被误报为 `overlap`。**半开区间的边界恰好是「不允许 `<`，允许 `==`」。**

---

## 6. 实现：`schedule_validation.py`

对应文件 [schedule_validation.py](../../projects/01_scheduling_core/scheduling_core/schedule_validation.py)。整个模块只有两个公开函数，职责切得很干净。

### 6.1 两个函数的契约

```text
schedule_errors(instance, schedule) -> list[str]     收集全部诊断，不抛异常
validate_schedule(instance, schedule) -> None        有诊断时抛 ValueError
```

`validate_schedule` 的实现只有三行，是 `schedule_errors` 的薄包装：

```python
def validate_schedule(instance: Instance, schedule: Schedule) -> None:
    errors = schedule_errors(instance, schedule)
    if errors:
        raise ValueError("; ".join(errors))
```

**为什么保留两个入口？** 因为诊断的用途不同：写测试时想看到「到底错在哪几条」（用 `schedule_errors`），搜索主循环里只想「错了就停」（用 `validate_schedule`）。用分号 `; ` 拼接而不是只抛第一条，是为了让一次运行暴露尽可能多的信息。

### 6.2 顺序上的三个细节

**第一行是 `validate_instance(instance)。** 验证排程前先确认问题本身合法。因此给 `schedule_errors` 传一个非法 `Instance` 时，它会**抛异常**而不是返回诊断——输入错误和结果错误是两码事，前者 fail-fast，后者收集式。

**先统计计数，再逐条检查。** 第 1 项用 `Counter` 一次统计完 `operation_id` 的出现次数：

```python
counts = Counter(item.operation_id for item in schedule.operations)
for oid in operations:            # 遍历的是输入，不是排程
    if counts[oid] == 0:     errors.append(f"missing: {oid}")
    elif counts[oid] > 1:    errors.append(f"duplicate: {oid}")
```

注意循环的**遍历对象是 `instance.operations`**（输入），不是 `schedule.operations`（结果）。这样「排程里少了一道工序」才会被看见——如果遍历结果，缺失的工序根本不会出现在迭代里。

**`valid_times` 是第 5、6 项的公共输入。** 所有时刻类型不过关的工序会被排除在外：

```python
by_id = {item.operation_id: item for item in valid_times}
```

`precedence` 与 `overlap` 都只在这份「时刻可信」的子集上工作，避免在垃圾数据上产生连锁误报。

### 6.3 第 5 项与第 6 项的写法

第 5 项直接扫作业链的相邻二元组：

```python
for before, after in zip(job.operation_ids, job.operation_ids[1:]):
    if by_id[before].end_time > by_id[after].start_time:
        errors.append(f"precedence: {before} -> {after}")
```

这里用的是 `>`，所以 `end == start`（相接）合法。同时它要求两道工序都在 `by_id` 里——少一道就不报 `precedence`，因为那已经由第 1 项报过了。

第 6 项就是第 4.2 节的 `frontier` 循环，`sorted` 的键是 `item.start_time`。注意它外层遍历的是 `machines` 集合（输入里的机器），内层挑选 `valid_times` 中落在该机器上的工序。**没有任何一处调用 `decode`、`Candidate` 或 `neighborhoods`。**

### 6.4 这个验证器覆盖不到的

写完检查清单还要写清边界，否则容易把它当成「可行性证明机」：

```text
不覆盖：换型时间、维护日历、工人/模具容量、抢占、机器相关加工时间
不覆盖：语义正确性（例如「B 应该排在 C 之前」这类业务规则）
不覆盖：最优性——它只判断可行，不判断好不好
```

---

## 7. 实验：`m1w2d4_validator`

对应脚本 [m1w2d4_validator.py](../../projects/01_scheduling_core/examples/m1w2d4_validator.py)，在项目目录下运行：

```bash
python examples/m1w2d4_validator.py
```

脚本构造的五段内容：可行排程基线、九类破坏的诊断、相接合法性、多诊断、`frontier` 包住短区间。实际输出：

```text
== 1. 可行排程（手工构造，不经过 decoder）==
  A on M0 [2,5)
  B on M1 [5,7)
  C on M0 [5,6)
  schedule_errors -> []；validate_schedule 未抛异常

== 2. 九类破坏的诊断 ==
  [precedence] 1 条诊断
      precedence: A -> B
      validate_schedule -> ValueError: precedence: A -> B
  [overlap] 1 条诊断
      overlap: M0/C
      validate_schedule -> ValueError: overlap: M0/C
  [illegal assignment] 1 条诊断
      illegal assignment: A
      validate_schedule -> ValueError: illegal assignment: A
  [missing] 1 条诊断
      missing: C
      validate_schedule -> ValueError: missing: C
  [duplicate] 2 条诊断
      duplicate: A
      overlap: M0/A
      validate_schedule -> ValueError: duplicate: A; overlap: M0/A
  [release] 1 条诊断
      release: A
      validate_schedule -> ValueError: release: A
  [duration] 3 条诊断
      duration: A
      precedence: A -> B
      overlap: M0/C
      validate_schedule -> ValueError: duration: A; precedence: A -> B; overlap: M0/C
  [unknown operation] 2 条诊断
      missing: A
      unknown operation: X
      validate_schedule -> ValueError: missing: A; unknown operation: X
  [invalid time type] 1 条诊断
      invalid time type: A
      validate_schedule -> ValueError: invalid time type: A

== 3. [start,end) 相接是合法的 ==
  J0: A M0[0,3) 与 B M0[3,5) 相接 -> []

== 4. 一个坏排程可以有多条诊断 ==
  duration 类共 3 条：['duration: A', 'precedence: A -> B', 'overlap: M0/C']

== 5. frontier 识别长区间包住短区间 ==
  overlap: M0/B
  overlap: M0/C

全部断言通过。
```

**实验结论**：

1. 九类破坏共产生 **13 条诊断**，每一类都非空，且第 3 项的 `continue` 让 `invalid time type` 只报一条而不会连锁误报。
2. `duration` / `unknown operation` / `duplicate` 三类都产生了**多条**诊断——「一个坏排程可以有多条诊断，不要求只出现一条」是设计意图，不是实现缺陷。
3. 第 5 段里 `overlap: M0/B` 与 `overlap: M0/C` 同时出现，正是 `frontier` 与「相邻比较」的分水岭：只比较相邻 `end` 时 `C` 会被漏掉。
4. 脚本中的 `assert errors == []`（相接）与 `assert len(duration_errors) == 3` 把第 5 节的手算固化成断言——**实验脚本的第一职责就是把手算变成可重复的检查**。

测试侧的对应入口（同一批破坏在 `pytest` 里各是一条参数化用例）：

```bash
python -m pytest tests/test_month1.py -k corruption -v
```

`-k corruption` 命中 9 条用例（实测 `9 passed, 47 deselected`），与上表九类一一对应。

---

## 8. 今日练习

1. **练习 1（构造）**：给 `route_instance` 加一道 J1 的工序 D（`p=2`，只能上 M0），排出可行时间线，并验证 `schedule_errors` 为空。
2. **练习 2（预测）**：不看第 7 节输出，先写出「把 A 的 `start_time` 改成 `-1`」会报哪几条诊断，再运行脚本核对。
3. **练习 3（frontier）**：构造一台机器上 `[0,100)`、`[10,20)`、`[30,40)`、`[90,95)` 四条区间，说明哪几条被报、哪几条不被报。
4. **练习 4（相接边界）**：把第 5.2 节实例的 B 改成 `M0[2,4)`，说明为什么这次报的不是 `overlap` 而是 `precedence` 与 `overlap` 两条。
5. **练习 5（代码阅读）**：不看 `schedule_validation.py`，自己写一遍六项检查的伪代码，标出哪一项需要 `continue`、哪一项需要先排序。

---

## 9. 验收清单

- [ ] 能说出验证器「独立」的四个含义，并解释为什么不能调用 `decode`。
- [ ] 能背出六项独立检查清单及各自的诊断标签。
- [ ] 能独立写出 `frontier` 循环，并解释为什么必须用 `max`。
- [ ] 能解释 `[start,end)` 为什么允许相接，以及判断为何写成 `<` 而不是 `<=`。
- [ ] 能预测 `duration`、`duplicate`、`unknown operation` 三类破坏会各报几条诊断。
- [ ] 能说清 `schedule_errors` 与 `validate_schedule` 的分工，以及 `validate_instance` 为何是第一步。
- [ ] 能说明 Objective 不做可行性检查，调用顺序必须是「先验证、后算指标」。
- [ ] 能列出验证器覆盖不到的约束（换型、日历、工人、抢占）。
- [ ] `python -m pytest tests/test_month1.py -k corruption -q` 输出 `9 passed`。
- [ ] `python -m pytest -q` 全部通过（本仓库当前为 127 条）。

---

## 10. 自测题

不看上文回答：

- Q1：为什么不能用「再 `decode` 一次」代替独立验证？
- Q2：验证器为什么不假设 `Schedule.operations` 按 `start_time` 排序？
- Q3：六项检查分别对应哪些诊断标签？
- Q4：`[start,end)` 的相接在代码里体现为哪个比较符号？
- Q5：为什么机器不重叠检查必须维护 `frontier = max(...)`？
- Q6：`invalid time type` 之后为什么是 `continue` 而不是继续往下检查？
- Q7：`duplicate` 为什么几乎总会伴随一条 `overlap`？
- Q8：为什么报 `unknown operation` 时通常还会报一条 `missing`？
- Q9：Objective 面对一个非法排程会怎么做？调用顺序应该是什么？
- Q10：验证器覆盖不了哪几类约束？

### 参考答案

- A1：因为重新解码得到的是**新生成**的排程，原始输出里的错误时间已经被覆盖，等于让 `decoder` 自己给自己发合格证。
- A2：`Schedule.operations` 是解码器的**构造顺序**，不是时间顺序；只按相邻元素扫一遍会漏掉反向重叠。
- A3：① `missing` / `duplicate` / `unknown operation`；② `illegal assignment`；③ `invalid time type` / `duration`；④ `release`；⑤ `precedence`；⑥ `overlap`。
- A4：`item.start_time < frontier`——用严格小于，`start == frontier` 合法。
- A5：按 `start` 排序后 `end` 未必单调递增；一个长区间可以包住多个短区间，只比较相邻 `end` 会漏掉第二个之后的全部重叠。
- A6：时刻本身不可信（可能是浮点或 NaN），继续参与 `precedence` / `overlap` 只会产生连锁误报；先排除，再在可信子集上做几何检查。
- A7：同一道工序的两份记录占用同一台机器的同一段时间，第 1 项报「出现两次」，第 6 项必然报「时间轴被占了两次」。
- A8：输入里那道工序的出现次数变成 0（`missing`），而结果里多出一个输入不认识的 ID（`unknown operation`）——同一处破坏的两个视角。
- A9：`objective.py` 不做可行性检查，只会照公式返回一个没有意义的数字。调用顺序必须是「`validate_schedule` → Objective」。
- A10：换型时间、维护日历、工人与模具容量、抢占、机器相关加工时间，以及任何业务语义规则和最优性判断。

---

## 11. 今日一句话总结

> **`Objective` 告诉你排程「多好」，只有独立的 `Validator` 能告诉你它「对不对」；验证器只吃 `(Instance, Schedule)`、不调用 `decoder`、不信任列表顺序，用六项检查加一个 `frontier` 把「声称可行」变成「可复核」。**
