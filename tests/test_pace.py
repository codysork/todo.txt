"""Specification: `todo pace 3.0` is not a valid input.

The `pace` action takes a period mode (daily|weekly|monthly|annual) and an
optional count, not a numeric pace. A number in the mode position must be
rejected. This behavior already exists in `actions/pace`; these tests guard it.

Run with:
    cd ~/.todo
    python -m pytest tests/test_pace.py -v
"""

import shlex
import subprocess
import tempfile
from pathlib import Path

TODO_SH = "todo.sh"

# Scratch history so any failure is caused by the invalid argument, not a
# missing/unreadable done file.
DONE_LINES = (
    "x 2026-11-12 effort:3.0\n",
    "x 2026-11-13 effort:3.5\n",
    "x 2026-11-17 effort:4.0\n",
)


def run_pace(*args):
    """Run `todo.sh pace <args>` against a scratch done file."""
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
            [TODO_SH, "-d", str(config), "pace", *args],
            capture_output=True,
            text=True,
            check=False,
        )


def test_pace_rejects_numeric_argument():
    """`pace 3.0` is invalid input: the action should exit nonzero."""
    assert run_pace("3.0").returncode != 0


def test_pace_explains_invalid_mode():
    """The rejection should name the invalid mode."""
    assert "Error: Invalid pace mode '3.0'." in run_pace("3.0").stderr
