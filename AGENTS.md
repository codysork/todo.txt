# AGENTS.md

Scope: `~/.todo` — configuration, custom actions, and output filters for
[todo.txt-cli](https://github.com/todotxt/todo.txt-cli) (`/usr/bin/todo.sh`).

This directory is part of the dotfiles repository rooted at `$HOME`
(`git rev-parse --show-toplevel` → `/home/cody`), so tracked paths appear as
`.todo/...`. Task data lives in `$HOME/Sync/Todo` (`TODO_DIR`) and is **not**
tracked in git. Do not edit `/usr/bin/todo.sh`; it is a distro package. Extend
behavior with files here.

## Layout

| Path | Purpose |
| --- | --- |
| `config` | todo.sh configuration, sourced on every run; defines paths, colors, sort/final filter, behavior |
| `actions/` | Executable add-ons; each filename is the `todo.sh` subcommand name |
| `filters/` | Executable stdin→stdout filters (currently `futureTasks`, wired via `TODOTXT_FINAL_FILTER`) |

Current actions: `kanban`, `pace`, `popup`, `repeat`, `routine`, `schedule`,
`today`.

## Runtime model

- todo.sh finds `~/.todo/config` automatically (also `-d CONFIG_FILE` /
  `TODOTXT_CFG_FILE`), sources it, exports environment, then dispatches.
- Executable files in `actions/` are invoked as
  `"$TODO_ACTIONS_DIR/<name>" "$@"`. **`$1` is the action name**, so scripts
  start with `action=$1; shift` (see `pace`, `repeat`, `schedule`).
  `routine` and `popup` also tolerate being run directly by stripping `$1`
  when it matches the script name.
- todo.sh calls every add-on with a single `usage` argument to build
  `todo.sh help`, `shorthelp`, and `listaddons` output. Every action must
  handle `usage` (and ideally `help`, `-h`, `--help`) by printing indented help
  to stdout and exiting 0.
- Environment supplied or respected: `TODO_DIR`, `TODO_FILE`, `DONE_FILE`,
  `REPORT_FILE`, `TODO_ACTIONS_DIR`, `TODO_SH`, `TODO_FULL_SH`,
  `TODOTXT_VERBOSE`, and the `PRI_*` / `COLOR_*` variables.
- Add-ons should resolve the CLI and data paths themselves so they also work
  standalone:
  `TODO_CMD="${TODO_FULL_SH:-${TODO_SH:-todo.sh}}"`
  `TODO_FILE="${TODO_FILE:-${TODO_DIR:-$HOME}/todo.txt}"`

## File header convention

Bash actions and `config` carry a metadata block:

```bash
#!/usr/bin/env bash
#
# @file routine (todo.sh action)
# @author Cody Sork <codysork@gmail.com> with help from AI agents
# @created 2026-11-20
# @modified 2026-11-20
# @description Set or show @Routine:<frequency> tags.
#
# Usage:
#   todo.sh routine set weekly 43 "next monday"
```

- Keep `@file`, `@author`, `@created`, `@modified`; use `@description` **or**
  `@purpose` (both appear), and bump `@modified` on substantive edits.
- New scripts use `#!/usr/bin/env bash`; older files use `#!/bin/bash` to match
  the file you are editing rather than churning shebangs.
- Python filters use a module docstring instead of the `@` block and follow the
  tab-indented style of `filters/futureTasks`.

## Shell conventions

- Strict mode is mandatory. Most actions use `set -euo pipefail`;
  `kanban` uses `set -Eeuo pipefail`; `routine` deliberately uses
  `set -uo pipefail` because it composes todo.sh calls and handles failures
  explicitly. Choose deliberately and do not silently weaken existing mode.
- Bash features in use: `[[ ... ]]`, arrays, `local`, `case`, C-style `for`,
  `${var,,}` / `${var^^}`, `=~` with `BASH_REMATCH`.
- UPPER_CASE for environment/config/global constants (`TODO_FILE`, `DONE_FILE`,
  `TODAY`, `MODE`); lower_case for function locals declared with `local`.
  Quote every expansion. Use `$(( ))` and force base 10 with `10#$n` for user
  input (`pace`, `routine`).
- Section banners separate `Configuration`, `Constants`, `Helper Functions`,
  `Rendering Functions`, and `Main`. Match the neighboring banner style:
  `#----...` (pace) or `#====` with `#----` subsections (kanban).
- Function syntax varies: `function name { ... }` in `repeat`, `routine`,
  `schedule`; `name() { ... }` in `pace`, `kanban`. Stay consistent within a
  file.
- Errors go to stderr with `>&2` and `exit 1`; help goes to stdout with
  `exit 0`. `routine` uses a `fail()` helper. Preserve child exit codes with
  `|| exit $?` or `|| fail "..."`. User-facing messages echo todo.sh phrasing
  (`TODO: No task 4.`) and status prefixes (`Routine: ...`).
- Dates: GNU `date -d` is assumed. Validate with
  `date -d "$input" +%F >/dev/null 2>&1`, then compare ISO `%F` strings
  lexicographically (`[[ "$end" > "$today" ]]`). Accept human dates
  (`today`, `tomorrow`, `next monday`) and normalize numeric offsets to
  `N days` (see `normalize_target_date` in `repeat`).
- Read tasks from `$TODO_FILE` with
  `sed -n "${n}p" "$TODO_FILE"` or `sed "${n}!d"`.
- **Never hand-edit `todo.txt`/`done.txt`.** Mutate through todo.sh builtins:
  `add`, `append`, `replace`, `do`, `archive`, or `command <builtin>` to bypass
  add-on lookup (`repeat` does this). Suppress chatter with `TODOTXT_VERBOSE=0`
  on the invocation or before calling.
- `todo.sh list` output may contain ANSI colors. When parsing it, strip codes
  first: `gsub(/\033\[[0-9;]*m/, "", plain)` (see `routine`).
- Usage text mimics todo.sh: two-space indent for the action name, four spaces
  for descriptions/examples, `$ $TODO_SH ...` examples.

## Task data model

- `(A)`–`(Z)` priority, `x YYYY-MM-DD` completed, `+Project`, `@Context`.
- Metadata uses `key:value`: `t:YYYY-MM-DD` (threshold), `due:YYYY-MM-DD`,
  and the custom scoring fields `effort:`, `hassle:`, `uplift:` (decimals).
  `pace` sums `effort:` from completed lines in `done.txt`.
- Routine tasks use `@Routine:<frequency>` (`daily`, `weekly`, `monthly`,
  `quarterly`, `yearly`, `irregular`).
- `config` sorts list output by `t:` (undated lines sort first as
  `0000-00-00`) and applies `filters/futureTasks`, which hides future
  thresholds unless todo.sh runs with `-x`.

## Config and filter conventions

- `config` uses `export`, `# === SECTION ===` banners, commented-out defaults
  copied from todo.sh, and an absolute `TODO_DIR`.
- Filters are executable, read stdin, write stdout, preserve line content
  (colors included), and must be safe per line. `futureTasks` uses tab
  indentation, a regex module constant, and `main(args=None) -> bool` with
  `sys.exit(not main(sys.argv))`.

## Validating changes

```bash
cd ~/.todo

# Syntax / lint
bash -n actions/<name>
shellcheck actions/<name>            # when available
python -m py_compile filters/futureTasks

# Help contract (todo.sh invokes "<action> usage")
todo.sh help <name>
todo.sh shorthelp
todo.sh listaddons

# Exercise against a scratch config so real tasks are untouched
todo.sh -d /tmp/todo-test.cfg <name> ...
```

There is no automated test suite. Verify behavior manually, including direct
invocation (`./actions/<name> <name> ...`) and invocation through `todo.sh`.
Keep actions executable (`chmod +x`). Do not commit generated files or task
data; commit messages in this repo are short and past tense
("Added ...", "Adjusted ...", "Fixed ...").
