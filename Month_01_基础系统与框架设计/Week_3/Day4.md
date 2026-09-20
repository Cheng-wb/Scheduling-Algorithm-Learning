# Day 4：Multi-start 与预算分配

> 当日主题：用多个起点缓解初始解依赖，同时让总预算保持可比
> 当日产出：**Multi-start 的分段预算账本**（重启触发、分段计数、全局 best）+ 实验脚本 [m1w3d4_multistart.py](../../projects/01_scheduling_core/examples/m1w3d4_multistart.py)
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 写出 Multi-start 的组成：一个公共初始解上的 First + 后续随机起点上的 First。
2. 说出重启的**两个**触发条件：当前分段到达局部最优，或当前分段已用完 `restart_interval` 次评价。
3. 解释「总预算 150 + 分段上限 40」**不是**「每次重启额外获得 150 次」，并手工数出一次运行的重启次数。
4. 说清初始评价是第 1 次且属于第一段；重启本身消耗 1 次评价，并且是新段的第 1 项。
5. 解释同一个 `seed` 为什么能复现同一串重启序列，以及它为什么完全不影响固定邻居扫描。
6. 说明全局 `best` 在重启时绝不清空，而 `current` 允许在重启后变差。
7. 用「盆地（basin）」解释分段过短与过长的两种失败模式，并说明 `restart_interval=40` 只是教学起点。
8. 能说出 `restart_interval=1` 与「`restart_interval` 大于总预算」两个极端分别退化成什么。

---

## 2. 为什么第 4 天要做多起点

Day 2 与 Day 3 的 First、Best 有一个共同的、无法通过调参消除的弱点：

> **它们的结果完全取决于起点。**

局部搜索只能沿着「严格改善」的方向走，走到一个邻域里没有更好邻居的位置就停下。而 Day 2 已经强调过：**「局部最优」是相对于邻域的结论，不是相对于问题的结论**。换一个起点，可能停在一个完全不同的、质量差很多的局部最优上。

```text
起点 x1 → 局部最优 A（120）   起点 x2 → 局部最优 B（95）   起点 x3 → 局部最优 C（140）
同一个实例、同一个算法，只换了起点
```

Multi-start 用最朴素的办法缓解这件事：**多跑几次，每次换一个起点。** 它不改变邻域，不改变接受准则，只改变**起点的分布**——所以它不是「更聪明的搜索」，而是「更稳的抽样」。

必须同时记住它的代价：起点不是免费的。每个新起点都要解码、校验、评价，这些都在同一个预算账本里扣除。**Day 1 定的「预算是评价次数」这条契约，今天第一次真正被考验。**

---

## 3. 方法组成：一个公共初始解 + 一串随机起点

**定义（Multi-start）**：先在**所有算法共享的那个初始解**上跑 First，之后每当触发重启条件，就生成一个**随机起点**并在其上继续跑 First；全程只维护**一个**全局最好解。

重启的触发条件有两条，满足任意一条就重启：

| 触发条件 | 代码里的判断 | 含义 |
|---|---|---|
| 当前分段到达局部最优 | `not moved` | 这一轮的完整扫描没有找到任何严格改善 |
| 当前分段用完额度 | `len(trace) - segment_start >= restart_interval` | 本段已经花掉了 `restart_interval` 次评价 |

```python
restart = config.algorithm == "multistart" and (
    not moved or len(trace) - segment_start >= config.restart_interval
)
if restart:
    candidate = random_candidate()
    schedule, score = evaluate(candidate)
    current, value = candidate, score
    record(candidate, schedule, score, True)
    segment_start = len(trace) - 1
```

三行代码对应三个要点：

1. `random_candidate()` 打乱当前的 `order`，并为每道工序在**合法机器集合**里重抽一台（`rng.choice(op.eligible_machine_ids)`）——它生成的一定是合法候选，不需要额外修复。
2. 重启候选先被 `evaluate`（一次解码 + 一次校验 + 一次目标），**这就是「重启消耗 1 次评价」的位置**；然后才成为 `current`。
3. `segment_start = len(trace) - 1` 把刚刚记录的重启点算作**新段的第 1 项**，而不是旧段的最后一项。

还有一条容易忽略的后果：`status = "LOCAL_OPTIMUM"` 只在 `elif not moved:` 分支里被赋值，而 multi-start 的 `not moved` 会走 `if restart:` 分支。**所以 multi-start 永远不会返回 `LOCAL_OPTIMUM`**。

---

## 4. 预算是唯一的账本

### 4.1 「总预算 150、分段上限 40」到底是什么意思

这是本日最容易理解错的一句话。它的正确含义是：

```text
budget = 150          → 整条 trace 的长度上限，整个搜索一共只有 150 次评价
restart_interval = 40 → 单个分段最多花 40 次评价，用完就换起点
```

`while len(trace) < config.budget` 与内层 `if len(trace) >= config.budget: break` 是这个账本的全部实现：**重启、被拒绝的候选、初始解，全都在同一个 `trace` 里排队计数。**

> **结论**：「150 次预算 + 40 的分段上限」绝不等于「每次重启额外获得 150 次」。重启只从这 150 次里再花掉 1 次。

### 4.2 手工数预算

```text
记 budget = B，restart_interval = R

第 1 段的第 1 次评价 = 初始解评价，编号 #1（它不是重启）
每段最多 R 次评价：
    额度检查发生在每次评价之前：len(trace) - segment_start >= R 就退出扫描
    → 第 R+1 次评价不可能是扫描评价
第 R+1 次评价 = 随机重启（前提是预算还没用完）
    它消耗 1 次评价，同时是新段的第 1 项
第 2 段最多再 R 次：#(R+1) .. #(2R)
...
```

配合两个具体数字记：

- 「第 1 段在第 10 次评价上已确认局部最优」→ 第 11 次评价是随机起点，且这次评价**是新段的第一项**（因为 `segment_start` 在记录它之后被改成 10）。
- 「预算只剩 1 次」→ 这一轮可以评价一个新起点（它成为第 B 次评价），但**没有任何剩余评价**可以在这个起点上做局部搜索；这个起点只是一个「额外抽到的随机样本」。

### 4.3 提前停止会让重启次数变化

分段长度是「≤ R」而不是「= R」：只要某一段在一轮里 `not moved`（确认局部最优），它就不必用满 R 次。所以：

> **重启次数取决于实例，不能只按 B / R 估算。**

反过来，如果每一段都用满 R 次，重启次数就是 `floor((B − 1) / R)`。

### 4.4 seed 的作用范围

```python
rng = Random(config.seed)
...
def random_candidate() -> Candidate:
    order = list(current.order)
    rng.shuffle(order)
    return Candidate(
        tuple(order),
        tuple(rng.choice(op.eligible_machine_ids) for op in instance.operations),
    )
```

`rng` 在整个 `solve` 里**只被 `random_candidate()` 使用**：`first` / `best` 分支完全不消耗随机数（`random_move()` 只在 `random` / `sa` 分支被调用）。所以：固定邻居扫描**不受 seed 影响**（扫描顺序只由 `neighbors` 的固定生成顺序决定）；同样的 seed + 同样的输入会重现**同一串重启序列**（同样的起点、同样的顺序、同样的机器指派）；换一个 seed 只改变随机起点的内容，不改变第一次局部搜索的路径。这就是为什么 `test_search_budget_reproducibility_and_incumbent` 敢断言 `result.trace == replay.trace`——两次运行的随机数流完全相同。

### 4.5 全局 best 从不清空

```python
if restart:
    candidate = random_candidate()
    schedule, score = evaluate(candidate)
    current, value = candidate, score          # current 可以变差
    record(candidate, schedule, score, True)   # best 只在严格更小时更新
```

重启时被覆盖的是 `current` 与 `value`；`best` / `best_schedule` / `best_value` 只在 `record` 里的 `if score < best_value` 分支被更新。所以：

> **随机起点即使比当前解差，也会成为新的当前解；但全局 `best` 在整个运行里从不被清空。**

第 5 节会给出这一现象在真实轨迹上的直接证据。

---

## 5. 手算 / 示例：`restart_interval=7` 的分段账本

### 5.1 输入表

| 项 | 值 |
|---|---|
| 生成式 | `generate_instance(40, jobs=6, machines=2, operations_per_job=2)` |
| 工序数 | 12 |
| 邻域规模（去重后） | 188 |
| 目标 | `makespan` |
| `budget` | 30 |
| `restart_interval` | 7 |
| `seed` | 9 |

选 `restart_interval=7`（远小于月度默认的 40）是为了让分段短到能在纸上数清；选 `budget=30` 是为了让整条轨迹能完整打印出来。

### 5.2 逐评价轨迹

```text
evaluation,segment,proposed,current,best,accepted,note
1,1,135.0,135.0,135.0,True,初始评价，属于第 1 段
2,1,135.0,135.0,135.0,False,扫描候选，未改善
3,1,135.0,135.0,135.0,False,扫描候选，未改善
4,1,135.0,135.0,135.0,False,扫描候选，未改善
5,1,135.0,135.0,135.0,False,扫描候选，未改善
6,1,135.0,135.0,135.0,False,扫描候选，未改善
7,1,135.0,135.0,135.0,False,扫描候选，未改善
8,2,115.0,115.0,115.0,True,随机重启：新段的第 1 项，本身消耗 1 次评价
9,2,115.0,115.0,115.0,False,扫描候选，未改善
10,2,115.0,115.0,115.0,False,扫描候选，未改善
11,2,115.0,115.0,115.0,False,扫描候选，未改善
12,2,111.0,111.0,111.0,True,扫描发现严格改善并移动
13,2,111.0,111.0,111.0,False,扫描候选，未改善
14,2,111.0,111.0,111.0,False,扫描候选，未改善
15,3,100.0,100.0,100.0,True,随机重启：新段的第 1 项，本身消耗 1 次评价
16,3,100.0,100.0,100.0,False,扫描候选，未改善
17,3,100.0,100.0,100.0,False,扫描候选，未改善
18,3,100.0,100.0,100.0,False,扫描候选，未改善
19,3,100.0,100.0,100.0,False,扫描候选，未改善
20,3,100.0,100.0,100.0,False,扫描候选，未改善
21,3,100.0,100.0,100.0,False,扫描候选，未改善
22,4,110.0,110.0,100.0,True,随机重启：新段的第 1 项，本身消耗 1 次评价
23,4,110.0,110.0,100.0,False,扫描候选，未改善
24,4,110.0,110.0,100.0,False,扫描候选，未改善
25,4,110.0,110.0,100.0,False,扫描候选，未改善
26,4,109.0,109.0,100.0,True,扫描发现严格改善并移动
27,4,109.0,109.0,100.0,False,扫描候选，未改善
28,4,109.0,109.0,100.0,False,扫描候选，未改善
29,5,100.0,100.0,100.0,True,随机重启：新段的第 1 项，本身消耗 1 次评价
30,5,100.0,100.0,100.0,False,扫描候选，未改善
```

`segment` 一列来自 `(评价编号 − 1) // 7 + 1`，其成立前提是「每段都用满 7 次评价额度」；脚本对此做了断言（每个分段起点的 `accepted` 都必须是 `True`，因为重启记录一定是 `accepted=True`），本运行成立。

### 5.3 预算算术

```text
分段起点 = 评价编号 (k − 1) 是 7 的倍数 → k = 1, 8, 15, 22, 29
共 5 段、4 次重启

第 1 段 = #1 .. #7    （#1 是初始评价；#2..#7 是 6 次扫描评价）
第 2 段 = #8 .. #14   （#8 是重启；#9..#14 是 6 次扫描评价）
第 3 段 = #15 .. #21  （#15 是重启；#16..#21 是 6 次扫描评价）
第 4 段 = #22 .. #28  （#22 是重启；#23..#28 是 6 次扫描评价）
第 5 段 = #29 .. #30  （#29 是重启；#30 是 1 次扫描评价，预算在此耗尽）

预算分解：30 = 1（初始评价）+ 4（重启）+ 25（扫描评价）
重启编号：8, 15, 22, 29 —— 每个都占 1 次评价
上界核对：floor((30 − 1) / 7) = 4 次重启，与实际一致
```

再看 `current` 列的两次「非重启的变化」：#12（115 → 111）与 #26（110 → 109）都是段内的严格改善；而 #22 是唯一的一次 `current` **上升**：

```text
#21 → #22：current 100.0 → 110.0（变差），同一时刻 best 仍是 100.0
```

**结论**：随机起点可以比当前解更差，但它照样成为当前解；全局 `best` 完全没有被这次重启影响（第 4.5 节的行为在真实轨迹上被确认）。顺带一句：First 的移动只接受严格改善，`current` 永远不会上升——所以「`current` 上升」这件事本身就可以作为「发生了重启」的判据之一。

### 5.4 对比表：两个极端

| 设置 | 段数 | 重启次数 | 扫描评价数 | objective | status |
|---|---|---|---|---|---|
| `restart_interval=1` | 30 | 29 | 0 | **82.0** | `BUDGET` |
| `restart_interval=7` | 5 | 4 | 25 | 100.0 | `BUDGET` |
| `restart_interval=300` | 1 | 0 | 29 | 107.0 | `BUDGET` |
| `first`（对照，同实例同预算） | —— | —— | 29 | 107.0 | `BUDGET` |

三个现象的读法：

1. **`restart_interval=1` 时扫描评价数恰好为 0。** 额度检查发生在每次评价之前，`len(trace) - segment_start >= 1` 在每段开头就成立，扫描循环一次都没进入过 → 整轮运行退化为**连续随机重启**，等价于「随机抽样 + 取最好」。
2. **`restart_interval=300 > budget=30` 时，轨迹与 `first` 逐点相同**（脚本断言 `big.trace == first_result.trace` 为 `True`）。因为本运行里每一轮扫描都被总预算打断，没有任何一轮真正扫完整个邻域（确认局部最优），所以多起点从未被触发。
3. **两个极端都不是普遍最佳。** 注意第 5.4 节表格里 82.0 反而是三者中最好的——但这**不能**读成「interval=1 更好」：本例邻域有 188 个候选而预算只有 30 次，局部搜索本来就没有展开的空间，随机抽样自然占优。月度批次里也能看到多起点并不总是赢：在 `single_12`（12 作业、单机、`total_tardiness`、预算 150、3 个 seed）上，`first` 的均值是 575、multi-start 是 373（明显变好），但纯随机的均值是 313（更好）。**多起点是一次真实的改进，但它不是万能药。**

如果某一轮在预算用尽之前就确认了局部最优，multi-start 仍然会重启，这一点与 `first` 立即以 `LOCAL_OPTIMUM` 停机不同——这正是「`restart_interval` 大于预算」只是**接近**而不是**等于**单起点 First 的原因。

---

## 6. 实现：`search.py`

对应文件 [search.py](../../projects/01_scheduling_core/scheduling_algorithms/search.py)。

### 6.1 分段账本的三个变量

```python
segment_start = 0
while len(trace) < config.budget:
    scan_current = current
    chosen, chosen_value = current, value
    for candidate in neighbors(instance, current):
        if len(trace) >= config.budget:
            break
        if (
            config.algorithm == "multistart"
            and len(trace) - segment_start >= config.restart_interval
        ):
            break
        ...
```

| 变量 | 含义 | 更新时机 |
|---|---|---|
| `config.budget` | 整条 `trace` 的长度上限 | 构造时校验 `budget >= 1` |
| `segment_start` | 当前分段起点的 0 基下标 | 只在重启后：`segment_start = len(trace) - 1` |
| `len(trace) - segment_start` | 当前分段已花掉的评价数 | 只读 |

注意两层循环里的两个 `break`：内层因为**预算**耗尽而 `break` 时，外层马上也会因 `len(trace) >= config.budget` 结束；内层因为**分段额度**耗尽而 `break` 时，外层会走到重启判断。

### 6.2 与 First 共享的部分

multi-start 的扫描段与 Day 3 第 6.1 节的 First 完全一样（`config.algorithm != "best"` 让它在改善时立刻 `current, value = chosen, chosen_value` 并 `break`）。**所以「多起点 = 一串 First」不是类比，而是字面事实**：把 `restart_interval` 设成大于预算，得到的逐评价轨迹与 `algorithm="first"` 完全相同（第 5.4 节已断言）。

### 6.3 multi-start 的 `status` 为什么不是 `LOCAL_OPTIMUM`

```python
    if restart:
        ...
    elif not moved:
        status = "LOCAL_OPTIMUM"
        break
```

`not moved` 时，multi-start 先命中 `if restart:`，把 `status` 留在初始值 `"BUDGET"` 并继续；只有非 multi-start 的算法才会落到 `elif` 并把状态改成 `"LOCAL_OPTIMUM"`。

### 6.4 测试如何固定这套账本

`tests/test_month1.py` 的 `test_search_budget_reproducibility_and_incumbent` 用与第 5 节**同一个实例、同一个 `seed=9`、同一个 `restart_interval=7`**，对 `algorithm ∈ {lpt, random, first, best, multistart, sa}` × `budget ∈ {1, 2, 60}` 断言：

```text
result.trace == replay.trace                  两次运行逐点一致（可复现）
result.evaluations == len(result.trace) <= budget
if algorithm in ("random", "sa", "multistart"):
    result.evaluations == budget              这三个算法一定用满预算
[point.best for point in result.trace] 等于其自身降序
```

**「一定用满预算」是 multi-start 的结构性事实**：它的循环只在 `len(trace) < budget` 时继续，而「确认局部最优」走的是重启而不是停机，所以它从不提前退出。

---

## 7. 实验：`m1w3d4_multistart`

对应脚本 [m1w3d4_multistart.py](../../projects/01_scheduling_core/examples/m1w3d4_multistart.py)，在项目目录下运行：

```bash
python examples/m1w3d4_multistart.py
```

脚本用第 5 节的配置打印完整逐评价轨迹与分段编号，验证「重启点一定是 `accepted=True`」「全局 `best` 单调不增」，再跑两个极端设置并与单起点 `first` 逐点对比。固定 `seed`，不写 `artifacts/`。

**实际运行输出**（原文粘贴）：

```text
instance = generate_instance(40, jobs=6, machines=2, operations_per_job=2)
总预算 budget=30，分段上限 restart_interval=7，seed=9
预算账本：总预算 30 次评价是整个搜索的全部额度，
绝不是「每次重启额外获得 30 次」；重启只从这 30 次里再花掉 1 次。

=== 主实验：multistart, restart_interval=7 ===
objective=100.0  evaluations=30  status=BUDGET
检测到的分段起点（评价编号）: [1, 8, 15, 22, 29] → 共 5 段，重启 4 次
evaluation,segment,proposed,current,best,accepted,note
1,1,135.0,135.0,135.0,True,初始评价，属于第 1 段
2,1,135.0,135.0,135.0,False,扫描候选，未改善
3,1,135.0,135.0,135.0,False,扫描候选，未改善
4,1,135.0,135.0,135.0,False,扫描候选，未改善
5,1,135.0,135.0,135.0,False,扫描候选，未改善
6,1,135.0,135.0,135.0,False,扫描候选，未改善
7,1,135.0,135.0,135.0,False,扫描候选，未改善
8,2,115.0,115.0,115.0,True,随机重启：新段的第 1 项，本身消耗 1 次评价
9,2,115.0,115.0,115.0,False,扫描候选，未改善
10,2,115.0,115.0,115.0,False,扫描候选，未改善
11,2,115.0,115.0,115.0,False,扫描候选，未改善
12,2,111.0,111.0,111.0,True,扫描发现严格改善并移动
13,2,111.0,111.0,111.0,False,扫描候选，未改善
14,2,111.0,111.0,111.0,False,扫描候选，未改善
15,3,100.0,100.0,100.0,True,随机重启：新段的第 1 项，本身消耗 1 次评价
16,3,100.0,100.0,100.0,False,扫描候选，未改善
17,3,100.0,100.0,100.0,False,扫描候选，未改善
18,3,100.0,100.0,100.0,False,扫描候选，未改善
19,3,100.0,100.0,100.0,False,扫描候选，未改善
20,3,100.0,100.0,100.0,False,扫描候选，未改善
21,3,100.0,100.0,100.0,False,扫描候选，未改善
22,4,110.0,110.0,100.0,True,随机重启：新段的第 1 项，本身消耗 1 次评价
23,4,110.0,110.0,100.0,False,扫描候选，未改善
24,4,110.0,110.0,100.0,False,扫描候选，未改善
25,4,110.0,110.0,100.0,False,扫描候选，未改善
26,4,109.0,109.0,100.0,True,扫描发现严格改善并移动
27,4,109.0,109.0,100.0,False,扫描候选，未改善
28,4,109.0,109.0,100.0,False,扫描候选，未改善
29,5,100.0,100.0,100.0,True,随机重启：新段的第 1 项，本身消耗 1 次评价
30,5,100.0,100.0,100.0,False,扫描候选，未改善
全局 best 单调不增? True （首值 135.0 → 末值 100.0）

随机重启可以比当前解更差的直接证据（current 上升）：
  #21 → #22: current 100.0 → 110.0（变差了，但仍然成为当前解）
  同一次评价里 best 仍为 100.0：全局 best 从不在重启时清空。
反过来说，First 的移动只接受严格改善，current 永远不会上升。

分段长度：每段最多 7 次评价，其中第 1 次是重启（第 1 段是初始评价），剩下 6 次留给局部搜索；本运行共 30 次评价，恰好用完 budget=30。

=== 极端 1：restart_interval=1 → 每段只剩 1 次评价，全部是随机重启 ===
objective=82.0  evaluations=30  status=BUDGET  accepted=True 的评价数=30
分段上限为 1 时，扫描循环在每次评价前就因「本段额度已用完」而退出，
所以每一段都没有任何扫描评价，整轮运行退化成连续随机重启。
current 列: ['135', '115', '100', '109', '100', '108', '109', '100', '97', '130', '130', '91', '133', '111', '121', '94', '116', '115', '105', '112', '109', '124', '95', '82', '99', '98', '98', '118', '109', '103']

=== 极端 2：restart_interval=300 远大于 budget=30 ===
objective=107.0  evaluations=30  status=BUDGET  accepted=True 的评价数=2
与单起点 First 的逐点对比：
  逐评价 trace 完全相同? True
  multistart: objective=107.0 evaluations=30 status=BUDGET
  first     : objective=107.0 evaluations=30 status=BUDGET
  本运行里每一轮扫描都被总预算打断，没有一轮真正扫完整个邻域（确认局部最优），
  所以多起点从未被触发；若某一轮提前确认局部最优，multistart 仍会重启，
  这一点与 first 立即以 LOCAL_OPTIMUM 结束不同。

对照：restart_interval=7 得到 100.0，restart_interval=1 得到 82.0，接近单起点 First 得到 107.0
两个极端都不是普遍最优：分段太短无法深入改善，太长则可能只在同一个 basin 里打转。
```

**实验观察**（只陈述输出里看得到的事实）：

1. **预算分解可核对**：`evaluations=30` = 1 次初始评价 + 4 次重启 + 25 次扫描评价；重启编号 8、15、22、29 正好是第 5.3 节手算的那四个。
2. **初始评价属于第 1 段**（`segment=1`），**重启点是新段的第一项**（#8 的 `segment=2`）。
3. **重启允许变差**：#22 把 `current` 从 100 推到 110，同一次评价里 `best` 不动。
4. **`best` 列单调不增**（脚本断言为 `True`），首值 135.0 → 末值 100.0，重启没有让它回升过。
5. **两个极端**：`interval=1` 时 30 次评价全是重启（扫描评价数为 0）；`interval=300` 时轨迹与 `first` 逐点相同。

---

## 8. 今日练习

1. **练习 1（手算）**：设 `budget=50`、`restart_interval=6`，且每一段都用满额度。写出所有分段起点、重启次数，以及「重启一共花掉多少次评价」。
2. **练习 2（提前停止）**：设 `budget=50`、`restart_interval=6`，但第 2 段在第 3 次评价上就确认了局部最优。写出第 2 段的实际长度、下一次重启的编号，并说明它是否与练习 1 的答案相同。
3. **练习 3（轨迹阅读）**：在第 7 节的轨迹里找出所有「`current` 发生变化但 `accepted=False`」的行、所有「`current` 上升」的行，并分别解释它们的成因。
4. **练习 4（两个极端）**：把 `restart_interval` 改为 `1` 与改为「大于总预算」，各跑一次并记录 `objective` 与 `evaluations`。解释为什么两者都不该被当成默认设置。
5. **练习 5（代码阅读）**：不看 `search.py` 与本文，写出 `segment_start` 的初值、唯一更新点、以及它为什么是 `len(trace) - 1` 而不是 `len(trace)`。

---

## 9. 验收清单

- [ ] 能写出 Multi-start 的组成，并说出重启的两个触发条件。
- [ ] 能解释「总预算 150 + 分段上限 40」不是「每次重启额外 150 次」，并能手工数出重启次数与预算分解。
- [ ] 能说出初始评价是第 1 次、属于第 1 段，重启点是新段的第 1 项。
- [ ] 能解释预算只剩 1 次时「可以评价一个新起点，但不能执行局部搜索」。
- [ ] 能说明 `seed` 只驱动随机起点、不影响固定邻居扫描，以及它如何保证轨迹可复现。
- [ ] 能说明全局 `best` 在重启时绝不清空，而 `current` 允许变差。
- [ ] 能用 basin（盆地）解释分段过短与过长的两种失败模式，并说明 `restart_interval=40` 只是教学起点。
- [ ] 能说出为什么 multi-start 永远不会返回 `LOCAL_OPTIMUM`。
- [ ] 在项目目录下运行 `python -m examples.m1w3d4_multistart`，输出与第 7 节粘贴一致，两个极端与单起点对照可复现。
- [ ] 在项目目录下运行 `python -m pytest tests/test_month1.py -k search_budget -v`，18 条预算/可复现测试全部通过（本日无新增测试）。

---

## 10. 自测题

不看上文回答：

- Q1：Multi-start 由哪两部分组成？它改变了搜索的哪个环节？
- Q2：重启的两个触发条件分别是什么？
- Q3：`budget=150`、`restart_interval=40` 是不是意味着每次重启额外获得 150 次评价？
- Q4：初始评价属于第几段？重启评价属于第几段？
- Q5：重启本身消耗几次评价？为什么？
- Q6：预算只剩 1 次时，你能做和不能做的是什么？
- Q7：同一个 `seed` 能复现哪些东西？它不影响什么？
- Q8：重启时全局 `best` 会被清空吗？`current` 呢？
- Q9：什么是 basin？分段太短和太长分别有什么问题？
- Q10：`restart_interval=1` 与 `restart_interval` 大于总预算，分别退化成什么？

### 参考答案

- A1：一个公共初始解上的 First + 后续随机起点上的 First；它改变的是**起点的分布**，不改变邻域，也不改变接受准则。
- A2：当前分段到达局部最优（一轮 `not moved`），或当前分段用完 `restart_interval` 次评价额度。
- A3：不是。150 是整个搜索的全部评价额度，重启只从这 150 次里再花掉 1 次。
- A4：初始评价是第 1 段的第一项；重启评价是**新段**的第一项（`segment_start = len(trace) - 1`）。
- A5：1 次。因为重启候选要经过 `evaluate`（解码 + 校验 + 目标）才会成为 `current`，这次评价被 `record` 记进 `trace`。
- A6：可以做的是评价一个新起点（它成为最后一次评价）；不能做的是在这个起点上执行任何局部搜索——已经没有剩余预算。
- A7：能复现同一串重启序列（同样的随机起点与机器指派），因而逐点轨迹相同；它不影响固定邻居扫描的顺序与路径。
- A8：`best` 永不清空（只在严格更小时更新）；`current` 会被随机起点覆盖，允许变差。
- A9：basin 是从一批相近起点出发做局部搜索、最终落到同一个局部最优的区域。分段太短无法深入改善，分段太长可能只探索一个 basin。
- A10：`interval=1` 退化为连续随机重启（扫描评价数为 0）；`interval` 大于总预算时接近单起点 First（但若某轮提前确认局部最优，multi-start 仍会重启）。

---

## 11. 今日一句话总结

> **Multi-start 用「一个公共初始解 + 一串随机起点」把起点依赖摊平成抽样；它的全部代价都记在同一个预算账本上——重启消耗 1 次评价、是新段的第 1 项、并且只覆盖 `current` 而不动全局 `best`，而 `restart_interval` 的取值就是「深度」与「盆地覆盖数」之间的取舍旋钮。**
