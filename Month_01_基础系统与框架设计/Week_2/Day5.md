# Day 5：随机实例生成与输入质量

> 当日主题：可复现地产生不同规模的输入，并理解生成分布的局限
> 当日产出：**生成器参数表的完整认识 + 局部 RNG 与 JSON/CSV 往返实验**（`generator.py` 解读 + 示例脚本）
> 建议投入：3～4 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 背出 `generate_instance` 的六个参数与默认值（`12 / 3 / 1 / 10 / 1.5`）。
2. 说出加工时间、权重、释放时刻各自的抽取区间，以及交期公式 `due = r + int(sum(p) * due_factor)`。
3. 解释为什么生成器使用局部 `Random(seed)`，以及「调用它不扰动 `random.random()`」意味着什么。
4. 区分「生成器 seed」与「算法 seed」：它们是两个独立 RNG，描述两件不同的事。
5. 说清楚生成器只负责**合法正例**，负例由输入验证器与手工测试负责。
6. 区分**输入验证器**的负例（问题本身非法）与**排程验证器**的负例（结果非法）。
7. 用 CSV 三表入口（`machines.csv` / `jobs.csv` / `operations.csv`）读入实例，知道 `|` 分隔与空交期的处理。
8. 解释为什么 JSON 里的浮点工时会被拒绝，而不是被静默截断成整数。

---

## 2. 为什么第 5 天要「造实例」

到昨天为止，流水线是完整的——但**它没有燃料**：

```text
Instance ──┬─→ Candidate ─→ decode ─→ Schedule ──┬─→ Objective ─→ 数字
           │                                     │
           └─────────────────────────────────────┴─→ Schedule Validator ─→ 诊断
```

每一个方框都验证过了，可所有实验都是在一个两作业三工序的手算实例上跑的。要谈「算法 A 在规模变大时表现如何」，前提是**能造出规模可以调的实例**。

```text
Instance ──┬─→ Candidate ─→ decode ─→ Schedule ──┬─→ Objective ─→ 数字
           │                                     │
           └─────────────────────────────────────┴─→ Schedule Validator ─→ 诊断
     ▲
     └── 【今天接入】Generator：seed → Instance
```

今天要接上的一环在最左边：**实例从哪来**。这一环的位置决定了它极其危险——如果生成器产出的实例有偏，后面所有验证都会通过，所有结论都会「正确但无意义」。

三个必须现在就回答的问题：

1. **可复现**：同一个 `seed` 必须给出同一个实例（否则实验无法重跑）。
2. **不污染**：生成实例不能顺手把全局随机状态改掉，否则算法里的随机行为会因为「是否先生成过实例」而不同。
3. **诚实**：生成器只产合法输入，**负例要另外造**——不能让一个「永远合法」的生成器替输入验证器做证明。

> **一句话：生成器决定实验的「天花板」，它自己却不在任何一张测试表里——所以它的每条约定都必须写成文档 + 断言。**

---

## 3. 生成器的参数表与分布

对应文件 [generator.py](../../projects/01_scheduling_core/scheduling_io/generator.py)。签名只有六个参数，全部有名字：

| 参数 | 含义 | 默认值 |
|---|---|---:|
| `seed` | 实例种子，与算法种子分开 | 必填 |
| `jobs` | 作业数 | 12 |
| `machines` | 同质机器数 | 3 |
| `operations_per_job` | 每个作业链长度 | 1 |
| `release_max` | 释放时刻均匀整数范围上界 | 10 |
| `due_factor` | 交期相对自身总工时的系数 | 1.5 |

抽取规则：

```text
加工时间   p ~ randint(1, 20)        每个工序独立抽一次
权重       w ~ randint(1, 5)        然后转成 float
释放时刻   r ~ randint(0, release_max)
交期       due = r + int(sum(p) * due_factor)     sum(p) 是该作业自身的总工时
```

三点说明：

- **`int()` 是向下取整**（正数上等价于截断）。`due_factor=1.5`、`sum(p)=13` 时 `int(19.5)=19`，交期是 `r+19` 而不是 `r+20`。
- **交期相对「作业自身总工时」定义，不是相对整个实例的工期。** `due_factor=1.5` 的意思是「给这个作业自己 1.5 倍于它工时的窗口」。在繁忙的单机上，多个作业互相排队，`Cj` 很容易超过 `dj`，于是单机实例上会出现大面积迟交。**这是分布的设计选择，不是 bug，但也意味着它不代表任何真实工厂的订单结构。**
- **每个作业的工时先抽完再算交期**，因此 `operations_per_job > 1` 时交期覆盖的是整条工序链，而不是单道工序。

参数合法性检查只有一行，任何一项越界就 fail-fast：

```python
if min(jobs, machines, operations_per_job) < 1 or release_max < 0 or due_factor <= 0:
    raise ValueError("invalid generator parameters")
```

于是 `jobs=0`（没有作业）、`machines=0`（没有机器）、`release_max=-1`（负上界）、`due_factor=0`（交期等于释放时刻）在生成阶段就被挡住，不会流到输入验证器那里。

---

## 4. 决策：局部 RNG、全机器资格、两个独立的 seed

### 4.1 局部 `Random(seed)`：不扰动全局随机状态

```python
rng = Random(seed)          # 一个独立的生成器对象
processing = [rng.randint(1, 20) for _ in route]
```

**定义**：`rng` 是标准库 `random.Random` 的一个实例，它持有自己的状态，与模块级的 `random.random()` / `random.seed()` 使用的那个全局实例**互不影响**。

**理论结论**：只要生成器内部不出现 `random.xxx`（模块级函数），调用 `generate_instance` 就不会改变全局 RNG 的状态。

**实验观察**：先 `random.seed(12345)` 取三个数，再重置种子、在中间调用一次 `generate_instance(99, jobs=8, machines=2)`、再取三个数，两次序列完全相同（见第 7 节实际输出）。

为什么重要：

1. **算法实验的可复现性**。`search.py` 里的 `solve` 用 `Random(config.seed)` 驱动随机移动。如果生成实例会推进全局 RNG，那么「先生成实例还是先求解」会改变搜索结果，实验记录就不再可复现。
2. **测试的独立性**。批量生成 100 个实例不应该让任何依赖全局随机状态的库函数产生不同序列。
3. **这条约定写进了 Week 1 的周总结**（遗留问题第 7 条），也是本项目所有随机性的统一规矩：**谁需要随机，谁自己开一个 `Random`。**

### 4.2 全机器资格：一个必须写清楚的局限

```python
Operation(oid, jid, p, machine_ids)     # machine_ids = 全部机器的 ID
```

生成器把**每道工序的 `eligible_machine_ids` 都设成全部机器**。这不是偷懒，而是为了让 `P||Cmax` 这类经典模型能被直接构造出来（全资格 + `r` 可调 + 同质加工时间）。

但它同时意味着：

> **生成器产出的实例上，「资格受限」这个维度完全没有被覆盖。**

所以「资格受限的案例另用手工测试覆盖」：`route_instance` 里 A 只能上 M0；`test_invalid_inputs_and_rule_eligibility` 里把资格改成 `("M1",)` 再要求 `spt(machine_id="M0")` 抛 `illegal assignment`。**不要让生成器的分布替整个测试矩阵负责。**

### 4.3 生成器 seed ≠ 算法 seed

两个 `seed` 长得一模一样，含义完全不同：

| | 生成器 `seed` | 算法 `seed` |
|---|---|---|
| 作用对象 | `Instance` 的数据 | 搜索过程中的随机动作 |
| 决定 | 工时、权重、释放时刻、交期 | `swap` / `insert` / `reassign` 的选择、SA 的接受判定 |
| 典型取值 | `generate_instance(seed, ...)` | `SearchConfig(algorithm="sa", seed=...)` |
| 相同是否代表同一过程 | **不是** | **不是** |

> **它们是两个独立的 RNG 实例。** 种子数值相同只是巧合，不代表「同一个随机过程」，更不能推出「生成实例和搜索用了同一串随机数」。

因此一个完整的实验记录必须**同时**写下两个种子，并且更稳妥的做法是把**实际生成的输入本身**落盘——`artifacts/month1_refactored/instances/` 下存着 `parallel_12.json` 等真实输入，`results.csv` 里每一行带一个 `input_sha256` 列（例如 `tiny_single` 是 `e55495a649146422c71d4bbceadd6dcfc4c027a6c3605a643ef53ca6a677986a`）。

**只保存随机种子是不够的**：种子只有在生成器代码一字不改时才可复现。一旦 `generate_instance` 的实现或参数默认值变了，同一个种子会产出不同实例，而所有历史结果都失去参照。**输入哈希把「可复现」从「依赖代码版本」变成「自证」。**

### 4.4 正例与负例的分工

| 角色 | 负责 | 靠什么 |
|---|---|---|
| 生成器 | 合法**正例**（工时正、权重正、ID 唯一、引用完整） | `randint` 的区间天然保证 |
| 输入验证器 | 问题本身**非法**的负例 | 手工 `replace` 出坏字段 |
| 排程验证器 | 结果**非法**的负例 | 手工构造坏排程（Day 4） |

输入验证器处理的是这类问题：负工时、重复 ID、引用不存在的机器、空工序链、非有限权重。

```text
输入负例：  这个 Instance 本身合法吗？        → validation.py
排程负例：  这份 Schedule 对这个 Instance 可行吗？ → schedule_validation.py
```

**两个验证器不要混为一谈**：拿一个坏 `Instance` 去问排程验证器，会在第一步 `validate_instance` 上就抛异常；拿一个坏 `Schedule` 去问输入验证器，它根本看不见——它的参数里没有 `Schedule`。

---

## 5. 手算 / 构造：交期公式与规模缩放

### 5.1 手算 `generate_instance(0)` 的前三个作业

`seed=0`、其余全默认（`jobs=12, machines=3, operations_per_job=1, release_max=10, due_factor=1.5`）。前三个作业的实际字段：

| Job | `rj` | `sum(p)` | `due` 推导 | `due` | `wj` |
|---|---:|---:|---|---:|---:|
| J000 | 6 | 13 | `6 + int(13*1.5) = 6 + 19` | 25 | 1 |
| J001 | 8 | 9 | `8 + int(9*1.5) = 8 + 13` | 21 | 4 |
| J002 | 4 | 13 | `4 + int(13*1.5) = 4 + 19` | 23 | 4 |

注意 J001 的 `int(13.5)` 取到 **13** 而不是 14——向下取整在这里是可以手算验证的。

资格字段：

```text
J000_O0: p=13, eligible_machine_ids=('M0','M1','M2')
```

全部机器（`machines=3`，所以是 `M0/M1/M2`），验证第 4.2 节的结论。

### 5.2 规模对照：同一 `seed`，`jobs=6` 与 `jobs=24`

固定 `seed=7`、`machines=3`，只改 `jobs`：

| `jobs` | 工序数 | `total_p` | `max_p` | `mean_p` | `lower_bound` |
|---:|---:|---:|---:|---:|---:|
| 6 | 6 | 35 | 14 | 5.83 | 14 |
| 12 | 12 | 65 | 14 | 5.42 | 22 |
| 24 | 24 | 201 | 19 | 8.38 | 67 |

三点读法：

1. **`total_p` 不是严格按 `jobs` 线性增长的。** 6→24 是 4 倍作业数，总工时从 35 涨到 201（约 5.74 倍）。因为每次抽取都是 `randint(1,20)`，小样本上均值波动很大。
2. **`lower_bound = max(max_p, ceil(total_p / m))`。** `jobs=6` 时 `max_p=14` 本身就压过了 `ceil(35/3)=12`，所以下界是 14；`jobs=24` 时是 `ceil(201/3)=67`。**规模变大后，瓶颈从「最长的那道工序」转移到「平均负载」。**
3. **「目标值更大」≠「算法更差」。** `Cmax` 从十几涨到六十几，只是因为问题本身变大了。跨规模比较目标值毫无意义，**只能在同一实例上比较算法**。

### 5.3 负例：JSON 浮点工时

JSON 入口不做任何类型转换：

```python
processing_time=item["processing_time"]
```

于是 `"processing_time": 1.5` 读进来就是 `float`，然后被输入验证器挡住：

```text
validate_instance -> InstanceValidationError: processing_time must be an integer
```

**为什么不能在这里静默 `int()` 一下？** 因为 `int(1.5)` 会得到 `1`，把「写错的输入」变成「看起来正常的输入」。数据被悄悄改了，后面所有结论都建立在一个不存在的实例上。**fail-fast 的意义就在这里：宁可在门口吵一次，也不要在结果里埋一个永远查不出的偏差。**

同一处约定在测试里的形式是：

```python
with pytest.raises(ValueError):
    validate_instance(replace(instance, operations=(replace(..., processing_time=1.5),)))
```

`InstanceValidationError` 继承自 `ValueError`，所以断言 `pytest.raises(ValueError)` 即可。

### 5.4 CSV 三表入口

`load_csv_instance(directory)` 需要目录下三个文件，用 `|` 表示列表字段：

| 文件 | 列 |
|---|---|
| `machines.csv` | `id`, `name` |
| `jobs.csv` | `id`, `operation_ids`, `release_time`, `due_date`, `weight` |
| `operations.csv` | `id`, `job_id`, `processing_time`, `eligible_machine_ids` |

```text
jobs.csv 一行：     J0,O0|O1,2,,2
operations.csv 一行：O0,J0,3,M0|M1

operation_ids        "O0|O1"   → ("O0", "O1")
eligible_machine_ids "M0|M1"   → ("M0", "M1")
due_date             ""        → None      （空字符串表示「无交期」）
release_time         ""        → 0
weight               ""        → 1.0
```

两个细节：

- **空字符串不是 0，是 `None`。** `int(job["due_date"]) if job.get("due_date") else None`——空交期在模型中表示「不参与 tardiness 目标」，不能退化成 0（0 会被当成「交期是时刻 0」，直接让所有作业迟交）。
- **读文件用 `utf-8-sig`**，可以吃掉 Excel 另存 CSV 时写在前面的 BOM，否则第一列名会读成 `﻿id`。`newline=""` 交给 `csv` 模块处理换行。

JSON 与 CSV 的分工：**JSON 是本项目的规范格式**（可表达嵌套、由 `save_json_instance` 用 `asdict` 直接写出数据类的全部字段），**CSV 是三表入口**，面向「从表格/Excel 里拿数据」的场景。两者最终都走同一个 `_parse_instance`，因此后续的验证与求解完全一致。

---

## 6. 实现：`generator.py` 与 `parser.py`

### 6.1 `generator.py` 的循环结构

```text
rng = Random(seed)                                   # 局部 RNG
resources = tuple(Machine(f"M{i}", f"Machine {i}") for i in range(machines))
machine_ids = tuple(machine.id for machine in resources)

for j in range(jobs):
    jid = f"J{j:03}"                                 # J000 / J001 / ...
    route = tuple(f"{jid}_O{k}" for k in range(operations_per_job))
    processing = [rng.randint(1, 20) for _ in route] # 先抽工时
    release = rng.randint(0, release_max)            # 再抽释放时刻
    Job(jid, route, release, release + int(sum(processing) * due_factor),
        float(rng.randint(1, 5)))                    # 最后抽权重
    Operation(...)                                   # 全部机器资格
```

四个工程细节：

1. **ID 命名 `J{j:03}` / `{jid}_O{k}`**：零填充到三位，保证字典序与数值序一致（`J009` < `J010` < `J024`）。这直接影响所有「按 `job.id` / `op.id` 升序决胜」的确定性约定（Day 4 第 7.5 节、Day 5 第 8 节）。用 `J9` 和 `J10` 时字典序会变成 `J10` < `J9`，决胜结果就不再符合直觉。
2. **抽取顺序固定**：工时 → 释放时刻 → 权重。同一 `seed` 下顺序一致，所以结果可复现；**改变抽取顺序等于改变生成的全部数据**，这是生成器实现被冻结的真正原因。
3. **`zip(route, processing, strict=True)`**：`strict` 让长度不一致时立刻报错，而不是静默截断。
4. **返回值是 `Instance`**，与手写实例走同一条流水线——生成器不产生任何「特殊输入」。

### 6.2 `parser.py` 的两个方向

```text
load_json_instance(path) -> Instance     读 JSON，只做结构、类型转换与默认值
save_json_instance(instance, path)       用 asdict 写出全部字段
load_csv_instance(dir) -> Instance       读三表 CSV，拼成同一份 dict 再解析
```

`save_json_instance` 用 `json.dumps(asdict(instance), ensure_ascii=False, indent=2)`：`asdict` 递归展开 frozen dataclass，`ensure_ascii=False` 让中文机器名不被转义成 `\uXXXX`，`indent=2` 让 diff 可读。

**解析器不判断业务合法性。** `parser.py` 的 docstring 写得很明确：「只负责读取、结构、类型转换与缺失字段的默认值；业务上的合法性判断（唯一性、引用完整性等）在 `validation.py`。」这条边界让 `load_*` 可以安全地对一份可疑文件做「先读进来看看」，而把「拒收」留给验证器。

也正因为如此，**往返（round-trip）测试才是解析器的核心测试**：`save → load` 必须得到相等的 `Instance`。它证明了「写出去的字段」和「读回来的字段」是对称的——少写一个字段、多写一个默认值，都会在这里暴露。

---

## 7. 实验：`m1w2d5_generator`

对应脚本 [m1w2d5_generator.py](../../projects/01_scheduling_core/examples/m1w2d5_generator.py)，在项目目录下运行：

```bash
python examples/m1w2d5_generator.py
```

脚本只写入 OS 临时目录（`tempfile.TemporaryDirectory()`），不写 `artifacts/`。实际输出：

```text
== 1. 生成器参数表 ==
  seed                 实例种子，与算法种子分开             默认 必填
  jobs                 作业数                      默认 12
  machines             同质机器数                    默认 3
  operations_per_job   每个作业链长度                  默认 1
  release_max          释放时刻均匀整数范围上界             默认 10
  due_factor           交期相对自身总工时的系数             默认 1.5
  加工时间 p ~ randint(1, 20)；权重 w ~ randint(1, 5)；release ~ randint(0, release_max)
  交期 due = release + int(sum(p) * due_factor)；所有工序默认可上全部机器

== 2. 同一 seed、不同规模 ==
  seed=7 jobs= 6 machines=3 total_p= 35 max_p=14 mean_p= 5.83 lower_bound= 14
  seed=7 jobs=12 machines=3 total_p= 65 max_p=14 mean_p= 5.42 lower_bound= 22
  seed=7 jobs=24 machines=3 total_p=201 max_p=19 mean_p= 8.38 lower_bound= 67
  总工时 35 -> 201，约 5.74 倍；目标更大只是问题更大，不代表算法更差

== 3. 交期公式与全机器资格 ==
  J000: r=6 sum_p=13 due=25 = 6 + int(13*1.5)
  J001: r=8 sum_p=9 due=21 = 8 + int(9*1.5)
  J002: r=4 sum_p=13 due=23 = 4 + int(13*1.5)
  实例 J000 的工序资格：('M0', 'M1', 'M2')

== 4. 局部 RNG：调用生成器不扰动全局状态 ==
  调用前 random.random() -> [0.41661987254534116, 0.010169169457068361, 0.8252065092537432]
  调用后 random.random() -> [0.41661987254534116, 0.010169169457068361, 0.8252065092537432]
  序列相同 -> True
  同 seed 两次生成的结果相等 -> True

== 5. JSON 往返 ==
  写入 instance.json，读回后 Instance 相等 -> True
  JSON 中第一条 job -> {'id': 'J000', 'operation_ids': ['J000_O0'], 'release_time': 9, 'due_date': 16, 'weight': 1.0}

== 6. CSV 三表往返 ==
  J0: operation_ids=('O0', 'O1') r=2 due=None w=2.0
  J1: operation_ids=('O2',) r=0 due=9 w=1.0
  O0: job=J0 p=3 eligible=('M0', 'M1')
  O1: job=J0 p=2 eligible=('M0', 'M1')
  O2: job=J1 p=4 eligible=('M1',)
  J0 的空交期被读成 None -> True
  总加工时间 = 9

全部断言通过。
```

**实验结论**：

1. 第 2 段与第 5.2 节的手算逐位一致（`35 / 65 / 201`，下界 `14 / 22 / 67`），说明规模缩放的方向是「总工时涨、下界涨、单件时长不变」。
2. 第 3 段验证了交期公式与「全机器资格」两条约定，包括 `int(13.5)=13` 的向下取整。
3. 第 4 段的两个序列逐元素相同，且 `generate_instance(3, jobs=6) == generate_instance(3, jobs=6)`——**局部 RNG 与确定性同时成立**。
4. 第 6 段里 `J0` 的空交期读成 `None`、`O0` 的 `|` 分隔字段读成 `('M0','M1')`，两条 CSV 约定都被实测覆盖。
5. 脚本对上述每一条都加了 `assert`，因此它不是「打印演示」，而是**可回归的手算对拍**。

测试侧的对应入口（覆盖往返、输入负例与九类排程负例）：

```bash
python -m pytest tests/test_month1.py -k 'roundtrip or invalid_inputs or corruption' -v
```

实测 `11 passed, 45 deselected`——`roundtrip` 1 条、`invalid_inputs` 1 条、`corruption` 9 条，合计 11。也可只跑 `-k roundtrip`（1 条）或 `-k invalid_inputs`（1 条）。

---

## 8. 今日练习

1. **练习 1（手算）**：`generate_instance(0, jobs=5, machines=2, release_max=0)` 里所有 `rj` 是多少？交期公式会退化成什么？
2. **练习 2（参数边界）**：分别用 `jobs=0`、`machines=0`、`release_max=-1`、`due_factor=0` 调用生成器，确认都被 `invalid generator parameters` 挡住。
3. **练习 3（局部 RNG）**：把第 7 节第 4 段的 `generate_instance` 换成直接调用 `random.random()`，确认两次序列**不再相同**，从而说明这个实验确实在检测「是否污染全局状态」。
4. **练习 4（CSV 负例）**：把 `jobs.csv` 里的 `due_date` 从空改成 `0`，说明为什么这不是「更保险的默认值」。
5. **练习 5（分布批判）**：用 `due_factor=1.0` 与 `due_factor=3.0` 各生成一批实例，在单机上跑 `edd`，观察 `ΣTj` 如何随 `due_factor` 变化，并说明「生成器分布决定结论适用范围」。

---

## 9. 验收清单

- [ ] 能背出生成器六个参数与默认值 `12 / 3 / 1 / 10 / 1.5`。
- [ ] 能写出 `p∈[1,20]`、`w∈[1,5]`、`due = r + int(sum(p) * due_factor)` 三条抽取规则。
- [ ] 能解释为什么必须用局部 `Random(seed)`，「不扰动全局状态」到底防住了什么。
- [ ] 能说清生成器 `seed` 与算法 `seed` 是两个独立 RNG，以及为什么两者都要记录。
- [ ] 能说出「只存种子不够」，并解释 `input_sha256` 解决了什么问题。
- [ ] 能区分输入验证器的负例与排程验证器的负例，并说明各自的入口函数。
- [ ] 能写出 CSV 三表的列名、`|` 分隔规则与「空交期 → `None`」的处理。
- [ ] 能解释 JSON 浮点工时为什么被拒绝而不是被 `int()` 截断。
- [ ] `python -m pytest tests/test_month1.py -k 'roundtrip or invalid_inputs or corruption' -q` 输出 `11 passed`。
- [ ] `python -m pytest -q` 全部通过（本仓库当前为 127 条）。

---

## 10. 自测题

不看上文回答：

- Q1：`generate_instance` 的六个参数与默认值分别是什么？
- Q2：加工时间、权重、释放时刻分别从什么区间抽取？交期公式是什么？
- Q3：交期是相对什么定义的？为什么单机上容易出现大量迟交？
- Q4：为什么生成器要用 `Random(seed)` 而不是模块级 `random.seed`？
- Q5：生成器 `seed=3`、算法 `seed=3` 是否表示同一个随机过程？
- Q6：为什么「只保存随机种子」不足以复现实验？替代方案是什么？
- Q7：生成器产出的实例在「机器资格」这个维度上有什么局限？谁来补这个洞？
- Q8：输入验证器与排程验证器各处理什么负例？入口函数分别是什么？
- Q9：CSV 里空的 `due_date` 为什么必须读成 `None` 而不是 0？
- Q10：JSON 里的 `"processing_time": 1.5` 为什么不静默 `int()` 成 1？

### 参考答案

- A1：`seed`（必填）、`jobs=12`、`machines=3`、`operations_per_job=1`、`release_max=10`、`due_factor=1.5`。
- A2：`p ~ randint(1,20)`、`w ~ randint(1,5)`、`r ~ randint(0, release_max)`；`due = release + int(sum(p) * due_factor)`。
- A3：相对**该作业自身的总工时**。多个作业在单机上互相排队，`Cj` 很容易超过「1.5 倍自身工时」的窗口，所以单机实例上会大面积迟交；这是分布的设计选择。
- A4：局部 `Random` 持有自己的状态，生成实例不会推进全局 RNG，因此「先生成还是先求解」不影响算法里的随机行为，实验才可复现。
- A5：不是。它们是两个独立的 RNG 实例，分别描述数据生成与搜索动作；数值相同只是巧合。
- A6：种子只有在生成器实现与参数默认值一字不改时才可复现。替代方案是把实际生成的输入落盘到 `instances/`，并在 `results.csv` 里记录 `input_sha256`。
- A7：生成器把所有工序的 `eligible_machine_ids` 设成全部机器，因此「资格受限」完全没被覆盖；由手工构造的实例与 `test_invalid_inputs_and_rule_eligibility` 等测试补上。`route_instance` 里 A 只能上 M0 就是一例。
- A8：输入验证器处理「问题本身非法」（负工时、重复 ID、引用不存在、空链、非有限权重），入口 `validate_instance`；排程验证器处理「结果非法」（缺工序、重叠、越界指派等），入口 `schedule_errors` / `validate_schedule`。
- A9：`None` 表示「无交期、不参与 tardiness 目标」；0 会被当成「交期是时刻 0」，让所有作业一律迟交，语义完全变了。
- A10：静默 `int(1.5)` 会把写错的输入改成一个看起来正常的实例，数据被悄悄改动，后续结论都建立在不存在的输入上；正确做法是 fail-fast 报 `processing_time must be an integer`。

---

## 11. 今日一句话总结

> **生成器用局部 `Random(seed)` 把「实例从哪来」变成可复现的一步，`p∈[1,20]`、`w∈[1,5]`、`due = r + int(sum(p) * due_factor)` 定义了实验的全部数据分布；但生成器 seed 不是算法 seed、全机器资格不是全部问题、只存种子不算复现——所以要把真实输入连同 `input_sha256` 一起落盘。**
