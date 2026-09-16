# Day 1：统一 Benchmark 入口

> 当日主题：一条命令完成输入生成、算法运行、记录、统计和图表
> 当日产出：**配置驱动的 `benchmark.py` 运行流程** + **一次完整批次的原始证据** + **输出目录契约**
> 建议投入：2.5 小时

---

## 1. 今日学习目标

完成今天的学习后，你应该能够：

1. 说清楚「配置驱动」到底意味着什么：哪些东西必须写进 JSON，哪些东西绝不能写死在算法里。
2. 说出默认配置 [month1.json](../../projects/01_scheduling_core/configs/month1.json) 的五个顶层字段各自控制什么。
3. 按顺序背出一次批次的九个步骤，并说出每一步为什么必须排在那一步。
4. 解释「先保存输入、再求解」为什么是公平比较的前提，并知道 `input_sha256` 是它的证据。
5. 说出运行 ID 的四段构成，并知道每一段用来定位什么。
6. 知道输出目录里九个产物的名字与作用，以及「目录须为空或不存在」这条硬规则保护的是什么。
7. 知道运行环境的三条事实：依赖装什么、运行库主要用什么、墙钟时间为什么不能跨平台比较。

---

## 2. 为什么第 1 天要做「统一入口」

前三周做出来的是**算法**：规则、decoder、邻域、First/Best/SA，各自的正确性都已被手算和测试验证过。但「算法正确」和「有可信的实验结论」之间还差一整套**实验装置**：

```text
没有统一入口时：手写临时脚本 → 生成实例 → 跑算法 → print → 复制进报告
问题：实例没保存、参数没记录、失败被静默跳过、换台机器跑不出同样的数
```

Week 4 第一天的任务就是把这条临时链路换成**一条可重复执行的命令**，让每次实验都留下完整的证据链：

```text
config.json      这次用了什么参数
metadata.json    这次用的哪份代码、哪个 Python、哪个平台、输入有没有被改过
instances/       这次实际求解的输入（可按 SHA-256 校验）
runs/            每一次运行的候选解、排程和逐评价轨迹
results.csv      每次运行一行的原始记录     summary.csv  按「实例 × 组 × 算法」聚合的统计
failures.json    失败清单（可以是空的，但不能不存在）
report.md        由脚本生成的结果表         *.png        质量分布、收敛曲线、甘特图
```

> **核心认识**：**「结果」不是报告里的那张表，而是产出那张表的全部原始记录。** 报告可以由脚本重新生成；原始记录丢掉了，就再也补不回来。

---

## 3. 配置驱动：什么必须写进 JSON，什么绝不能写死

### 3.1 必须写进配置的

`configs/month1.json` 的五个顶层字段：

| 字段 | 内容 | 控制什么 |
|---|---|---|
| `seeds` | `[0, 1, 2]` | 每个算法在每个实例上重复几次 |
| `algorithms` | 六种算法名 | 本批次要跑哪些算法 |
| `search` | `budget` / `temperature` / `cooling` / `restart_interval` | 所有算法共享的搜索参数 |
| `sensitivity` | 三个 SA 变体 | 额外要跑的敏感性组 |
| `instances` | 六个实例规格 | 数据规模、目标、是否需要精确参考 |

`instances` 里每一项的样子（以 `single_12` 为例）：

```text
{"name": "single_12", "generator": {"seed": 20, "jobs": 12, "machines": 1}, "objective": "total_tardiness"}
```

两个 `tiny_` 实例多一个字段 `"exact": true`——它告诉流程「这个实例小到可以用穷举算出精确参考」。

### 3.2 绝不能写死在算法里的

> **数据规模、目标、种子、预算和敏感性参数都不写死在算法中。**

三条原因，每条都能从代码结构上验证：

- **规模不写死**：`generate_instance(**spec["generator"])` 用**字典展开**传参，实例规模完全由 JSON 决定；算法侧只看到 `Instance`，不知道它是 4 个作业还是 24 个作业。
- **目标不写死**：目标是一个**字符串**，通过 `OBJECTIVES[config.objective]` 查表拿函数（Day 7 第 6.2 节）。换目标只改一个字符串，不改任何算法代码。
- **预算不写死**：`budget` 从 `config["search"]` 与敏感性参数合并后传给 `SearchConfig`，算法内部只读 `config.budget`。

反过来说，**如果某个算法里出现了「如果是 12 个作业就……」，它就已经不可信了**——读者无法判断它是真的更好，还是被特调过。

### 3.3 变体如何表达：组（group）

敏感性实验不是「另一个算法」，而是**同一个算法 + 不同参数**。代码用「组」把这个区别表达清楚：

```python
variants  = [("main", algorithm, {}) for algorithm in config.get("algorithms", ALGORITHMS)]
variants += [(f"sa_t{item['temperature']}_c{item['cooling']}", "sa", item)
             for item in config.get("sensitivity", [])]
```

于是得到七个组：`main` 加上 `sa_t0.1_c0.98`、`sa_t100.0_c0.98`、`sa_t10.0_c0.9`。**组名进 `run_id`、进 `results.csv`、进 `summary.csv`，所以敏感性结果永远和主实验分开统计，不会被误读成新算法。**

---

## 4. 一次批次的九个步骤与输出目录契约

### 4.1 运行顺序

```text
① 读取配置                    json.loads(config_path.read_text())
② 生成并保存输入              generate_instance(**spec["generator"]) → instances/<name>.json
③ 对 tiny 实例计算精确参考     exhaustive_optimum(instance, spec["objective"])
④ 按「算法 × 种子」逐个运行    solve(instance, settings)
⑤ 保存候选解和排程            runs/<run_id>.json
⑥ 保存逐评价轨迹              runs/<run_id>.trace.csv
⑦ 补充参考值和 gap            回填 reference / gap 两列
⑧ 生成统计表                  summary.csv + report.md
⑨ 生成图表                    quality.png / convergence.png / gantt.png
```

**为什么顺序不能换？** 三条硬理由：

- **② 必须在 ④ 之前。** 「先保存输入、再求解」让同一个实例上的**所有算法和所有种子共享完全相同的输入**。如果边生成边求解，或每个算法各自生成一次，「同一个实例」就只是个名字，不是同一份数据。
- **③ 必须在 ④ 之前（对 tiny 实例）。** 精确参考是**对照物**，不是搜索结果；先算参考再跑算法，参考才不受批次影响。
- **⑦ 必须在 ⑧ 之前。** `gap` 依赖参考值，而参考值可能来自「全批次的最好值」（实例没有精确参考时），所以必须先跑完全部运行才能回填。

### 4.2 `input_sha256` 是「共享输入」的证据

保存输入之后立刻算哈希，并写进**该实例的每一行**：

```python
path = output / "instances" / f"{name}.json"
save_json_instance(instance, path)
input_hash = hashlib.sha256(path.read_bytes()).hexdigest()
```

于是可以直接核对：**同一个实例的 27 行（6 算法 × 3 种子 + 3 敏感性变体 × 3 种子）里，`input_sha256` 必须完全相同。** 官方批次实测（读自 `results.csv`）：六个实例**每个都只有 1 个不同的哈希值**（`single_12` 的哈希前缀 `de904454fddb…`）。这就是「所有算法共享同一份字节级输入」的直接证据；哈希还有一个副作用——**它同时记录了输入有没有被人手工改过**。

### 4.3 运行 ID：四段定位

```python
run_id = f"{name}__{group}__{algorithm}__{seed}"
```

| 段 | 例子 | 用来定位 |
|---|---|---|
| 实例 | `single_12` | 哪份输入（对 `instances/single_12.json`） |
| 组 | `main` / `sa_t100.0_c0.98` | 主实验还是敏感性，哪一组参数 |
| 算法 | `sa` / `first` | 哪个算法 |
| 种子 | `0` | 哪个 `seed` |

**四段合起来唯一确定一条结果**，所以 `run_id` 同时是文件名（`runs/<run_id>.json` 与 `runs/<run_id>.trace.csv`）和 `results.csv` 的主键，例如 `tiny_single__main__lpt__0`、`single_12__main__sa__2`。

### 4.4 输出目录契约：必须为空或不存在

```python
if output.exists() and any(output.iterdir()):
    raise ValueError(f"output must be empty (preserve previous experiments): {output}")
```

这条检查在**写入任何文件之前**执行，保护的是一个很具体的场景：

> **旧报告的证据在同一个目录里。把它覆盖掉，旧报告就失去了全部原始记录。**

一份已经写进文档、发给别人的报告，如果它的 `results.csv` 被新一批实验覆盖，那么报告里引用的数字就**再也无法被核对**——既不能复现，也不能证伪。所以流程选择**拒绝启动**，而不是「备份后覆盖」或「静默追加」。配合「运行 ID 里没有时间戳」这个设计，正确的复跑姿势就是**换一个新目录名**：

```text
正确：--output .../artifacts/month1_refactored   （第一次）
      --output .../artifacts/month1_myrun        （第二次，新目录）
错误：--output .../artifacts/month1_refactored   （第二次，目录非空 → ValueError）
```

---

## 5. 手算 / 示例：`single_12` 的一次运行如何变成 `results.csv` 的一行

### 5.1 输入：配置里的那一项

| 字段 | 值 |
|---|---|
| `name` | `single_12` |
| `generator` | `{"seed": 20, "jobs": 12, "machines": 1}` |
| `objective` | `total_tardiness` |
| `exact` | 缺省（即不需要精确参考） |
| 生成的文件 | `instances/single_12.json` |
| `input_sha256`（实测） | `de904454fddb…`（前 12 位） |

### 5.2 一批次跑出多少行：算术

```text
主实验      = 实例数 × 算法数 × 种子数
            =     6    ×    6    ×    3     = 108

敏感性实验  = SA 变体数 × 实例数 × 种子数
            =      3     ×    6    ×    3     = 54

总计        = 108 + 54 = 162
```

官方批次实测：`results.csv` 恰好 162 行，`runs/` 下恰好 162 个 `.json` 与 162 个 `.trace.csv`，`instances/` 下恰好 6 个 `.json`；分组计数为 `main = 108` 与三个敏感性组各 18。

### 5.3 一次运行的记录（`single_12` 的 18 行主实验原始记录）

三个 `seed` 的原始 `objective` 值（逐行读自 `artifacts/month1_refactored/results.csv`）；六种算法的 `reference` 全是 250.0，`reference_type` 全是 `best-known`：

| `run_id` 前缀 | `seed=0` | `seed=1` | `seed=2` | `evaluations` | `status` |
|---|---:|---:|---:|---:|---|
| `single_12__main__lpt` | 719.0 | 719.0 | 719.0 | 1 | `BASELINE` |
| `single_12__main__random` | 303.0 | 340.0 | 296.0 | 150 | `BUDGET` |
| `single_12__main__first` | 575.0 | 575.0 | 575.0 | 150 | `BUDGET` |
| `single_12__main__best` | 529.0 | 529.0 | 529.0 | 150 | `BUDGET` |
| `single_12__main__multistart` | 371.0 | 322.0 | 426.0 | 150 | `BUDGET` |
| `single_12__main__sa` | 263.0 | 266.0 | 256.0 | 150 | `BUDGET` |

读这张表的一个要点：**`lpt` / `first` / `best` 三列完全相同**，因为它们不使用 RNG；`random` / `multistart` / `sa` 三列不同，因为各自的随机流不同（Day 7 第 4.3 节）。

### 5.4 `gap` 的算术

公式（写在 `report.md` 的第一行说明里）：

```text
gap = (objective - reference) / max(1.0, abs(reference))
```

手算三个点：

```text
lpt      : (719 - 250) / max(1, 250) = 469 / 250 = 1.876   ✓ 与表中一致
sa  seed0: (263 - 250) / 250         =  13 / 250 = 0.052   ✓ 与表中一致
random s1: (340 - 250) / 250         =  90 / 250 = 0.360   ✓ 与表中一致
```

**`max(1.0, abs(reference))` 这个保护必须讲清楚**：当参考值接近 0 时除法会放大噪声甚至除零，所以分母取 `max(1, |reference|)`——**参考为零时 `gap` 退化成绝对差，而不是百分比**。这句话被写进了 `report.md`，因为它直接决定 `gap` 能不能跨实例比较。

参考值本身分两类，由 `reference_type` 列写明：

| `reference_type` | 来源 | 本批次计数 | 强度 |
|---|---|---:|---|
| `optimum` | `oracle` 穷举证实 | 54 | 可以写「最优」 |
| `best-known` | 全批次（含敏感性）的最好值 | 108 | **只是本批最好记录，不是最优性证书** |

`optimum` 恰好 54 行 = 2 个 `tiny_` 实例 × （6 主算法 + 3 敏感性变体）× 3 种子 = 2 × 9 × 3。两个 `tiny_` 实例能被穷举证实，是因为枚举规模很小：

```text
tiny_single   : 4 个作业、1 台机器 → 4! × 1^4 =  24 × 1 =  24 个组合
tiny_parallel : 4 个作业、2 台机器 → 4! × 2^4 =  24 × 16 = 384 个组合
```

### 5.5 从 18 行到 `summary.csv` 的一行：聚合算术

`summary.csv` 按「实例 × 组 × 算法」聚合。以 `single_12` / `main` / `sa`（三个种子值 263、266、256）与 `multistart`（371、322、426）为例：

```text
sa:
  mean   = (263 + 266 + 256) / 3 = 785 / 3 = 261.6667
  median = 排序后 [256, 263, 266] 的中间值 = 263
  best   = 256
  stdev  = sqrt( (1.7778 + 18.7778 + 32.1111) / 2 ) = sqrt(26.3333) = 5.1316
  mean_gap = (0.052 + 0.064 + 0.024) / 3 = 0.140 / 3 = 0.046667
multistart:
  mean   = (371 + 322 + 426) / 3 = 1119 / 3 = 373.0
  median = 371
  best   = 322
  stdev  = sqrt( ((-2)^2 + (-51)^2 + (53)^2) / 2 ) = sqrt(2707) = 52.029
```

实测 `summary.csv` 中两行分别是 `mean=261.6666666666667, median=263.0, stdev=5.131601439446884, best=256.0, mean_gap=0.04666666666666667` 与 `mean=373.0, median=371.0, stdev=52.028838157314254, best=322.0`——**与手算完全一致。** 注意 `multistart` 的标准差 52.03 是这张表里最大的一个（三个 `seed` 从 322 跨到 426），比 `sa` 的跨度 10（256 到 266）大一个数量级，因此对它只报一个均值是不完整的（Day 7 第 4.3 节）。

### 5.6 对比：同一实例上「谁更好」

`single_12` 主实验三月均值（越小越好）：

| `lpt` | `random` | `first` | `best` | `multistart` | `sa` |
|---:|---:|---:|---:|---:|---:|
| 719 | 313 | 575 | 529 | 373 | **261.67** |

四条读表的纪律：**（1）** 这三个 `seed` 的均值不等于三个独立随机样本的统计量——`lpt` / `first` / `best` 的标准差都是 0.000，把它们当样本算显著性没有意义；**（2）** 不同目标的原始值不能混在一起平均（`single_12` 是 `ΣT`、`parallel_12` 是 `Cmax`）；**（3）** `lpt` 只评价一次，其他方法用满 150 次，预算是共同上限但实际用量不同（Day 6 第 3 节）；**（4）** `single_12` 的参考 250 来自 `best-known`，**只反映与本批最好记录的差异，不是全局最优性证书**。

---

## 6. 实现：`scheduling_experiments/benchmark.py`

对应文件 [benchmark.py](../../projects/01_scheduling_core/scheduling_experiments/benchmark.py)，共 358 行，按职责分成五个函数：

| 函数 | 职责 |
|---|---|
| `run(config_path, output)` | 主流程：目录检查、配置落盘、`metadata`、九步循环、回填 `gap`、写两张表与图 |
| `summarize(rows, output, trajectories)` | 生成 `summary.csv` 与 `report.md`，然后调用 `plot` |
| `plot(rows, output, trajectories)` | 生成 `quality.png` / `convergence.png` / `gantt.png` |
| `source_hash()` | 把四个包的全部 `.py` 按路径排序后喂进 SHA-256 |
| `write_json` / `write_csv` | 两个最小的落盘助手 |

### 6.1 `metadata.json`：一次运行的版本指纹

```python
write_json(output / "metadata.json", {
    "schema_version": 1,
    "created_utc": datetime.now(timezone.utc).isoformat(),
    "python": platform.python_version(),
    "platform": platform.platform(),
    "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], ...).stdout.strip(),
    "working_tree_dirty": bool(subprocess.run(["git", "status", "--porcelain"], ...).stdout.strip()),
    "source_sha256": source_hash(),
    "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
    "budget_unit": "full decode + validate + objective, including initialization and rejection",
})
```

**九个字段各防一种「说不清」**：`schema_version` 防「以后字段变了旧文件读不懂」；`created_utc` 防「这是哪天的」；`python` / `platform` 防「墙钟时间在什么环境下测的」；`git_commit` 防「跑的是哪份代码」；**`working_tree_dirty` 防「代码没提交就跑了」**；`source_sha256` 给出四个包全部 `.py` 的内容指纹（比 commit 更细）；`config_sha256` 防「配置被改过」；`budget_unit` 固定「一次评价」的含义（Day 7 第 6.3 节）。注意 `source_hash()` 会**逐文件读文本并按 `as_posix()` 规范化路径**，目的是让 Windows 与 Linux 检出的同一份代码算出同一个哈希。

### 6.2 `plot`：三张图各回答一个问题

| 图 | 横轴 / 纵轴 | 回答的问题 | 不能做的事 |
|---|---|---|---|
| `quality.png` | 算法 / 归一化 gap 箱线图 | 质量分布长什么样 | 标题写明是描述性分布，**不做显著性声明** |
| `convergence.png` | 评价数 / 历史最好值 | 改善发生在预算的哪个位置 | 一条曲线只有一个实例一个 `seed`，**不是三 `seed` 平均** |
| `gantt.png` | 时间 / 机器 | 最好解长什么样 | 展示的是**该实例主实验里最好的那一次**，不等于全批最好 |

两个细节：收敛图用 `ax.step(..., where="post")`——历史最好值是**阶梯**，只能在评价点下降；甘特图颜色按 `job_ids.index(...) % 10` 取 `C0`～`C9`，保证**同一个作业颜色一致**。

### 6.3 `failures.json`：失败也要留痕

```python
try:
    result = solve(instance, settings)
    ...
except Exception as exc:            # 单次失败留痕，批次继续
    row["failure_reason"] = f"{type(exc).__name__}: {exc}"
```

**单次运行抛异常不会中断整批**，而是把该行标成 `status = "FAILED"`、记下 `failure_reason`，批次继续；最后 `main()` 汇总失败数，`failed` 非零时以 `SystemExit(1)` 退出并打印 `runs=<总数>, failed=<失败数>`。**失败是实验结果的一部分，不是要被隐藏的意外。** `test_benchmark_failure_is_recorded` 用注入异常验证了整条链路：`failures.json` 有记录、`summary.csv` 的 `failed` 计数为 1、`gap` 保持 `None`。官方批次的 `failures.json` 是 `[]`，即 162 次运行全部成功。

---

## 7. 实验：`m1w4d1_benchmark.py`

对应脚本 [m1w4d1_benchmark.py](../../projects/01_scheduling_core/examples/m1w4d1_benchmark.py)，它只有 12 行——从任何工作目录调用 `scheduling_experiments.benchmark.main`。在仓库根目录运行：

```bash
python projects/01_scheduling_core/examples/m1w4d1_benchmark.py --output projects/01_scheduling_core/artifacts/my_run
```

在项目目录下等价的写法是：

```bash
python -m scheduling_experiments.benchmark --output artifacts/my_run
```

`--output` 指向的目录必须**为空或不存在**（第 4.4 节）。官方批次落在 `artifacts/month1_refactored`，**复跑时请换一个新目录名，不要指向它。**

### 7.1 官方批次的输出目录（实测）

```text
artifacts/month1_refactored/
  config.json      配置快照（与 configs/month1.json 同内容）
  metadata.json    版本指纹           failures.json    []
  instances/       6 个实例输入        runs/            162 个 .json + 162 个 .trace.csv
  results.csv      162 行原始记录      summary.csv      54 行聚合统计
  report.md        脚本生成的结果表
  quality.png / convergence.png / gantt.png
  verification.json  独立复现脚本的核对结论
```

### 7.2 `metadata.json`（实测，节选）

```text
  "python": "3.14.6",
  "platform": "Windows-10-10.0.19045-SP0",
  "git_commit": "538886b3ded5c11afcfd137fa1aebc14fe59020c",
  "working_tree_dirty": true,
  "source_sha256": "025ed469c2621c036403f7876a865ac858c1951563f7dc7058113c305e142477",
  "config_sha256": "8b126be787355ee715d0113338609863e130b7f047f6c25da8fb255a4742eeaa"
```

注意 `working_tree_dirty` 是 `true`——**这一批数据是在工作区有未提交改动时生成的**。这不是错误，而是被**如实记录**的状态：配合 `source_sha256`，任何人拿到这份数据都能判断它对应的是哪一版源码。**如果当初只记了 `git_commit` 而没记 dirty 标记，这份数据的来源就说不清了。**

### 7.3 `failures.json` 与 `report.md`

`failures.json` 的实测全文是 `[]`——162 次运行全部成功。空数组仍然是一个**必须存在的文件**：**「没有失败」和「没检查失败」是两件事。**

`report.md` 的开头（实测）：

```text
# 实验汇总（脚本生成）

gap=(value-reference)/max(1,abs(reference))；最小化。参考为零时是绝对差，不是百分比。

| 实例 | 组 | 算法 | 成功/失败 | 均值 | 标准差 | 最好 | 平均 gap | 平均评价数 |
|---|---|---|---|---|---|---|---|---|
| parallel_12 | main | best | 3/0 | 45.0 | 0.000 | 45.0 | 0.046511627906976744 | 150 |
...
```

表头九列，其中「成功/失败」直接来自 `summary.csv` 的 `successful` / `failed`。表后还有三行说明：**同一实例跨种子汇总；不把不同目标的原始值求平均；LPT 只评价一次、LS 可提前停机；预算是共同上限。**

### 7.5 为什么不能手工复制结果进报告

因为手工复制会**系统性地**丢掉三类信息：**失败**（复制时最自然的动作是跳过报错那一行，于是报告里只剩成功案例）、**参数**（表格里不会写 `budget=150`、`T0=10`、`cooling=0.98`、`seed=[0,1,2]`）、**版本**（报告里不会写 Python 版本、平台、Git commit、源码哈希）。而且手工复制的结果**无法被重新核对**：读者拿到报告，无法判断某个数字是测出来的还是抄错的。**所以 `report.md` 由 `summarize()` 生成，人只负责解读，不负责转抄。**

### 7.6 安装与环境

在项目目录下安装开发依赖：

```bash
python -m pip install -r requirements-dev.txt
```

三条环境事实：**（1）运行库主要使用标准库**，绘图依赖 `matplotlib`——只有 `plot()` 会 `import matplotlib`，并且先设 `matplotlib.use("Agg")` 以免需要图形界面；**（2）验收环境的精确包版本保存在 `requirements-lock.txt`**，与 `requirements-dev.txt` 分开：前者是「复现用的锁定清单」，后者是「安装用的宽松清单」；**（3）不同 Python 版本 / 平台上的墙钟时间不能直接比较**——本批次记录的是 `python 3.14.6` + `Windows-10-10.0.19045-SP0`，换一个平台 `elapsed_seconds` 会整体移动。**算法结果（目标值、评价数、轨迹）可以严格比较，墙钟时间不行。**

---

## 8. 今日练习

1. **练习 1（目录契约）**：对已经存在且非空的输出目录运行一次，确认抛出的是「output must be empty」而不是覆盖。说明为什么流程选择拒绝启动而不是自动备份。
2. **练习 2（哈希核对）**：从 `results.csv` 里按实例分组统计 `input_sha256` 的不同取值个数，确认每个实例都只有 1 个，并解释这说明什么。
3. **练习 3（gap 手算）**：任取 `summary.csv` 里的一行，用它的三个种子值手算 `mean`、`median`、`stdev`、`mean_gap`，与文件里的值逐项对照。
4. **练习 4（参考类型）**：统计 `results.csv` 里 `reference_type` 的两种取值各有多少行，算出它们为什么分别是 54 与 108，并说明哪一种能写「最优」。
5. **练习 5（配置驱动）**：把 `configs/month1.json` 的 `seeds` 改成 `[0]`，推算 `results.csv` 会变成多少行、`instances/` 仍有多少个文件，并说明为什么实例数不变。

---

## 9. 验收清单

- [ ] 能说出配置驱动意味着「规模、目标、种子、预算、敏感性参数都不写死在算法里」。
- [ ] 能按顺序背出九个步骤，并说出「先存输入再求解」与「先算参考再跑算法」各自为什么。
- [ ] 能解释 `input_sha256` 是「所有算法共享同一份输入」的证据。
- [ ] 能拆开 `run_id` 的四段并说出每段定位什么。
- [ ] 能解释输出目录为什么必须为空或不存在，以及误覆盖会造成什么后果。
- [ ] 能手算 `gap = (objective - reference) / max(1.0, |reference|)` 并说明分母保护的作用。
- [ ] 能区分 `reference_type` 的 `optimum` 与 `best-known`，并说出各自多少行、为什么。
- [ ] 能说出 `metadata.json` 的九个字段各防哪一种「说不清」。
- [ ] `python -m scheduling_experiments.benchmark --help` 能打印参数说明。
- [ ] `python -m pytest tests/test_month1.py -k 'benchmark_failure' -q` 选定 1 条并通过。

---

## 10. 自测题

不看上文回答：

- Q1：「配置驱动」具体指哪些东西不能写死在算法里？
- Q2：一次批次的九个步骤是什么？
- Q3：为什么必须「先保存输入、再求解」？
- Q4：`input_sha256` 出现在每一行里有什么用？
- Q5：`run_id` 的四段分别是什么？
- Q6：输出目录为什么必须为空或不存在？
- Q7：`gap` 的公式是什么？分母为什么要写成 `max(1.0, |reference|)`？
- Q8：`optimum` 与 `best-known` 有什么区别？本批次各多少行？
- Q9：为什么不把结果直接 `print` 后复制进报告？
- Q10：为什么墙钟时间不能跨 Python 版本或平台比较，而目标值可以？

### 参考答案

- A1：数据规模（`jobs` / `machines` 等）、目标（`objective` 字符串）、种子（`seeds`）、预算（`budget`）、敏感性参数（`sensitivity`）都由 JSON 决定；算法侧只读 `Instance` 与 `SearchConfig`。
- A2：读配置 → 生成并保存输入 → 对 tiny 实例算精确参考 → 按算法/种子运行 → 保存候选与排程 → 保存轨迹 → 回填参考与 gap → 生成统计表与报告 → 生成三张图。
- A3：这样同一实例上的所有算法和所有种子共享**字节级完全相同**的输入，结果差异才能归因到算法而不是数据。
- A4：它是「共享输入」的可核对证据（同实例全部行哈希相同），同时记录了输入有没有被手工改过。
- A5：`{实例}__{组}__{算法}__{种子}`，四段合起来唯一确定一条结果，同时充当文件名与 `results.csv` 主键。
- A6：防止覆盖掉旧报告赖以核对的原始记录；旧证据一旦被覆盖，报告里的数字就再也无法复现或证伪。
- A7：`gap = (objective - reference) / max(1.0, abs(reference))`。分母保护避免参考接近 0 时放大噪声或除零——参考为零时 `gap` 是绝对差，不是百分比。
- A8：`optimum` 由 `oracle` 穷举证实（本批次 54 行，来自两个 `tiny_` 实例），可以写「最优」；`best-known` 取自全批次最好记录（108 行），只是本批最好记录，不是最优性证书。
- A9：手工复制会系统性地丢掉失败行、参数与版本信息，而且读者无法重新核对。所以报告由脚本生成，人只解读不转抄。
- A10：墙钟时间依赖 Python 版本、平台与机器负载；而目标值、评价数、轨迹由代码逻辑与固定 `seed` 决定，因此可以严格比较。

---

## 11. 今日一句话总结

> **统一 Benchmark 入口把「跑算法」升级成「留下证据链」：配置决定跑什么、先存输入保证公平比较、`run_id` 让每条结果可定位、`metadata.json` 锁定版本、拒绝覆盖保护旧证据——报告只是这套记录的一个视图，原始记录才是结果本身。**
