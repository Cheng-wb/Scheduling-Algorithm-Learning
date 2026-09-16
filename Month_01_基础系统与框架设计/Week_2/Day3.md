# Day 3：swap、insert 与机器指派邻域

> 当日主题：把「邻域」从「搜索算法」里拆出来，定义三类移动与它们的边界
> 当日产出：**三类邻域算子与完整邻域生成器**（`neighborhoods.py` + 实验脚本）
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 说清楚「邻域」的定义：`N(x)` 是一组候选解，不是一个算法。
2. 解释为什么 First-improvement、Best-improvement、SA 可以共用同一套移动却表现不同。
3. 说出 swap、insert、reassign 三类移动各自改变什么、保持什么不变。
4. 准确说出 insert 的 `j` 与 reassign 的 `index` 各自的语义，避免差一位错误。
5. 掌握四类边界行为：越界抛异常、`i == j` 返回等值候选解、非法资格被拒绝、交换优先级不构成 precedence 违规。
6. 手推 ABCD 上的 `swap(0,2)` 与 `insert(0,2)`，以及 ABC 上的五个去重排列邻居。
7. 会算邻域规模：`swap = n(n−1)/2`、`insert` 去重后 `= (n−1)²`、两者合并去重后 `= (n−1)(3n−4)/2`。
8. 解释为什么「swap + insert」不能简单相加，以及为什么这个合并规模是 `O(n²)` 而不是 `n! − 1`。

---

## 2. 为什么 Day 3 要把「移动」和「算法」分开

前两天的流水线是「决策 → 时间」：

```text
Candidate(order, assignments) → decode → Schedule → objective → 数字
```

今天我们给这条流水线接上**第二个入口**：从「一个候选解」到「一批候选解」。

```text
                    Candidate
                        ↓
        ┌───────────────┴───────────────┐
        ↓                               ↓
     decode                       neighborhoods        ← 今天新增的一环
        ↓                               ↓
    Schedule                    {Candidate₁, Candidate₂, ...}
        ↓                               ↓（下一个算法日才接上）
    objective  →  数字           搜索策略：First / Best / SA / ...
```

为什么要把「移动」单独抽成一层，而不是直接在搜索算法里写 `order[i], order[j] = ...`？

1. **同一套移动会被多种搜索策略复用。** First-improvement、Best-improvement、模拟退火（SA）用的是**同一批邻居**，区别只在「如何从邻居里挑下一个当前解」。把移动写在算法内部，等于把同一段代码抄三遍。
2. **移动是纯函数，最容易单独测试。** `swap(candidate, i, j)` 不依赖任何搜索状态，输入一个 `Candidate`、输出一个新 `Candidate`（Day 1 的不可变约定）。这类函数可以逐条断言，而「搜索跑出来的结果」很难断言。
3. **邻域的组合决定了搜索能走到哪里。** 只改顺序的邻域走不到「换一台机器」的解，只改机器的邻域走不到「重新排序」的解。**邻域的形状是搜索能力的上限**，必须能被单独拿出来讲清楚。

一句话：**邻域回答「能走到哪些解」，搜索策略回答「往哪走」，两件事必须分开设计。**

---

## 3. 三种移动

实现见 [neighborhoods.py](../../projects/01_scheduling_core/scheduling_algorithms/neighborhoods.py)。三类移动在 ABCD 上的效果：

| 操作 | ABCD 的示例 | 改变什么 | 保持不变 |
|---|---|---|---|
| `swap(0,2)` | **CBAD** | `order` 中两个位置互换 | 机器指派、`order` 长度 |
| `insert(0,2)` | **BCAD** | `order` 中一个元素整体挪位 | 机器指派、`order` 长度 |
| `reassign(op_index, machine)` | `order` 完全不变 | 某一个位置的机器 | 其余工序的机器与整个 `order` |

### 3.1 `swap(i, j)`：交换两个位置

```python
def swap(candidate: Candidate, i: int, j: int) -> Candidate:
    _indices(candidate, i, j)
    order = list(candidate.order)
    order[i], order[j] = order[j], order[i]
    return replace(candidate, order=tuple(order))
```

`swap` 是**对合**（involution）：交换两次回到原样。这一点被测试直接断言（`swap(swap(candidate, 0, 2), 0, 2) == candidate`），也是 Week 4 里「交换两次恢复」这条回归检查的来源。

### 3.2 `insert(i, j)`：把一个元素挪到另一个位置

```python
def insert(candidate: Candidate, i: int, j: int) -> Candidate:
    """把原位置 i 的元素移到结果的 j 位置。"""
    _indices(candidate, i, j)
    order = list(candidate.order)
    order.insert(j, order.pop(i))
    return replace(candidate, order=tuple(order))
```

**`j` 是「移除之后插入的最终下标」，不是「原下标 j 之前」。** 这是最容易差一位的地方：

```text
ABCD 上 insert(0,2)：pop(0) 取走 A → [B,C,D]；insert(2, A) → [B,C,A,D] = BCAD
A 最终落在下标 2 上 ✓ 与「最终下标」的说法一致
```

若误以为 `j` 指「原数组里第 j 个元素之前」，就会算出 `[B,A,C,D]`（那是 `insert(0,1)` 的结果）。**Python 的 `list.insert` 作用在已经 `pop` 过的列表上**，所以实现天然满足「最终下标」语义。

### 3.3 `reassign(instance, candidate, index, machine)`：改一台机器

```python
def reassign(instance, candidate, index, machine) -> Candidate:
    if not 0 <= index < len(instance.operations):
        raise IndexError("operation index outside instance")
    if machine not in instance.operations[index].eligible_machine_ids:
        raise ValueError("illegal assignment")
    assignments = list(candidate.assignments)
    assignments[index] = machine
    return replace(candidate, assignments=tuple(assignments))
```

两个语义要点：**`index` 是 `instance.operations` 中的位置，不是 `order` 中的位置**（与 Day 1 的 `assignments` 对齐约定一致）；**`reassign` 是唯一需要 `instance` 参数的移动**，因为「这台机器合不合格」必须对照输入的 `eligible_machine_ids` 才能判断，而 `swap` / `insert` 只碰 `order`。

### 3.4 三类移动的共同点

三点必须一致：**都返回新对象**（`dataclasses.replace`），父解原封不动；**都属于单点修改**，只改 `Candidate` 的一个字段；**都不检查移动之后解的质量**——邻域算子只负责「产出合法邻居」，好不好的事交给 objective 与搜索策略。

---

## 4. 边界、去重与规模

### 4.1 四类边界行为

| 情形 | 行为 | 理由 |
|---|---|---|
| `i` 或 `j` 为负、或 `≥ n` | `IndexError` | 位置不存在，静默裁剪会掩盖调用方的错误 |
| `i == j` | 返回等值候选解 | 数学上「移动到自己」是恒等变换，是合法结果 |
| `reassign` 到不合格机器 | `ValueError` | 违反输入的 `eligible_machine_ids`，属于非法解 |
| `reassign` 的 `index` 越界 | `IndexError` | 指向了不存在的工序 |

`swap` 与 `insert` 共用同一个检查函数：

```python
def _indices(candidate: Candidate, i: int, j: int) -> None:
    if not (0 <= i < len(candidate.order) and 0 <= j < len(candidate.order)):
        raise IndexError("move indices outside permutation")
```

**为什么 `i == j` 返回等值候选解而不是报错？** 因为 `neighbors()` 需要它。邻域生成器用双重循环遍历所有 `(i, j)` 组合，包括 `i == j`；`swap(i, i)` 与 `insert(i, i)` 都产出「与原解相等」的候选解，被去重逻辑自然丢掉。**如果这里抛异常，生成器就要写一堆 `if i != j` 的防护**——用「返回值」表达「无效果」，比用「异常」表达更贴合生成器的使用方式。

### 4.2 交换优先级不等于 precedence 违规

`order = ("A","B","C")`（A 是 B 的前驱）经 `swap(0,1)` 变成 `("B","A","C")`——B 跑到了前驱 A 的前面。**这不是违规**：Day 2 已经说明 `order` 是优先级列表，decoder 会跳过前驱尚未排定的工序，实际构造顺序仍是 A → B。测试对这一点有直接保障：完整邻域里的每一个邻居都要能 `decode` 出通过 `validate_schedule` 的可行排程。

> **记住这条：`order` 没有「非法排列」的概念，任何工序 ID 的全排列都是合法候选解。** 会不会产生坏排程是 decoder 的事，不是邻域的事。

### 4.3 完整邻域的扫描顺序与去重

`neighbors(instance, candidate)` 是一个生成器，固定做三件事：

```python
def neighbors(instance, candidate) -> Iterator[Candidate]:
    seen = {candidate}                     # 自身先进去，避免产出自身
    for i in range(len(candidate.order)):
        for j in range(len(candidate.order)):
            for moved in (swap(candidate, i, j), insert(candidate, i, j)):
                if moved not in seen:
                    seen.add(moved)
                    yield moved
    for i, op in enumerate(instance.operations):
        for machine in sorted(op.eligible_machine_ids):
            moved = reassign(instance, candidate, i, machine)
            if moved not in seen:
                seen.add(moved)
                yield moved
```

三个设计点：

1. **扫描顺序固定**：先 `swap` 再 `insert`，最后 `reassign`（机器按 `sorted()` 遍历）。固定顺序是「同一输入得到同一邻居序列」的前提。
2. **`seen` 集合去重、初始含自身**：`Candidate` 可哈希（Day 1 第 4 节），所以能直接放进 `set`。ABC 上 `swap(0,1)`、`insert(0,1)`、`insert(1,0)` 都得到 `BAC`，只产出一次；`i == j` 的移动与「reassign 到当前机器」产出的原解也在这里被滤掉。
3. **生成器而不是列表**：调用方可以随时 `break`，不必先付完整个邻域的内存与时间（第 6.3 节）。

### 4.4 规模：swap、insert 与它们的交集

设 `order` 长度为 `n`：

```text
swap 的不同结果 = n(n−1)/2        每对位置只算一次（(i,j) 与 (j,i) 同结果）
insert 的原始有向移动 = n(n−1)     每个 (i, j)、i ≠ j 算一个
insert 的不同结果 = (n−1)²         n−1 个元素各可放到 n−1 个「别的位置」
两者的重合 = n−1                   相邻位置对：insert(i,i+1) = insert(i+1,i) = swap(i,i+1)
合并去重后 = n(n−1)/2 + (n−1)² − (n−1) = (n−1)(3n−4)/2
```

实测（第 5.3 节表格）：`n = 4` 时是 `6 + 9 − 3 = 12`。

> **不能把两者简单相加当作去重后大小。** `n = 4` 时 `6 + 9 = 15`，真实规模是 12——差出来的 3 就是相邻交换。

### 4.5 这个规模是 `O(n²)`，不是 `n! − 1`

`(n−1)(3n−4)/2` 是二次多项式，而全排列有 `n!` 个：`n = 4` 时邻域只有 12 个邻居，全排列有 23 个——**swap + insert 远远够不到整个排列空间**。好的一面是一步扫描只需 `O(n²)`；要记住的一面是「邻域里没有更好的解」不等于「没有更好的解」。

### 4.6 装配完整的邻域

把三类移动合起来，本仓库的完整邻域是：

```text
N(candidate) = { swap(i,j) } ∪ { insert(i,j) } ∪ { reassign(op_index, machine) }
                ↑ 排列移动（(n−1)(3n−4)/2 个）  ↑ 指派移动（Σ(资格数) 个）
```

以 ABC 实例（A 只能 M0，B、C 各两台资格）为例：排列侧 5 个 + 指派侧 2 个 = **7 个邻居**（第 5.2 节逐条列出）。注意「指派侧 2 个」不是「3 × 2 = 6 个」——A 的资格集只有一个元素，`reassign` 到当前机器会产出原解被去重，所以只留下「B 改到 M0」「C 改到 M1」两个。

---

## 5. 手算：两个实例

### 5.1 输入

| 实例 | 构造 | 用途 |
|---|---|---|
| P | 四个单工序作业 A/B/C/D，`p` 都是 1，共用一台 M0 | 只观察排列邻域（单机时 `reassign` 不产生新解） |
| R | Week 2 起一直使用的两作业三工序实例：A(p=3, r=2, 仅 M0) → B(p=2, 两台资格)；C(p=1, r=0, 两台资格) | 观察完整邻域（排列 + 指派） |

### 5.2 手推：ABCD 上的两类排列移动

```text
base = ABCD

swap(0,2)：位置 0 与 2 互换 → C B A D          索引 0 与 2 的元素对调
insert(0,2)：pop(0) 得 A，剩余 [B,C,D]，
             insert(2, A) → B C A D            A 落在最终下标 2

两者不同：swap 把 C 也带到了下标 0；insert 只挪 A，其余元素相对顺序不变。
```

再手推一组重合：

```text
insert(0,1)：pop(0) 得 A，剩余 [B,C,D]，insert(1, A) → B A C D
swap(0,1)：位置 0 与 1 互换 → B A C D
```

**相邻位置的 insert 与 swap 完全等价**，这就是第 4.5 节 `overlap = n−1` 的来源。

### 5.3 手算：邻域规模

```text
n = 3：swap 3 个（(0,1)/(0,2)/(1,2)）
       insert 原始 6 个（i≠j），去重后 4 个（(n−1)² = 4）
       重合 2 个（相邻对 (0,1)、(1,2) 各一个交换）
       合并去重 = 3 + 4 − 2 = 5

n = 4：swap 6 个
       insert 去重 9 个（(n−1)² = 9）
       重合 3 个
       合并去重 = 6 + 9 − 3 = 12
       （而全排列有 4! − 1 = 23 个邻居，邻域只覆盖其中一半）
```

| n | swap | insert 原始 | insert 去重 | **合并去重** | 直接相加（错） | 重合 |
|---:|---:|---:|---:|---:|---:|---:|
| 3 | 3 | 6 | 4 | **5** | 7 | 2 |
| 4 | 6 | 12 | 9 | **12** | 15 | 3 |
| 5 | 10 | 20 | 16 | **22** | 26 | 4 |
| 10 | 45 | 90 | 81 | **117** | 126 | 9 |
| 20 | 190 | 380 | 361 | **532** | 551 | 19 |

**结论**：`swap` 一列恒等于 `n(n−1)/2`，`insert 去重` 一列恒等于 `(n−1)²`，`重合` 一列恒等于 `n−1`；`直接相加` 永远比真实规模大 `n−1`。**看到「邻域大小约等于 n² 的两倍」这类说法时，先问一句「去重了没有」。**

### 5.4 对比表：ABC 上的完整邻域与它们的目标值

`candidate = Candidate(("A","B","C"), ("M0","M1","M0"))`，当前解 `ΣCj = 13`、`Cmax = 7`（Day 2 第 5.4 节）。逐个邻居解码求 `1|rj|ΣCj`：

| 邻居 | 产生它的移动 | `order` | `assignments` | `ΣCj` | 相对当前解 |
|---|---|---|---|---|---|
| 1 | `swap(0,1)` / `insert(0,1)` / `insert(1,0)` | B,A,C | M0,M1,M0 | 13 | 持平 |
| 2 | `swap(0,2)` | C,B,A | M0,M1,M0 | **8** | **改善** |
| 3 | `insert(0,2)` | B,C,A | M0,M1,M0 | **8** | **改善** |
| 4 | `swap(1,2)` / `insert(1,2)` / `insert(2,1)` | A,C,B | M0,M1,M0 | 13 | 持平 |
| 5 | `insert(2,0)` | C,A,B | M0,M1,M0 | **8** | **改善** |
| 6 | `reassign(1, "M0")` | A,B,C | M0,**M0**,M0 | 15 | 变差 |
| 7 | `reassign(2, "M1")` | A,B,C | M0,M1,**M1** | 15 | 变差 |

```text
邻居总数 = 7（排列侧 5 个 + 指派侧 2 个），与第 4.6 节一致
排列侧 9 次 swap 尝试 + 9 次 insert 尝试只落到 5 个不同 order 上：
  邻居 1 与邻居 4 各被三个移动重复产出，邻居 2、3、5 各只由一个移动产出
指派侧只有 5 次尝试（A 一个资格、B 与 C 各两个），3 次产出原解被滤掉

当前解 ΣCj = 13；邻居最小值 = 8，由邻居 2、3、5 同时达到
严格改善 = 3 个；持平 = 2 个；变差 = 2 个
```

**结论**：七个邻居里只有三个真正改善，而这三个又**解码出同一个 Schedule**（Day 1 第 5.5 节的表示冗余）。所以「邻域里有 3 个改善解」这句话是**误导性的**：从时间表的角度看只有 1 个新解。同时注意两个改指派的邻居把 `ΣCj` 从 13 推到 15——**邻域里天然同时存在改善与变差的移动**。

> **邻域里邻居的个数 ≠ 新时间表的个数。** 统计搜索效率时必须先解码再去重，不能只数 `Candidate`。

---

## 6. 实现：`neighborhoods.py`

对应文件 [neighborhoods.py](../../projects/01_scheduling_core/scheduling_algorithms/neighborhoods.py)，全文 55 行，只有四个函数：`swap` / `insert` / `reassign` / `neighbors`。

### 6.1 为什么每个算子都返回新 `Candidate`

三个算子都用 `dataclasses.replace(candidate, ...)` 创建一个新的 frozen dataclass 实例，原对象的字段一个字节都不动。三个好处：**父解安全**（搜索同时持有「当前解」与「某个邻居」时不会互相污染）、**可比较**（`moved not in seen` 靠的就是 `Candidate` 的相等语义）、**可回溯**（回到上一步只需留着旧对象，不需要「反向移动」）。

这与 Day 5 第 7 节「`machine_ready` 不能塞进输入 `Machine`」是同一条原则的两种体现：**可变状态要么留在算法局部，要么根本不存在。**

### 6.2 为什么只提供「单点移动」

当前实现的三类移动都是一次只换一个位置、挪一个元素、改一台机器的**单点移动**。复合移动等价于「连续做两次单点移动」，可以由搜索在两步里完成；而单点移动的邻域小、易去重、易测试。**先把最小可用的移动集合做对，再考虑要不要加复合移动。**

### 6.3 邻域生成器的成本

```text
排列侧：双重循环 n × n × 2 次移动尝试 → O(n²) 次移动
指派侧：Σ(每道工序的资格数) 次移动尝试 → O(n·m) 次移动
去重：每次移动做一次 set 查找 → O(1)（哈希）
```

`neighbors()` 是生成器，调用方**不必等它跑完**：First-improvement 就是「扫到第一个改善就停」，Best-improvement 则在预算不足时被截断。**邻域的存储与评估成本随 `n²` 增长**，实例变大时会立刻体现出来。

### 6.4 搜索能走到哪里，取决于邻域

两个方向的直觉：

```text
只改顺序（swap/insert）  → 能调整「谁先做」，但每道工序的机器固定
                           如果瓶颈是机器负载不均，改顺序缓解不了
只改机器（reassign）     → 能调整「在哪台做」，但优先级不变
                           如果瓶颈是交期顺序，改机器缓解不了
两者都改（完整邻域）      → 才能同时调整「顺序」与「负载」
```

Month 1 的报告记下过一个相关的观察：**First/Best 先扫描排列再扫描机器指派，小预算可能根本到不了指派邻域**（[MONTH1_REPORT.md](../MONTH1_REPORT.md) 第 9 节）。也就是说，即使邻域**定义**里包含 `reassign`，预算太小也会让搜索在**实际执行**中只用到排列移动。**「邻域里有什么」与「搜索这一步能不能走到」是两件事。**

SA 的用法又不同：它**不生成整个邻域**，而是随机抽一个移动（swap / insert / reassign 各按概率抽取），再按 `exp(−Δ/T)` 决定接受与否。生成器的完整扫描是 First/Best 的用法，SA 只需要「能随机产出合法邻居」。

---

## 7. 实验：`m1w2d3_neighborhoods`

对应脚本 [m1w2d3_neighborhoods.py](../../projects/01_scheduling_core/examples/m1w2d3_neighborhoods.py)，在项目目录下运行：

```bash
python examples/m1w2d3_neighborhoods.py
```

脚本做六件事：ABCD 上的两类移动、ABC 上的完整邻域（逐条列出）、四类边界的报错、邻域规模表、邻居目标值与选择策略、swap 与 insert 的重合位置对。实际输出：

```text
[1] ABCD 上的 swap 与 insert
  base order = ('A', 'B', 'C', 'D')
  swap(0,2)   = ('C', 'B', 'A', 'D') （交换位置 0 与 2）
  insert(0,2) = ('B', 'C', 'A', 'D') （把位置 0 的元素移到结果的第 2 位）
  insert(0,1) = ('B', 'A', 'C', 'D')   swap(0,1) = ('B', 'A', 'C', 'D') → 相邻交换与 insert 重合
  swap 两次恢复 = True
  i == j 时返回等值候选解： True True
  机器指派不变： True True

[2] ABC 实例上的完整邻域（swap + insert + reassign）
  当前解 order = ('A', 'B', 'C')  assignments = ('M0', 'M1', 'M0')
  邻居数 = 7  去重后 = 7  含自身 = False
  逐条邻居（扫描顺序）：
    order=B,A,C  assignments=M0,M1,M0
    order=C,B,A  assignments=M0,M1,M0
    order=B,C,A  assignments=M0,M1,M0
    order=A,C,B  assignments=M0,M1,M0
    order=C,A,B  assignments=M0,M1,M0
    order=A,B,C  assignments=M0,M0,M0
    order=A,B,C  assignments=M0,M1,M1
  只改顺序的邻居 = ['B,A,C', 'C,B,A', 'B,C,A', 'A,C,B', 'C,A,B'] （5 个）
  只改指派的邻居 = ['M0,M0,M0', 'M0,M1,M1'] （2 个，order 均为 A,B,C）
  每个邻居都能解码成可行排程。

[3] 边界与非法输入
  swap(-1, 0)          -> IndexError: move indices outside permutation
  swap(0, 3)           -> IndexError: move indices outside permutation
  insert(3, 0)         -> IndexError: move indices outside permutation
  reassign(0, M1)      -> ValueError: illegal assignment
  reassign(3, M0)      -> IndexError: operation index outside instance
  decode(order=A,A,C)  -> ValueError: order must contain every operation exactly once

[4] 邻域规模：swap 与 insert 的数量关系
  n    swap   insert_raw  insert_uniq   union   naive_sum  overlap
  3    3       6            4            5        7          2
  4    6       12           9            12       15         3
  5    10      20           16           22       26         4
  10   45      90           81           117      126        9
  20   190     380          361          532      551        19
  swap = n(n-1)/2；insert_raw = n(n-1) 个有向移动；
  insert_uniq = (n-1)^2；naive_sum 把两者直接相加，overlap = n-1；
  union = (n-1)(3n-4)/2，是 O(n^2) 而不是 n!-1。
  校验：neighbors() 在 n=3、单机全资格实例上返回 5 个邻居（单机时 reassign 不产生新解）。
  校验：neighbors() 在 n=4、单机全资格实例上返回 12 个邻居（单机时 reassign 不产生新解）。

[5] 邻居的目标值与「选哪一个」
  当前解 ΣCj = 13  Cmax = 7
    order=B,A,C  assignments=M0,M1,M0  ΣCj=13
    order=C,B,A  assignments=M0,M1,M0  ΣCj=8 <-- 严格改善
    order=B,C,A  assignments=M0,M1,M0  ΣCj=8 <-- 严格改善
    order=A,C,B  assignments=M0,M1,M0  ΣCj=13
    order=C,A,B  assignments=M0,M1,M0  ΣCj=8 <-- 严格改善
    order=A,B,C  assignments=M0,M0,M0  ΣCj=15
    order=A,B,C  assignments=M0,M1,M1  ΣCj=15
  邻居中最小的 ΣCj = 8 ，共 3 个邻居严格改善当前解。
  达到最小值的邻居 order = ['C,B,A', 'B,C,A', 'C,A,B']
  best-improvement 与 first-improvement 在本例中都选 C,B,A：
  它既是扫描中第一个严格改善的邻居，也是第一个达到最小值的邻居。
  但 CBA、BCA、CAB 的 ΣCj 相同，它们解码出的是同一个 Schedule
  —— 邻域里的「多个改善邻居」可能只是同一个时间表的重复表示。

[6] swap 与 insert 的确会重合
  ABCD 上 insert(i,j) == swap(i,j) 的位置对 = [(0, 1), (1, 0), (1, 2), (2, 1), (2, 3), (3, 2)]
  这些正是相邻位置对 (0,1)、(1,2)、(2,3) 的两个方向，
  说明 swap 与 insert 的结果集合有交集，不能简单相加计数。
```

**实验结论**：

1. 第 [2] 段的 7 个邻居与第 5.4 节的手推表逐条对应；「只改顺序 5 个 + 只改指派 2 个」的分组，说明**指派的自由度受资格集限制**（A 只有一台资格）。
2. 第 [3] 段的六条报错分别命中 `IndexError` 与 `ValueError`，其中 `reassign(0, "M1")` 被拒绝的原因是 **A 的资格集只有 `("M0",)`**，与 Day 1 第 4.1 节的不变量三是同一件事。
3. 第 [4] 段印证第 5.3 节的公式：`swap`、`insert_uniq`、`overlap`、`union` 四列分别等于 `n(n−1)/2`、`(n−1)²`、`n−1`、`(n−1)(3n−4)/2`，并且 `neighbors()` 的真实返回值与公式一致。
4. 第 [5] 段给出一个重要的反直觉结论：**三个「改善邻居」其实是同一个时间表的三种写法**；同时两个改指派的邻居把 `ΣCj` 从 13 推到 15——**邻域里天然同时存在改善与变差的移动，这正是 SA 需要「以概率接受坏解」的原因**（Month 1 报告第 3 节）。

配套测试在项目目录下运行：

```bash
python -m pytest tests/test_month1.py -k moves -v
```

`test_moves_and_boundaries` 一条测试覆盖了今天全部要点：`insert(0,2)` 的方向、`swap` 的两次恢复、邻域无重复且不含自身、每个邻居都能解码成可行排程、越界抛 `IndexError`、非法资格抛 `ValueError`、重复 `order` 抛 `ValueError`。

---

## 8. 今日练习

1. **练习 1（手推）**：对 ABCD，写出 `insert(0,3)` 与 `insert(3,0)` 的结果，并说明为什么两者都不是 `swap`。
2. **练习 2（规模）**：对 `n = 6`，用第 4.5 节的公式算出 `swap`、`insert` 去重、`overlap`、合并去重四个数，再用脚本里的表格验证。
3. **练习 3（去重）**：在 `candidate = Candidate(("A","B","C"), ("M0","M1","M0"))` 上，列出所有会产出 `order = ("B","A","C")` 的移动（用 `(移动名, i, j)` 的形式）。
4. **练习 4（边界）**：构造一个 `order` 长度正确但 `assignments` 里有一台不合格机器的候选解，确认 `decode` 会在计算时间**之前**就抛错。
5. **练习 5（可选扩展，勿当结论）**：禁用 `reassign` 再对并行机实例运行搜索，记录目标变化。**注意**：月度已运行的敏感性实验聚焦**温度和冷却率**，没有做过邻域消融；因此这一步的结果只能作为个人观察，**不能写成「禁用 reassign 会导致 X% 劣化」这类结论**。

---

## 9. 验收清单

- [ ] 能说出邻域与搜索策略的区别，并举出「同一邻域、不同选择策略」的例子。
- [ ] 能说出 `swap`、`insert`、`reassign` 各自改变什么、保持什么不变。
- [ ] 能准确解释 `insert` 的 `j` 是「移除后插入的最终下标」。
- [ ] 能解释 `reassign` 的 `index` 指 `instance.operations` 中的位置，而不是 `order` 中的位置。
- [ ] 能说出四类边界行为，并解释 `i == j` 为什么不报错。
- [ ] 能解释「交换优先级可能把前驱放到后面」为什么不是 precedence 违规。
- [ ] 会算 `swap = n(n−1)/2`、`insert 去重 = (n−1)²`、`overlap = n−1`、合并去重 `= (n−1)(3n−4)/2`。
- [ ] 能说出「邻域里的邻居个数 ≠ 新时间表个数」，并给出 CBA/BCA/CAB 的例子。
- [ ] `python -m examples.m1w2d3_neighborhoods` 输出与第 5 节的表格一致（7 个邻居、最小 `ΣCj = 8`）。
- [ ] `python -m pytest tests/test_month1.py -k moves -q` 全部通过（1 条）。

---

## 10. 自测题

不看上文回答：

- Q1：什么是邻域 `N(x)`？它和搜索算法的关系是什么？
- Q2：`swap`、`insert`、`reassign` 三类移动分别改变 `Candidate` 的哪个字段？
- Q3：`insert(candidate, 0, 2)` 在 ABCD 上的结果是什么？`j` 的语义是什么？
- Q4：`reassign` 的下标参数对应哪一个序列的位置？
- Q5：`swap(candidate, i, i)` 会怎样？为什么这样设计？
- Q6：`swap` 与 `insert` 在什么情况下结果相同？这会影响邻域规模的计算吗？
- Q7：`n = 4` 时 `swap + insert` 合并去重后有多少个邻居？全排列有多少个？说明了什么？
- Q8：把 `order` 里的前驱换到后继后面，是不是非法候选解？为什么？
- Q9：`neighbors()` 里 `seen = {candidate}` 的初始值起了什么作用？
- Q10：为什么说「邻域里有 3 个改善解」可能是误导性的？

### 参考答案

- A1：`N(x)` 是当前候选解 `x` 附近允许考察的一组解；搜索策略决定「从 `N(x)` 里怎么挑下一个当前解」，First / Best / SA 可以共用同一个 `N(x)`。
- A2：`swap` 与 `insert` 改 `order`；`reassign` 改 `assignments` 的一个位置。
- A3：`BCAD`（A 被移到最终下标 2）；`j` 是移除之后插入的最终下标，不是「原下标 j 之前」。
- A4：`instance.operations` 的位置（与 `assignments` 的对齐方向一致）。
- A5：返回一个与原解相等的候选解（恒等变换）；这样 `neighbors()` 可以无脑遍历所有 `(i, j)`，靠去重滤掉自身。
- A6：相邻位置对时两者相同（`insert(i, i+1) = insert(i+1, i) = swap(i, i+1)`）；会，重合数为 `n−1`，所以不能简单相加。
- A7：合并去重 12 个，全排列 23 个（`4! − 1`）；说明单点移动的邻域远小于整个排列空间，搜索只能走到邻域覆盖到的地方。
- A8：不是非法解。`order` 只是优先级列表，decoder 会跳过前驱尚未排定的工序，实际构造顺序仍然满足 precedence。
- A9：把自身预先放进 `seen`，这样 `i == j` 的移动与「reassign 到当前机器」产出的原解会被自动滤掉，保证邻域不含自身。
- A10：因为那三个邻居可能解码出**同一个 Schedule**（本例中 CBA、BCA、CAB 都是 `ΣCj = 8` 的同一张时间表）；从时间表角度只算一个新解。

---

## 11. 今日一句话总结

> **邻域是「能走到哪些解」的集合、搜索策略是「往哪走」的规则，两者必须分开；`swap`/`insert` 只动 `order`（且 `insert` 的 `j` 是最终下标），`reassign` 只动 `assignments` 的一个位置（下标对齐 `instance.operations`），三者合并去重后规模是 `(n−1)(3n−4)/2` 而非 `n! − 1`——邻域的形状就是搜索能力的上限。**
