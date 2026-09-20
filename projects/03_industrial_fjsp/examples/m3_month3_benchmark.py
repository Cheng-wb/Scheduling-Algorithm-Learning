"""从任何工作目录运行 M3 的跨方法批次（Flow Shop / JSP / FJSP）。

仓库根目录：
    python projects/03_industrial_fjsp/examples/m3_month3_benchmark.py --output <目录>

项目目录：
    python examples/m3_month3_benchmark.py --output artifacts/month3

输出目录必须为空或不存在；参数与 `python -m fjsp_experiments.benchmark` 完全一致。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fjsp_experiments.benchmark import main  # noqa: E402

if __name__ == "__main__":
    main()
