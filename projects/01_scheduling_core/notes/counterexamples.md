# 失效反例库（Counterexamples）

> 「知道什么时候有效」和「知道什么时候失效」同样重要。真实项目里最常见的 bug 就是：业务多了一个约束（`rj` / setup / calendar / 机器资格），原来的简单理论结论立刻失效，但代码还在机械套用。
>
> 每个反例都可执行：`tests/test_week1_review.py` 用 `pytest` 断言了下面每一个数字。

---

## CE-01：Release Time 破坏 SPT 最优性

```text
Problem:  1|rj|ΣCj
Input:    A: r=0, p=100
          B: r=1, p=1

Rule Result（non-delay SPT）:
          t=0 只有 A 已释放 → A: 0→100
          B: 100→101
          ΣCj = 100 + 101 = 201

Better Alternative（故意空转）:
          idle 0→1
          B: 1→2
          A: 2→102
          ΣCj = 2 + 102 = 104

Conclusion:
          SPT 对 1||ΣCj 的最优性不能推广到 1|rj|ΣCj。
          有 rj 时，最优排程可能需要在机器空闲时故意等待一个即将到达的短任务；
          non-delay 策略主动放弃了这类选择。1|rj|ΣCj 是 NP-hard。
```

---

## CE-02：EDD 不保证最小 Total Tardiness

```text
Problem:  1||ΣTj
Input:    J1: p=1, d=1
          J2: p=1, d=3
          J3: p=3, d=2

Rule Result（EDD：d 升序 → J1, J3, J2）:
          C = [1, 4, 5]
          T = [0, 2, 2]
          ΣTj = 4

Better Alternative（J1, J2, J3）:
          C = [1, 2, 5]
          T = [0, 0, 3]
          ΣTj = 3

Conclusion:
          EDD 对 1||Lmax 最优，但不能推出它对 1||ΣTj 也最优。
          「都是交期指标」不代表它们有相同的最优规则——Lmax 只看最糟的一次，
          ΣTj 看累计。1||ΣTj 是 NP-hard。
```

---

## CE-03：Parallel LPT 不保证 P||Cmax 最优

```text
Problem:  P||Cmax
Input:    2 台机器，p = [3, 3, 2, 2, 2]

Rule Result（LPT：p 降序 + 最小负载机器，平局选 M0）:
          M0: 3 → 3+2=5 → 5+2=7
          M1: 3 → 3+2=5
          Cmax_LPT = 7
          LB = max(3, ceil(12/2)) = 6  →  Cmax > LB，逼近但未达

Better Alternative:
          M0: 3+3 = 6
          M1: 2+2+2 = 6
          Cmax_OPT = 6

Conclusion:
          LPT 是 P||Cmax 的启发式（近似界 4/3 − 1/(3m)），一般不保证最优。
          Cmax > LB 说明还有改进空间（此处确实如此），但不能由此断定 LPT 差；
          它仍是必须打对的基线。要证明最优必须 Cmax == LB，或用精确算法。
```

---

## CE-04：单机 LPT 对 ΣCj 很差

```text
Problem:  1||ΣCj
Input:    p = [6, 4, 2]

Rule Result（LPT：p 降序 → 6, 4, 2）:
          C = [6, 10, 12]
          ΣCj = 28

Better Alternative（SPT：2, 4, 6）:
          C = [2, 6, 12]
          ΣCj = 20

Conclusion:
          单机上 LPT 应当只当作对照 baseline，不能当作 ΣCj 规则。
          先做长任务会拖长所有后续任务的完工时间，而 ΣCj 对「每一个」完成时刻求和。
          LPT 的正途是 P||Cmax 的列表调度。
```

---

## 反例的通用价值

看到一个新问题（例如 `1|rj|ΣCj`），应该立刻反应：

```text
1. 这个问题的 β 字段和哪个经典模型不同？
2. 经典模型的最优结论还成立吗？
3. 有没有现成的反例说明它失效？
4. 我的实现是按哪个模型写的？适用边界写清楚了吗？
```

而不是第一反应「套一个熟悉的规则试试」。
