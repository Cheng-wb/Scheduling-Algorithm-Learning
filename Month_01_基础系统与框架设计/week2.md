# M1 Week 2 周总结：解表示、邻域与独立验证器

> 笔记：[Day1](Week_2/Day1.md) · [Day2](Week_2/Day2.md) · [Day3](Week_2/Day3.md) · [Day4](Week_2/Day4.md) · [Day5](Week_2/Day5.md) · [Day6](Week_2/Day6.md) · [Day7](Week_2/Day7.md)

## 1. 本周目标与成果

Week 1 建立了「规则 → Schedule → Objective」这条直线。但规则只会给「一个解」，不会告诉你这个解好不好、还能不能更好。要谈「更好」，就必须先能**表示一个可被改动的解**（Candidate），再能**把它变成合法排程**（decoder），最后能**独立地判断它到底合不合法**（schedule validator）。

本周完成四件事：

1. **第三种对象**：`Candidate` 把「决策」与「时间」分开，决策可改、时间由解码器重算。
2. **构造式解码**：`decode` 把 `order` + `assignments` 变成可行 `Schedule`，并给出三条可手推的精确轨迹。
3. **邻域**：`swap` / `insert` / `reassign` 三种移动，只产生新 Candidate，不负责判断可行性。
4. **独立验证器**：`schedule_errors` 不调用 decoder、不信任顺序，独立发现九类损坏。

此外补上**随机实例生成器**（可复现地产生不同规模的输入）与**单工序枚举 oracle**（在极小实例上给出可称 `optimum` 的参考值）。

## 2. 三类对象：Instance / Candidate / Schedule

| 对象 | 角色 | 是否可变 | 谁负责 |
|---|---|---|---|
| `Instance` | 业务输入（问题数据） | 不可变 | Parser / 手写 |
| `Candidate` | **决策**（优先级 + 指派） | 不可变 | 邻域产生 |
| `Schedule` | **结果**（落到时间轴） | 不可变 | decoder 产生 |

```text
Instance  ──►  Candidate  ──►  Schedule  ──►  Objective
（问题）       （决策）          （时间）        （评价）
                   ▲
                   │ 邻域只在这一层移动
```

**为什么不能直接移动 `Schedule` 里的时间戳？** 因为改一个 `start_time` 会连带破坏释放时间、机器不重叠、作业内 precedence。改动决策、由解码器重算时间，是唯一能保证「移动后仍是一个良定义的解」的方式。

```python
Candidate(order=("A", "B", "C"), assignments=("M0", "M1", "M0"))
```

两条硬约定：

- `order` 是**所有工序 ID 的优先级排列**，每个 ID 恰好出现一次；
- `assignments` 的**位置永远对齐 `instance.operations`**，不随 `order` 排列。这条最容易写错，也是所有洗牌类 bug 的来源。

**顺序不是拓扑序**：`order` 不必让前驱在前；解码器扫描时会跳过前驱尚未排定的工序。因此**不同 `order` 可能得到完全相同的 `Schedule`**——这叫**表示冗余**。它的直接后果是：搜索空间的计数（排列数）不能等同于「不同可行时间表的数量」。

## 3. 解码器：追加式构造

对应文件 [decoder.py](../projects/01_scheduling_core/scheduling_algorithms/decoder.py)。

```text
machine_ready = {每台机器: 0}                      # state
ends = {}                                          # 已排工序的结束时间
remaining = list(candidate.order)                  # 优先级列表

while remaining:
    取 remaining 中第一道「前驱已排定」的工序 op      # 构造顺序条件
    m = candidate 给 op 指派的机器
    start = max(machine_ready[m], ends[前驱] or 0, release(作业))   # 递推
    end = start + op.processing_time
    machine_ready[m] = ends[op] = end              # transition
```

**核心公式**：

```text
start(op) = max( machine_ready[m] , end(predecessor) , release(job) )
end(op)   = start(op) + p(op)
```

三项 `max` 分别对应三类约束：**机器不重叠**、**作业内 precedence**、**释放时间**。

三条精确轨迹（输入 `A(p=3,r=2)→B(p=2)`、`C(p=1,r=0)`；A 仅 M0，B、C 可 M0/M1）：

| 编码 | 轨迹 |
|---|---|
| `ABC`；`M0,M1,M0` | A:M0[2,5)，B:M1[5,7)，C:M0[5,6) |
| `BCA`；`M0,M1,M0` | B 未就绪被跳过，C:M0[0,1)，A:M0[2,5)，B:M1[5,7) |
| `BCA`；`M0,M0,M1` | C:M1[0,1)，A:M0[2,5)，B:M0[5,7) |

第一例中 M0 的 `[0,2)` 空隙**没有**被 C 填充——这是本周最重要的实现边界：

> **当前解码器是「追加式」的：它只会把工序排在机器的末尾，不会向已有空隙插入。** 这让程序易读、易验证，但会损失解质量。

复杂度：每步线性扫描候选列表并移除元素，总体约 `O(n²)`，另有输入与候选校验开销。M1 阶段优先保持**可验证**；增量评估留到后续月份。

## 4. 邻域：只产生新的 Candidate

对应文件 [neighborhoods.py](../projects/01_scheduling_core/scheduling_algorithms/neighborhoods.py)。

| 操作 | `ABCD` 的示例 | 改变了什么 | 保持不变 |
|---|---|---|---|
| `swap(i,j)` | `swap(0,2)` → `CBAD` | 两个位置的优先级 | 机器指派 |
| `insert(i,j)` | `insert(0,2)` → `BCAD` | 把 i 处元素移到结果位置 j | 机器指派 |
| `reassign(index, machine)` | — | 一道工序的机器 | `order` 与其余指派 |

两个**极易误解**的语义：

- `insert(i, j)` 的 `j` 是**移除后元素最终所在的下标**，不是「插在原索引 j 之前」；
- `reassign` 的 `index` 是 **`instance.operations` 中的位置**，不是 `order` 中的位置。

**邻域不是算法**。`N(x)` 只是「当前解附近允许考察的一组解」；First、Best、SA 都可以用**同一套**移动，区别只在于**如何选下一步**。

**边界与去重**：

- `swap`/`insert` 拒绝负数与越界（`IndexError`）；`i == j` 返回等值候选解；
- `reassign` 只允许 `eligible_machine_ids` 中的机器（否则 `ValueError`）；
- 交换优先级可能把后继排到前驱之前，但**这不等于 precedence 违规**——解码器会等前驱，可行性由解码与验证保证；
- `neighbors` 按固定顺序扫描 swap → insert → 机器替换，用 `seen` 集合去重并排除自身。

**规模**（`n = 4` 的实测值）：

```text
swap   的非自身结果      6      ← 即 n(n−1)/2 个位置对
insert 的非自身结果      9      ← 原始有 n(n−1) = 12 个有向移动，但内部已有重合
朴素相加                15      ← 6 + 9
去重后的并集            12
重合                     3
```

两处重合的来源不同，都要记住：

1. **`insert` 自己内部就重合**：`insert(0, 1)` 与 `insert(1, 0)` 都得到 `(B,A,C,D)`——「把相邻元素移出再插入」与「交换相邻元素」是同一个结果；
2. **`swap` 与 `insert` 之间也重合**：同一个相邻换位既能写成 `swap` 也能写成 `insert`。

所以**不能把 swap 与 insert 的移动数简单相加**当作去重后的邻域大小。当前完整邻域的存储与评估成本随 `n²` 增长；SA 使用随机移动，不先生成整个邻域。

## 5. 独立验证器：为什么不能只信 solver

对应文件 [schedule_validation.py](../projects/01_scheduling_core/scheduling_core/schedule_validation.py)。

**验证器的独立契约**：

```text
不调用 decoder
不假设 operations 按时间排序
不依据任何算法的内部状态
接受任意工序列表顺序
```

六项独立检查：

1. 每道输入工序**恰好出现一次**（缺失 / 重复 / 未知 ID 分别报告）；
2. 机器存在，且属于该工序的 `eligible_machine_ids`；
3. 起止时刻为整数，`start ≥ 0`，且 `end − start == processing_time`；
4. `start >= 作业的 release_time`；
5. 同一作业内相邻工序满足 `end(before) <= start(after)`；
6. 每台机器按 `start` 排序后，当前 `start` 不早于此前区间的**最大** `end`。

两点设计细节：

- **区间是 `[start, end)`**，所以 `[0,3)` 与 `[3,5)` 相接是**合法**的，不算重叠；
- 第 6 条维护**历史最大结束时间**（`frontier`），因此能识别「一个长区间包住多个短区间」——只比较相邻区间会漏掉这种重叠。

九类可执行的损坏样例：`precedence`、`overlap`、`illegal assignment`、`missing`、`duplicate`、`release`、`duration`、`unknown operation`、`invalid time type`。一个坏排程可以产生**多条**诊断，不要求只出现一条。

**两条必须记住的分工**：

- **Input Validator** 检查**问题数据**是否合法（重复 ID、非法引用、`p > 0`、非有限权重……），fail-fast；
- **Schedule Validator** 检查**求解结果**是否可行（上面六条）。
- **Objective 只算指标，不做验证**。调用方必须先验证再评价，否则会得到「一个坏排程的漂亮数字」。

**为什么不能只检查 `Cmax` 是否合理？** 因为删掉一个长任务会得到**更小**的目标值——目标值好看恰恰可能是解已经损坏的信号。

**为什么不能用 decoder 再解码一次代替检查？** 因为那验证的是**新生成的**排程，原始输出里的错误时间已经被覆盖掉了。**不能让 decoder 自己证明自己**——这与 Week 1「expected 不由被测函数生成」是同一个思想。

## 6. 实例生成器与输入质量

对应文件 [generator.py](../projects/01_scheduling_core/scheduling_io/generator.py)。

| 参数 | 含义 | 默认值 |
|---|---|---:|
| `seed` | 实例种子（与算法种子**无关**） | 必填 |
| `jobs` | 作业数 | 12 |
| `machines` | 同质机器数 | 3 |
| `operations_per_job` | 每个作业链长度 | 1 |
| `release_max` | 释放时刻均匀整数范围上界 | 10 |
| `due_factor` | 交期相对自身总工时的系数 | 1.5 |

```text
p     = randint(1, 20)
r     = randint(0, release_max)
due   = r + int(sum(p_of_this_job) * due_factor)
w     = float(randint(1, 5))
eligible_machine_ids = 全部机器        ← 生成器默认全资格
```

三点必须记住：

1. **局部 RNG**：生成器使用 `Random(seed)` 局部实例，**不修改 Python 全局随机状态**。因此生成实例不会污染任何其他随机过程。
2. **实例种子 ≠ 算法种子**：前者描述**数据怎么来**，后者描述**搜索怎么做**，是两个独立 RNG。相同数值不代表同一个随机过程。
3. **交期是「相对自身工时」定义的**（`due = r + 1.5 × Σp`）。所以在繁忙的单机上会**大量迟交**，不能认为它代表真实工厂的订单分布。

生成器只负责**合法正例**，且默认**全机器资格**；资格受限的案例另用手工测试覆盖（例如「A 只能 M0、B 只能 M1」）。JSON 浮点工时**不再被 int 静默截断**，而是由校验器拒绝——静默截断会让「输入有误」伪装成「输入正常」。

## 7. 枚举 oracle：什么时候能称 optimum

对应文件 [oracle.py](../projects/01_scheduling_core/scheduling_algorithms/oracle.py)。

`exhaustive_optimum` 只支持**每作业一道工序**，遍历 `n!` 个排列与全部指派的笛卡尔积：

```text
n=4、每任务 m=2 台资格  →  24 × 16 = 384 个组合
n=5                     →  120 × 32 = 3 840
n=8                     →  40 320 × 256 = 10 321 920   ← 超过 limit=100_000，拒绝运行
```

**为什么这里的枚举结果可以称为 `optimum`？**

```text
固定每台机器上的任务顺序后，按释放时间尽早启动不会使 Cmax / ΣT / ΣwC 变差；
这三个目标都是「完成时间的非减函数」，提早完成只会更好或不变。
遍历全部机器指派 × 每台机器的顺序，即覆盖最优解所需的全部决策。
全局排列会重复覆盖某些并行顺序，但不会漏掉。
```

**这个论证的三条边界**（必须一并记住）：

1. **只对「完成时间单调」的目标成立**。换一个含**提前惩罚**的目标，最优解可能需要**故意延后**，上面的论证立刻失效；
2. **只对单工序实例成立**，多工序输入直接拒绝（`ValueError`）；
3. **组合数超过 `limit` 时拒绝运行**，不能拿受限枚举冒充整个问题的 `optimum`。

oracle **自己维护机器可用时刻，不调用 `decode`**。测试另用 `Candidate + decode` 遍历同样的决策空间，比较两者的最小值——这是一次真正的**交叉验证**。但两者**共享领域模型与目标公式**，所以目标公式本身仍需要 Week 1 的手算提供另一层独立证据。

> **「一个启发式在某实例上追平了枚举最优值」≠「该启发式具有全局最优保证」。** 前者只是**一例上的事实**（实验观察），后者是**理论结论**。

## 8. 测试证据

| 本周要求 | 证据 |
|---|---|
| 三类解表示与解码轨迹 | `test_three_decoder_traces`（3 条精确时间轨迹） |
| swap / insert / 机器指派 | `test_moves_and_boundaries` |
| 至少五类非法排程 | `test_independent_validator_corruption`（**九类**） |
| 可复现输入、JSON/CSV | `test_roundtrip_and_csv` |
| 至少五个小例枚举 | `test_five_independent_enumerations`（seed 0–4，每例 384 组合） |

复跑命令：

```bash
cd projects/01_scheduling_core
python -m pytest -q
```

或只跑本周相关的一组：

```bash
python -m pytest tests/test_month1.py -k 'decoder or moves or corruption or enumeration or roundtrip' -v
```

## 9. 接口约定（API Contract）

```python
# 候选解
Candidate(order, assignments)
validate_candidate(instance, candidate) -> None

# 解码
decode(instance, candidate) -> Schedule
initial_candidate(instance) -> Candidate          # LPT 优先级 + 最早完工指派

# 邻域
swap(candidate, i, j) -> Candidate
insert(candidate, i, j) -> Candidate
reassign(instance, candidate, index, machine) -> Candidate
neighbors(instance, candidate) -> Iterator[Candidate]

# 独立验证
schedule_errors(instance, schedule) -> list[str]
validate_schedule(instance, schedule) -> None

# 输入生成
generate_instance(seed, jobs=12, machines=3, operations_per_job=1,
                  release_max=10, due_factor=1.5) -> Instance

# 精确参考
exhaustive_optimum(instance, objective="makespan", limit=100_000)
    -> tuple[float, Schedule, int]                # (最优值, 一个最优排程, 枚举个数)
```

**贯穿全周的一条链**：

```text
Instance → Candidate → decode → Schedule → validate_schedule → objective
```

任何一次「完整评价」都必须走完这条链：**解码 → 独立验证 → 目标计算**。不允许某个算法跳过验证，也不允许它使用自己的一套目标公式——否则不同算法之间无法公平比较。

## 10. 确定性契约

```text
相同 Instance + 相同 Candidate  →  相同 Schedule
```

本周新增的确定性来源：

```text
机器指派平局:    candidate.assignments 的位置对齐 instance.operations（不随 order 变化）
邻域扫描顺序:    swap → insert → reassign，固定顺序，按 seen 去重
reassign 候选序: eligible_machine_ids 按 sorted() 升序
oracle 平局:     严格小于才更新，保留首次找到的最优
```

Week 1 的 `job.id` 升序 / `machine.id` 升序仍然有效，两者叠加构成完整的**可复现性契约**。

## 11. 已知局限与隐含假设

```text
表示:        order 是优先级而非拓扑序 → 表示冗余，搜索空间计数 ≠ 不同时间表数
解码:        追加式，不向机器已有空隙插入 → 有构造偏置，可能损失解质量
             每步线性扫描 → 约 O(n²)
机器时长:    同质（同一工序在所有合格机器上工时相同）→ 不支持 Q / R
约束:        不可抢占、作业内线性工序链、支持释放时间与机器资格
             无 setup、无维护日历、无工人容量、无动态事件
生成器:      默认全机器资格；交期相对自身工时定义
oracle:      仅单工序；仅完成时间单调目标；组合数上限 100_000
```

这些是**明确的模型或实现边界**，不能靠「在同一分布上多跑几个测试」消除——要改的是模型，不是测试数量。

## 12. 遗留问题

| # | 问题 | 状态 |
|---|---|---|
| 1 | 所有搜索方法如何共享同一套评价预算？ | 已由 Week 3 的 `SearchConfig` / `SearchResult` 落地 |
| 2 | 邻域的存储成本随 `n²` 增长怎么办？ | SA 改用随机移动，不枚举整个邻域（Week 3） |
| 3 | 多工序实例能否被搜索流水线覆盖？ | 已由 `routes_12` 实例贯穿（Week 4） |
| 4 | 枚举只能覆盖极小实例，大实例的参考值从哪来？ | 本批次 best-known，明确不称 `optimum`（Week 4） |
| 5 | 若 precedence 从「线性链」改成任意边集？ | **当前结构就不够了**：线性链因 `operation_ids` 唯一而不可能成环，任意边集需要新增**环检测** |
| 6 | 追加解码不填空隙，损失多少解质量？ | 未做消融实验，列为后续工作 |

第 5 条值得强调：**当前结构合法，不代表未来任意 precedence 图都合法。** 一个线性工序链天然无环，是因为每个工序只出现一次；一旦允许多前驱 / 多后继的任意有向图，就必须显式检测环，否则会出现「永远没有就绪工序」的死锁。

## 13. 待个人完成

1. **不用 decoder**，手工构造一个包含机器重叠的 `Schedule`，解释验证器会给出哪条诊断、为什么。
2. 手推 Day 2 的三条解码轨迹，确认不运行代码也能写出每道工序的机器与起止时刻。
3. 构造一个 `order` 不同但 `Schedule` 相同的例子，说明表示冗余的含义。
4. 用 `generate_instance` 生成 `jobs=6` 与 `jobs=24` 的实例，比较总工时，并解释「大实例的目标更大」为什么不等于「算法更差」。
