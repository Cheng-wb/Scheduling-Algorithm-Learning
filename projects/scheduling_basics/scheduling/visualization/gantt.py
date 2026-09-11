"""使用非交互画布生成甘特图，调用方决定保存位置。"""

from matplotlib import colormaps
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from ..models import Schedule


def plot_gantt(schedule: Schedule, title: str | None = None) -> Figure:
    schedule.validate()
    figure = Figure(figsize=(13, max(2.5, 1.1 * schedule.machine_count + 1.5)), layout="constrained")
    FigureCanvasAgg(figure)
    ax = figure.subplots()
    ids = sorted(item.job.job_id for item in schedule.assignments)
    colors = {job_id: colormaps["tab20"](i % 20) for i, job_id in enumerate(ids)}
    for item in schedule.assignments:
        ax.barh(item.machine_id, item.completion_time - item.start_time,
                left=item.start_time, height=0.6, color=colors[item.job.job_id],
                edgecolor="white", linewidth=1)
        ax.text((item.start_time + item.completion_time) / 2, item.machine_id,
                item.job.job_id, ha="center", va="center", fontsize=8, rotation=90)
    ax.set_yticks(range(schedule.machine_count), [f"M{i}" for i in range(schedule.machine_count)])
    ax.set_ylim(schedule.machine_count - 0.4, -0.6)
    end = max((item.completion_time for item in schedule.assignments), default=0)
    ax.set_xlim(0, max(1, end * 1.02))
    ax.set_xlabel("Time")
    ax.set_ylabel("Machine")
    ax.set_title(title or schedule.algorithm or "Schedule")
    ax.grid(axis="x", alpha=0.2)
    ax.set_axisbelow(True)
    return figure
