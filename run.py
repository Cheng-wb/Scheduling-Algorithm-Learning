"""在独立进程中运行每周实验：python run.py --list。"""

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    registry = json.loads((ROOT / "projects/experiments.json").read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="列出已实现的实验")
    parser.add_argument("project", nargs="?", choices=registry)
    parser.add_argument("experiment", nargs="?")
    parser.add_argument("arguments", nargs=argparse.REMAINDER, help="传给实验的原有参数")
    args = parser.parse_args()
    if args.list:
        for name, item in registry.items():
            print(f"{name} ({item['directory']})")
            for experiment in item["experiments"]:
                print(f"  python run.py {name} {experiment}")
        return 0
    if args.project is None or args.experiment is None:
        parser.error("请指定 project 和 experiment，或使用 --list")
    project = registry[args.project]
    if args.experiment not in project["experiments"]:
        parser.error(f"未知实验 {args.experiment!r}；使用 --list 查看可运行入口")
    directory = ROOT / project["directory"]
    script = directory / "experiments" / f"{args.experiment}.py"
    if not script.is_file():
        parser.error(f"实验文件不存在：{script}")
    extra = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
    return subprocess.call([sys.executable, "-m", f"experiments.{args.experiment}", *extra], cwd=directory)


if __name__ == "__main__":
    raise SystemExit(main())
