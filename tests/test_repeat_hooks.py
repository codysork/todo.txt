"""Scratch-data integration tests for repeat's configured hooks."""

import os
import shlex
import subprocess
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TODO_SH = "todo.sh"


class ScratchTodo:
    def __init__(self, hooks_dir=None):
        self.temp = tempfile.TemporaryDirectory(
            prefix="todo-repeat-hooks-", dir="/tmp/opencode"
        )
        self.root = Path(self.temp.name)
        self.todo_file = self.root / "todo.txt"
        self.config = self.root / "config"
        settings = {
            "TODO_DIR": str(self.root),
            "TODO_FILE": str(self.todo_file),
            "DONE_FILE": str(self.root / "done.txt"),
            "REPORT_FILE": str(self.root / "report.txt"),
            "TODO_ACTIONS_DIR": str(ROOT / "actions"),
            "TODO_HOOKS_DIR": str(
                hooks_dir if hooks_dir is not None else ROOT / "hooks"
            ),
            "TODOTXT_VERBOSE": "0",
        }
        self.config.write_text(
            "".join(
                f"export {key}={shlex.quote(value)}\n"
                for key, value in settings.items()
            ),
            encoding="utf-8",
        )
        self.env = {**os.environ, **settings}

    def run(self, *args):
        return subprocess.run(
            [TODO_SH, "-d", str(self.config), *args],
            capture_output=True,
            text=True,
            env=self.env,
            check=False,
        )

    def lines(self):
        if not self.todo_file.exists():
            return []
        return self.todo_file.read_text(encoding="utf-8").splitlines()

    def close(self):
        self.temp.cleanup()


def test_repeat_target_date_runs_schedule_hook_on_new_item():
    todo = ScratchTodo()
    expected = (date.today() + timedelta(days=2)).isoformat()
    try:
        added = todo.run("add", "(A) repeated task")
        assert added.returncode == 0, added.stderr

        result = todo.run("repeat", "1", "2")

        assert result.returncode == 0, result.stderr
        assert len(todo.lines()) == 1
        assert todo.lines()[0].startswith("(A) repeated task")
        assert f"t:{expected}" in todo.lines()[0]
    finally:
        todo.close()


def test_invalid_target_date_fails_before_completing_original():
    todo = ScratchTodo()
    try:
        added = todo.run("add", "(A) repeated task")
        assert added.returncode == 0, added.stderr
        before = todo.lines()
        done_file = Path(todo.env["DONE_FILE"])
        done_before = done_file.read_text(encoding="utf-8")

        result = todo.run("repeat", "1", "not-a-date")

        assert result.returncode != 0
        assert "invalid repeat target date" in result.stderr
        assert todo.lines() == before
        assert done_file.read_text(encoding="utf-8") == done_before
    finally:
        todo.close()


def test_target_date_requires_a_preflight_hook():
    with tempfile.TemporaryDirectory(
        prefix="todo-no-hooks-", dir="/tmp/opencode"
    ) as hooks_dir:
        todo = ScratchTodo(hooks_dir)
        try:
            added = todo.run("add", "(A) repeated task")
            assert added.returncode == 0, added.stderr
            before = todo.lines()
            done_file = Path(todo.env["DONE_FILE"])
            done_before = done_file.read_text(encoding="utf-8")

            result = todo.run("repeat", "1", "tomorrow")

            assert result.returncode != 0
            assert "repeat date hooks are not fully configured" in result.stderr
            assert todo.lines() == before
            assert done_file.read_text(encoding="utf-8") == done_before
        finally:
            todo.close()


def test_repeat_without_date_does_not_require_schedule_hook():
    with tempfile.TemporaryDirectory(
        prefix="todo-no-hooks-", dir="/tmp/opencode"
    ) as hooks_dir:
        todo = ScratchTodo(hooks_dir)
        try:
            added = todo.run("add", "(A) repeated task")
            assert added.returncode == 0, added.stderr

            result = todo.run("repeat", "1")

            assert result.returncode == 0, result.stderr
            assert len(todo.lines()) == 1
            assert todo.lines()[0].startswith("(A) repeated task")
            assert "t:" not in todo.lines()[0]
        finally:
            todo.close()


if __name__ == "__main__":
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} tests passed.")
