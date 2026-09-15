"""统一实例和评价预算，对比五种搜索方法与 LPT 初始基线。"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_core.generator import generate_instance
from scheduling_core.search import ALGORITHMS, SearchConfig, solve


def main() -> None:
    instance = generate_instance(20, jobs=12, machines=1)
    print("algorithm,objective,evaluations,status,seconds")
    for algorithm in ALGORITHMS:
        result = solve(
            instance,
            SearchConfig(
                algorithm=algorithm, objective="total_tardiness", budget=150, seed=0
            ),
        )
        print(
            f"{algorithm},{result.objective},{result.evaluations},{result.status},{result.elapsed_seconds:.6f}"
        )


if __name__ == "__main__":
    main()
