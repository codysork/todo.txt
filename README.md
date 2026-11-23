# todo.txt Productivity Suite

A collection of configuration, add-ons, and filters for [todo.txt-cli](https://github.com/todotxt/todo.txt). It adds threshold-based scheduling, recurring routines, completion reports, and task views while keeping your todo data separate from the repository.

## Features

- **Threshold scheduling:** Set a `t:` date to keep a task hidden until it is ready to appear. Tasks with future thresholds are hidden from the normal list and can be shown with `todo.sh -x`.
- **Recurring routines:** Tag tasks with a frequency such as `@Routine:weekly` and set their next threshold.
- **Task overview:** Combine configured todo.sh views, suppress duplicates, and optionally show tasks not covered by those views.
- **Completion tracking:** `pace` reports completed effort points over time; `predict pace` estimates the probability of maintaining a target pace.
- **Task management:** Add tasks through a desktop dialog with `popup`, repeat completed tasks with `repeat`, and view due tasks with `today`.
- **Kanban groundwork:** `kanban` identifies tasks for board columns, but does not yet draw the board.

## Repository layout

| Path | Purpose |
| --- | --- |
| `config` | todo.sh configuration, including paths, colors, sorting, and the final filter |
| `actions/` | Executable todo.txt-cli add-ons |
| `filters/` | Executable filters for todo.txt-cli output |
| `tests/` | Tests and executable specifications |
| `doc/` | Design notes and test plans |

The repository contains configuration and code, not task data. By default, task files are stored under `$HOME/Sync/Todo` and are not tracked in git.

## Add-ons

| Command | What it does |
| --- | --- |
| `todo.sh today [TERM...]` | Shows tasks whose threshold is today or earlier |
| `todo.sh schedule` | Lists scheduled tasks |
| `todo.sh schedule <item> <date>` | Sets a task’s threshold |
| `todo.sh schedule <item> mv <date>` | Moves a task’s threshold |
| `todo.sh schedule <item> rm` | Removes a task’s threshold |
| `todo.sh schedule R <date>` | Schedules every task of the specified priority |
| `todo.sh routine set <frequency> <task-number> [<date>\|<day>]` | Sets a routine frequency and threshold |
| `todo.sh routine show <frequency>\|all` | Lists routine tasks |
| `todo.sh overview` | Displays the configured task views and, optionally, tasks not shown in those views |
| `todo.sh repeat ITEM [DATE\|DAY]` | Completes and re-adds a task, optionally rescheduling its threshold |
| `todo.sh pace [daily\|weekly\|monthly\|annual] [count]` | Reports completed effort points per day for each period |
| `todo.sh predict pace [pace]` | Estimates the probability that total effort meets the target average pace over each calendar period; historical samples include only days with valid effort entries |
| `todo.sh popup` | Opens a dialog to add a task |
| `todo.sh kanban` | Identifies tasks for the board’s columns; board rendering is not implemented yet |

All add-ons support `usage`, `help`, `-h`, and `--help`. The main CLI’s `help`, `shorthelp`, and `listaddons` commands also provide help and add-on listings.

`overview` uses `TODO_OVERVIEW_VIEWS` as an ordered, comma-separated list of
todo.sh commands. By default it runs `today`, `routine show all`, `ls due`, and
`schedule`. It suppresses repeated task numbers across views when
`TODO_OVERVIEW_DUPLICATE_TASKS=false`; `TODO_OVERVIEW_SHOW_REMAINING_TASKS=true`
adds active tasks not shown by any view at the end.

### How `predict pace` estimates probabilities

`predict pace [pace]` reads completed tasks with valid `effort:` values from
`done.txt`, sums effort recorded on the same date, and uses those daily totals
as its historical observations. If no pace is supplied, the target is the
historical mean effort per observation. Future-dated completions and completed
dates without valid effort entries are excluded.

The prediction uses a moving-block bootstrap: it repeatedly builds simulated
sequences by sampling historical observations in consecutive blocks of up to
seven entries. For each sequence, it checks whether cumulative effort by the
end of each period is at least the target pace multiplied by the period's
calendar days. The Day result is a one-observation check; Week, Month, and Year
results ask whether the average over the whole period meets the target. They
do not require meeting the target every day, so higher-effort days can offset
lower-effort days.

The reported percentages are estimates from 20,000 simulations. The displayed
Monte Carlo error describes simulation sampling noise, not uncertainty about
future productivity. A limitation is that dates without valid effort entries
are omitted rather than treated as zero-effort days, so sampled observations
are not necessarily consecutive calendar days even though period targets use
calendar-day counts.

## Task conventions

Tasks use todo.txt conventions: priorities such as `(A)`, project tags such as `+Project`, and context tags such as `@Context`. This suite also uses:

- `t:YYYY-MM-DD` for a threshold date
- `due:YYYY-MM-DD` for a due date
- `effort:` for decimal scoring values
- `@Routine:<frequency>` for a routine frequency: `daily`, `weekly`, `monthly`, `quarterly`, `yearly`, or `irregular`

The configuration sorts tasks by threshold date, with undated tasks first. Its final filter hides tasks whose threshold is in the future. Use `todo.sh -x` to show those tasks.

## Setup

1. Install and configure [todo.txt-cli](https://github.com/todotxt/todo.txt).
2. Place this repository at `~/.todo` or link it there.
3. Ensure the add-ons and filter are executable.
4. Set your task-data location in `config` if you do not want to use the default `$HOME/Sync/Todo`.
5. Configure todo.txt-cli to load `~/.todo/config` and use `~/.todo/actions` as its add-ons directory.

Add-ons resolve the todo.sh command and task-file paths themselves, so they can also be run outside the usual add-on setup.

## Tests and current status

Run the `predict` tests with:

```bash
python -m pytest tests/test_predict.py -v
```

Or run the test file directly:

```bash
python tests/test_predict.py
```
