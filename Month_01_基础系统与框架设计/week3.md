# M1 Week 3 周总结：局部搜索与模拟退火

> 笔记：[Day1](Week_3/Day1.md) · [Day2](Week_3/Day2.md) · [Day3](Week_3/Day3.md) · [Day4](Week_3/Day4.md) · [Day5](Week_3/Day5.md) · [Day6](Week_3/Day6.md) · [Day7](Week_3/Day7.md)

## 1. 本周目标与成果

Week 2 把「一个解」变成了「可以移动的解」。但「能移动」不等于「会搜索」——需要一个**统一的搜索契约**，让不同策略在**同一个预算、同一个初始解、同一套评价流程**下被公平比较。

本周完成六件事：

1. **统一搜索契约**：`SearchConfig` / `SearchResult`，所有目标统一**最小化**。
2. **统一评价预算**：一次评价 = 完整解码 + 独立验证 + 目标计算；初始化、被拒绝候选、no-op、重启全部计入。
3. **Random Search**：只保留严格改善，作为「无智能」的下限参照。
4. **First / Best Improvement**：同一邻域、两种选步策略。
5. **Multi-start**：公共初始解上的 First + 随机重启。
6. **Simulated Annealing**：以 `exp(−Δ/T)` 接受坏解，配合几何降温。

额外保留 **LPT 初始基线**作为一个只有 1 次评价的参照点。

> **贯穿全周的一条纪律**：`solve` 返回的永远是**历史最好解**，不是「最后走到的解」。允许搜索过程变差，但不允许结果质量变差。

## 2. 搜索契约

对应文件 [search.py](../projects/01_scheduling_core/scheduling_algorithms/search.py)。

```python
solve(instance, config, initial=None) -> SearchResult

@dataclass(frozen=True, slots=True)
class SearchConfig:
    algorithm: str = "sa"              # lpt / random / first / best / multistart / sa
    objective: str = "makespan"        # makespan / total_tardiness / weighted_completion_time
    budget: int = 200
    seed: int = 0
    temperature: float = 10.0
    cooling: float = 0.98
    restart_interval: int = 40

@dataclass(frozen=True, slots=True)
class SearchResult:
    candidate: Candidate
    schedule: Schedule
    objective: float
    evaluations: int
    status: str
    elapsed_seconds: float
    trace: tuple[TracePoint, ...]
```

三条**最小化**约定：

- `OBJECTIVES` 只暴露 `makespan`、`total_tardiness`、`weighted_completion_time` 三个目标；其余指标（`ΣCj`、`ΣFj`、`Lmax`）不在搜索接口内。
- 目标名必须在 `OBJECTIVES` 中存在，算法名必须在 `ALGORITHMS` 中存在，否则 `SearchConfig` 构造时就抛 `ValueError`（**fail-fast**）。
- `temperature` 必须有限且为正，`cooling ∈ (0, 1]`，`budget ≥ 1`，`restart_interval ≥ 1`。

**默认初始解**统一来自 `initial_candidate(instance)`（LPT 优先级 + 最早完工指派），**所有算法共享同一个初始解**。LPT 基线只花 1 次评价，**不人为填满预算**。

## 3. 评价预算：本周最关键的定义

```text
一次评价 = 完整解码 decode + 独立验证 validate_schedule + 目标计算 objective
```

计数规则（**必须逐条记住**）：

| 事件 | 是否计入 |
|---|---|
| 初始解 | **计入**（永远是第 1 次评价） |
| 被拒绝的候选 | **计入** |
| 同一个候选重复评价 | **计入** |
| no-op 移动（i=j 或抽回原机器） | **计入** |
| Multi-start 的重启候选 | **计入** |
| LS 提前停机 | 只是**不用满**预算，不是「省下的可转移」 |

因此 `evaluations == len(trace)`，且**恒有 `evaluations <= budget`**。`budget` 是**上限**，不是承诺。

**为什么用评价数而不是「迭代 100 次」？** 因为不同算法「一次迭代」的成本差了一个数量级：Best 的一轮可能检查数百个邻居，First 的一次移动只评价 1 个。用**共同上限 + 真实评价数**记录，才谈得上公平。

```text
公平性 = 同一个预算上限 + 同一套评价流程
       ≠ 伪造相同的实际评价数
```

`trace` 的四个字段语义（最易混淆）：

| 字段 | 含义 |
|---|---|
| `proposed` | 本次评价的候选目标值 |
| `current` | **接受决策之后**的当前值（接受则为 `proposed`；拒绝则沿用旧值） |
| `best` | 到该点为止的历史最好值，**单调不增** |
| `accepted` | **逐算法不同**（见下） |
| `temperature` | 仅 SA 非 `None`；初始化点为 `None` |

> **`accepted` 的语义是本周最大的陷阱**：SA 的 `accepted` 是**逐候选**的接受事件；而 Best 的 `accepted` 在**扫描末的最后一个点**表示「这一轮有没有真的移动」。因此**接受率只能对 SA 计算**，把 Best 的点混进去会得到毫无意义的数字。

## 4. 五种方法

| 方法 | 下一步怎么选 | 等值解 | 坏解 | 主要代价 |
|---|---|---|---|---|
| Random | 全新随机排列 + 随机合法指派 | 只保留严格改善 | 拒绝 | 大量无效抽样 |
| First | 固定顺序扫描，**第一个**严格改善邻居 | 不接受 | 拒绝 | 对扫描顺序敏感 |
| Best | 扫完一整轮，选**最好**的严格改善邻居 | 不接受 | 拒绝 | 每轮评价数多 |
| Multi-start | First + 随机重启 | 重启可接受变差 | 拒绝 | 深度与起点数的取舍 |
| SA | 随机单个移动 | **等值接受** | 按 `exp(−Δ/T)` 概率接受 | 对参数与目标尺度敏感 |

四条必须说清的实现事实：

1. **First 和 Best 的邻域完全相同**（都用 `neighbors`）。区别**只在选步策略**，不在邻域。
2. **First 和 Best 都无法穿过等值平台**——两者都只接受**严格**改善。SA 的等值接受是它能到达局部搜索到不了的新区域的原因之一。
3. **Best 在扫描途中耗尽预算时**，保留已见到的最好候选并结束。这一轮只是**被预算截断的 Best**，**不是**完整邻域的最优移动；所有已评估候选都可以更新历史最好解。
4. **Multi-start 永远不会返回 `LOCAL_OPTIMUM`**：它的 `not moved` 分支不可达，因为「没有移动」会先触发重启。因此它总是用满预算。

## 5. 终止状态：三种，且都不是最优性声明

```text
BASELINE       规则基线完成（lpt，evaluations == 1）
BUDGET         达到评价上限（random / sa / multistart 总是这个）
LOCAL_OPTIMUM  完整扫描邻域，不存在严格改善的邻居
FAILED         该次求解抛异常（由 benchmark 记录，solve 自己不产生）
```

两条要点：

- **`LOCAL_OPTIMUM` 是相对于当前邻域的结论**，不是全局最优，也不意味着「离最优很近」。
- **预算截断时不能宣称局部最优**：如果扫描到一半因预算停止且没找到改善，代码保守地报 `BUDGET`。只有**完整覆盖整个邻域**才有资格说 `LOCAL_OPTIMUM`。

**边界**：空实例、或只有一个工序且不能换机时，邻域为空，必须**立即停止**——不能沿用上一轮的接受标记，否则会形成死循环。

## 6. Simulated Annealing

```text
Δ = f(y) − f(x)

Δ ≤ 0            →  接受
Δ > 0            →  以 exp(−Δ / T) 的概率接受

每次提议后：  T ← cooling × T
```

接受概率的**量纲**认识：`T` 与目标差值 `Δ` 同量纲，所以**同一个 `T` 在 makespan 和总迟交上含义完全不同**。

| Δ = 5 | 接受概率 |
|---|---|
| `T = 10` | ≈ 0.607 |
| `T = 1` | ≈ 0.0067 |

**三条轨迹必须分开看**（用第 3 节的字段）：

```text
当前 20、历史最好 18，接受一个 23 的候选：
   proposed = 23
   current  = 23     ← 允许上升
   best     = 18     ← 必须不变
   最终返回 best 对应的排程，绝不返回最后的 current
```

> **允许变差是搜索策略，不允许丢失历史最好是结果管理。** 两件事同时成立，SA 才有意义。

**实现选择**：

- 随机在 `swap` / `insert` / `reassign` 三种移动中选一种；
- **允许 no-op**（`i == j`，或 `reassign` 抽回原机器）并照常计入评价——这是为了避免单元素实例陷入「必须抽到不同解」的死循环；
- 用 `max(temperature, 1e-12)` 做除零保护；
- **只实现了有限预算的几何降温启发式**，不声称具有渐近全局最优保证。

**接受率**的算法与陷阱：

```text
接受率 = 窗口内 accepted_count / proposals      （排除第 1 个初始化点）
```

no-op 与等值接受**都算接受**，所以**高接受率本身不证明探索有效**——它可能只说明等值移动多。

## 7. 手算示例：First Improvement 的一轮

单机，`p = [3, 1, 2]`，全部 `w = 1`，目标 `weighted_completion_time`（等价于 `ΣwjCj`）。

| 顺序 | 完工时间 | ΣwjCj |
|---|---|---|
| `ABC`（初始） | 3, 4, 6 | **13** |
| `BAC` | 1, 4, 6 | **11** ← 严格改善，First 立即接受 |

再从已较优的 `BCA`（`p = 1, 2, 3`）出发：

```text
ΣwjCj = 1 + 3 + 6 = 10
所有单次 swap 与 insert 都没有严格改善  →  LOCAL_OPTIMUM
```

**注意这里的推理边界**：在这个特定实例上，SPT 理论还能额外证明全局最优；**但不能把这个结论一般化**——有释放时间时（见 CE-01）SPT 连最优性都不成立。

## 8. 实验观察（本批次结果）

主实验 `single_12`（12 个单机作业，目标总迟交，3 个算法 seed 的均值）：

```text
初始解(LPT) 719
SA          261.67   ← 本批最好
Random      313
Multi-start 373
Best        529
First       575
```

`routes_12`（6 作业 × 2 工序，3 台机器，目标 Cmax，3 seed 均值）：

```text
First  41
Best   41
SA     42
Multi-start 45
Random 45.33
LPT    54
```

> **实验观察，不是理论结论**：**不存在在本批次所有实例上领先的方法**——SA 在单机迟交案例中更好，First/Best 在多工序 Cmax 案例中更好。这是**六个合成实例、三个 seed** 上的现象，不能写成「SA 优于 First」这类普遍结论。

还有两个容易被忽略的解释项：

- **First/Best 的排名同时反映邻域扫描顺序和预算大小**。当前实现按固定顺序**先扫描排列、再扫描机器指派**，预算较小时可能**根本没走到指派邻域**。所以「First 在并行机实例上没赢」不能只归因于算法名字。
- **确定性方法重复三次不算三个独立随机样本**。First 在三个 seed 下结果相同是**合理现象**（它的扫描不使用 RNG），不是「稳定」的证据。

**实际评价数**（不是循环次数）：tiny 实例上 First/Best 会提前停机（tiny_single 分别用 23 / 37 次评价，tiny_parallel 都是 17 次），较大实例上两者都用满 150 且部分邻域扫描被截断。

## 9. 测试证据

| 要求 | 证据 |
|---|---|
| 预算边界与复现 | `test_search_budget_reproducibility_and_incumbent`（6 算法 × 预算 1/2/60 = 18 条） |
| 局部最优与 SA 接受坏解 | `test_ls_local_optimum_and_sa_accepts_worse` |
| 空 / 单元素终止 | `test_singleton_and_empty_terminate`（6 算法） |

测试断言的**不变量**：

```text
两次运行（同 config）→ trace 与 schedule 相等
evaluations == len(trace) <= budget
result.objective == makespan(instance, result.schedule)        ← 结果可复算
[p.best for p in trace] 单调不增                                ← best 不回升
random / sa / multistart 恰好用满 budget
返回的 schedule 通过 validate_schedule
```

复跑命令：

```bash
cd projects/01_scheduling_core
python -m pytest tests/test_month1.py -k 'search or local_optimum or singleton' -v
```

对比实验脚本（仓库根目录或项目目录均可）：

```bash
python -m examples.m1w3d6_search
```

一个**容易误判的事实**：该脚本用的实例是 `generate_instance(20, jobs=12, machines=1)`，它与 §8 主实验的 `single_12` **逐字节相同**（SHA-256 为 `de904454fddb4a08…`）。所以这个「Week 3 演示」并不是另一个小玩具——它就是 §8 主实验里那张表所用的实例，脚本输出可以直接和 §8 的均值对照（脚本固定搜索 seed=0，取的是三个 seed 中的一个）。

## 10. 接口约定（API Contract）

```python
solve(instance, config, initial=None) -> SearchResult

OBJECTIVES = {"makespan", "total_tardiness", "weighted_completion_time"}
ALGORITHMS = ("lpt", "random", "first", "best", "multistart", "sa")

TracePoint(evaluation, proposed, current, best, accepted, temperature)
```

**完整评价链**（与 Week 2 §9 同一条链，本周把它变成可计数的一步）：

```text
candidate → decode → validate_schedule → objective        = 1 次评价
```

## 11. 本月默认配置

```json
{
  "seeds": [0, 1, 2],
  "search": {"budget": 150, "temperature": 10.0, "cooling": 0.98, "restart_interval": 40}
}
```

来源是**可快速重跑的教学设置**，**不是**经过独立验证集选择的生产参数。完整配置见 [month1.json](../projects/01_scheduling_core/configs/month1.json)。

**为什么不能把「本批四种 SA 设置里最好的那个」直接当成默认值？** 那是在**这批数据上调参**的结果；要这样做，必须另留一个**独立测试集**验证，而且此后不能继续把同一批数据当作「未见数据」。本项目保留原教学默认值，**不声称完成了参数优化**。

## 12. 确定性契约

```text
相同 Instance + 相同 SearchConfig  →  相同 objective、evaluations、Candidate、Schedule、trace
```

```text
随机性来源:  仅 Random(config.seed)，局部 RNG，不改全局随机状态
First/Best:  不使用 RNG → 三个 seed 结果相同是合理的
Multi-start: 随机只用于生成重启起点，不影响固定邻居扫描
墙钟时间:    elapsed_seconds 依赖机器与环境，不参与复现比较
```

## 13. 已知局限与隐含假设

```text
邻域:        只实现 swap / insert / reassign（无 2-opt、无块移动、无并行机专用移动）
扫描顺序:    先排列后指派 → 小预算可能到不了指派邻域（影响排名解释）
追加解码:    不填空隙 → 搜索能到达的解空间本身受构造偏置限制
no-op:       SA 允许 no-op 且计入评价 → 接受率不等于有效探索率
参数:        未在独立留出集上调参，不能宣称生产可用
样本量:      三 seed、小规模合成数据；不做统计显著性声明
理论:        有限预算几何降温，无渐近全局最优保证
```

## 14. 遗留问题

| # | 问题 | 状态 |
|---|---|---|
| 1 | 不同算法如何证明「同预算同流程」？ | 已由 `evaluations` + 统一 `evaluate()` 落地（Week 3 Day 1） |
| 2 | 逐次运行的证据如何保存？ | 本周结束时仍是开放问题 |
| 3 | 排名受扫描顺序影响，如何量化？ | **未做邻域消融实验**，明确列为后续工作 |
| 4 | 参数如何选择才算可信？ | 需要独立测试集 + 配对分析；本月未做 |
| 5 | 三 seed 的均值差是否显著？ | **不能据此做显著性声明**；需要更多实例与不确定性估计 |
| 6 | 增量评估（不重新完整解码）能否实现？ | 不在本月范围，M1 优先保持可验证性 |

第 3 条要特别诚实：**未执行的邻域消融不能写成结论。** 本周的敏感性实验聚焦温度与冷却率，**没有**做「禁用 reassign」的消融；任何关于「指派邻域贡献多少」的说法都必须先跑那个实验。

## 15. 待个人完成

1. **口述三问**（能从代码与轨迹分别回答才算过）：
   - 为什么 Best 不一定比 First 好？
   - 为什么 Multi-start 的随机起点也计入预算？
   - 为什么 SA 的高接受率可能只是等值移动多？
2. 选一条 SA 轨迹，找到一行 `accepted=True` 且 `proposed > 之前的 current`，确认历史 `best` 没有回升。
3. 把 `restart_interval` 改成 1 和「大于总预算」，各跑一次，解释两个极端为什么都不是普遍最佳选择。
4. 解释「换扫描顺序可能改变 First 的最终值，但不改变每次候选的可行性」。
5. 用同一个 config 连跑两次，确认目标、候选、排程与轨迹一致，而墙钟时间通常不同——并解释为什么「同 seed」不能要求毫秒数完全相同。
