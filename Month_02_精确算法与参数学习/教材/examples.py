"""教材的小算例：先手算，再运行；all 包含 OR-Tools MILP/CP-SAT 核验。"""

from __future__ import annotations

import argparse
from fractions import Fraction as F
from itertools import combinations, permutations, product


def production_vertices(machine: int = 100, labor: int = 80):
    # 每行表示一条候选边界 ax+by=c；两条边界相交得到候选顶点。
    boundaries = [(1, 0, 0), (0, 1, 0), (2, 1, machine), (1, 2, labor)]
    points = set()
    for (a, b, c), (d, e, f) in combinations(boundaries, 2):
        determinant = a * e - b * d
        if not determinant:
            continue
        x = F(c * e - b * f, determinant)
        y = F(a * f - c * d, determinant)
        if x >= 0 and y >= 0 and 2*x+y <= machine and x+2*y <= labor:
            points.add((x, y))
    return sorted(points)


def lp_examples():
    print('\n[LP：候选顶点与目标]')
    points = production_vertices()
    for x, y in points:
        print(f'x={x}, y={y}, profit={40*x+30*y}')
    best = max(points, key=lambda xy: 40*xy[0]+30*xy[1])
    assert best == (40, 20)
    u, v = F(50, 3), F(20, 3)
    assert 2*u+v == 40 and u+2*v == 30
    assert 100*u+80*v == 2200
    print(f'Dual certificate: u={u}, v={v}, upper bound=2200')

    # 用每个整数资源值的顶点枚举核验三段公式，不使用公式产生标准答案。
    for machine in range(201):
        exact = max(40*x+30*y for x, y in production_vertices(machine))
        if machine <= 40:
            predicted = 30*machine
        elif machine <= 160:
            predicted = F(50, 3)*machine+F(1600, 3)
        else:
            predicted = 3200
        assert exact == predicted, (machine, exact, predicted)
    for machine in (90, 100, 103, 110, 160, 200):
        value = max(40*x+30*y for x, y in production_vertices(machine))
        print(f'Machine capacity {machine}: optimal profit={value}')
    transport = [(q, q+4*(3-q)+3*(2-q)+2*q) for q in range(3)]
    assert min(transport, key=lambda row: row[1]) == (2, 10)
    print('PASS: duality, 201 sensitivity scenarios, transportation.')


def binary_examples():
    print('\n[0-1：完整枚举]')
    feasible = []
    for bits in product((0, 1), repeat=3):
        cost = sum(a*x for a, x in zip((2, 3, 4), bits))
        value = sum(a*x for a, x in zip((3, 4, 5), bits))
        print(bits, 'cost=', cost, 'value=', value, 'feasible=', cost <= 5)
        if cost <= 5:
            feasible.append((value, bits))
    assert max(feasible) == (7, (1, 1, 0))
    covering = []
    for a, b, c in product((0, 1), repeat=3):
        if a+c >= 1 and a+b >= 1 and b+c >= 1:
            covering.append((3*a+2*b+4*c, (a, b, c)))
    assert min(covering) == (5, (1, 1, 0))
    assert not any(a+c == a+b == b+c == 1
                   for a, b, c in product((0, 1), repeat=3))
    for a, b, z in product((0, 1), repeat=3):
        assert (a <= b) == (not a or bool(b))
        encoded_and = z <= a and z <= b and z >= a+b-1
        assert encoded_and == (z == a*b)
        encoded_or = z >= a and z >= b and z <= a+b
        assert encoded_or == (z == int(bool(a or b)))
    for z, x, w in product((0, 1), range(-2, 6), range(-2, 6)):
        encoded = -2*z <= w <= 5*z and x-5*(1-z) <= w <= x+2*(1-z)
        assert encoded == (w == z*x)
    choices = []
    for a, b, c, d in product((0, 1), repeat=4):
        if 2*a+3*b+4*c+d <= 6 and c <= d and a+b <= 1 and a+b+c+d >= 2:
            choices.append((4*a+5*b+7*c+d, (a, b, c, d)))
    assert max(choices) == (8, (0, 0, 1, 1))
    print('PASS: knapsack=7, cover=5, logic truth tables, product linearization, capstone=8.')


P = (2, 3, 1)
DUE = (2, 4, 3)


def validate_schedule(rows, processing, *, machines, precedences=(), capacity=None):
    """rows 为 (任务编号, 机器编号, 开始, 结束)，独立于求解器对象。"""
    assert sorted(row[0] for row in rows) == list(range(len(processing)))
    by_task = {row[0]: row for row in rows}
    for task, machine, start, end in rows:
        assert 0 <= machine < machines
        assert start >= -1e-7
        assert abs(end-start-processing[task]) < 1e-7
    for left, right in combinations(rows, 2):
        if left[1] == right[1]:
            assert left[3] <= right[2]+1e-7 or right[3] <= left[2]+1e-7
    for before, after in precedences:
        assert by_task[before][3] <= by_task[after][2]+1e-7
    if capacity is not None:
        # 此例每任务需求为 1；半开区间的负载在开始/结束事件之间恒定。
        for time in sorted({v for row in rows for v in row[2:]}):
            assert sum(s <= time < e for _, _, s, e in rows) <= capacity


def schedule_examples():
    print('\n[单机：枚举六个排列]')
    results = {}
    for order in permutations(range(3)):
        time, rows = 0, []
        for j in order:
            rows.append((j, 0, time, time+P[j]))
            time += P[j]
        validate_schedule(rows, P, machines=1)
        value = sum(max(0, e-DUE[j]) for j, _, _, e in rows)
        name = ''.join('ABC'[j] for j in order)
        results[name] = value
        print(name, rows, 'tardiness=', value)
    assert results == {'ABC': 4, 'ACB': 2, 'BAC': 6, 'BCA': 5, 'CAB': 3, 'CBA': 4}
    assert min(results.values()) == 2
    restricted = min(v for order, v in results.items() if order.startswith('C'))
    assert restricted == 3
    print('Original optimum=2; fixing C first gives restricted optimum=3.')


def milp_examples():
    from ortools.linear_solver import pywraplp

    print('\n[MILP：同一单机实例，CBC 与 LP 松弛]')
    for relax in (False, True):
        solver = pywraplp.Solver.CreateSolver('GLOP' if relax else 'CBC')
        if solver is None:
            raise RuntimeError('Required OR-Tools backend is unavailable.')
        solver.SetTimeLimit(10000)
        H = sum(P)
        starts = [solver.NumVar(0, H-P[j], f's{j}') for j in range(3)]
        tardiness = [solver.NumVar(0, H, f't{j}') for j in range(3)]
        for j in range(3):
            solver.Add(tardiness[j] >= starts[j]+P[j]-DUE[j])
        for j, k in combinations(range(3), 2):
            y = solver.NumVar(0, 1, f'y{j}{k}') if relax else solver.BoolVar(f'y{j}{k}')
            solver.Add(starts[k] >= starts[j]+P[j]-H*(1-y))
            solver.Add(starts[j] >= starts[k]+P[k]-H*y)
        solver.Minimize(solver.Sum(tardiness))
        status = solver.Solve()
        assert status == pywraplp.Solver.OPTIMAL, status
        value = solver.Objective().Value()
        if relax:
            assert abs(value) < 1e-6, value
            print('LP relaxation lower bound:', value)
        else:
            rows = [(j, 0, starts[j].solution_value(), starts[j].solution_value()+P[j])
                    for j in range(3)]
            validate_schedule(rows, P, machines=1)
            recomputed = sum(max(0, e-DUE[j]) for j, _, _, e in rows)
            assert abs(value-2) < 1e-6 and abs(recomputed-value) < 1e-6
            print('MILP schedule:', rows, 'objective:', value)


def solve_cp(model):
    from ortools.sat.python import cp_model

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10
    solver.parameters.num_search_workers = 1
    status = solver.solve(model)
    # 本教材的小算例期待完整证明；限时未完成不能当作测试通过。
    assert status == cp_model.OPTIMAL, solver.status_name(status)
    return solver


def cp_single():
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    H = sum(P)
    starts, ends, intervals, tardiness = [], [], [], []
    for j in range(3):
        s = model.new_int_var(0, H-P[j], f's{j}')
        e = model.new_int_var(P[j], H, f'e{j}')
        intervals.append(model.new_interval_var(s, P[j], e, f'task{j}'))
        t = model.new_int_var(0, H, f't{j}')
        model.add(t >= e-DUE[j])
        starts.append(s)
        ends.append(e)
        tardiness.append(t)
    model.add_no_overlap(intervals)
    model.minimize(sum(tardiness))
    solver = solve_cp(model)
    rows = [(j, 0, solver.value(starts[j]), solver.value(ends[j])) for j in range(3)]
    validate_schedule(rows, P, machines=1)
    assert sum(max(0, e-DUE[j]) for j, _, _, e in rows) == solver.objective_value == 2
    print('CP single machine:', rows, 'total tardiness=2')


def cp_parallel(workers):
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    p, H = (3, 2, 2), 7
    starts, ends, actual_intervals = [], [], []
    machine_intervals = [[], []]
    selections = {}
    for j, duration in enumerate(p):
        s = model.new_int_var(0, H-duration, f's{j}')
        e = model.new_int_var(duration, H, f'e{j}')
        starts.append(s)
        ends.append(e)
        actual_intervals.append(model.new_interval_var(s, duration, e, f'actual{j}'))
        choices = []
        for m in range(2):
            a = model.new_bool_var(f'choose_{j}_{m}')
            selections[j, m] = a
            interval = model.new_optional_interval_var(s, duration, e, a, f'candidate{j}_{m}')
            machine_intervals[m].append(interval)
            choices.append(a)
        model.add_exactly_one(choices)
    for intervals in machine_intervals:
        model.add_no_overlap(intervals)
    # 每项任务必做，工人资源用主区间，避免把候选机器重复算成实际任务。
    model.add_cumulative(actual_intervals, [1]*3, workers)
    makespan = model.new_int_var(0, H, 'makespan')
    model.add_max_equality(makespan, ends)
    model.minimize(makespan)
    solver = solve_cp(model)
    rows = []
    for j in range(3):
        chosen = [m for m in range(2) if solver.value(selections[j, m])]
        assert len(chosen) == 1
        rows.append((j, chosen[0], solver.value(starts[j]), solver.value(ends[j])))
    validate_schedule(rows, p, machines=2, capacity=workers)
    expected = 4 if workers == 2 else 7
    assert max(row[3] for row in rows) == solver.objective_value == expected
    print(f'CP parallel, workers={workers}:', rows, f'makespan={expected}')


def cp_jsp():
    from ortools.sat.python import cp_model

    # 工序 0、1 属于 J1；2、3 属于 J2。
    p, assigned, precedence = (3, 2, 2, 1), (0, 1, 1, 0), ((0, 1), (2, 3))
    H = sum(p)
    model = cp_model.CpModel()
    starts, ends, machine_intervals = [], [], [[], []]
    for j, duration in enumerate(p):
        s = model.new_int_var(0, H-duration, f's{j}')
        e = model.new_int_var(duration, H, f'e{j}')
        interval = model.new_interval_var(s, duration, e, f'task{j}')
        starts.append(s)
        ends.append(e)
        machine_intervals[assigned[j]].append(interval)
    for before, after in precedence:
        model.add(starts[after] >= ends[before])
    for intervals in machine_intervals:
        model.add_no_overlap(intervals)
    makespan = model.new_int_var(0, H, 'makespan')
    model.add_max_equality(makespan, [ends[1], ends[3]])
    model.minimize(makespan)
    solver = solve_cp(model)
    rows = [(j, assigned[j], solver.value(starts[j]), solver.value(ends[j])) for j in range(4)]
    validate_schedule(rows, p, machines=2, precedences=precedence)
    assert max(row[3] for row in rows) == solver.objective_value == 5
    print('CP job shop:', rows, 'makespan=5')


def cp_examples():
    print('\n[CP-SAT：独立验证四个模型]')
    cp_single()
    cp_parallel(2)
    cp_jsp()
    cp_parallel(1)


def main():
    modes = {'lp': lp_examples, 'binary': binary_examples, 'schedule': schedule_examples,
             'milp': milp_examples, 'cp': cp_examples}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=[*modes, 'all'], nargs='?', default='all')
    args = parser.parse_args()
    for name, action in modes.items():
        if args.mode in (name, 'all'):
            action()
    print('\nAll selected teaching checks passed.')


if __name__ == '__main__':
    main()
