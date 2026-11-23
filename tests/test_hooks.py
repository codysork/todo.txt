"""Tests for the shared Bash hook runner."""

import os
import subprocess
import tempfile
from pathlib import Path

LIBRARY = Path(__file__).resolve().parent.parent / "lib" / "hooks.sh"


def make_hook(path, source):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)


def run_hooks(hooks_dir, *args, log_path=None):
    script = (
        'source "$1"; shift\n'
        'todo_run_hooks repeat "$@"\n'
        'status=$?\n'
        'printf "status=%s count=%s\\n" "$status" "$TODO_HOOKS_RUN_COUNT"\n'
        'exit 0\n'
    )
    env = {**os.environ, "TODO_HOOKS_DIR": str(hooks_dir)}
    if log_path is not None:
        env["HOOK_LOG"] = str(log_path)
    return subprocess.run(
        ["bash", "-c", script, "test-hooks", str(LIBRARY), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_hooks_run_in_filename_order_with_event_context():
    with tempfile.TemporaryDirectory(
        prefix="todo-hooks-", dir="/tmp/opencode"
    ) as temp:
        root = Path(temp)
        log = root / "log"
        hook_dir = root / "repeat" / "preflight.d"
        context = (
            "printf '%s:%s:%s:%s\\n' \"$TODO_HOOK_ACTION\" "
            "\"$TODO_HOOK_EVENT\" \"$1\" \"$2\" >> \"$HOOK_LOG\"\n"
        )
        make_hook(
            hook_dir / "20-second",
            "#!/usr/bin/env bash\necho second >> \"$HOOK_LOG\"\n" + context,
        )
        make_hook(
            hook_dir / "10-first",
            "#!/usr/bin/env bash\necho first >> \"$HOOK_LOG\"\n" + context,
        )
        result = run_hooks(
            root, "preflight", "71", "tomorrow", log_path=log
        )
        log_lines = log.read_text(encoding="utf-8").splitlines()

    assert result.returncode == 0
    assert result.stdout.strip() == "status=0 count=2"
    assert log_lines == [
        "first",
        "repeat:preflight:71:tomorrow",
        "second",
        "repeat:preflight:71:tomorrow",
    ]


def test_missing_optional_hook_is_a_success():
    with tempfile.TemporaryDirectory(
        prefix="todo-hooks-", dir="/tmp/opencode"
    ) as temp:
        result = run_hooks(Path(temp), "after_add", "71", "72", "")

    assert result.returncode == 0
    assert result.stdout.strip() == "status=0 count=0"


def test_executable_runner_supports_other_action_languages():
    with tempfile.TemporaryDirectory(
        prefix="todo-hooks-", dir="/tmp/opencode"
    ) as temp:
        root = Path(temp)
        hook_dir = root / "python-action" / "after_success.d"
        make_hook(
            hook_dir / "10-record",
            "#!/usr/bin/env bash\n"
            "printf '%s:%s:%s\\n' \"$TODO_HOOK_ACTION\" "
            "\"$TODO_HOOK_EVENT\" \"$1\"\n",
        )
        result = subprocess.run(
            [str(LIBRARY), "run", "python-action", "after_success", "payload"],
            capture_output=True,
            text=True,
            env={**os.environ, "TODO_HOOKS_DIR": str(root)},
            check=False,
        )

    assert result.returncode == 0
    assert result.stdout.strip() == "python-action:after_success:payload"


def test_hook_failure_stops_later_hooks_and_propagates_status():
    with tempfile.TemporaryDirectory(
        prefix="todo-hooks-", dir="/tmp/opencode"
    ) as temp:
        root = Path(temp)
        log = root / "log"
        hook_dir = root / "repeat" / "after_add.d"
        make_hook(hook_dir / "10-fail", "#!/usr/bin/env bash\nexit 7\n")
        make_hook(
            hook_dir / "20-later",
            "#!/usr/bin/env bash\necho later >> \"$HOOK_LOG\"\n",
        )
        result = run_hooks(
            root, "after_add", "71", "72", "", log_path=log
        )
        if log.exists():
            log_lines = log.read_text(encoding="utf-8").splitlines()
        else:
            log_lines = []

    assert result.stdout.strip() == "status=7 count=1"
    assert log_lines == []


if __name__ == "__main__":
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} tests passed.")
