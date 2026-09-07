from data import create_jobs
from metrics import evaluate_schedule
from rules import fcfs, lpt, spt
from scheduler import schedule_jobs


def print_schedule(name, schedule):
    print(f"\n================ {name} ================")
    print("Order:", " -> ".join(job.job_id for job in schedule))
    print(
        f"{'Job':<6}"
        f"{'P':>4}"
        f"{'Start':>8}"
        f"{'Finish':>9}"
        f"{'Due':>6}"
        f"{'Tardiness':>12}"
    )

    for job in schedule:
        print(
            f"{job.job_id:<6}"
            f"{job.processing_time:>4}"
            f"{job.start_time:>8}"
            f"{job.completion_time:>9}"
            f"{job.due_date:>6}"
            f"{job.tardiness:>12}"
        )


def print_comparison(results):
    print("\n================ Comparison ================")
    print(
        f"{'Algorithm':<12}"
        f"{'Makespan':>10}"
        f"{'Avg Completion':>18}"
        f"{'Avg Tardiness':>16}"
        f"{'Max Tardiness':>16}"
    )

    for result in results:
        print(
            f"{result['algorithm']:<12}"
            f"{result['makespan']:>10}"
            f"{result['average_completion_time']:>18.2f}"
            f"{result['average_tardiness']:>16.2f}"
            f"{result['max_tardiness']:>16}"
        )


def single_machine_scheduling(jobs, algorithms, show_schedule=True, show_comparison=True):

    results = []

    for name, rule in algorithms.items():
        ordered_jobs = rule(jobs)
        schedule = schedule_jobs(ordered_jobs)
        metrics = evaluate_schedule(schedule)

        if show_schedule:
            print_schedule(name, schedule)
        results.append({
            "algorithm": name,
            **metrics,
        })
    if show_comparison:
        print_comparison(results)


if __name__ == "__main__":
    jobs = create_jobs()
    algorithms = {
        "FCFS": fcfs,
        "SPT": spt,
        "LPT": lpt,
    }
    single_machine_scheduling(jobs, algorithms)
