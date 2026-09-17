"""从任何工作目录运行 M2 的跨方法批次（MILP / CP-SAT / 启发式）。

仓库根目录：
    python projects/02_optimization_models/examples/m2_month2_benchmark.py --output <目录>

项目目录：
    python examples/m2_month2_benchmark.py --output artifacts/month2

输出目录必须为空或不存在；参数与 `python -m opt_experiments.benchmark` 完全一致。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from opt_experiments.benchmark import main  # noqa: E402

if __name__ == "__main__":
    main()
