# Day 5：统一结果接口——让 MILP / CP-SAT / 启发式说同一种话

> 当日主题：用一份共同的 `SolveResult` 收拢三类方法的输出，把「没有 bound」与「bound 为 0」彻底分开
> 当日产出：**统一结果接口的说明与验收**（8 个状态、三条纪律、缺值写空、独立验证器挂钩）
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 说出为什么「三种方法各自返回自己的字典」会让比较退化成「读日志」。
2. 背出 8 个状态并说出每一个对应什么结局。
3. 说出 `SolveResult` 的九个字段各自记录什么，哪些允许为 `None`。
4. 说清 `gap` 什么时候返回 `None`、什么时候返回 `0`，以及两者的区别为什么是纪律问题。
5. 说清「求解器说 `OPTIMAL`」与「解真的可行」为什么是两件事，以及本仓库靠什么把两者分开。
6. 说出 `__post_init__` 里那条 `best_bound > objective + 1e-6` 守卫拦的是什么错误。
7. 说出 `to_row()` 为什么让 `None` 保持为空，而不是落成 0。

---

## 2. 为什么今天要专门讲「一个接口」

前四天各做一件事：Day 1 加破缺、Day 2 加初解、Day 3 做诊断、Day 4 配预算。它们有一个共同的前提：**四种方法的结果必须落到同一张表上**。否则 Day 6 的比较、Day 7 的汇总、甚至 Week 4 的选择矩阵都无从谈起。

问题在于四种方法的原生输出差别很大：

```text
LP / MILP     status + objective + best_bound，三者齐全
CP-SAT        OPTIMAL / FEASIBLE / UNKNOWN / INFEASIBLE / MODEL_INVALID，
              而且「只找可行解」模式下**没有可比的下界**
启发式        M1 的规则、局部搜索、SA —— **完全没有 bound**
JSP / 累积    可能有解但没有排程（纯参数模型），也可能有排程没有界
```

如果放任每种方法各返回各的字典，比较就会退化成「把四份日志并排看」。更糟的是**缺值会被悄悄填成 0**：启发式没有界，`best_bound = 0`，于是 `gap = 1.0`；或者更常见的错误——把 `best_bound` 填成 `objective`，`gap = 0.0`，看上去「已证明最优」。

```text
接口的职责不是「让输出好看」，
而是**让不可能被混淆的东西在类型层面就无法混淆**。
```

这一节的知识链：

```text
M1 Week 2 Day 4   区分 incumbent / bound / gap：三个量三个来源
M2 Week 3 Day 5   五个状态的含义；OUTPUT 只在有解状态下可读
Day 4（昨天）      预算、终止原因、两类时间必须一起记
Day 5（今天）      把这些量收进一个冻结的数据类，缺值一律 None   ← 今天
Day 6             在同一张表上比较方法                              ← 明天
```

---

## 3. 概念：状态词表与字段表

### 3.1 定义（8 个状态）

`opt_solvers/result.py` 的 `STATUSES` 是一个 8 元组。前五个来自 CP-SAT 的原生语义，后三个是工程包装：

| 状态 | 含义 | 有解吗 |
|---|---|---|
| `OPTIMAL` | 已证明最优：存在达到 `best_bound` 的可行解 | 有 |
| `FEASIBLE` | 找到可行解，但未证明最优（时间限制 / 未搜完） | 有 |
| `INFEASIBLE` | 已证明无可行解 | 无 |
| `UNKNOWN` | 预算内既没找到解，也没证明不可行 | 无 |
| `MODEL_INVALID` | 模型本身非法（变量界矛盾、表达式溢出等） | 无 |
| `FEASIBLE_OR_UNKNOWN` | CP-SAT 在「只找可行解」模式下的原生状态 | 可能有 |
| `FAILED` | 包装层异常（求解抛错），原因放 `detail` | 无 |
| `NOT_SOLVED` | 求解器根本没被调用（例如建模阶段就报错） | 无 |

配套一个 3 元组 `FEASIBLE_STATUSES = ("OPTIMAL", "FEASIBLE", "FEASIBLE_OR_UNKNOWN")`，用来回答「这个结果里到底有没有排程可查」。

**注意 `FEASIBLE_OR_UNKNOWN` 的位置**：它被放进了「有解」那一组。这条归类的依据是 CP-SAT 的语义——该状态的产出是一个**已经满足全部约束的解**，只是求解器拒绝声称自己证明了最优。这与 `UNKNOWN` 有本质区别：`UNKNOWN` 什么都没给。

### 3.2 定义（九个字段）

```python
method: str                      方法名（与注册表里的名字一致）
status: str                      上面 8 个之一
objective: float | None          目标值（没找到解时为 None）
best_bound: float | None         已证明的下界（不提供下界时为 None）
schedule: Schedule | None        排程（纯参数模型允许为 None）
build_time: float                建模耗时
solve_time: float                求解耗时
iterations: int | None           搜索规模（CP-SAT 记 branches，CBC 记 nodes）
detail: dict[str, Any]           诊断细节（终止原因、求解器自己的状态等）
```

加一条派生属性 `wall_time = build_time + solve_time`。**它是属性而不是字段**，这一点是刻意的：如果 `wall_time` 是可写字段，就允许出现「总计 3 秒、建模 1 秒、求解 1 秒」这种自相矛盾的行。

### 3.3 定义（两种「没有」）

今天的核心区分不是「有 / 没有」，而是**两种不同的「没有」**：

```text
没有这个量          启发式没有 bound —— 这是**方法的性质**，换实例也不会变
这次没算出这个量    求解器没给 bound —— 这是**这次运行的性质**，加预算可能就有
```

在 `SolveResult` 里两者**都写 `None`**，理由是外部的读表人不需要（也不应该）从数值上区分它们：无论哪种情况，`gap` 都不可计算。要区分时看 `status` 与 `detail`。

---

## 4. 手算：把显示值和真实值分开

`m2w4d5` 的输出里 `milp_tight` 一行是 `目标 543 / bound 55.2 / gap 0.8984`。用接口里那条定义手算一遍：

```text
gap = (objective - best_bound) / max(1, |objective|)
    = (543 - 55.2) / max(1, 543)
    = 487.8 / 543
    = 0.89834...
```

手算得 `0.8983`，屏幕上是 `0.8984`，差 `1e-4`。这不是接口算错了，而是**反推**：

```text
0.8984 = (543 - b) / 543  →  b = 543 × (1 - 0.8984) = 55.1688
```

真实的界约 `55.17`，显示时被舍成一位小数变成 `55.2`。**用显示值手算永远对不上最后一位**，要复现就得拿未舍入的数。这正是接口的设计：`SolveResult` 内部保存完整精度，只在 `to_row()` 里对时间做 6 位舍入，数值字段**一个都不舍**；打印成表是示例脚本的职责。读数时不要拿表格里的显示值去反推公式。

### 4.1 手算：那条守卫在什么数值上会响

`__post_init__` 里的判定是 `best_bound > objective + 1e-6`。用具体数值走三个例子：

```text
① 正常（最小化）：objective = 968, best_bound = 65.5093
   65.5093 > 968 + 1e-6 ？ 否 → 通过
② 方向搞反（把最大化问题的上界塞进来）：objective = 543, best_bound = 950
   950 > 543 + 1e-6 ？ 是 → 抛 ValueError
③ 浮点误差边缘：objective = 543, best_bound = 543 + 5e-7
   543.0000005 > 543.000001 ？ 否 → 通过（被容差放过）
④ 超出容差一点点：objective = 543, best_bound = 543 + 2e-5
   543.00002 > 543.000001 ？ 是 → 抛 ValueError
```

两条读数：

- **容差是双向的**：它让浮点误差不至于误报，代价是 `1e-6` 以内的真正越界会被静默放过。所以守卫是「拦大错」，不是「保证正确」。
- **`gap` 与守卫用的是同一个方向约定**：都假设最小化（`objective >= best_bound`）。换目标方向时，包装层必须自己完成转换，接口不会替它判断——这也是为什么报错信息写的是「请检查目标方向」，而不是「界算错了」。

---

## 5. 实现：`opt_solvers/result.py` 逐段读

对应文件 [result.py](../../projects/02_optimization_models/opt_solvers/result.py)（128 行）。它是 M2 的共享地基，**本日不重新实现它**——今天要做的是读懂它、用它、并检验它的纪律。

### 5.1 构造即校验

```python
@dataclass(frozen=True, slots=True)
class SolveResult:
    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"unknown status: {self.status}")
        if self.objective is not None and self.best_bound is not None:
            if self.best_bound > self.objective + 1e-6:
                raise ValueError(
                    "best_bound > objective: 下界高于可行解，请检查目标方向"
                )
```

三处设计值得记住：

1. **`frozen=True`**：结果一旦产生就不可改。避免调用方在拿到结果后「顺手修一下界」，让证据链断掉。
2. **状态白名单**：拼错的状态（`"OPTIMAL "` 带空格、`"optimal"` 小写）在构造时就抛错，而不是等到落表时才发现某一列多了个奇怪的取值。
3. **`best_bound > objective` 守卫**：对最小化问题，已证明的下界**不可能**高于已找到的可行解目标值。触发这条守卫意味着包装层搞错了方向——最常见的原因是**把最大化问题的界直接塞进最小化的结果里**（对最大化，`best_bound` 是上界，数值上常常大于目标值）。容差 `1e-6` 是给浮点误差留的。

### 5.2 三个派生属性

```python
@property
def gap(self) -> float | None:
    if self.objective is None or self.best_bound is None:
        return None
    return (self.objective - self.best_bound) / max(1.0, abs(self.objective))
```

- `has_solution`：`objective is not None`——**只看目标值**，不看状态。原因是一个方法在某些包装层里可能返回排程却忘了填目标值（那是 bug），此时不应该被当成「有解」。
- `gap`：任一端为 `None` 就返回 `None`。**绝不返回 0**。已证明最优时（`objective == best_bound`）自然返回 `0.0`——所以「`gap` 是 0」和「`gap` 是 `None`」分别表示「证明完了」和「无从谈起」，两者在数值上相距无穷远，在语义上也是。
- `proven_optimal`：`status == "OPTIMAL"`。注意它**不看 `gap`**：有些求解器会给出 `objective == best_bound` 但状态仍是 `FEASIBLE`（界恰好撞上），此时不能声称证明最优。**状态是唯一权威**，数值一致只是巧合。

### 5.3 落表：`None` 保持为空

```python
def to_row(self) -> dict[str, Any]:
    """展开为 benchmark CSV 的一行。``None`` 保持为空，不写成 0。"""
```

`to_row()` 只做一件事：给出 CSV 一行的九个键。`None` 原样保留，由写 CSV 的那一层落成空单元格。为什么不能写 0：

```text
空单元格    读表人看到「这项没有」
0           读表人看到「测出来是 0」
            对 bound 来说，「0」是一个**有意义且常常正确**的值
            （混合整数模型的根界确实可能是 0，见 Week 2），
            所以填 0 不是「近似」，是**伪造了一个具体结论**。
```

### 5.4 独立验证器挂钩

```python
def validate_result(instance: Instance, result: SolveResult) -> list[str]:
    if result.schedule is None:
        return []
    from opt_common.bridge import schedule_errors
    return list(schedule_errors(instance, result.schedule))
```

这是今天最重要的一段。它把 M1 的 `schedule_errors`（独立验证器）挂在统一接口上，回答一个求解器**无法**回答的问题：

```text
求解器说的 OPTIMAL 是「在我这个模型里最优」，
不是「这份排程在现实的时间轴上合法」。
模型可能建错（漏了 release time、目标写反、时间索引差一格），
求解器照样会给你一个漂亮的 OPTIMAL。
```

所以每个返回排程的结果都要过一遍独立验证器。这一步与 Week 2 建立的纪律是同一条：「不信任求解器的自我声明，用独立实现的对拍」。`require_feasible()` 是它的强化版（不通过就直接抛异常），供测试与示例使用。

### 5.5 这段代码**不**检查什么

接口的边界要和它的能力一起记住，否则会把「没报错」当成「没问题」：

```text
不检查 objective 与 schedule 是否一致
    可以传入一个目标值 100 但排程实际目标 250 的结果，构造不会报错。
    对不上的话，只能靠 validate_result 与逐日实验里的人工核对。
不检查 status 与数值的搭配
    status="INFEASIBLE" 同时带一个 objective 是允许的（接口不禁止）。
不检查 NaN / inf
    objective 是 nan 时，best_bound > objective 的比较恒为 False，守卫不会响。
不阻止修改 detail
    frozen 只冻结字段的重新绑定；detail 是一个可变字典，其内容仍可被改写。
```

最后一条是这类「冻结数据类」的常见误解：`frozen=True` 保证的是「不能给 `result.objective` 重新赋值」，不保证 `result.detail["nodes"] = 0` 会失败。**证据链的完整性靠纪律，不靠 `frozen`。**

---

## 6. 三类方法进同一个接口会长什么样

把字段表按方法族摊开：

| 方法族 | `status` | `objective` | `best_bound` | `gap` | `schedule` | `build_time` |
|---|---|---|---|---|---|---|
| 规则启发式 | 恒为有解类 | 有 | **恒为 `None`** | **恒为 `None`** | 有 | ≈ 0 |
| 序列 MILP | 5 类之一 | 有解时 | 有（时间到了也给） | 有解时 | 有 | 有 |
| CP-SAT | 5 类之一 | 有解时 | 通常有；只找可行解模式下 `None` | 视上格 | 有 | 有 |
| 纯参数模型（LP） | 5 类之一 | 有 | 有 | 有 | `None` | 有 |

这张表解释了一个很容易踩的坑：**「`gap` 全是 `None` 的一列」不代表方法弱，只代表这一列对它不适用**。规则启发式在任何实例、任何预算下都给 `None`——因为规则解**没有**下界可证，这不是这次的运气问题。Day 1 实验表里的 `heur_spt` 行永远读不出 `gap`，读不出就得写「不适用」，不能写 0，也不能拿它去和 MILP 的 gap 并列比较。

---

## 7. 实验：`m2w4d5_unified_result`

对应脚本 [m2w4d5_unified_result.py](../../projects/02_optimization_models/examples/m2w4d5_unified_result.py)，在项目目录下运行：

```bash
python examples/m2w4d5_unified_result.py
```

实例是 `seed=51, jobs=12, machines=1` 的单机 ΣT，`spec` 给 `time_limit=10.0`、`seed=0`。实际输出：

```text
== 1. 状态词表：一次说清所有可能的结局 ==
  8 个状态：OPTIMAL, FEASIBLE, INFEASIBLE, UNKNOWN, MODEL_INVALID, FEASIBLE_OR_UNKNOWN, FAILED, NOT_SOLVED
  前五个是 CP-SAT 的原生语义；FAILED / NOT_SOLVED 是工程包装；
  FEASIBLE_OR_UNKNOWN 是「只找可行解」模式下的原生状态。

== 2. 三类方法进同一个接口 ==
  方法                     状态             目标     bound      gap    建模(s)    求解(s)     验证
  heur_spt               FEASIBLE      532      None     None    0.000    0.000     通过
  milp_tight             FEASIBLE      543      55.2   0.8984    0.013   10.519     通过

== 3. 纪律一：启发式必须写 None，不能写 0 ==
  heur_spt: best_bound=None  gap=None
  如果把 best_bound 填成目标值，gap 会恒为 0，看起来「已证明最优」——
  这是求解器实验里最严重的伪证据，接口层直接禁止这种填法。

== 4. 纪律二：建模时间与求解时间是两个问题 ==
  heur_spt               建模 0.0000s / 总计 0.0002s（占   0.0%）
  milp_tight             建模 0.0134s / 总计 10.5326s（占   0.1%）

== 5. 纪律三：OPTIMAL 不等于解可行 ==
  milp_tight 状态 = FEASIBLE —— 求解器未证明最优，只给出一个可行解
  独立验证器对返回排程的诊断 = 无（可行）
  两件事必须分开：前者是求解器对**模型**的声明（而且本例里它并没有做出
  「最优」的声明），后者是 M1 的 schedule_errors 对**时间轴是否真的合法**的判断。
  无论状态是 OPTIMAL 还是 FEASIBLE，排程都必须过独立验证器——
  求解器的声明不构成可行性的证据。

== 6. 落表时 None 保持为空 ==
  heur_spt.to_row() = {'method': 'heur_spt', 'status': 'FEASIBLE', 'objective': 532.0, 'best_bound': None, 'gap': None, 'iterations': None, 'build_time': 0.0, 'solve_time': 0.000228, 'wall_time': 0.000228}
  写进 CSV 后是空单元格，不是 0——读表的人一眼能看出「这项没有」，
  而 0 会被误读成「测出来是 0」。

== 7. 当前注册的方法总览 ==
  cpsat_cumulative
  cpsat_jsp
  cpsat_parallel
  cpsat_symmetry
  heur_edd
  heur_lpt
  heur_parallel_lpt
  heur_spt
  heur_wspt
  milp_alt
  milp_fixing
  milp_loose
  milp_tight
  milp_warmstart

全部断言通过。
```

### 7.1 读数

1. **`heur_spt` 与 `milp_tight` 落在同一张表上，列数一样。** 这就是接口的全部意义：两种语义完全不同的方法，输出形状一致，可以并排读、可以落进同一份 CSV。表头里的 `None` 是**字符串** `None`（脚本显式做了 `"None" if r.gap is None`），不是空——真正的空只出现在 CSV 里。
2. **启发式那一行的 `None` 是方法性质，不是这次运行的结果**：换实例、换预算、换机器，这一列永远是 `None`。这正是「两种没有」里应当由 `status` 与 `detail` 区分、而不该由数值区分的情形。
3. **这一行同时暴露了一条不好看但必须写进笔记的事实**：`milp_tight` 在 10 秒预算下给出 `543`，比 `heur_spt` 的 `532` **更差**。正确读法是「预算内的精确方法不保证优于一个规则解」——10 秒不够 CBC 在序列模型上搜出比 SPT 更好的解。这不是接口的问题，而是 Day 6 选择矩阵里的一条实测依据：**大规模 / 预算不足时先给规则解**。
4. **第 4 节的百分比只在这一行内部有意义**：`heur_spt` 的 `0.0%` 是因为它根本没有建模阶段（`build_time = 0.0`），不是「建模快得测不出来」；`milp_tight` 的 `0.1%` 则完全由分母（10.5 秒的求解）撑出来。两者的占比不可比。
5. **`wall_time` 是算出来的**：`0.000228` 秒 = `build_time 0.0 + solve_time 0.000228`，与 `to_row()` 里的 `wall_time` 一致——它没有被单独存储，所以不可能与两段之和不符。
6. **第 5 节那一行括号文本是本脚本的固定模板**，写的是「求解器证明了自己的**模型**最优」。本次运行的 `status` 是 `FEASIBLE`，**没有**证明最优（Day 4 已说明 10 秒档在这个实例上搜不完）。所以这句括号不能按字面读成本次结论——**以打印出来的状态为准**，脚本在这一点上的措辞是宽松的。真正承重的是紧跟着的那句「两件事必须分开」。
7. **`**模型**` 在终端里就是字面的四个字符**（两个星号 + 模型 + 两个星号），终端不做 Markdown 渲染。粘贴输出时不要手改，改了就不叫「实际输出」了。
8. **第 7 节列出 14 个方法**：5 个 M1 规则（`heur_spt` / `heur_edd` / `heur_wspt` / `heur_lpt` / `heur_parallel_lpt`）、3 个 CP-SAT（`cpsat_parallel` / `cpsat_jsp` / `cpsat_cumulative`）、3 个 MILP（`milp_tight` / `milp_loose` / `milp_alt`）、3 个本模块的新方法（`cpsat_symmetry` / `milp_warmstart` / `milp_fixing`）。名字由 `registry` 统一注册，Benchmark 只认名字——所以「某一周还没实现」不会让整批跑不起来，缺名字会被记成 `FAILED` 而不是崩溃。

### 7.2 一条已知局限（如实记录）

`validate_result()` 在 `schedule is None` 时返回空列表，与「验证通过」的返回值**完全相同**。也就是说：

```text
对一个不返回排程的结果（纯参数模型），
调用 validate_result 得到的 [] 什么都没验证。
```

这是有意的宽松设计（接口不能强迫每个方法都产出排程），但它意味着「验证列全是通过」这句话在**混合方法表**里是弱结论：要确认验证真的发生了，得先确认该方法确实返回了排程（`schedule is not None`）。`require_feasible()` 在这一点上更严：没有排程直接抛异常。

### 7.3 接入一个新方法要做的六件事

统一接口的价值在「加方法不用改比较脚本」上兑现。接入一个 M3 的新模型，只需要：

```text
① 写 solve_fn(instance, spec) -> SolveResult，spec 里读 time_limit / seed / objective
② 用 @register("名字", "一句话说明") 注册（重名会抛 ValueError，硬拦）
③ 有排程就填 schedule；没有排程（纯参数模型）留 None
④ 有界就填 best_bound；启发式没有界就留 None —— 绝不填 0 或目标值
⑤ 分开记 build_time 与 solve_time（求解器调用前后各打一次 perf_counter）
⑥ 用 validate_result 自检一次，确认返回的排程过得了 M1 的 schedule_errors
```

反过来说，只要这六件事都做到，月末批次的 `benchmark.py` 就能按名字调到它——**不需要改批次代码，也不需要改领域模型**。这正是 Day 7 那句「交给 M3 的接口：一行都不用改」的具体含义。

一个最小的骨架：

```python
@register("fjsp_cpsat", "M3 FJSP：工序机器双重选择 + NoOverlap")
def solve_fjsp(instance: Instance, spec: dict[str, Any]) -> SolveResult:
    started = time.perf_counter()
    model, ctx = build_fjsp_model(instance, spec)
    build_time = time.perf_counter() - started
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(0.001, float(spec.get("time_limit", 10.0)))
    call_started = time.perf_counter()
    status = solver.Solve(model)
    solve_time = time.perf_counter() - call_started
    return SolveResult(
        method="fjsp_cpsat",
        status=solver.StatusName(status),
        objective=solver.ObjectiveValue() if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
        best_bound=solver.BestObjectiveBound() if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
        schedule=...,
        build_time=build_time,
        solve_time=solve_time,
    )
```

骨架里有两处**故意留的省略**，接入时都要补上：一是 `schedule` 的还原（从求解器变量反解出 M1 的 `Schedule`），二是状态与数值的配对（只有在有解的状态下才读目标值与界）。省略它们是为了让骨架短，不是因为它们可以省。

---

## 8. 今日练习

1. **练习 1（状态判定）**：某方法返回 `status="FEASIBLE"`、`objective=100`、`best_bound=100`，它能否声称证明了最优？请写出判断依据，并说明数值一致为什么不能替代状态。
2. **练习 2（守卫生效）**：把某**最大化**问题的 `best_bound`（上界，数值上大于目标值）塞进 `SolveResult` 会触发什么？说出报错信息里的关键那句。
3. **练习 3（手算 gap）**：用 `milp_tight` 的 `543 / 55.2` 手算 `gap`，解释为什么与屏幕上的 `0.8984` 差 `1e-4`。
4. **练习 4（缺值）**：为什么 `heur_spt` 的 `best_bound` 必须写 `None` 而不是 `0`？给出两条理由（一条关于语义、一条关于「0 是一个合法值」）。
5. **练习 5（接口纪律）**：说出把 `wall_time` 设计成属性而不是字段的好处，并举出一种「字段版本」才可能出现的矛盾行。

---

## 9. 验收清单

- [ ] 能背出 8 个状态并说出每一个对应什么结局。
- [ ] 能说出 `FEASIBLE_OR_UNKNOWN` 为什么被归进「有解」那一组。
- [ ] 能说出 `gap` 什么时候返回 `None`、什么时候返回 `0`，以及两者的语义差别。
- [ ] 能说出 `best_bound > objective + 1e-6` 守卫拦的是什么错误（含最大化问题的情形）。
- [ ] 能说出 `proven_optimal` 为什么不看 `gap`、只看 `status`。
- [ ] 能说出 `validate_result` 与 `require_feasible` 的分工，以及前者在 `schedule is None` 时的局限。
- [ ] 能说出 `to_row()` 为什么让 `None` 保持为空。
- [ ] 能说清「启发式没有 bound」与「求解器这次没给出 bound」是两种不同的「没有」。
- [ ] 在项目目录下运行 `python examples/m2w4d5_unified_result.py`，全部断言通过。
- [ ] 在项目目录下运行 `python -m pytest -q` 全绿（含 `tests/test_foundation.py` 里对状态白名单与守卫的用例）。

---

## 10. 自测题

不看上文回答：

- Q1：为什么四种方法各自返回字典会让比较退化成「读日志」？
- Q2：8 个状态里哪些属于「有解」？`FEASIBLE_OR_UNKNOWN` 为什么在其中？
- Q3：`SolveResult` 的 `wall_time` 为什么是属性而不是字段？
- Q4：`gap` 在什么情况下返回 `None`？在什么情况下返回 `0`？两者能混用吗？
- Q5：`proven_optimal` 为什么只看 `status`，不看 `gap == 0`？
- Q6：`__post_init__` 里的守卫拦的是什么？为什么容差是 `1e-6`？
- Q7：求解器说 `OPTIMAL` 为什么不等于解可行？本仓库靠什么把两者分开？
- Q8：`to_row()` 为什么要让 `None` 保持为空？把缺的 bound 写成 0 会误导成什么？
- Q9：「启发式没有 bound」与「求解器这次没给 bound」有什么区别？在接口里怎么体现？
- Q10：本次运行里 `milp_tight`（543）比 `heur_spt`（532）更差，这说明什么？

### 参考答案

- A1：四种方法的原生输出字段和语义都不同（有的没有界、有的没有排程），并排看结果就没有共同列可比；统一接口让它们形状一致。
- A2：`OPTIMAL` / `FEASIBLE` / `FEASIBLE_OR_UNKNOWN`；后者是 CP-SAT「只找可行解」模式的原生状态，它确实给出了满足全部约束的解，只是不声称最优。
- A3：因为它是派生量（`build_time + solve_time`）。做成字段就可能出现「总计 ≠ 两段之和」的自相矛盾行。
- A4：`objective` 或 `best_bound` 任一端为 `None` 时返回 `None`；两端都有且相等（已证明最优）时返回 `0.0`。不能混用：`None` 表示「无从计算」，`0` 表示「已证明最优」。
- A5：因为状态是求解器的权威声明。数值上 `objective == best_bound` 可能只是巧合（界恰好撞上），此时求解器并未证明最优，不能替它宣称。
- A6：拦的是「已证明的下界高于已找到的可行解目标值」这种自相矛盾——最小化问题里不可能发生，最常见的成因是把最大化问题的上界塞了进来。容差 `1e-6` 是给浮点误差留的。
- A7：`OPTIMAL` 只说明「在这个模型里最优」，模型本身可能建错（漏 release time、时间索引差一格）；本仓库让每个返回排程的结果过 M1 的 `schedule_errors` 独立验证（`validate_result` / `require_feasible`）。
- A8：写 0 会被读成「测出来是 0」，而 `bound = 0` 是一个**有意义且常常正确**的取值（根界常为 0），所以那不是近似而是伪造结论；空单元格才表示「这项没有」。
- A9：前者是**方法的性质**（换实例也不会变），后者是**这次运行的性质**（加预算可能就有）；接口里两者都写 `None`，需要区分时看 `status` 与 `detail`。
- A10：说明预算内的精确方法不保证优于规则解——10 秒不够 CBC 在序列模型上搜出比 SPT 更好的解。这也正是选择矩阵里「大规模、预算不足时先给规则解」的实测依据。

---

## 11. 今日一句话总结

> **统一接口的价值不在「输出好看」，而在让缺值无法被伪造：8 个状态说清所有结局，启发式的 `best_bound` / `gap` 恒为 `None`（不是 0），求解器说的 `OPTIMAL` 还要再过一遍 M1 的独立验证器才算数——本次 `milp_tight` 在 10 秒预算下给 543（界 55.2、gap 0.8984），甚至比 `heur_spt` 的 532 更差，这条实测同时说明了「预算内的精确方法不保证更优」与「`None` 与 0 必须分开写」。**
