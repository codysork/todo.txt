"""Focused tests for the configured todo.sh overview add-on."""

import os
import subprocess
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

ACTION = Path(__file__).resolve().parent.parent / "actions" / "overview"
overview = types.ModuleType("overview")
overview.__file__ = str(ACTION)
exec(compile(ACTION.read_text(encoding="utf-8"), str(ACTION), "exec"),
     overview.__dict__)


def test_parse_views_preserves_order_and_arguments():
    assert overview.parse_views("today, ls due, schedule") == [
        ["today"],
        ["ls", "due"],
        ["schedule"],
    ]


# AI-generated code (unreviewed by a human)
def test_routine_view_keeps_its_explicit_arguments():
    assert overview.parse_views("routine show all") == [["routine", "show", "all"]]


def test_parse_views_ignores_empty_entries():
    assert overview.parse_views("today, , schedule,") == [
        ["today"],
        ["schedule"],
    ]


def test_task_id_works_with_ansi_coloring():
    assert overview.task_id("\033[1;32m12\033[0m (A) task +Project") == "12"


# AI-generated code (unreviewed by a human)
def test_filter_suppresses_repeats_but_preserves_non_task_output():
    lines, _ = overview.filter_view_output(
        "No routine tasks.\n1 (A) first\n2 second\n1 duplicate\n",
        {"2"},
        allow_duplicates=False,
    )
    assert lines == ["No routine tasks.", "1 (A) first"]


# AI-generated code (unreviewed by a human)
def test_filter_allows_cross_view_duplicates_when_enabled():
    lines, _ = overview.filter_view_output(
        "4 task", {"4"}, allow_duplicates=True
    )
    assert lines == ["4 task"]


def test_run_todo_disables_verbose_chatter():
    class Result:
        returncode = 0
        stdout = "output\n"
        stderr = ""

    with patch.dict(os.environ, {"TODOTXT_VERBOSE": "2"}):
        with patch.object(overview.subprocess, "run", return_value=Result()) as run:
            assert overview.run_todo(["todo.sh"], ["list"]) == "output\n"
    assert run.call_args.args[0] == ["todo.sh", "list"]
    assert run.call_args.kwargs["env"]["TODOTXT_VERBOSE"] == "0"


def test_cli_deduplicates_views_and_shows_remaining_tasks():
    with tempfile.TemporaryDirectory(
        prefix="todo-overview-", dir="/tmp/opencode"
    ) as temp:
        root = Path(temp)
        config = root / "config"
        todo_file = root / "todo.txt"
        config.write_text(
            f"export TODO_DIR={root}\n"
            f"export TODO_FILE={todo_file}\n"
            f"export TODO_ACTIONS_DIR={ACTION.parent}\n"
            "export TODO_OVERVIEW_VIEWS='ls +Focus, ls @Work'\n"
            "export TODO_OVERVIEW_SHOW_REMAINING_TASKS=true\n"
            "export TODO_OVERVIEW_DUPLICATE_TASKS=false\n",
            encoding="utf-8",
        )

        def todo(*args):
            return subprocess.run(
                ["todo.sh", "-d", str(config), *args],
                capture_output=True,
                text=True,
                check=False,
            )

        assert todo("add", "shared +Focus @Work").returncode == 0
        assert todo("add", "remaining").returncode == 0
        result = todo("overview")

        assert result.returncode == 0, result.stderr
        assert result.stdout.count("shared +Focus @Work") == 1
        assert result.stdout.count("remaining") == 1
        assert result.stdout.index("=== ls +Focus ===") < result.stdout.index(
            "=== ls @Work ==="
        )
        assert result.stdout.index("=== Remaining tasks ===") > result.stdout.index(
            "=== ls @Work ==="
        )


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
            failures.append(f"{test.__name__}: {error}")
            print(f"FAIL {test.__name__}: {error}", file=sys.stderr)
        else:
            print(f"PASS {test.__name__}")
    if failures:
        sys.exit(1)
    print(f"\nAll {len(tests)} tests passed.")
