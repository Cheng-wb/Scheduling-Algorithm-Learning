"""从任何工作目录运行第一月全部基准与敏感性实验。"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduling_experiments.benchmark import main

if __name__ == "__main__":
    main()
