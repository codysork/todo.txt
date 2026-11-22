# `~/.todo` — todo.txt configuration and productivity suite

Scope: configuration, custom actions (add-ons), and output filters for
[todo.txt-cli](https://github.com/todotxt/todo.txt).

Task data lives in `$HOME/Sync/Todo` (`TODO_DIR`) and is **not** tracked in git.
This repo is the dotfiles repo (tracked at `.todo/`), with `AGENTS.md` holding
the conventions documented below.

## Layout

| Path | Purpose |
| --- | --- |
| `config` | todo.sh configuration, sourced on every run; defines paths, colors, sort/final filter, behavior |
| `actions/` | Executable add-ons; each filename is the `todo.sh` subcommand name |
| `filters/` | Executable stdin→stdout filters (currently `futureTasks`, wired via `TODOTXT_FINAL_FILTER`) |
| `doc/` | Analysis docs, e.g. `test-plan-paceprob.md` |
| `tests/` | Executable specifications for the suite |

## The suite

### Configured behavior (`config`)

- Data locations: `TODO_DIR="$HOME/Sync/Todo"`, `TODO_FILE=$TODO_DIR/todo.txt`,
  `DONE_FILE=$TODO_DIR/done.txt`, `REPORT_FILE=$TODO_DIR/report.txt`,
  `TODO_ACTIONS_DIR=$HOME/.todo/actions`.
- Colors: `PRI_A`=pink (urgent, important, do now), `PRI_B`=yellow,
  `PRI_C`=green, `PRI_D`=light blue, `PRI_E`=white, `PRI_W`=light grey (waiting).
- Sort: `TODOTXT_SORT_COMMAND` sorts `todo.sh list` output by the `t:`
  threshold; undated tasks sort first (`0000-00-00`).
- Final filter: `TODOTXT_FINAL_FILTER=$HOME/.todo/filters/futureTasks` — hides
  tasks whose `t:YYYY-MM-DD` threshold is in the future (visible again with
  `todo.sh -x`).

### Add-ons (`actions/`)

| Action | Purpose |
| --- | --- |
| `kanban` | Kanban board over the contexts `@Routine:[A-Za-z]*`, `@Todo`, `@Doing`, plus a backlog column. Status: skeleton — computes board geometry but the board is not drawn yet. |
| `pace` | Story-point velocity report: sums `effort:` values from completions in `done.txt`; prints points/day per period. Usage: `todo.sh pace [daily\|weekly\|monthly\|annual] [count]`. |
| `paceprob` | Bayesian probability (%) of maintaining a target pace, computed from `done.txt` history (reads only `done.txt`). Usage: `todo.sh paceprob [pace] [tolerance]`; defaults are the posterior-mean pace and a 20% band; periods Day/Week/Month/Year. |
| `popup` | Add a task via a kdialog inputbox ("Add Todo Task"); `notify-send` confirms or reports failure. |
| `repeat` | Mark an item complete and immediately re-add it: `todo.sh repeat ITEM [DATE\|DAY]`; the optional date reschedules its threshold via `schedule`. |
| `routine` | Set or show `@Routine:<frequency>` tags: `todo.sh routine set <frequency> <task-number> [<date>\|<day>]`, `todo.sh routine show <frequency>\|all`. Frequencies: `daily weekly monthly quarterly yearly irregular`. Adds `(R)` if the task has no priority, then sets the `t:` threshold via `schedule`. |
| `schedule` | Set, move or remove `t:` thresholds: `todo.sh schedule <item> <date>`, `todo.sh schedule <item> mv <date>`, `todo.sh schedule <item> rm`, or schedule every task of one priority: `todo.sh schedule R <date>`. With no arguments it lists scheduled tasks. |
| `today` | Show tasks whose threshold is on or before today: `todo.sh today [TERM...]`. |

### How the pieces compose

- `routine` ↔ `schedule`: routine tasks are recurring threshold-scheduled
  tasks; `routine set` sets the tag and the threshold.
- `repeat` ↔ `schedule`: repeating items can be rescheduled at each cycle.
- `today` ↔ `futureTasks`: threshold-aware "what's due today" view.
- `pace` + `paceprob`: completed `effort:` values feed both the velocity report
  and the probability model.

### Data model highlights

- Priorities `(A)`–`(Z)`, `+Project` and `@Context` tags.
- Metadata: `t:YYYY-MM-DD` (threshold), `due:YYYY-MM-DD`, scoring fields
  `effort:`/`hassle:`/`uplift:` (decimals).
- Routine tasks: `@Routine:<frequency>` (`daily`, `weekly`, `monthly`,
  `quarterly`, `yearly`, `irregular`).
- `futureTasks`: stdin→stdout filter hiding future-threshold lines; intended as
  the `TODOTXT_FINAL_FILTER`.

### Help contract

- Every action handles `usage`/`help`/`-h`/`--help`: prints indented help to
  stdout and exits 0. `todo.sh help`, `todo.sh shorthelp` and
  `todo.sh listaddons` list the suite.
- Add-ons should resolve the CLI and data paths themselves so they also work
  standalone, per `~/.todo/AGENTS.md`:
  `TODO_CMD="${TODO_FULL_SH:-${TODO_SH:-todo.sh}}"`
  `TODO_FILE="${TODO_FILE:-${TODO_DIR:-$HOME}/todo.txt}"`

## Tests and docs

- `tests/test_paceprob.py` — executable spec for `paceprob`
  (`python -m pytest tests/test_paceprob.py -v` or `python tests/test_paceprob.py`).
  Status per `doc/test-plan-paceprob.md` §2 (observed 2026-11-21): **6 passed,
  2 failed** — `S7` (pace 0 → 100% maintain) and `S8` (strictly decreasing
  P) fail against the current `maintained_prob` implementation. See
  `doc/test-plan-paceprob.md` §9 for the intended behavior (fail-first
  scenarios, expected fixes).
- `doc/test-plan-paceprob.md` — plan-only document: fixtures, requirements,
  scenario tables and "current behavior" notes.

## Validating changes

```sh
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

New add-ons should follow the header convention (`@file`, `@author`,
`@created`, `@modified`, `@description` or `@purpose`, `Usage:` examples) and
the conventions in `~/.todo/AGENTS.md`.

## Noted gaps

- `~/.todo/AGENTS.md` "Current actions" list omits `paceprob` although
  `actions/paceprob` exists (same observation as `doc/test-plan-paceprob.md`
  §10).
