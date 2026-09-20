# Day 2：First Improvement 与停止条件

> 当日主题：理解局部最优是相对于邻域的结论
> 当日产出：**First Improvement（首个改善即移动）** + 扫描顺序与停止条件实验脚本
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 写出邻域 N(x) 的定义，并说明「邻域不是算法」这句话的确切含义。
2. 用一句话说清 First Improvement 与 Best Improvement 的唯一区别（什么时候移动）。
3. 写出 First 的一轮：固定顺序扫描、遇到严格改善立即移动、然后对新解重新扫描。
4. 区分三种停止结果：`LOCAL_OPTIMUM`、`BUDGET`、以及「邻域为空导致的立即停止」。
5. 解释等值候选为什么不被接受，以及这如何避免在平台上原地游走。
6. 手算单机 p=[3,1,2]、w=1 的逐次扫描与逐评价记账。
7. 解释为什么 `seed` 不改变 First 的结果，以及「三个种子跑出同一个值」为什么不是 bug。

---

## 2. 为什么「邻域」不是「算法」

**定义**：给定一个候选解 x，它的**邻域** N(x) 是所有对 x 做一次允许移动（move）能得到的新候选解集合。

```text
N(x) = { y | y = move(x)，且 move 在本月允许的移动集合里 }
```

本月的移动集合在 [neighborhoods.py](../../projects/01_scheduling_core/scheduling_algorithms/neighborhoods.py) 里，只有三种：

| 移动 | 改变什么 | 不改变什么 |
|---|---|---|
| `swap(candidate, i, j)` | 优先级排列中第 i、j 位的顺序 | 机器指派 |
| `insert(candidate, i, j)` | 把第 i 位元素挪到结果的第 j 位 | 机器指派 |
| `reassign(instance, candidate, i, machine)` | 第 i 道工序的机器 | 整个优先级排列 |

关键的**理论结论**：

> **邻域决定「能走到哪里」，算法决定「怎么选下一步」。两者是正交的。**

同一个 N(x) 可以喂给三种完全不同的策略：

| 策略 | 选择方式 | 一次移动要评价多少邻居 |
|---|---|---|
| First Improvement | 遇到第一个严格改善就移动 | 1 ～ 整个邻域 |
| Best Improvement | 扫完整个邻域，取最好的那个 | 整个邻域 |
| Simulated Annealing | 随机抽一个邻居，按概率接受 | 1 |

所以「我的邻域比你的算法强」是一句无意义的话。**换邻域和换算法是两个独立实验**：只换移动集合，三种策略的表现会一起变；只换策略，邻域大小和结构不变。任何构建在 `neighbors` 之上的方法都复用今天这一份，唯一变化的是「怎么选」。

`neighbors` 的其中一个设计也值得先记住：它**只产生新 `Candidate`，从不修改传入的 x**。`Candidate` 是 `frozen` 的，`swap` / `insert` / `reassign` 都通过 `dataclasses.replace` 返回新对象。这保证了「父解在扫描过程中绝不被污染」——否则「当前解」会在你不知道的地方变掉。

---

## 3. 一轮 First Improvement 的精确语义

### 3.1 伪代码

```text
评价初始解（计数 = 1）
while 还有预算:
    从头扫描 N(current)
    遇到第一个严格改善的邻居 y  ->  接受 y，回到 while 开头重新扫描
    完整扫描都没有严格改善      ->  LOCAL_OPTIMUM，停止
    扫描被预算打断              ->  BUDGET，停止（不能说已证明局部最优）
```

三句话概括：**顺序扫描、见好就收、收完重扫。**

### 3.2 四个必须说准的细节

1. **「严格改善」是 `<`，不是 `<=`。** 代码里是 `improved = score < chosen_value`。等值候选不算改善。
2. **移动到 y 之后要重新扫描 y 的邻域**，而不是继续扫 x 剩下的邻居。因为 y 的邻居和 x 的邻居几乎没有关系，继续扫旧列表等于在一个已经不存在的点上做决策。
3. **First 不需要证明 y 是这一轮最好的邻居。** 它只需要知道「y 比 x 好」。这正是它便宜的原因：可能第 1 个邻居就中，也可能扫到最后一个才中。
4. **「局部最优」是相对邻域的结论。** `LOCAL_OPTIMUM` 的完整含义是「在我这个 N(x) 里没有比当前更好的解」，而不是「在全局没有更好的解」。换一个邻域，同一个解可能立刻不再是局部最优。

### 3.3 代码映射

对应文件 [search.py](../../projects/01_scheduling_core/scheduling_algorithms/search.py) 的局部搜索分支。

```python
scan_current = current
chosen, chosen_value = current, value
for candidate in neighbors(instance, current):
    if len(trace) >= config.budget:
        break
    schedule, score = evaluate(candidate)
    improved = score < chosen_value
    if improved:
        chosen, chosen_value = candidate, score
    if config.algorithm != "best" and improved:
        current, value = chosen, chosen_value
    record(candidate, schedule, score, config.algorithm != "best" and improved)
    if improved and config.algorithm != "best":
        break          # ← First 的全部区别就在这一行
moved = chosen != scan_current
```

注意 `for candidate in neighbors(instance, current)` 里的 `current` 在生成器创建时就被绑定，所以即使循环体内把 `current` 改成了 y，循环仍然在扫 x 的邻居列表——但 First 会立刻 `break`，所以这个细节不会造成行为差异。

---

## 4. 停止条件、等值与确定性

### 4.1 `LOCAL_OPTIMUM` 与 `BUDGET`

扫描结束后的判断顺序（**实现观察**，顺序决定了状态标签）：

```text
1. 预算已用尽              -> break，status 保持 BUDGET
2. 否则若「一步都没动」     -> status = LOCAL_OPTIMUM，break
3. 否则（动了）             -> 回到 while 开头，重新扫描
```

第 1 条排在前面，这带来一个容易被忽略的后果：**如果一次干净扫描刚好把预算用完，状态仍然是 `BUDGET`**。第 7 节的实验里，`budget=9` 与 `budget=12` 的目标值都是 10，但只有后者能拿到 `LOCAL_OPTIMUM`——因为前者在扫到第 3 个邻居时预算就断了，剩下的 2 个邻居没被看过。

> **这正是「预算截断时必须保守」的原因：没看过的邻居里完全可能有更好的解。**

对应的自测题答案要记牢：**扫描 100 个邻居后因预算停止、没找到更好解，只有在「这 100 个邻居已经覆盖了完整邻域」时才构成局部最优的证据；代码保守地把预算边界一律标成 `BUDGET`。**

### 4.2 等值候选不接受

`improved = score < chosen_value` 用的是严格小于。等值候选被拒绝有两个后果：

- **好的一面**：不会沿着目标值不变的长平台一路漂移，把预算烧在零收益的移动上。
- **代价**：如果最优解必须穿过一段等值平台才能到达，First 永远到不了。这时需要 SA 那种「允许等值甚至更差」的移动。

### 4.3 扫描顺序敏感，但 `seed` 无关

`neighbors` 的产出顺序是**固定**的：

```text
for i in range(n):
    for j in range(n):
        swap(i, j)      # 先交换
        insert(i, j)    # 再插入，跳过与已产出候选重复的
然后 for 每道工序（按 instance.operations 顺序）:
    for 每台合格机器（按 machine.id 升序）:
        reassign(...)
```

因此：

1. **First 对扫描顺序敏感**：同样的邻域，只把 `(swap, insert)` 换成 `(insert, swap)`，第一个被接受的邻居可能完全不同，最终停下的局部最优也可能不同。这是**理论结论**（由 First 的定义直接推出），不是实现缺陷。
2. **`seed` 不改变 First 的结果**：First 的代码路径里**根本没有用到 `rng`**。`rng = Random(config.seed)` 会被创建，但只在 `random` / `sa` 提议和 Multi-start 重启时使用。所以同一个实例、不同种子跑出完全相同的结果是**合理现象**，不是 bug。

月末批次可以直接验证第 2 点（**实验观察**，来自 [results.csv](../../projects/01_scheduling_core/artifacts/month1_refactored/results.csv)）：`single_12` 上 `first` 的三个种子都是 575、150 次评价；`routes_12` 上 `first` 与 `best` 的三个种子都是 41。**只要算法不掷骰子，换种子不会换结果。**

### 4.4 空邻域必须立即停止

最危险的边界是**邻域为空**：

```text
空实例（没有任何工序）        -> N(current) = 空集
单个工序、只有一台合格机器     -> swap/insert/reassign 都只能得到自身，去重后为空集
```

如果代码写成「循环扫描直到找到改善」，这两种情况会变成死循环。本实现不会，因为：

1. `neighbors` **去重并排除自身**，空邻域时 `for` 循环体一次都不执行；
2. 循环体不执行 ⇒ `trace` 不增长 ⇒ 靠 `len(trace)` 的预算判断永远等不到结束；
3. 所以必须靠**循环外**的判断兜底：`moved = chosen != scan_current` 为 `False`，走 4.1 的第 2 条直接 `LOCAL_OPTIMUM` 退出。

> **结论**：空邻域的解**本身就是**它自己邻域内的局部最优。这不是异常，而是定义直接给出的结果。

对 `multistart` 则走另一条路：它看到 `not moved` 会**先重启**（重启评价 1 次），所以 `trace` 每轮都在增长，预算耗尽后正常结束。`test_singleton_and_empty_terminate` 就是为这两种极端输入写的（`singleton` 共 6 条，覆盖全部六个算法）。

---

## 5. 手算 / 示例：单机 p=[3,1,2]

### 5.1 输入

| Job | `pj` | `wj` | 合格机器 |
|---|---:|---:|---|
| A | 3 | 1 | `M0` |
| B | 1 | 1 | `M0` |
| C | 2 | 1 | `M0` |

目标 `weighted_completion_time`（ΣwC）。因为 `w = 1`，ΣwC 就等于 ΣCj。单机、无释放时间，所以**顺序即时间表**，`Cmax = Σp = 6` 恒定。

### 5.2 初始解 ABC

```text
A: 0 -> 3
B: 3 -> 4
C: 4 -> 6
C = [3, 4, 6]
ΣwC = 1*3 + 1*4 + 1*6 = 3 + 4 + 6 = 13
```

### 5.3 邻居 BAC

```text
B: 0 -> 1
A: 1 -> 4
C: 4 -> 6
C = [1, 4, 6]
ΣwC = 1 + 4 + 6 = 11     ← 11 < 13，严格改善，First 立即接受
```

这里要特别注意：First **不需要**知道「BAC 是 ABC 这一轮邻居里最好的」。事实上 ABC 的邻居里 BCA 值 10，比 BAC 还好，但 First 不看——它只看「第一个比当前好的」。

### 5.4 从 BCA 出发（p 顺序 1,2,3）

```text
B: 0 -> 1
C: 1 -> 3
A: 3 -> 6
C = [1, 3, 6]
ΣwC = 1 + 3 + 6 = 10
```

从 BCA 出发的**完整**邻居扫描（含全部 5 个去重排列）：

| 邻居 | 时间表 `C` | ΣwC | 是否严格改善 |
|---|---|---:|---|
| CBA | 2, 3, 6 | 11 | 否 |
| ACB | 3, 5, 6 | 14 | 否 |
| CAB | 2, 5, 6 | 13 | 否 |
| BAC | 1, 4, 6 | 11 | 否 |
| ABC | 3, 4, 6 | 13 | 否 |

5 个邻居全部 ≥ 10 ⇒ **完整扫描无严格改善** ⇒ `LOCAL_OPTIMUM`，停在 ΣwC = 10。

### 5.5 逐评价对比表

| 阶段 | 起点 | 评价次数 | ΣwC | 结果 |
|---|---|---:|---:|---|
| 初始化 | —— | 1 | 13 | `trace[0]`，`accepted=True` |
| 第一轮 | ABC | 2 | 11 | 第 1 个邻居 BAC 即严格改善，接受 |
| 第二轮 | BAC | 6 | 10 | 扫到第 4 个邻居 BCA 才改善，接受 |
| 第三轮 | BCA | 11 | 10 | 完整扫描 5 个邻居，无一严格改善 → `LOCAL_OPTIMUM` |

**最后一行的 10 是不是全局最优？** 在这个实例上是——单机、`w = 1` 时 SPT 对 `1||ΣCj` 最优，而 BCA 恰好就是 SPT 顺序（p = 1, 2, 3）。但这是**理论结论只对这个特定问题成立**：换成带 `rj`、带权重、或者多机，`LOCAL_OPTIMUM` 与全局最优就再也没有这种关系。第 7 节的脚本会独立枚举 6 个排列确认最小值为 10，作为**实验观察**的证据。

---

## 6. 实现：`neighborhoods.py` 与 `search.py`

### 6.1 邻域的边界处理

```python
def _indices(candidate: Candidate, i: int, j: int) -> None:
    if not (0 <= i < len(candidate.order) and 0 <= j < len(candidate.order)):
        raise IndexError("move indices outside permutation")
```

三条边界约定：

- `swap` / `insert` 的索引越界抛 `IndexError`，而不是静默钳位。静默钳位会让「移动根本没发生」和「移动发生了但结果相同」变得无法区分。
- `reassign` 要求目标机器在 `eligible_machine_ids` 里，否则抛 `ValueError`。**非法指派在邻域入口就被挡掉**，不会流到解码器。
- `i == j` 时 swap/insert 返回等值候选，`neighbors` 再把它去重掉，所以「原地移动」不会进入扫描列表。

`neighbors` 的去重是**必要的**：`swap(i, i+1)` 与 `insert(i, i+1)` 产生的排列**完全相同**，相邻交换也会与 insert 重合。所以「swap 有 n(n−1)/2 个位置对、insert 有 n(n−1) 个有向移动」不能简单相加当作邻域大小——必须去重后才知道真实规模。

### 6.2 局部搜索分支的结构

`first` 与 `best` 共用同一个 `else` 分支，区别只有两处：

| 位置 | `first` | `best` |
|---|---|---|
| 循环内是否立即移动 | `if config.algorithm != "best" and improved:` 移动并 `break` | 不移动，继续扫完 |
| 循环结束后 | 已经移动过，`start` 不变 | 用 `chosen` 统一移动一次 |

Best 的「一轮」因此在 `trace` 里表现为一串 `current` 不变、`proposed` 各异的记录，最后一条记录的 `accepted` 才表示这一轮是否真的移动了。

### 6.3 为什么 `moved` 要用比较，而不是布尔标志

```python
moved = chosen != scan_current
```

如果用一个「本轮是否接受过」的布尔量，并且忘了每轮重置，就会退化成 4.4 节说的死循环：上一轮置过 `True`，下一轮即使邻域为空也认为「动了」，于是 `while` 永远不退出。**用「当前解和扫描起点是否同一个对象」来推断，天然不可能携带陈旧状态。**

### 6.4 邻域到底有多大

在单机、每道工序只有一台合格机器的实例上，`reassign` 只能得到自身，邻域就是「一次 swap 或一次 insert 能到达的**去重排列**」。把 `len(list(neighbors(...)))` 真实数出来（**实验观察**）：

| `n` | 去重邻居数 | `n!` |
|---:|---:|---:|
| 2 | 1 | 2 |
| 3 | 5 | 6 |
| 4 | 12 | 24 |
| 5 | 22 | 120 |
| 6 | 35 | 720 |
| 7 | 51 | 5040 |

**理论结论**：这个数有闭式解

```text
|N(x)| = C(n, 2) + (n-1)^2 - (n-1) = (n-1)(3n-4)/2
        ↑ 交换      ↑ 插入      ↑ 相邻交换与 insert 重合的部分
```

代入 `n=3` 得 `2 × 5 / 2 = 5`，`n=7` 得 `6 × 17 / 2 = 51`，与上表逐行吻合。

两条直接推论：

1. **邻域大小是 O(n²)，不是 O(n!)。** 所以「扫描整个邻域」在小实例上完全可以承受，但代价仍然随规模平方增长。
2. **不能把 `C(n,2)` 与 `n(n−1)` 直接相加。** 相邻交换（如 `swap(0,1)`）与插入（如 `insert(0,1)`）会产生同一个排列，必须先减去这个重合部分，否则会高估邻域规模，进而算错「一轮扫描需要多少预算」。

---

## 7. 实验：`m1w3d2_first`

对应脚本 [m1w3d2_first.py](../../projects/01_scheduling_core/examples/m1w3d2_first.py)，在项目目录下运行：

```bash
python examples/m1w3d2_first.py
```

脚本打印输入、初始解的算术、`neighbors` 的真实扫描顺序、逐评价轨迹，以及「预算截断 vs 完整扫描」的对照。实际输出（节选）：

```text
== 1. 输入：单机 p=[3,1,2]，w=1，目标 ΣwC ==
  Job  A  B  C
  p    3  1  2
  w    1  1  1
  Σp = 6，单机 Cmax 恒为 6

== 2. 初始解 ABC ==
  A:0->3  B:3->4  C:4->6  →  ΣC = 3+4+6 = 13.0

== 3. 邻域扫描顺序（neighbors 的固定产出顺序）==
  从 ABC 出发: BAC(11)  CBA(11)  BCA(10)  ACB(14)  CAB(13)
  从 BCA 出发: CBA(11)  ACB(14)  CAB(13)  BAC(11)  ABC(13)
  邻域 = 5 个去重排列（单资格机器，reassign 只会得到自身）
```

逐评价轨迹（`budget=12`，显式传入初始解 `ABC`）：

```text
== 4. First Improvement 逐评价轨迹（budget=12, 显式传入初始解）==
  evaluation  proposed  current  best  accepted
           1      13.0     13.0  13.0  True
           2      11.0     11.0  11.0  True
           3      13.0     11.0  11.0  False
           4      13.0     11.0  11.0  False
           5      14.0     11.0  11.0  False
           6      10.0     10.0  10.0  True
           7      11.0     10.0  10.0  False
           8      14.0     10.0  10.0  False
           9      13.0     10.0  10.0  False
          10      11.0     10.0  10.0  False
          11      13.0     10.0  10.0  False
  最终 order=('B', 'C', 'A')  objective=10.0  status=LOCAL_OPTIMUM

== 5. 预算截断 vs 完整扫描 ==
  budget=9 : evaluations=9 objective=10.0 status=BUDGET
  budget=12: evaluations=11 objective=10.0 status=LOCAL_OPTIMUM

== 6. 独立枚举：本实例的全局最优 ==
  6 个排列的最小 ΣwC = 10，对应 order=('B', 'C', 'A')
```

**实验观察**（全部来自上面的真实输出）：

1. 第 2 次评价就接受 BAC：扫描顺序里它排第一，值 11 < 13。**First 的「运气」完全由扫描顺序决定。**
2. 第 3～5 次评价是 13、13、14：这些是 BAC 的邻居，都 ≥ 11，所以全部拒绝；第 6 次评价 BCA 得 10，才再次移动。
3. 第 7～11 次评价是 BCA 的 5 个邻居（11、14、13、11、13），没有严格改善 ⇒ 第 11 次评价之后 `status=LOCAL_OPTIMUM`，`evaluations=11 < budget=12`——它是**提前停止**的。
4. `budget=9` 时目标值同样是 10，但状态是 `BUDGET`：扫描被预算打断，代码没有看过剩下 2 个邻居，所以**不敢声称局部最优**。这两行的对比就是第 4.1 节的实验证据。

复跑测试（在项目目录下运行）：

```bash
python -m pytest tests/test_month1.py -k 'local_optimum or singleton' -v
```

共 7 条：`test_ls_local_optimum_and_sa_accepts_worse` 用 p=[1,2]、单机、初始 `Candidate(("O0","O1"),("M0","M0"))` 的**已经最优**候选，确认 `first` 与 `best` 都返回 `LOCAL_OPTIMUM` 且目标值为 4；`test_singleton_and_empty_terminate` 覆盖单元素与空实例在六个算法上的终止。

---

## 8. 今日练习

1. **练习 1（定义）**：写出 N(x) 的定义，并说明为什么「邻域」不能和「算法」混为一谈。举一个「换邻域不换算法」的实验例子。
2. **练习 2（手算）**：对 p=[4,2,3]、单机、w=1，从初始顺序 ABC 出发手工跑一遍 First，写出每一轮接受的邻居与评价次数，并标出最终状态是 `LOCAL_OPTIMUM` 还是 `BUDGET`（假设预算充足）。
3. **练习 3（边界）**：构造一个「扫描刚好用完预算」的场景，解释为什么即使目标值已经最优，`status` 也只能是 `BUDGET`。提示：把第 7 节的 `budget` 调成 11。
4. **练习 4（代码阅读）**：不看 `search.py`，写出局部搜索分支的伪代码，并说明 `moved = chosen != scan_current` 为什么比一个布尔标志更安全。
5. **练习 5（实验）**：在项目目录下运行 `python examples/m1w3d6_search.py`——它在同一个实例（`generate_instance(20, jobs=12, machines=1)`）与同样的 `budget=150` 下跑全部六个算法。对比输出里 `first` 与 `best` 两行的 `evaluations` 与 `status`，回答「相同预算、相同邻域，谁把评价花在了更多轮扫描上」。

---

## 9. 验收清单

- [ ] 能写出 N(x) 的定义，并说明 First / Best / SA 共用同一个邻域。
- [ ] 能写出 First 的一轮：固定顺序扫描、第一个严格改善就移动、移动后重新扫描。
- [ ] 能区分 `LOCAL_OPTIMUM` 与 `BUDGET`，并解释为什么预算截断时不能声称局部最优。
- [ ] 能解释等值候选不被接受的原因与代价。
- [ ] 能说明扫描顺序为什么影响 First 的结果，而 `seed` 为什么不影响。
- [ ] 能解释空实例与单元素单资格实例为什么必须立即停止，以及死循环会从哪里来。
- [ ] 能手算 p=[3,1,2]、w=1 的完整 First 过程（13 → 11 → 10）。
- [ ] 能用结果比较而不是循环次数解释「提前停止」与「跑满预算」的区别。
- [ ] 在项目目录下运行 `python examples/m1w3d2_first.py` 无报错，输出与第 7 节一致。
- [ ] 在项目目录下运行 `python -m pytest tests/test_month1.py -k 'local_optimum or singleton' -v` 全部通过。

---

## 10. 自测题

不看上文回答：

- Q1：什么是邻域 N(x)？为什么说「邻域不是算法」？
- Q2：First 与 Best 的唯一区别是什么？
- Q3：`improved` 用的是 `<` 还是 `<=`？等值候选为什么不被接受？
- Q4：`LOCAL_OPTIMUM` 与 `BUDGET` 分别在什么条件下产生？
- Q5：一次干净扫描刚好把预算用完时，状态是什么？为什么？
- Q6：First 对扫描顺序敏感吗？对 `seed` 敏感吗？为什么？
- Q7：换不同种子跑 First 得到完全相同的值，是 bug 吗？
- Q8：空实例或单工序单资格实例为什么不会陷入死循环？
- Q9：扫描 100 个邻居后因预算停止、没找到更好解，能否说已经局部最优？
- Q10：局部最优是相对什么的结论？举一个「这个解在 A 邻域里是局部最优、在 B 邻域里不是」的例子。

### 参考答案

- A1：N(x) 是对 x 做一次允许移动能得到的所有新解。邻域只定义「能走到哪里」，算法定义「怎么选下一步」；同一个邻域可以给 First、Best、SA 三种完全不同的策略使用。
- A2：什么时候移动。First 遇到第一个严格改善就移动并重新扫描；Best 扫完整个邻域，取最好的那个再移动一次。
- A3：`<`（严格改善）。等值候选会造成零收益的移动，在目标值不变的长平台上持续消耗预算；代价是必须先经过等值平台才能到达的更优解会被漏掉。
- A4：`LOCAL_OPTIMUM` 出现在「完整扫描过邻域且没有任何严格改善」之后；`BUDGET` 出现在预算被用尽（含扫描被预算中途打断）时。
- A5：`BUDGET`。因为判断顺序是先看预算、再看有没有移动，没看过的邻居里完全可能有更好的解。
- A6：对扫描顺序敏感——第一个改善的邻居取决于产出顺序，最终停下的局部最优也随之改变；对 `seed` 不敏感——First 的代码路径不使用 `rng`。
- A7：不是。`rng` 只在 `random` / `sa` 的提议和 Multi-start 的重启里使用，First 全程没有随机性。月末批次中 `first` 在三个种子上给出同一个值，正是这个结论的证据。
- A8：`neighbors` 去重并排除自身，空邻域时循环体一次也不执行；靠「当前解与扫描起点是否为同一对象」判断没动，直接返回 `LOCAL_OPTIMUM`。Multistart 则在 `not moved` 时先重启，每次重启消耗 1 次评价，所以预算照样耗尽。
- A9：不能。只有这 100 个邻居已经覆盖完整邻域时才构成局部最优的证据；代码保守地把预算边界一律标成 `BUDGET`。
- A10：局部最优是相对于**邻域**的结论。例如单机排序问题中，一个顺序在「只允许相邻交换」的邻域里可能是局部最优，但换成「允许任意插入」的邻域就能被进一步改善。

---

## 11. 今日一句话总结

> **First Improvement 的行为完全由两件事决定——邻域怎么排、什么时候停：它在固定扫描顺序下接受第一个严格改善的邻居并重新开始，只有走完一整轮干净扫描才敢说 `LOCAL_OPTIMUM`，而被预算截断时只能诚实地说 `BUDGET`。**
