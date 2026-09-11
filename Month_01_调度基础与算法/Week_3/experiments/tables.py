import csv
import json

def print_table(title, headers, rows, *, text_columns=()):
    """表头和内容共用动态列宽；数字右对齐，文本左对齐。"""
    rows = [[str(value) for value in row] for row in rows]
    widths = [max(len(header), *(len(row[i]) for row in rows))
              for i, header in enumerate(headers)] if rows else [len(header) for header in headers]
    separator = "+-" + "-+-".join("-" * width for width in widths) + "-+"

    def format_row(row):
        return "| " + " | ".join(
            value.ljust(width) if i in text_columns else value.rjust(width)
            for i, (value, width) in enumerate(zip(row, widths))
        ) + " |"

    print(f"\n=== {title} ===")
    print(separator)
    print(format_row(headers))
    print(separator)
    for row in rows:
        print(format_row(row))
    print(separator)


def number(value, spec="g"):
    return "N/A" if value is None else format(value, spec)


def result_table(title, rows):
    print_table(title, ["Algorithm", "Objective", "Improve", "Improve%", "Time(s)", "Eval", "Iter", "Status"],
                [(r["algorithm"], number(r["objective"]), number(r["improvement"]),
                  number(r["improvement_rate"], ".2%"), number(r["runtime"], ".4f"), r["evaluations"],
                  number(r["iterations"]), r["status"]) for r in rows], text_columns=(0, 7))
    for row in rows:
        if row["error"]:
            print(f"{row['algorithm']}: {row['error']}")


def write_csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: json.dumps(value) if isinstance(value, list) else value
                          for key, value in row.items()} for row in rows)
