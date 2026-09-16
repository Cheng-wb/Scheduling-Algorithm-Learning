# Day 6：极小实例的独立枚举对拍

> 当日主题：用可承受规模的完整枚举，为 `decoder`、Objective 与搜索算法提供独立的最优值参照
> 当日产出：**`oracle` 的适用边界与五个四任务两机实例的对拍认识**（`oracle.py` 解读 + 验证脚本）
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 说清楚 `exhaustive_optimum` 遍历的是什么：`n!` 个全局排列 × 每个工序的资格机器指派。
2. 手算出规模公式 `n! · m^n`，并算出 `n=4, m=2` 的 `384`、`n=5` 的 `3840`、`n=8` 的 `10321920`。
3. 解释 `oracle` 为什么必须**自己维护机器可用时刻**，而不能调用 `decode`。
4. 完整复述「为什么这个枚举可以称 `optimum`」的三段论证。
5. 说清楚 `regular objective` 是什么，以及为什么「提前惩罚」会推翻这套论证。
6. 解释 `limit=100_000` 的拒绝行为，以及「受限枚举结果不能冒充整个问题的 `optimum`」。
7. 区分「某启发式在一个实例上追平了枚举最优值」与「该启发式具有全局最优保证」。
8. 复述五个四任务两机实例的对拍流程：枚举最小值、`oracle` 排程可行、所有搜索算法返回值不低于 `optimum`。

---

## 2. 为什么第 6 天要「枚举」

这一周的流水线到这里已经三层都齐了：

```text
Generator ─→ Instance ──┬─→ Candidate ─→ decode ─→ Schedule ──┬─→ Objective ─→ 数字
                        │                                     │
                        └─────────────────────────────────────┴─→ Schedule Validator
```

现在有能力：造实例、产生排程、独立检查可行性、算指标。但**缺一行最关键的证据**：

> 所有算法都在优化的那个数字，**到底离最优值有多远**？

`Cmax = 29` 是好还是不好？Week 1 用 `LB = max(max p, ceil(Σp/m))` 回答过一部分——但 `LB` 只是下界，`Cmax > LB` 时既可能还有改进空间，也可能 `LB` 本身太松。Day 5 的 `Cmax` 跨规模比较更是完全无意义。

所以今天要接上的是**参照系**：

```text
Instance ──┬─→ Candidate ─→ decode ─→ Schedule ──┬─→ Objective ─→ 数字
           │                                     │
           ├─────────────────────────────────────┴─→ Schedule Validator
           │
           └──→ 【今天接入】Oracle：Instance → (optimum, 最优排程, 枚举次数)
```

关键在于 `oracle` 是**另一条完全独立的路径**：它不产生 `Candidate`、不调用 `decode`、不经过邻域，直接从 `Instance` 出发穷举所有可能。当两条路径在同一批实例上给出同一个最小值时，「`decode` + Objective 这条链是对的」才第一次有了**代码之外的证据**。

> **一句话：手算对拍能证明「这几个案例是对的」，枚举对拍能证明「这一整批小实例上是对的」——它把验证从「点」扩展成「面」。**

---

## 3. 枚举的是什么：`n! · m^n`

`exhaustive_optimum(instance, objective="makespan", limit=100_000)` 只支持**每个作业恰好一道工序**的实例。在这个前提下，一个可行排程由两件事决定：

```text
① 每个工序放在哪台机器上      → 每道工序有 |eligible| 种选择
② 同一台机器上这些工序的先后   → 由全局排列诱导
```

规模公式：

```text
组合数 = n!  ×  ∏_i |eligible_i|
         ↑        ↑
      全局排列   逐工序的机器选择

默认生成器给全部机器资格（Day 5 第 4.2 节），所以 |eligible_i| = m，公式退化成：

组合数 = n! · m^n
```

具体数字（已在代码中验证）：

| `n` | `m` | `n!` | `m^n` | 组合数 | 是否 ≤ `limit=100_000` |
|---:|---:|---:|---:|---:|---|
| 4 | 2 | 24 | 16 | **384** | 是 |
| 4 | 3 | 24 | 81 | 1944 | 是 |
| 5 | 2 | 120 | 32 | **3840** | 是 |
| 5 | 3 | 120 | 243 | 29160 | 是 |
| 6 | 2 | 720 | 64 | 46080 | 是 |
| 8 | 2 | 40320 | 256 | **10321920** | 否，拒绝 |

两点读法：

- **阶乘是主要增长项。** `n` 从 4 涨到 8，`n!` 从 24 涨到 40320（约 1680 倍），`m^n` 只涨了 16 倍。这也解释了为什么穷举「适合对拍、不适合求解」。
- **`limit` 是保护不是能力。** 拒绝的门槛是 `size > limit`，所以 6 任务两机的 46080 **可以跑**（实测约 0.78 秒），8 任务两机直接被拒。

代码里的写法与公式一一对应：

```python
size = factorial(len(instance.operations)) * prod(
    len(op.eligible_machine_ids) for op in instance.operations
)
if size > limit:
    raise ValueError(f"enumeration too large: {size} > {limit}")
```

注意 `size` 用的是**每道工序自己的资格机器数**，不是实例的机器总数。所以全机器资格时才是 `m^n`；如果某道工序只能上 1 台机器，它那一项就是 1。

---

## 4. 为什么它可以称 `optimum`

这是今天最需要看明白的一节。枚举凭什么保证「没有更差的解被漏掉」？

### 4.1 三段论证

**第一段：固定「每台机器上的顺序」后，尽可能早开工不会更差。**

给定一个指派和每台机器上工序的先后顺序，`oracle` 的做法是让每道工序在「机器可用」与「释放时刻」允许的最早时刻开工：

```python
start = max(available[machine], jobs[op.job_id].release_time)
```

任何其他可行排程在同样的机器顺序下都不可能让某道工序更早完成——因为 `available` 正是「该机器上前一道工序的完工时刻」，而释放时间是硬约束。所以这个「尽早开工」的排程**逐项支配**同顺序下的任何其他排程：

```text
对每道工序：C_尽早 ≤ C_任意
```

**第二段：本月三个目标都是 `regular objective`，所以「逐项更早」就「不更差」。**

**定义**：目标函数 γ 是 `regular` 的，如果所有 `Cj` 都不增时 γ 不增（等价地：目标对完工时间非降）。

| 目标 | 是否 `regular` | 理由 |
|---|---|---|
| `Cmax` | 是 | `max_j C_j` 对每个 `C_j` 非降 |
| `ΣTj` | 是 | `max(0, C_j − d_j)` 对 `C_j` 非降 |
| `ΣwjCj` | 是 | `w_j > 0`（输入已校验），`w_j·C_j` 对 `C_j` 非降 |

于是第一段的「逐项更早」直接推出「目标值不更大」。结合「枚举取的是所有候选里的最小值」，得到：

> `枚举最小值 ≤ 任何可行排程的目标值`

**第三段：全局排列 × 抽派的笛卡尔积覆盖了所有「每台机器顺序」。**

任取一个可行排程 S。把 S 里每台机器上的工序按开始时间排成一个序列，就得到「每台机器各自的一个顺序」。现在把这些序列**交错合并**成一个全局排列 π（同一台机器内部的相对先后保持不变，跨机器的顺序任意），再取 S 的机器指派 a。那么：

```text
(π, a) 属于「全局排列 × 指派」的笛卡尔积
→ 被枚举到
→ 它诱导的「每台机器顺序」与 S 完全一致
→ 由第一、二段，枚举出的目标值 ≤ S 的目标值
```

因为 S 是任取的，所以**最小的那个枚举值 ≤ 最优值**；又因为枚举出来的都是可行排程，**枚举最小值 ≥ 最优值**。两者夹住，只能相等。

### 4.2 重复覆盖只影响速度，不影响正确性

不同的全局排列可能诱导出**同一组**「每台机器顺序」。例如两台机器各自的顺序都保持不变、只把合并顺序换个交错方式，得到的是同一个排程。

```text
这是表示冗余（Day 1 第 2 节讲 `Candidate` 时出现过同一个词），后果只有一条：
  384 次循环里有一部分在重复评估同一个排程
不会漏掉任何排程，因此不威胁 correct 性。
```

### 4.3 论证失效的情形

**这套论证不适用于任意新目标。** 反例是**提前惩罚**（earliness penalty，`ΣEj = Σ max(0, d_j − C_j)`）：它不是 `regular` 的——**故意把工序往后拖**可能降低惩罚。这时「尽可能早开工」反而会让目标变差，第一段就不再成立。

同时，`oracle` 自身的适用范围也限死了它能证明什么：

```text
只支持：每作业恰好一道工序
只支持：regular 目标（本月的 makespan / total_tardiness / weighted_completion_time）
只支持：组合数不超过 limit 的实例
```

> **不能用受限枚举的结果宣称整个问题的 `optimum`。** 一个 8 任务两机实例跑不动枚举，不等于它「没有最优解」；一个多工序实例被 `oracle` 拒绝，也不等于它的解码器没有被验证过——那是靠 Week 1 的手算 + `test_three_decoder_traces` 的三条精确轨迹补的。

---

## 5. 手算 / 构造：`seed=0` 的四任务两机实例

用默认生成器产出（`generate_instance(0, jobs=4, machines=2)`），这个实例是本周枚举对拍的第一个。

| Job | 工序 | `pj` | `rj` | `dj` | `wj` |
|---|---|---:|---:|---:|---:|
| J000 | J000_O0 | 13 | 6 | 25 | 1 |
| J001 | J001_O0 | 9 | 8 | 21 | 4 |
| J002 | J002_O0 | 13 | 4 | 23 | 4 |
| J003 | J003_O0 | 12 | 9 | 27 | 2 |

全部工序都可在 `M0` / `M1` 上加工（生成器的全机器资格约定）。规模：

```text
4! × 2^4 = 24 × 16 = 384
```

### 5.1 枚举给出的最优排程

`exhaustive_optimum` 返回的最优排程（`objective="makespan"`，`best_value = 29.0`，`count = 384`）：

```text
M0：J000 [6,19)   →   J001 [19,28)          frontier: 6 → 19 → 28
M1：J002 [4,17)   →   J003 [17,29)          frontier: 4 → 17 → 29

Cmax = max(28, 29) = 29
Σp   = 13 + 9 + 13 + 12 = 47
```

逐项核对约束与「尽早开工」：

| 工序 | 机器 | `[start,end)` | 为什么不能更早 |
|---|---|---|---|
| J000 | M0 | `[6,19)` | `r=6`，M0 空闲 |
| J001 | M0 | `[19,28)` | M0 上 J000 到 19；自身 `r=8` 已满足 |
| J002 | M1 | `[4,17)` | `r=4`，M1 空闲 |
| J003 | M1 | `[17,29)` | M1 上 J002 到 17；自身 `r=9` 已满足 |

### 5.2 与下界对照

Week 1 的下界公式：

```text
LB = max( max_j p_j , ceil(Σ_j p_j / m) )
   = max( max(13, 9, 13, 12) , ceil(47 / 2) )
   = max( 13 , 24 )
   = 24

而 Cmax_OPT = 29 > LB = 24
```

**这不矛盾。** `LB` 是下界，不是最优值；`29 > 24` 只说明这个实例上 `LB` 不够紧（释放时刻把工期顶了上去：`p=12` 的 J003 在 `t=9` 才释放，两台机器上 `p=13` 的作业又都不能早于 `t=4/6` 启动）。**只有 `Cmax == LB` 时 `LB` 才能证明最优**（Week 1 Day 5 第 11 节）。

### 5.3 五个种子的对拍结果

对 `seed = 0…4`（每个都是 `jobs=4, machines=2`）分别跑 `exhaustive_optimum` 与 `parallel_lpt`：

| `seed` | `n! · m^n` | 枚举 `optimum` | `parallel_lpt` 的 `Cmax` | 是否追平 |
|---:|---:|---:|---:|---|
| 0 | 384 | 29.0 | 29 | 是 |
| 1 | 384 | 22.0 | 22 | 是 |
| 2 | 384 | 23.0 | 23 | 是 |
| 3 | 384 | 26.0 | 26 | 是 |
| 4 | 384 | 25.0 | 28 | **否** |

这张表是今天最重要的一份**实验观察**：

- `seed=4` 上 `LPT` 得 28、枚举最优是 25——**LPT 在这批实例上并不总是最优**，这正是 Week 1 CE-03 反例在随机实例上的复现；
- 但五个种子上 LPT 有四次追平，若只看这四次就会得出「LPT 就是最优」的错误结论；
- 顺带一个反直觉的事实：五个种子上 `Cmax_OPT > LB` 全部成立（`29>24`、`22>18`、`23>22`、`26>16`、`25>19`）。**下界从来没被取到过**，说明 Week 1 的 `LB = max(max p, ceil(Σp/m))` 在带释放时间的实例上相当松——它能证明最优，但很少有机会证明。

> **「一个启发式在某个实例上追平了枚举最优值」是一个数据点，「该启发式具有全局最优保证」是一个定理。前者永远推不出后者。**

---

## 6. 实现：`oracle.py`

对应文件 [oracle.py](../../projects/01_scheduling_core/scheduling_algorithms/oracle.py)。模块 docstring 把三件事一次说清：

```text
单工序极小实例穷举：独立于 decoder，regular 目标下证明最优。
固定每台机器上的任务顺序后，最早开工不会恶化本月三种目标。
全局排列与指派的笛卡尔积覆盖所有机器顺序；重复覆盖只影响速度。
```

### 6.1 主体结构

```text
validate_instance(instance)                     # 先确认问题本身合法
if any(len(job.operation_ids) != 1 ...): raise  # 只支持单工序
size = n! * ∏|eligible_i|;  if size > limit: raise
for assignments in product(*(每个工序的资格机器)):        # 外层：指派
    for order in permutations(range(n)):                 # 内层：全局排列
        available = {machine.id: 0 for machine in machines}   # 每次重置
        for index in order:
            op      = instance.operations[index]
            machine = assignments[index]
            start   = max(available[machine], jobs[op.job_id].release_time)
            end     = start + op.processing_time
            output.append(ScheduledOperation(op.id, machine, start, end))
            available[machine] = end
        value = float(OBJECTIVES[objective](instance, schedule))
        count += 1
        if value < best_value: best_value, best_schedule = value, schedule
return best_value, best_schedule, count
```

三个返回值各有用途：`best_value` 是**最优值**（对拍用），`best_schedule` 是**达到它的排程**（可行性用），`count` 是**实际枚举次数**（证明「真的穷举了」）。

### 6.2 为什么必须自己维护 `available`

**它不调用 `decode`。** 理由和 Day 4 的验证器是同一条，但方向相反：

| | `decode` | `oracle` |
|---|---|---|
| 输入 | `(Instance, Candidate)` | `(Instance,)` |
| 维护的是 | `machine_ready` + `ends`（前驱完工） | 只有 `available`（机器可用时刻） |
| 顺序从哪来 | `Candidate.order`（优先级列表，扫描时取前驱已就绪的第一道） | 全局排列直接给出遍历顺序 |
| 支持多工序 | 是 | 否 |

如果 `oracle` 调用 `decode`，那么它「证明」的就变成了「`decode` 在自己能到达的解空间里的最小值和 `decode` 的最小值一致」——**同义反复**。独立路径的价值恰恰在于它重写了一遍时间推进逻辑：

```python
start = max(available[machine], jobs[op.job_id].release_time)
```

对比 `decode` 的 `max(machine_ready, predecessor_end, release)`——少了 `predecessor_end`，因为单工序作业没有前驱。

**两条路径都算出一个相同的 `Cmax`，才说明时间推进没写错。** 这是 Week 1「不能让 `decoder` 自己证明自己」原则的又一次落地，也是周总结遗留问题第 6 条的答案。

### 6.3 与测试里的第三条路径

`test_five_independent_enumerations` 在 `oracle` 之外又走了一条**中间路径**：

```python
actual = min(
    makespan(instance, decode(instance, Candidate(order, assignment)))
    for order in permutations(op.id for op in instance.operations)
    for assignment in product(("M0", "M1"), repeat=4)
)
assert actual == optimum
```

这条路径用 `Candidate + decode` 遍历**同样大小的 384 个组合**，取目标最小值，再要求它等于 `oracle` 的 `best_value`。于是同一批实例上有了三层证据：

```text
① Week 1 的手算：证明「规则 + 时间推进」在若干显式案例上正确
② Candidate + decode 全枚举：证明「解码器」在 384 个候选上正确
③ oracle 自建时间表：证明「目标公式的输入」在 384 个排程上正确
```

**注意这三条共享同一个 `objective.py`。** 所以目标公式本身还需要第 ① 层（手算）提供独立证据——这也是 Week 1 十个手算案例一直保留的原因。

### 6.4 覆盖不到的

```text
不覆盖：多工序（被显式拒绝）、资格受限的组合爆炸、非 regular 目标
不覆盖：大规模实例（limit 之外一律拒绝，不降级、不近似）
不覆盖：任何「最优性证明」的持久化——它每次运行都重算
```

---

## 7. 实验：`m1w2d6_verification`

对应脚本 [m1w2d6_verification.py](../../projects/01_scheduling_core/examples/m1w2d6_verification.py)，它把与本周相关的测试选择器打包成一次运行。在仓库根目录执行：

```bash
python projects/01_scheduling_core/examples/m1w2d6_verification.py
```

实际输出（截取末尾统计行）：

```text
tests/test_month1.py::test_five_independent_enumerations[0] PASSED       [ 39%]
tests/test_month1.py::test_five_independent_enumerations[1] PASSED       [ 42%]
tests/test_month1.py::test_five_independent_enumerations[2] PASSED       [ 46%]
tests/test_month1.py::test_five_independent_enumerations[3] PASSED       [ 50%]
tests/test_month1.py::test_five_independent_enumerations[4] PASSED       [ 53%]
tests/test_month1.py::test_three_decoder_traces[order0-assignments0-expected0] PASSED [ 57%]
tests/test_month1.py::test_three_decoder_traces[order1-assignments1-expected1] PASSED [ 60%]
tests/test_month1.py::test_three_decoder_traces[order2-assignments2-expected2] PASSED [ 64%]

====================== 28 passed, 28 deselected in 0.34s ======================
```

只跑枚举那 5 条（在项目目录下）：

```bash
python -m pytest tests/test_month1.py -k enumeration -v
```

实测 `5 passed, 51 deselected`——正好对应 `seed = 0…4` 五个实例。

**实验结论**：

1. `test_five_independent_enumerations` 对每个种子做四件事：枚举得到 `optimum`、断言 `count == 384`、用 `Candidate + decode` 独立复算最小值并要求相等、对六个算法断言 `result.objective >= optimum`。
2. **最后一条断言是不等式而不是等式**，这一点必须读懂：它验证的是「搜索没有报出比最优值更小的数」——这是**正确性检查**（`decoder` 或 Objective 若偏小就会立刻暴露），不是「搜索找到了最优」。
3. 五个实例都是 `jobs=4, machines=2`，与 MONTH1_REPORT 第 4 节记录的「oracle 与 decoder 对拍，每例 384 组合」一致。
4. 报告里另有 `tiny_single`（`optimum=36`）与 `tiny_parallel`（`optimum=38`）两个被枚举证明最优的实例，它们的 `reference_type` 在 `results.csv` 里记为 `optimum`，因此 gap 的分母是**真最优值**，而不是 `best-known`。

**规模练习**：把 `jobs` 改成 5，每例组合数变成 `120 × 32 = 3840`；改成 8，`40320 × 256 = 10321920`，超过默认限额 `100_000`，`exhaustive_optimum` 会抛 `enumeration too large: 10321920 > 100000`。

---

## 8. 今日练习

1. **练习 1（手算）**：对第 5 节的 `seed=0` 实例，手动检查「J000 与 J002 交换机器」后的 `Cmax`，说明为什么它不更优。
2. **练习 2（规模）**：手算 `n=6, m=3` 的组合数（`524880`），说明为什么它一定被 `limit` 拒绝。
3. **练习 3（论证复述）**：不看第 4 节，把「为什么可以称 `optimum`」的三段论证写一遍，并指出每一段各自推翻了哪种「漏解」的可能。
4. **练习 4（regular）**：给出一个具体的 `ΣEj`（提前惩罚）实例，说明「尽早开工」会让它变差。
5. **练习 5（表述辨析）**：把「`LPT` 在 `seed=0…3` 上追平了枚举最优值」改写成两种句子：一种是**实验观察**，一种是**错误的理论结论**，并说明错在哪里。

---

## 9. 验收清单

- [ ] 能写出规模公式 `n! · m^n`，并算出 384 / 3840 / 46080 / 10321920 四个数字。
- [ ] 能说出 `oracle` 只支持「每作业一道工序」，并解释为什么。
- [ ] 能说明 `oracle` 自己维护 `available` 而不调用 `decode` 的理由（同义反复）。
- [ ] 能完整复述「尽可能早开工 + regular objective + 笛卡尔积覆盖」三段论证。
- [ ] 能说明重复覆盖为什么只影响速度、不影响正确性。
- [ ] 能举出 `ΣEj` 这个非 `regular` 目标，说明论证为何失效。
- [ ] 能解释 `limit=100_000` 的拒绝行为，以及为什么不能用受限枚举冒充整体 `optimum`。
- [ ] 能区分「某实例上追平枚举最优值」与「具有全局最优保证」。
- [ ] `python -m pytest tests/test_month1.py -k enumeration -q` 输出 `5 passed`。
- [ ] `python -m pytest -q` 全部通过（本仓库当前为 127 条）。

---

## 10. 自测题

不看上文回答：

- Q1：`exhaustive_optimum` 遍历的两层循环分别是什么？
- Q2：`n=4, m=2` 的组合数是多少？`n=5` 呢？`n=8` 呢？
- Q3：`size` 用的是实例的机器总数还是每道工序的资格机器数？
- Q4：`oracle` 为什么不调用 `decode`？
- Q5：`oracle` 的 `start` 公式比 `decode` 少了哪一项？为什么可以少？
- Q6：什么是 `regular objective`？本月哪三个目标是 `regular` 的？
- Q7：三段论证分别是什么？哪一段用到了 `regular`？
- Q8：为什么不同全局排列会重复覆盖同一个排程？这会造成错误吗？
- Q9：`limit` 默认值是多少？超限时代码怎么做？
- Q10：为什么「`LPT` 在 `seed=0` 上追平了 `optimum=29`」不能推出「`LPT` 是最优算法」？

### 参考答案

- A1：外层是 `product(*eligible)` 遍历机器指派，内层是 `permutations(range(n))` 遍历全局排列。
- A2：384（`24×16`）、3840（`120×32`）、10321920（`40320×256`）。
- A3：每道工序自己的 `len(op.eligible_machine_ids)`，所以只有全机器资格时才退化成 `m^n`。
- A4：调用 `decode` 就变成「用 `decode` 验证 `decode`」的同义反复；`oracle` 需要一条独立的时间推进路径才有证据价值。
- A5：少了 `predecessor_end`。因为 `oracle` 只支持每作业一道工序，不存在前驱工序。
- A6：所有 `Cj` 都不增时目标值不增（对完工时间非降）的目标。本月的 `makespan` / `total_tardiness` / `weighted_completion_time` 都是。
- A7：① 固定机器顺序后尽早开工逐项支配；② `regular objective` 使「逐项更早」推出「不更差」；③ 全局排列 × 指派的笛卡尔积覆盖所有「每台机器顺序」。第 ② 段用到 `regular`。
- A8：跨机器的交错合并方式不唯一，同一组「每台机器顺序」可以由多个全局排列诱导；只造成重复评估，不会漏解。
- A9：`100_000`。超限时直接 `raise ValueError(f"enumeration too large: {size} > {limit}")`，不降级、不近似。
- A10：那只是一个实例上的**实验观察**；`seed=4` 上同一算法得 28 而最优是 25，已经反证了它没有全局最优保证。

---

## 11. 今日一句话总结

> **`oracle` 用 `n! · m^n` 的完整枚举、自己维护的 `available` 时间表和「尽早开工 + `regular` 目标 + 笛卡尔积覆盖」的三段论证，给出了本月唯一一个能称 `optimum` 的参照值；但它只在单工序、小规模、`regular` 目标下成立——而「某个启发式追平过一次」永远只是实验观察，不是最优性证明。**
