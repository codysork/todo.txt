"""Fail-first specification for the `todo.sh predict` CLI interface.

Spec:
* `todo.sh predict pace 3.0` is valid input — `pace` is a subcommand/mode and
  `3.0` is the target pace value.
* `todo.sh predict 3.0` is not valid input — a bare number without the `pace`
  subcommand must be rejected.

These tests fail today because `actions/predict` accepts a bare pace number and
has no `pace` subcommand; the production action is left unchanged by this spec.

Run with:
    cd ~/.todo
    python -m pytest tests/test_predict.py -v
"""

import shlex
import subprocess
import tempfile
from pathlib import Path

TODO_SH = "todo.sh"

# Fixed synthetic history: total effort 10.5 over 6 days -> alpha=11.5, beta=7.
DONE_LINES = (
    "x 2026-11-12 effort:3.0\n",
    "x 2026-11-13 effort:3.5\n",
    "x 2026-11-17 effort:4.0\n",
)


def run_predict(*args):
    """Run `todo.sh predict <args>` against a scratch done file."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        done_file = root / "done.txt"
        done_file.write_text("".join(DONE_LINES), encoding="utf-8")
        config = root / "todo-test.cfg"
        config.write_text(
            f"export TODO_DIR={shlex.quote(str(root))}\n"
            f"export DONE_FILE={shlex.quote(str(done_file))}\n",
            encoding="utf-8",
        )
        return subprocess.run(
            [TODO_SH, "-d", str(config), "predict", *args],
            capture_output=True,
            text=True,
            check=False,
        )


def run_predict_pace(value):
    """Run `todo.sh predict pace <value>` against a scratch done file."""
    return run_predict("pace", value)


def test_predict_pace_subcommand_runs_successfully():
    """`todo.sh predict pace 3.0` is valid input: the action should exit 0."""
    result = run_predict_pace("3.0")
    assert result.returncode == 0, (
        f"exit={result.returncode}, stdout={result.stdout!r}, stderr={result.stderr!r}"
    )


def test_predict_pace_subcommand_reports_target_pace():
    """The subcommand value 3.0 should be used as the target daily pace."""
    result = run_predict_pace("3.0")
    assert "Target pace:    3.00 effort/day" in result.stdout, (
        f"stdout={result.stdout!r}, stderr={result.stderr!r}"
    )


def test_predict_rejects_bare_pace_number():
    """`todo.sh predict 3.0` is invalid without the `pace` subcommand."""
    result = run_predict("3.0")
    assert result.returncode != 0, (
        f"exit={result.returncode}, stdout={result.stdout!r}, stderr={result.stderr!r}"
    )


def test_predict_bare_pace_number_prints_no_report():
    """A rejected bare number must not print a pace report."""
    result = run_predict("3.0")
    assert "Target pace:" not in result.stdout, f"stdout={result.stdout!r}"
