"""Day 3：运输模型与指派模型——两张网络结构的 LP 长什么样。

两个模型都是 ``min c'x`` 配一组等式行，但行的含义完全不同：运输里每行是
「一个节点的流量守恒」，指派里每行是「一个人 / 一个任务恰好用一次」。
本脚本打印两者的约束矩阵、求解结果与对偶解，并各配一个**手算**核对：
运输用「逐项成本相加 = 180」，指派用「6 种排列全枚举，最小 = 9」。

两个模型的对偶都是 ``max Σ a_i u_i + Σ b_j v_j`` s.t. ``u_i + v_j <= c_ij``，
物流里的名字叫「位势」。**两个对偶都不唯一**：运输是产销平衡带来的整体平移
自由度，指派是「取等的对偶约束比未知数还少」带来的。所以脚本不硬编码
``u``、``v``，只核验不变量（``u_i + v_j <= c_ij``、正分量处取等、``Σu + Σv``）。
"""

import sys
from itertools import permutations
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fractions import Fraction

from opt_models.lp_models import (
    ASSIGNMENT_BASE,
    TRANSPORT_BASE,
    build_assignment_lp,
    build_transportation_lp,
    solve_model,
)

TOLERANCE = 1e-9


def print_transport_data(data) -> None:
    print("== 1. 运输算例：先集合、后参数 ==")
    print(f"源集合 S = {list(data.sources)}，汇集合 D = {list(data.destinations)}")
    print(f"供应 supply    = {dict(zip(data.sources, data.supply))}")
    print(f"需求 demand    = {dict(zip(data.destinations, data.demand))}")
    print(f"产销平衡：{sum(data.supply):g} = {sum(data.demand):g}")
    print(f"{'单位运费':<10s}" + "".join(f"{name:>8s}" for name in data.destinations))
    for i, source in enumerate(data.sources):
        body = "".join(f"{data.cost[i][j]:>8g}" for j in range(len(data.destinations)))
        print(f"{source:<10s}{body}")
    print()


def print_matrix_brief(model) -> None:
    print("== 2. 约束矩阵（运输：每行是一个节点的流量守恒）==")
    print(f"规模：{model.num_variables} 个变量、{model.num_rows} 条等式约束。")
    print("变量 = 源 x 汇 的组合，每条变量恰好出现在两条等式里（一源一汇）。")
    for row in model.rows:
        terms = " + ".join(f"{name}" for name, _ in row.terms)
        print(f"  {row.name:<14s} {terms} = {row.rhs:g}")
    print()


def print_transport_solution(model, solution) -> None:
    print("== 3. 运输最优解 ==")
    print(f"状态 {solution.status}，最小运费 {solution.objective:g}")
    destinations = TRANSPORT_BASE.destinations
    print(f"{'':<6s}" + "".join(f"{name:>9s}" for name in destinations) + f"{'行和':>9s}{'供应':>8s}")
    for i, source in enumerate(TRANSPORT_BASE.sources):
        values = [
            solution.primal[f"x_{source}_{destinations[j]}"] for j in range(len(destinations))
        ]
        row_sum = sum(values)
        print(
            f"{source:<6s}"
            + "".join(f"{value:>9.4f}" for value in values)
            + f"{row_sum:>9.4f}{TRANSPORT_BASE.supply[i]:>8g}"
        )
    column_sums = [
        sum(solution.primal[f"x_{source}_{destinations[j]}"] for source in TRANSPORT_BASE.sources)
        for j in range(len(destinations))
    ]
    print(
        f"{'列和':<6s}"
        + "".join(f"{value:>9.4f}" for value in column_sums)
        + f"{sum(column_sums):>9.4f}"
    )
    print(f"{'需求':<6s}" + "".join(f"{value:>9g}" for value in TRANSPORT_BASE.demand))
    print()


def print_transport_hand_check(solution) -> None:
    print("== 4. 手算核对：逐项成本相加 ==")
    terms = []
    total = Fraction(0)
    for i, source in enumerate(TRANSPORT_BASE.sources):
        for j, destination in enumerate(TRANSPORT_BASE.destinations):
            value = Fraction(str(round(solution.primal[f"x_{source}_{destination}"])))
            cost = Fraction(str(TRANSPORT_BASE.cost[i][j]))
            total += cost * value
            terms.append(f"{cost}*{value}")
    print("Σ c_ij x_ij = " + " + ".join(terms) + f" = {total}")
    print(f"求解器报 {solution.objective:g}，手算 {total}，差值 "
          f"{abs(solution.objective - float(total)):.3e}")
    print()
    integral = all(
        abs(value - round(value)) < TOLERANCE for value in solution.primal.values()
    )
    print(f"本算例的 LP 最优解是否全部取整：{'是' if integral else '否'}")
    print("观察（不是定理）：运输约束矩阵是全幺模的，所以 LP 的极点天然整数；")
    print("本算例只是这条定理的一个样本，不是它的证明。")
    print()


def print_transport_dual(model, solution) -> None:
    print("== 5. 运输的对偶（位势）与 reduced cost ==")
    u = {source: solution.dual[f"supply_{source}"] for source in TRANSPORT_BASE.sources}
    v = {
        destination: solution.dual[f"demand_{destination}"]
        for destination in TRANSPORT_BASE.destinations
    }
    print(f"u（源的位势） = {{{', '.join(f'{k}: {val:.4f}' for k, val in u.items())}}}")
    print(f"v（汇的位势） = {{{', '.join(f'{k}: {val:.4f}' for k, val in v.items())}}}")
    dual_objective = sum(
        TRANSPORT_BASE.supply[i] * u[source] for i, source in enumerate(TRANSPORT_BASE.sources)
    ) + sum(
        TRANSPORT_BASE.demand[j] * v[destination]
        for j, destination in enumerate(TRANSPORT_BASE.destinations)
    )
    print(f"对偶目标 Σ a_i u_i + Σ b_j v_j = {dual_objective:.6f}")
    print(f"{'变量':<12s}{'c_ij':>7s}{'u_i+v_j':>10s}{'rc':>9s}   位势是否可行")
    worst = 0.0
    for i, source in enumerate(TRANSPORT_BASE.sources):
        for j, destination in enumerate(TRANSPORT_BASE.destinations):
            name = f"x_{source}_{destination}"
            cost = TRANSPORT_BASE.cost[i][j]
            potential = u[source] + v[destination]
            reduced = solution.reduced_cost[name]
            ok = potential <= cost + TOLERANCE
            worst = max(worst, max(0.0, potential - cost))
            print(
                f"{name:<12s}{cost:>7g}{potential:>10.4f}{reduced:>9.4f}   "
                f"{'可行' if ok else '不可行'}"
            )
    print(f"位势可行的最大违反量 = {worst:.3e}（对偶可行的含义就是 u_i + v_j <= c_ij）")
    print("正的 x 所在格 rc = 0；x = 0 的格 rc > 0，rc 就是「让这格开始运要便宜多少」。")
    print("注意：产销平衡时给全部 u 加 t、全部 v 减 t，不改变任何一条对偶约束，")
    print("对偶目标的变化量是 t * (Σa - Σb) = 0，所以运输问题的对偶解天然不唯一。")
    for shift in (0.0, 1.0, -2.5):
        shifted = sum(
            TRANSPORT_BASE.supply[i] * (u[source] + shift)
            for i, source in enumerate(TRANSPORT_BASE.sources)
        ) + sum(
            TRANSPORT_BASE.demand[j] * (v[destination] - shift)
            for j, destination in enumerate(TRANSPORT_BASE.destinations)
        )
        print(f"  平移 t = {shift:>4g}：对偶目标 = {shifted:.6f}")
    print()


def print_assignment_data(data) -> None:
    print("== 6. 指派算例：任务规模等于人数 ==")
    print(f"人员 {list(data.agents)}，任务 {list(data.tasks)}")
    print(f"{'成本':<8s}" + "".join(f"{name:>8s}" for name in data.tasks))
    for i, agent in enumerate(data.agents):
        body = "".join(f"{data.cost[i][j]:>8g}" for j in range(len(data.tasks)))
        print(f"{agent:<8s}{body}")
    print()


def brute_force_assignment(data):
    rows = []
    for perm in permutations(range(len(data.tasks))):
        total = sum(data.cost[i][perm[i]] for i in range(len(data.agents)))
        label = "、".join(
            f"{data.agents[i]}->{data.tasks[perm[i]]}" for i in range(len(data.agents))
        )
        rows.append((label, total))
    rows.sort(key=lambda item: item[1])
    return rows


def print_assignment_hand_check(data) -> None:
    print("== 7. 手算核对：把 3! = 6 种指派全部枚举 ==")
    rows = brute_force_assignment(data)
    for label, total in rows:
        print(f"  {label:<28s} 总成本 {total:g}")
    print(f"最小总成本 = {rows[0][1]:g}（{rows[0][0]}）")
    print()
    return rows[0]


def print_assignment_solution(model, solution) -> None:
    print("== 8. 指派 LP 的解 ==")
    print(f"状态 {solution.status}，最小总成本 {solution.objective:g}")
    print(f"{'':<6s}" + "".join(f"{name:>8s}" for name in ASSIGNMENT_BASE.tasks) + f"{'行和':>8s}")
    for agent in ASSIGNMENT_BASE.agents:
        values = [solution.primal[f"x_{agent}_{task}"] for task in ASSIGNMENT_BASE.tasks]
        print(f"{agent:<6s}" + "".join(f"{value:>8.4f}" for value in values) + f"{sum(values):>8.4f}")
    for task in ASSIGNMENT_BASE.tasks:
        column_sum = sum(
            solution.primal[f"x_{agent}_{task}"] for agent in ASSIGNMENT_BASE.agents
        )
        print(f"任务 {task} 的列和 = {column_sum:.4f}")
    print()


def print_assignment_dual(solution) -> None:
    print("== 9. 指派的对偶：不唯一，所以只核验不变量 ==")
    u = {agent: solution.dual[f"agent_{agent}"] for agent in ASSIGNMENT_BASE.agents}
    v = {task: solution.dual[f"task_{task}"] for task in ASSIGNMENT_BASE.tasks}
    print(f"u = {{{', '.join(f'{k}: {val:.4f}' for k, val in u.items())}}}")
    print(f"v = {{{', '.join(f'{k}: {val:.4f}' for k, val in v.items())}}}")
    total = sum(u.values()) + sum(v.values())
    print(f"Σu + Σv = {total:.6f}（应当等于最优成本 {solution.objective:g}）")
    worst = 0.0
    tight = 0
    for i, agent in enumerate(ASSIGNMENT_BASE.agents):
        for j, task in enumerate(ASSIGNMENT_BASE.tasks):
            gap = u[agent] + v[task] - ASSIGNMENT_BASE.cost[i][j]
            worst = max(worst, gap)
            if abs(gap) < TOLERANCE:
                tight += 1
            if solution.primal[f"x_{agent}_{task}"] > 0.5:
                print(
                    f"  {agent}->{task}：u + v = {u[agent] + v[task]:.4f}，"
                    f"c = {ASSIGNMENT_BASE.cost[i][j]:g}，取等（互补松弛）"
                )
    print(f"全部 9 个格子的 u_i + v_j - c_ij 最大值 = {worst:.3e}（要求 <= 0）")
    print(f"取等的对偶约束共有 {tight} 条：其中 3 条来自正分量，{tight - 3} 条来自退化的零分量。")
    print("对偶变量总共只有 6 个，所以最优对偶解不唯一——")
    print("打印出来的这一组只是其中一个代表，能核验的是不变量：")
    print("u_i + v_j <= c_ij 全部成立、正分量处取等、Σu + Σv = 最优成本。")
    print()


def main() -> None:
    transport_data = TRANSPORT_BASE
    transport_model = build_transportation_lp(transport_data)
    transport_solution = solve_model(transport_model)
    print_transport_data(transport_data)
    print_matrix_brief(transport_model)
    print_transport_solution(transport_model, transport_solution)
    print_transport_hand_check(transport_solution)
    print_transport_dual(transport_model, transport_solution)

    assignment_data = ASSIGNMENT_BASE
    assignment_model = build_assignment_lp(assignment_data)
    assignment_solution = solve_model(assignment_model)
    print_assignment_data(assignment_data)
    best = print_assignment_hand_check(assignment_data)
    print_assignment_solution(assignment_model, assignment_solution)
    print_assignment_dual(assignment_solution)

    print("== 10. 断言 ==")
    assert abs(transport_solution.objective - 180.0) < TOLERANCE
    assert abs(assignment_solution.objective - float(best[1])) < TOLERANCE
    assert abs(assignment_solution.objective - 9.0) < TOLERANCE
    print("运输手算 180、指派枚举最小 9，两者与求解器结果一致（容差 1e-9）。")


if __name__ == "__main__":
    main()
