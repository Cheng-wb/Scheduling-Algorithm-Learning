"""执行第一、二周手算、枚举及可行性验收。"""

import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    project = Path(__file__).resolve().parents[1]
    raise SystemExit(
        subprocess.call(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_month1.py",
                "-k",
                "hand or enumeration or decoder or corruption or moves",
                "-v",
            ],
            cwd=project,
        )
    )
