"""Scratch-data CLI tests for the three `todo pace` score tables."""

# AI-generated code (unreviewed by a human)
import os
import shlex
import subprocess
import tempfile
from datetime import date, timedelta
from pathlib import Path

# AI-generated code (unreviewed by a human)
TODO_SH = "todo.sh"


# AI-generated code (unreviewed by a human)
def run_pace(done_text):
    with tempfile.TemporaryDirectory(
        prefix="todo-pace-", dir="/tmp/opencode"
    ) as temp:
        root = Path(temp)
        done_file = root / "done.txt"
        done_file.write_text(done_text, encoding="utf-8")
        config = root / "config"
        config.write_text(
            f"export TODO_DIR={shlex.quote(str(root))}\n"
            f"export TODO_FILE={shlex.quote(str(root / 'todo.txt'))}\n"
            f"export DONE_FILE={shlex.quote(str(done_file))}\n"
            f"export REPORT_FILE={shlex.quote(str(root / 'report.txt'))}\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [TODO_SH, "-d", str(config), "pace", "daily", "2"],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"exit={result.returncode}, stderr={result.stderr!r}"
            )
        return result.stdout


# AI-generated code (unreviewed by a human)
def metric_rows(output, metric):
    lines = output.splitlines()
    title = f"{metric.title()} effort"
    start = lines.index(title) + 3
    rows = {}
    for line in lines[start:]:
        if not line.strip():
            break
        parts = line.split()
        if len(parts) == 4:
            rows[parts[0]] = (
                float(parts[1]),
                int(parts[2]),
                float(parts[3]),
            )
    return rows


# AI-generated code (unreviewed by a human)
def sample_done_history():
    today = date.today()
    yesterday = today - timedelta(days=1)
    return today, (
        f"x {yesterday} physical:2 mental:20 stress:200 effort:900\n"
        f"x {today} physical:3 mental:30 stress:300 effort:900\n"
        f"x {today} physical:4 mental:40 stress:400 effort:900\n"
    )


# AI-generated code (unreviewed by a human)
def test_pace_prints_three_separate_tables():
    _today, done_text = sample_done_history()
    output = run_pace(done_text)
    assert [title for title in (
        "Physical effort", "Mental effort", "Stress effort"
    ) if title in output] == [
        "Physical effort", "Mental effort", "Stress effort"
    ]


# AI-generated code (unreviewed by a human)
def test_physical_table_sums_only_physical_scores():
    today, done_text = sample_done_history()
    rows = metric_rows(run_pace(done_text), "physical")
    assert rows[today.isoformat()] == (7.0, 1, 7.0)


# AI-generated code (unreviewed by a human)
def test_mental_table_sums_only_mental_scores():
    today, done_text = sample_done_history()
    rows = metric_rows(run_pace(done_text), "mental")
    assert rows[today.isoformat()] == (70.0, 1, 70.0)


# AI-generated code (unreviewed by a human)
def test_stress_table_sums_only_stress_scores():
    today, done_text = sample_done_history()
    rows = metric_rows(run_pace(done_text), "stress")
    assert rows[today.isoformat()] == (700.0, 1, 700.0)


# AI-generated code (unreviewed by a human)
if __name__ == "__main__":
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} tests passed.")
