# Day 3：Best Improvement 与扫描成本

> 当日主题：分清「每轮最贪心」与「同预算最终最好」
> 当日产出：**Best Improvement 的逐评价行为分析**（扫描结构、预算截断、trace 语义）+ 实验脚本 [m1w3d3_best.py](../../projects/01_scheduling_core/examples/m1w3d3_best.py)
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 说出 First 与 Best 的**唯一**机制差别：「什么时候移动」，而不是「用不用邻域」。
2. 画出 Best 一轮的三段结构：扫完整轮 → 选出严格改善最多的候选 → 只执行一次移动。
3. 解释「预算截断的 Best」：扫描途中预算耗尽时保留已见最好候选并结束，这一轮**不是**完整邻域的最优移动。
4. 分别说出 `proposed` / `current` / `best` / `accepted` 四个字段在 First、Best、SA 下的语义，并说明为什么两种 `accepted` 不能混用。
5. 会用「评价次数」而不是「循环轮数」或「墙钟秒数」作横轴，比较两种扫描策略。
6. 解释为什么 First 与 Best 都跨不过等值平台，而 SA 的等值接受可以。
7. 能独立复现第 5 节的扫描手算：给定邻居序列与预算，预测两种策略各自的终点。
8. 能仅凭 `trace` 判断一次 Best 运行的返回值是否来自「完整邻域扫描」。

---

## 2. 为什么第 3 天要讲 Best Improvement

Day 2 的 First Improvement 有一个明显让人不满意的地方：

> **它碰到第一个严格改善就走，完全不管后面还有没有更好的候选。**

于是最自然的反问是「那我先把整轮邻居看一遍，再挑最好的那个呢？」——这就是 Best Improvement。它是局部搜索的第二块砖，也是几乎所有教材在讲爬山法时给出的第二个版本。

但今天真正的主题不是「Best 更聪明」，而是：

> **贪心节奏决定了预算怎么花。**

同样一批评价次数，First 切成许多小步，Best 切成少数大步。两种切法在**同一预算**下的收益完全不同：

| 维度 | First Improvement | Best Improvement |
|---|---|---|
| 一轮的终止条件 | 遇到第一个严格改善 | 扫完整个邻域 |
| 一轮的评价数 | 1 ～ 邻域规模 | 邻域规模（或被预算截断） |
| 一轮的移动次数 | 1 | 1 |
| 同一轮内是否比较全部候选 | 否 | 是 |
| 对邻居扫描顺序的敏感度 | 高（换个顺序就换条路） | 低（同一轮内取最小值） |

注意第三行：**两种策略一轮都只移动一次。** 所以「一轮」在两个算法里不是同一个工作量——用「跑了 3 轮」当横轴毫无意义，这正是 Day 1 第 2 节坚持「预算是评价次数」的原因。

还有一个容易被忽略的事实：Best 并不是终点，而是后续方法的零件。Day 4 的 multi-start 选择用 **First** 而不是 Best 做基础搜索（因为每个起点都要便宜），Day 5 的 SA 每次只评价 1 个候选。**先看清 Best 的成本结构，才知道什么时候不该用它。**

---

## 3. First 与 Best 的机制对照

**定义 1（First Improvement）**：从当前解 `x` 出发，按固定顺序遍历邻域 `N(x)`，遇到第一个满足 `f(y) < f(x)` 的候选 `y` 就立即移动，然后从 `y` 重新开始扫描。

**定义 2（Best Improvement）**：从当前解 `x` 出发，扫完**整个**邻域 `N(x)`，在其中选出目标值最小、且严格小于 `f(x)` 的候选 `y`，只执行**一次**移动。

```text
First 的一轮：
   评价 → 改善? 是 → 移动（本轮结束，立刻从新解重新扫描）
   评价 → 改善? 是 → 移动（本轮结束）
   ...

Best 的一轮：
   评价 → 评价 → 评价 → … → 评价（本轮扫完）
   → 在已评价的候选里挑目标最小的严格改善候选
   → 移动一次，然后开始新的一轮
```

**理论结论**（两条，都要记牢）：

1. 两者都是「只接受严格改善」的局部搜索，因此都会停在**相对于同一个邻域**的局部最优上；差别只是逼近路径不同。
2. 两者调用的是**同一个** `neighbors(instance, candidate)` 生成器（见 [neighborhoods.py](../../projects/01_scheduling_core/scheduling_algorithms/neighborhoods.py)）。

**所以：First 与 Best 的区别不是邻域不同，而是接受节奏不同。** 这句话是本日最容易考也最容易答错的一点。

---

## 4. 预算截断的 Best：本项目最重要的实现细节

教材里的 Best 默认「一轮能把邻域扫完」。在本项目的实现里，这句话**不成立**：一轮中途预算就可能耗尽。

```python
for candidate in neighbors(instance, current):
    if len(trace) >= config.budget:
        break                      # 预算用尽 → 扫描被截断
    ...
moved = chosen != scan_current     # chosen 是「已评价前缀」里最好的候选
if config.algorithm == "best":
    current, value = chosen, chosen_value   # 截断也照样移动
```

由此得到本日的核心区分：

| 术语 | 条件 | 保证 |
|---|---|---|
| 完整扫描的 Best | 本轮评价完整个 `N(x)` | `f(x_new) = min_{y∈N(x)} f(y)`，且严格下降 |
| 预算截断的 Best | 本轮扫描到一半预算耗尽 | 只保证 `f(x_new)` 是「已评价前缀」里的最小值 |

**结论**：预算截断的 Best **不是**「完整邻域的最优移动」，只是「已看过的候选里最好的那一个」。它仍然是一步合法的严格改善，但不能宣称它是这一轮的最优选择。

那么被截断掉的候选会不会让已发现的改善丢失？不会。因为 `record` 在**每一次评价**时都尝试更新历史 `best`：

```python
if score < best_value:
    best, best_schedule, best_value = candidate, schedule, score
```

**所以每一个被评价过的候选都可能刷新历史最好解，扫描被截断也不会丢掉已经发现的改善。** 需要分清的是两个不同的量：

- `current`：本轮回填的解，来自 `chosen`（本轮已评价前缀里最好的候选）；
- `best`：历史最好解，来自所有评价（含初始化点）里的最小值。

返回值是 `best`，不是 `current`（Day 1 第 3 节 + Day 6 第 6 节的结论在这里第一次显出必要性）。

---

## 5. 手算 / 示例：邻居序列 `99, 98, 80`

### 5.1 教学模型：把「一轮」缩到 3 个候选

为了保证每一步都能手算，先把邻域压到 3 个候选，并且规定扫描顺序固定。

| 状态 | 自身目标值 | 本轮邻居按固定顺序给出的目标值 |
|---|---|---|
| `s0` | 100 | `s1`=99, `s2`=98, `s3`=80 |
| `s1` | 99 | `s4`=90, `s5`=85 |
| `s4` | 90 | `s6`=70 |

```text
起点 s0，目标 100

First：
  第 1 次评价 = 99 < 100 → 立刻移动 s0 → s1，本轮结束
  第 2 次评价 = 90 < 99  → 立刻移动 s1 → s4，本轮结束
  第 3 次评价 = 70 < 90  → 立刻移动 s4 → s6，本轮结束
  预算到此用尽

Best：
  第 1、2、3 次评价 = 99、98、80（本轮扫完）
  本轮最小 = 80 < 100 → 移动 s0 → s3，只移动一次
  预算到此用尽
```

```text
算术（固定总预算 = 3 次评价）：
  First：100 → 99 → 90 → 70        共 3 次评价，3 次移动   → 终点目标 70
  Best ：100 → min(99, 98, 80) = 80 共 3 次评价，1 次移动   → 终点目标 80

  差值：80 − 70 = 10，First 在同样预算下反而更优
```

**对比表**（同一预算 3、同一邻域、同一扫描顺序）：

| 策略 | 3 次评价内的移动次数 | 每一步的评价数 | 最终目标 |
|---|---|---|---|
| First | 3 | 1 / 1 / 1 | **70** |
| Best | 1 | 3 | 80 |

**结论**：Best 的「更贪心」是在**同一轮之内**更贪心——它确实在 `99 / 98 / 80` 里挑到了最好的 80，而 First 只拿到 99。但把预算摊平到多次移动，First 反而走到更低的位置。**「每轮更贪心」推不出「同预算最终更好」。**

### 5.2 真实实例：两个方向相反的结论

教学模型是算术，不来自代码。真实结论必须来自实跑，用两个固定实例（同一个 `neighbors`、同一个预算上限）：

| 实例 | 生成式 | 目标 | 预算 | 邻域规模 |
|---|---|---|---|---|
| A | `generate_instance(20, jobs=12, machines=1)` | `total_tardiness` | 150 | 176 |
| B | `generate_instance(20, jobs=8, machines=2)` | `makespan` | 60 | 78 |

```text
实例 A（best，budget=150，seed=0）的逐评价轨迹摘录
  #  1  proposed=  719.0  current=  719.0  best=  719.0  accepted=True    ← 初始化点
  #  2  proposed=  704.0  current=  719.0  best=  704.0  accepted=False
  #  3  proposed=  728.0  current=  719.0  best=  704.0  accepted=False
  #  4  proposed=  698.0  current=  719.0  best=  698.0  accepted=False
  ...
  #148  proposed=  671.0  current=  719.0  best=  529.0  accepted=False
  #149  proposed=  683.0  current=  719.0  best=  529.0  accepted=False
  #150  proposed=  691.0  current=  529.0  best=  529.0  accepted=True    ← 轮末回填

实例 B（first，budget=60，seed=0）的逐评价轨迹摘录
  #  5  proposed=   40.0  current=   40.0  best=   40.0  accepted=False
  #  6  proposed=   40.0  current=   40.0  best=   40.0  accepted=False
  #  7  proposed=   40.0  current=   40.0  best=   40.0  accepted=False
  #  8  proposed=   40.0  current=   40.0  best=   40.0  accepted=False
  #  9  proposed=   39.0  current=   39.0  best=   39.0  accepted=True
```

```text
算术（实例 A，best）：
  邻域规模 = 176，本轮评价数 = #2 ～ #150 = 149
  176 − 149 = 27 个候选从未被评价 → 本轮被预算截断
  current 列只出现两个取值 {719.0, 529.0} → 149 次评价里 current 一次都没动
  accepted=True 的点只有 {1, 150} → 整个运行只完成了 1 次移动

算术（实例 A，first，同一实例同一预算）：
  accepted=True 的点 = {1, 2, 6, 12, 20, 36, 50, 73, 98, 125}
  → 9 次移动，各轮评价数 = 1, 4, 6, 8, 16, 14, 23, 25, 27，末尾 25 次为空扫
  平均每轮 149 / 9 ≈ 16.6 次评价（Best 是 149 次一轮）
```

**对比表**（同一实例 + 同一 seed，`status` 与 `evaluations` 都来自实跑）：

| 实例 | 算法 | objective | evaluations | 移动次数 | status |
|---|---|---|---|---|---|
| A（`total_tardiness`） | first | 575.0 | 150 | 9 | `BUDGET` |
| A（`total_tardiness`） | best | **529.0** | 150 | 1 | `BUDGET` |
| B（`makespan`） | first | **35.0** | 60 | 4 | `BUDGET` |
| B（`makespan`） | best | 39.0 | 60 | 1 | `BUDGET` |

**结论**：A 上 Best 赢（529 < 575），B 上 First 赢（35 < 39）。**方向相反，但两次 Best 都只完成了一次移动，而且那一次都来自被预算截断的半轮扫描。** 所以第 5.1 节的教学结论在真实实例上同样成立：谁更好取决于实例与预算，而不是名字。

---

## 6. 实现：`search.py`

对应文件 [search.py](../../projects/01_scheduling_core/scheduling_algorithms/search.py)。First、Best、multi-start 三个算法共用同一段扫描循环，差别只有三处 `config.algorithm != "best"` 的判断。

### 6.1 内层扫描：First 在循环内移动，Best 在循环外移动

```python
for candidate in neighbors(instance, current):
    if len(trace) >= config.budget:
        break
    if (
        config.algorithm == "multistart"
        and len(trace) - segment_start >= config.restart_interval
    ):
        break
    schedule, score = evaluate(candidate)
    improved = score < chosen_value
    if improved:
        chosen, chosen_value = candidate, score
    if config.algorithm != "best" and improved:
        current, value = chosen, chosen_value
    record(candidate, schedule, score, config.algorithm != "best" and improved)
    if improved and config.algorithm != "best":
        break
```

- `chosen` 记录「本轮到目前为止最好的候选」，`chosen_value` 从当前值 `value` 起步——所以 `improved` 一定是**严格**改善。
- First：`improved` 为真时立刻把 `current` 改成候选并 `break`（移动发生在循环**内**）。
- Best：`improved` 为真只更新 `chosen`，不 `break`，扫到预算耗尽或邻域结束（移动发生在循环**外**）。

### 6.2 轮末回填：`accepted` 在这里被重新赋值

```python
moved = chosen != scan_current
if config.algorithm == "best":
    current, value = chosen, chosen_value
    last = trace[-1]
    trace[-1] = TracePoint(
        last.evaluation, last.proposed, value, last.best, moved, None
    )
```

这段代码解释了两件事：

1. **Best 的 `current` 是回填值。** 扫描期间 `current` 一直是旧解（实例 A 里 149 次评价全部保持 719.0），轮末才一次性写成 529.0。所以 `best` 算法的轨迹里，某一行 `proposed` 与同一行 `current` 不相等是**正常现象**：`proposed` 是那次评价的候选值，`current` 是轮末回填的当前解。
2. **Best 的 `accepted` 是「这一轮是否移动」，不是「这个候选是否被接受」。** 它来自 `moved = chosen != scan_current`，与最后一个被评价的候选毫无关系。实例 A 的末行 `proposed=691.0` 却被标成 `accepted=True`，就是因为这一轮整体移动了。

### 6.3 四个字段在三种算法下的语义

| 算法 | `proposed` | `current`（记录时的值） | `accepted` | `best` |
|---|---|---|---|---|
| `first` | 本次评价的候选目标值 | 已接受的最新当前解 | 本次候选是否被接受并移动 | 历史最小值 |
| `best` | 本次评价的候选目标值 | 扫描期间保持旧值，轮末回填 | **本轮**是否移动 | 历史最小值 |
| `sa` | 本次评价的候选目标值 | 接受/拒绝后的当前解 | 本次候选是否被接受 | 历史最小值 |

**所以「接受率」这个词在三种算法里根本不是同一个量。** First/Best 的一个 `accepted=True` 代表一整轮（可能 149 次评价）的结果；SA 的一个 `accepted=True` 代表**一次**提议的接受事件。把两者的 `accepted` 混在一起算接受率，等于用「轮」除以「次」，是纯粹的统计口径错误。计算 SA 接受率时绝不能混入 Best 的轨迹（Day 5 第 5 节会给出正确算法）。

### 6.4 为什么两者都跨不过等值平台

`improved = score < chosen_value` 是**严格小于**。First 从 `value` 起步，Best 也从 `value` 起步，所以：

- 邻居目标值**等于**当前值 → `improved=False` → 不移动；
- 邻居目标值**大于**当前值 → `improved=False` → 不移动。

**理论结论**：First 与 Best 都只能在严格下降的方向上移动，一旦进入一段目标值恒定的平台（例如很多不同排程给出同一个 `makespan`），它们就停住了。

而 SA 的接受准则是 `delta <= 0 or rng.random() < exp(...)`（Day 5 第 2 节），**等值候选（Δ=0）无条件接受**。所以：

> **SA 的等值接受让它可以沿着等值平台横着走，走到局部搜索根本到不了的新区域。**

这是「邻域相同、结果不同」的第三种原因（前两种是接受节奏与随机性）。

### 6.5 状态是怎么定的

```python
status = "BUDGET"
...
elif not moved:
    status = "LOCAL_OPTIMUM"
    break
```

- First / Best 只有在**完整扫完一轮且没有任何严格改善**时才返回 `LOCAL_OPTIMUM`；
- 只要预算是被用尽的（无论有没有移动），返回 `BUDGET`。

实例 A 和 B 上四个运行全部是 `BUDGET`，原因见 6.1：12 工序的邻域有 176 个候选，150 次预算根本扫不完一轮。

---

## 7. 实验：`m1w3d3_best`

对应脚本 [m1w3d3_best.py](../../projects/01_scheduling_core/examples/m1w3d3_best.py)，在项目目录下运行：

```bash
python examples/m1w3d3_best.py
```

脚本做两件事：第 1 部分用 5.1 的教学模型复现「First 花 1 次拿到 99、Best 花 3 次拿到 80」以及同预算下 First 反超；第 2 部分在实例 A、B 上并排跑 `first` / `best`，打印 `objective`、实际 `evaluations`、移动次数与 `status`，并展示 Best 轨迹的 `current` 回填与 `accepted` 语义。固定 seed，不写 `artifacts/`。

**实际运行输出**（原文粘贴）：

```text
==============================================================================
第 1 部分：手算模型 —— current=100，一轮的邻居按固定顺序评价出 99, 98, 80
==============================================================================
初始解 s0，目标 100；同一轮邻居扫描顺序：s1=99, s2=98, s3=80
First: 用 3 次评价到达 s6（目标 70，移动 3 次）
Best : 用 3 次评价到达 s3（目标 80，移动 1 次）

两种走法的逐步展开：
  First： 第1次评价=99 < 100 → 立刻移动，本轮结束（1 次评价换来 99）
  Best ： 第1次评价=99，第2次评价=98，第3次评价=80 → 本轮扫完才移动（3 次评价换来 80）

把总预算固定为 3，两种策略在同一预算下的最终结果：
algorithm,final_objective,evaluations,moves
first,70,3,3
best ,80,3,1
结论：预算 3 下 First 用 1+1+1 次评价走完三轮，到达 70；Best 把 3 次评价全花在第一轮，按 99/98/80 中最小的 80 移动，到达 80。
「Best 每轮更贪心」说的是同一轮的候选里选得更好，而不是「同样总预算下最终目标一定更低」。

第 2 部分 A：单机 12 工序，目标 total_tardiness，预算 150，seed 0
同一 neighbors 生成器去重后的邻域规模: 176
algorithm,objective,evaluations,moves,status
first,575.0,150,9,BUDGET
best,529.0,150,1,BUDGET
best 的 current 列一共只出现 2 个取值: [529.0, 719.0]
best 的 accepted=True 点是: [1, 150]
best 完成的扫描轮次（评价区间）: [(2, 150)]；每轮评价数 [149]
对比邻域规模 176：轮次评价数小于邻域规模 → 这一轮扫描被预算截断，不是完整邻域。
best 的前 4 个 trace 点（扫描期间 current 不动）:
  #  1  proposed=  719.0  current=  719.0  best=  719.0  accepted=True
  #  2  proposed=  704.0  current=  719.0  best=  704.0  accepted=False
  #  3  proposed=  728.0  current=  719.0  best=  704.0  accepted=False
  #  4  proposed=  698.0  current=  719.0  best=  698.0  accepted=False
best 的最后一个 trace 点:
  #150  proposed=  691.0  current=  529.0  best=  529.0  accepted=True
  proposed=691.0 是这次评价的候选值；
  current=529.0 是本轮选定后回填的当前解，所以它不等于最后一个 proposed（本轮最好的候选出现在更早的评价里）。
  accepted=True 回答的是「这一轮最后到底移动了没有」，不是「最后一个候选被接受了没有」。

第 2 部分 B：2 台机器 8 工序，目标 makespan，预算 60，seed 0
同一 neighbors 生成器去重后的邻域规模: 78
algorithm,objective,evaluations,moves,status
first,35.0,60,4,BUDGET
best,39.0,60,1,BUDGET
best 的 current 列一共只出现 2 个取值: [39.0, 40.0]
best 的 accepted=True 点是: [1, 60]
best 完成的扫描轮次（评价区间）: [(2, 60)]；每轮评价数 [59]
对比邻域规模 78：轮次评价数小于邻域规模 → 这一轮扫描被预算截断，不是完整邻域。
best 的前 4 个 trace 点（扫描期间 current 不动）:
  #  1  proposed=   40.0  current=   40.0  best=   40.0  accepted=True
  #  2  proposed=   40.0  current=   40.0  best=   40.0  accepted=False
  #  3  proposed=   40.0  current=   40.0  best=   40.0  accepted=False
  #  4  proposed=   40.0  current=   40.0  best=   40.0  accepted=False
best 的最后一个 trace 点:
  # 60  proposed=   39.0  current=   39.0  best=   39.0  accepted=True
  proposed=39.0 是这次评价的候选值；
  current=39.0 正好等于最后一个 proposed，只是说明本轮最好的候选恰好是最后一个被评价的候选。
  accepted=True 回答的是「这一轮最后到底移动了没有」，不是「最后一个候选被接受了没有」。

==============================================================================
两个真实实例的结论方向相反：A 上 Best 更好（529 < 575），B 上 First 更好（35 < 39）。
两次运行里 Best 都只完成了 1 次移动，而它那一轮扫描都被预算截断（不是完整邻域），
所以它返回的并不是「完整邻域的最优移动」；First 用同样的预算完成了更多轮。
==============================================================================
```

**实验观察**（只陈述输出里看得到的事实）：

1. 教学模型里 First 反超 Best（70 < 80），而实例 A 上 Best 反超 First（529 < 575）、实例 B 上 First 又反超（35 < 39）——**没有哪个策略稳定更好**。
2. 实例 A 的 Best 用了 149 次评价只换来 1 次移动；同一实例的 First 用 150 次评价换来 9 次移动。多出来的移动次数没有让 First 在这一例上赢，但它确实覆盖了更多区域。
3. `best` 的 `current` 列在**所有**算法里都是「回填后」的值，读取轨迹做逐行分析时必须记住这条例外（与 Day 6 第 6.4 节一致）。
4. 两个实例的 `status` 都是 `BUDGET`，说明预算比一轮扫描更早耗尽。

---

## 8. 今日练习

1. **练习 1（手算）**：把 5.1 表格里 `s0` 的三个邻居值改成 `95, 90, 99`（`s0` 自身仍是 100，`s1`、`s4` 的邻居不变），预算仍为 3。分别写出 First 与 Best 的终点，并说明为什么 Best 这一次输得更惨。
2. **练习 2（截断判断）**：给定邻域规模 176、轮次评价区间 `(2, 150)`，判断这次 Best 是否为「完整扫描的 Best」；若不是，说出至少有 27 个候选没被评价的推导过程。
3. **练习 3（轨迹阅读）**：在实例 A 的 `best` 轨迹里找出「`proposed` 与 `current` 不等」的所有行，并解释这些行里 `current` 是从哪一次评价回填出来的。提示：`current` 列只有两个取值。
4. **练习 4（接受率口径）**：分别用 `first`、`best`、`sa` 在实例 A 上跑 150 次预算，统计各自的 `accepted=True` 比例。说明这三个比例为什么不能横向比较，并写出你会在报告里如何措辞。
5. **练习 5（代码阅读）**：不看 `search.py`，写出内层扫描循环里三处 `config.algorithm != "best"` 分别控制什么；再与实现对照，确认自己没有把「移动时机」和「记录时机」搞混。

---

## 9. 验收清单

- [ ] 能说出 First 与 Best 的唯一机制差别是「什么时候移动」，邻域是同一个 `neighbors`。
- [ ] 能画出 Best 一轮的三段结构，并说出「一轮只移动一次」。
- [ ] 能解释「预算截断的 Best」与「完整扫描的 Best」的差别，并举出实例 A 的 149 / 176。
- [ ] 能说清 `proposed` / `current` / `best` / `accepted` 在 `first` / `best` / `sa` 下的语义差别。
- [ ] 能解释为什么 Best 的 `accepted` 不能拿来算接受率，SA 的可以。
- [ ] 能解释为什么 First 与 Best 都跨不过等值平台，而 SA 的等值接受可以。
- [ ] 能仅凭 `trace` 与邻域规模判断一次 Best 运行是否发生过预算截断。
- [ ] 实验脚本 `examples/m1w3d3_best.py` 在项目目录下运行无报错，输出可复现。
- [ ] 在项目目录下运行 `python -m examples.m1w3d3_best` 输出的两实例结论与第 7 节粘贴一致。
- [ ] 在项目目录下运行 `python -m pytest -q`，127 条测试全部通过（本日无新增测试）。

---

## 10. 自测题

不看上文回答：

- Q1：First 与 Best 用的是不同的邻域吗？为什么？
- Q2：Best 一轮会移动几次？First 一轮会移动几次？
- Q3：什么叫「预算截断的 Best」？它返回的是这一轮的最优移动吗？
- Q4：预算截断时，已经发现过的改善会不会丢？代码靠什么保证？
- Q5：Best 轨迹里 `accepted=True` 表示什么？和 SA 的 `accepted=True` 有什么区别？
- Q6：为什么不能把 First / Best 的 `accepted` 与 SA 的混在一起算接受率？
- Q7：邻居目标值恰好等于当前值时，First 与 Best 会移动吗？SA 呢？
- Q8：实例 A 上 Best 用 149 次评价换来几次移动？First 用 150 次换来几次？
- Q9：`current` 与 `best` 在 Best 算法里分别来自哪里？返回值是哪一个？
- Q10：什么时候 First / Best 会返回 `LOCAL_OPTIMUM` 而不是 `BUDGET`？

### 参考答案

- A1：不是，两者都调用同一个 `neighbors(instance, candidate)`；差别在「什么时候移动」。
- A2：都是一轮移动一次；区别是一轮的评价数（First 是 1 ～ 邻域规模，Best 是邻域规模或被预算截断）。
- A3：扫描途中预算耗尽、只用了「已评价前缀」里最好的候选完成移动的一轮；它**不是**完整邻域的最优移动。
- A4：不会丢。`record` 在每次评价时都用 `if score < best_value` 更新历史 `best`，任何被评价过的候选都可能刷新它。
- A5：Best 的 `accepted` 表示「这一轮是否移动」（来自 `moved = chosen != scan_current`，轮末回填）；SA 的 `accepted` 是**逐候选**的接受事件。
- A6：因为两者的计数单位不同：Best 的一个 `accepted=True` 代表一整轮（实例 A 里是 149 次评价），SA 的一个 `accepted=True` 代表一次提议；混算等于用「轮」除以「次」。
- A7：First 与 Best 都不移动（`improved = score < chosen_value` 是严格小于）；SA 接受（`delta <= 0`）。
- A8：Best 是 1 次（`accepted=True` 只有 `{1, 150}`）；First 是 9 次（`{1, 2, 6, 12, 20, 36, 50, 73, 98, 125}` 去掉初始化点）。
- A9：`current` 来自本轮的 `chosen`（轮末回填），`best` 来自所有评价里的最小值；返回值是 `best`。
- A10：只有在完整扫完一轮且没有任何严格改善时；只要预算被用尽（无论有没有移动）就是 `BUDGET`。

---

## 11. 今日一句话总结

> **Best Improvement 用「扫完整轮再移动一次」换来了同一轮内的最优选择，但评价预算是有限的——**每轮更贪心不等于同预算最终更好**，而本项目里它常常只完成一轮被截断的扫描，返回的是「已看过的最好」而不是「邻域的最优」。**
