# 规则速查卡（Rules Cheatsheet）

> 复习用。规则必须和 `α|β|γ` 一起记——只说「SPT 最优」是错的，要说「SPT 对 `1||ΣCj` 最优」。

## 四条规则

```text
SPT
  priority:  p 升序
  optimal:   1||ΣCj
  baseline:  1|rj|ΣCj（non-delay，不保证最优）

EDD
  priority:  d 升序（due_date=None 视为 +∞，排最后）
  optimal:   1||Lmax
  baseline:  1||ΣTj（不保证最优，见 CE-02）

WSPT
  priority:  p/w 升序（等价 w/p 降序）
  optimal:   1||ΣwjCj（要求 w > 0）
  实现:      Fraction(p) / Fraction(w)，避免浮点误差

Parallel LPT
  priority:  p 降序
  assignment: 分给当前 ready_time 最小的机器（平局选 machine.id 最小）
  baseline:  P||Cmax 的列表调度启发式
  bound:     Cmax_LPT / Cmax_OPT ≤ 4/3 − 1/(3m)
  下界:      LB = max(max p, ceil(Σp / m))，Cmax==LB 时证明最优
```

## 实现入口

| 函数 | 位置 |
|---|---|
| `spt` / `edd` / `wspt` / `lpt` | [rules.py](../scheduling_algorithms/rules.py) |
| `parallel_lpt` / `parallel_makespan_lower_bound` | [rules.py](../scheduling_algorithms/rules.py) |
| `list_schedule`（单机通用内核） | [rules.py](../scheduling_algorithms/rules.py) |

## 目标速查

| 目标 | 含义 | 可为负 |
|---|---|---|
| `Cmax` | `max_j C_j` | 否 |
| `ΣCj` | 总完成时间 | 否 |
| `Lmax` | `max_j (C_j - d_j)` | **是** |
| `ΣTj` | `Σ max(0, C_j - d_j)` | 否 |
| `ΣwjCj` | 加权总完成时间 | 否 |

## 确定性契约

```text
Job 平局:     job.id 升序
Machine 平局: machine.id 升序
```

任何重构都不应改变这两条——它是可复现实验的基础。

## 适用范围（每条规则的隐含假设）

```text
单机规则（spt/edd/wspt/lpt）
  supports:     恰好一台机器（或显式 machine_id）
                每个 Job 恰好一道工序
                non-preemptive
  not supports: 多工序、并行机（用 decoder / parallel_lpt）

parallel_lpt
  supports:     P||Cmax 基线、人一工序、同质机器
  not supports: Q/R（机器相关加工时间）、多工序
```

更完整的反例与失效边界见 [counterexamples.md](counterexamples.md)。
