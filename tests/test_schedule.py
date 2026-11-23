"""Scratch-data CLI tests for multi-task scheduling."""

import os
import shlex
import subprocess
import tempfile
from datetime import date, timedelta
from pathlib import Path

ACTIONS_DIR = Path(__file__).resolve().parent.parent / "actions"
TODO_SH = "todo.sh"


class ScratchTodo:
    def __init__(self, count, reschedule_all=None):
        self.temp = tempfile.TemporaryDirectory(
            prefix="todo-schedule-", dir="/tmp/opencode"
        )
        self.root = Path(self.temp.name)
        self.todo_file = self.root / "todo.txt"
        self.config = self.root / "config"
        settings = {
            "TODO_DIR": str(self.root),
            "TODO_FILE": str(self.todo_file),
            "DONE_FILE": str(self.root / "done.txt"),
            "REPORT_FILE": str(self.root / "report.txt"),
            "TODO_ACTIONS_DIR": str(ACTIONS_DIR),
        }
        self.config.write_text(
            "".join(
                f"export {key}={shlex.quote(value)}\n"
                for key, value in settings.items()
            ),
            encoding="utf-8",
        )
        if reschedule_all is not None:
            with self.config.open("a", encoding="utf-8") as config_file:
                config_file.write(
                    "export TODO_SCHEDULE_PRIORITY_RESCHEDULE_ALL="
                    f"{str(reschedule_all).lower()}\n"
                )
        self.env = {**os.environ, **settings}
        for number in range(1, count + 1):
            result = self.run("add", f"task-{number}")
            assert result.returncode == 0, result.stderr

    def run(self, *args, input=None):
        return subprocess.run(
            [TODO_SH, "-d", str(self.config), *args],
            capture_output=True,
            text=True,
            env=self.env,
            input=input,
            check=False,
        )

    def lines(self):
        return self.todo_file.read_text(encoding="utf-8").splitlines()

    def close(self):
        self.temp.cleanup()


def test_schedule_inclusive_range():
    todo = ScratchTodo(5)
    try:
        result = todo.run("schedule", "2-4", "tomorrow")
        expected = (date.today() + timedelta(days=1)).isoformat()
        assert result.returncode == 0, result.stderr
        assert [f"t:{expected}" in line for line in todo.lines()] == [
            False, True, True, True, False
        ]
    finally:
        todo.close()


def test_schedule_single_task_still_works():
    todo = ScratchTodo(3)
    try:
        result = todo.run("schedule", "2", "tomorrow")
        assert result.returncode == 0, result.stderr
        assert ["t:" in line for line in todo.lines()] == [False, True, False]
    finally:
        todo.close()


def test_schedule_comma_separated_list():
    todo = ScratchTodo(5)
    try:
        result = todo.run("schedule", "2,5", "monday")
        assert result.returncode == 0, result.stderr
        assert ["t:" in line for line in todo.lines()] == [
            False, True, False, False, True
        ]
    finally:
        todo.close()


def test_schedule_mixed_list_and_range():
    todo = ScratchTodo(9)
    try:
        result = todo.run("schedule", "2,5-7,9", "tomorrow")
        assert result.returncode == 0, result.stderr
        assert ["t:" in line for line in todo.lines()] == [
            False, True, False, False, True, True, True, False, True
        ]
    finally:
        todo.close()


def test_invalid_selection_changes_no_tasks():
    todo = ScratchTodo(5)
    try:
        before = todo.lines()
        result = todo.run("schedule", "2,4-8", "tomorrow")
        assert result.returncode != 0
        assert "invalid task selection" in result.stderr
        assert todo.lines() == before
    finally:
        todo.close()


def test_invalid_selection_syntax_changes_no_tasks():
    todo = ScratchTodo(5)
    try:
        before = todo.lines()
        result = todo.run("schedule", "2,,4", "tomorrow")
        assert result.returncode != 0
        assert todo.lines() == before
    finally:
        todo.close()


def test_range_preserves_multiword_date_expression():
    todo = ScratchTodo(2)
    try:
        result = todo.run("schedule", "1-2", "next", "monday")
        expected = subprocess.run(
            ["date", "-d", "next monday", "+%F"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert result.returncode == 0, result.stderr
        assert all(f"t:{expected}" in line for line in todo.lines())
    finally:
        todo.close()


def test_list_can_move_existing_schedules():
    todo = ScratchTodo(3)
    try:
        assert todo.run("schedule", "1,3", "tomorrow").returncode == 0
        result = todo.run("schedule", "1,3", "mv", "next", "monday")
        expected = subprocess.run(
            ["date", "-d", "next monday", "+%F"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert result.returncode == 0, result.stderr
        assert [f"t:{expected}" in line for line in todo.lines()] == [
            True, False, True
        ]
    finally:
        todo.close()


def test_range_can_remove_existing_schedules():
    todo = ScratchTodo(3)
    try:
        assert todo.run("schedule", "1-3", "tomorrow").returncode == 0
        result = todo.run("schedule", "1-3", "rm")
        assert result.returncode == 0, result.stderr
        assert all("t:" not in line for line in todo.lines())
    finally:
        todo.close()


def test_schedule_help_documents_ranges_and_lists():
    todo = ScratchTodo(0)
    try:
        result = todo.run("help", "schedule")
        assert result.returncode == 0
        assert "71-75" in result.stdout
        assert "2,5,9" in result.stdout
    finally:
        todo.close()


def add_priority_task(todo, text):
    result = todo.run("add", f"(A) {text}")
    assert result.returncode == 0, result.stderr


def test_priority_reschedule_skips_future_dates_and_confirms_once():
    todo = ScratchTodo(0, reschedule_all=False)
    today = date.today()
    expected = (today + timedelta(days=1)).isoformat()
    try:
        add_priority_task(todo, "unscheduled")
        add_priority_task(todo, f"past t:{today - timedelta(days=1)}")
        add_priority_task(todo, f"today t:{today}")
        add_priority_task(todo, f"future t:{today + timedelta(days=7)}")

        result = todo.run("schedule", "A", "tomorrow", input="y\n")
        assert result.returncode == 0, result.stderr
        assert result.stderr.count("(y/N)") == 1
        assert [f"t:{expected}" in line for line in todo.lines()] == [
            True, True, True, False
        ]
        assert "skipping 1 future-scheduled task" in result.stdout
    finally:
        todo.close()


def test_priority_reschedule_all_includes_future_dates():
    todo = ScratchTodo(0, reschedule_all=True)
    today = date.today()
    expected = (today + timedelta(days=1)).isoformat()
    try:
        add_priority_task(todo, f"future t:{today + timedelta(days=7)}")
        result = todo.run("schedule", "A", "tomorrow", input="y\n")
        assert result.returncode == 0, result.stderr
        assert result.stderr.count("(y/N)") == 1
        assert f"t:{expected}" in todo.lines()[0]
    finally:
        todo.close()


def test_priority_mv_skips_future_dates_by_default():
    todo = ScratchTodo(0, reschedule_all=False)
    today = date.today()
    expected = (today + timedelta(days=1)).isoformat()
    future = (today + timedelta(days=7)).isoformat()
    try:
        add_priority_task(todo, f"past t:{today - timedelta(days=1)}")
        add_priority_task(todo, f"future t:{future}")
        result = todo.run("schedule", "A", "mv", "tomorrow", input="y\n")
        assert result.returncode == 0, result.stderr
        assert [f"t:{expected}" in line for line in todo.lines()] == [True, False]
        assert f"t:{future}" in todo.lines()[1]
        assert result.stderr.count("(y/N)") == 1
    finally:
        todo.close()


def test_priority_rm_ignores_reschedule_all_setting():
    todo = ScratchTodo(0, reschedule_all=False)
    today = date.today()
    try:
        add_priority_task(todo, f"past t:{today - timedelta(days=1)}")
        add_priority_task(todo, f"future t:{today + timedelta(days=7)}")
        result = todo.run("schedule", "A", "rm", input="y\n")
        assert result.returncode == 0, result.stderr
        assert result.stderr.count("(y/N)") == 1
        assert all("t:" not in line for line in todo.lines())
    finally:
        todo.close()


def test_declining_priority_confirmation_changes_nothing():
    todo = ScratchTodo(0, reschedule_all=False)
    today = date.today()
    try:
        add_priority_task(todo, "unscheduled")
        add_priority_task(todo, f"future t:{today + timedelta(days=7)}")
        before = todo.lines()
        result = todo.run("schedule", "A", "tomorrow", input="n\n")
        assert result.returncode == 0, result.stderr
        assert result.stderr.count("(y/N)") == 1
        assert todo.lines() == before
        assert "cancelled" in result.stdout
    finally:
        todo.close()


def test_all_future_priority_tasks_do_not_prompt_by_default():
    todo = ScratchTodo(0, reschedule_all=False)
    today = date.today()
    try:
        add_priority_task(todo, f"future t:{today + timedelta(days=7)}")
        before = todo.lines()
        result = todo.run("schedule", "A", "tomorrow")
        assert result.returncode == 0, result.stderr
        assert "(y/N)" not in result.stderr
        assert todo.lines() == before
        assert "No eligible tasks" in result.stdout
    finally:
        todo.close()


if __name__ == "__main__":
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    failures = []
    for test in tests:
        try:
            test()
        except Exception as error:
            failures.append(test.__name__)
            print(f"FAIL {test.__name__}: {error}")
        else:
            print(f"PASS {test.__name__}")
    if failures:
        raise SystemExit(1)
    print(f"\nAll {len(tests)} tests passed.")
