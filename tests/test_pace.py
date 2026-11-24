"""Scratch-data CLI tests for the combined `todo pace` score table."""

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
def sample_done_history():
    today = date.today()
    yesterday = today - timedelta(days=1)
    return today, (
        f"x {yesterday} physical:2 mental:20 stress:200 effort:900\n"
        f"x {today} physical:3 mental:30 stress:300 effort:900\n"
        f"x {today} physical:4 mental:40 stress:400 effort:900\n"
    )


# AI-generated code (unreviewed by a human)
def pace_rows(output):
    rows = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) != 8 or parts[0] == "Period" or parts[0].startswith("-"):
            continue
        rows[parts[0]] = tuple(float(part) for part in parts[1:])
    return rows


# AI-generated code (unreviewed by a human)
def test_pace_prints_one_combined_table():
    _today, done_text = sample_done_history()
    output = run_pace(done_text)
    headers = [
        line for line in output.splitlines()
        if line.split() and line.split()[0] == "Period"
    ]
    assert len(headers) == 1, output
    for name in ("Physical", "Mental", "Stress"):
        assert name in headers[0], headers[0]


# AI-generated code (unreviewed by a human)
def test_pace_rows_report_all_three_scores():
    today, done_text = sample_done_history()
    rows = pace_rows(run_pace(done_text))
    yesterday = (today - timedelta(days=1)).isoformat()
    assert set(rows) == {today.isoformat(), yesterday}
    assert rows[yesterday] == (1.0, 2.0, 2.0, 20.0, 20.0, 200.0, 200.0)
    assert rows[today.isoformat()] == (1.0, 7.0, 7.0, 70.0, 70.0, 700.0, 700.0)


if __name__ == "__main__":
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} tests passed.")
