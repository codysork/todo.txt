# todo.txt Productivity Suite

A collection of configuration, add-ons, and filters for [todo.txt-cli](https://github.com/todotxt/todo.txt). It adds threshold-based scheduling, recurring routines, completion reports, and task views while keeping your todo data separate from the repository.

## Features

- **Threshold scheduling:** Set a `t:` date to keep a task hidden until it is ready to appear. Tasks with future thresholds are hidden from the normal list and can be shown with `todo.sh -x`.
- **Recurring routines:** Tag tasks with a frequency such as `@Routine:weekly` and set their next threshold.
- **Task overview:** Combine configured todo.sh views, suppress duplicates, and optionally show tasks not covered by those views.
- **Completion tracking:** `pace` reports completed effort points over time; `predict pace` estimates the probability of maintaining a target pace.
- **Task management:** Add tasks through a desktop dialog with `popup`, repeat completed tasks with `repeat`, and view due tasks with `today`.
- **Kanban groundwork:** `kanban` defines board contexts and computes layout dimensions, but does not yet retrieve tasks or draw the board.

## Repository layout

| Path | Purpose |
| --- | --- |
| `config` | todo.sh configuration, including paths, colors, sorting, and the final filter |
| `actions/` | Executable todo.txt-cli add-ons |
| `filters/` | Executable filters for todo.txt-cli output |
| `tests/` | Tests and executable specifications |

The repository contains configuration and code, not task data. By default, task files are stored under `$HOME/Sync/Todo` and are not tracked in git.

## Configuration

`config` sets `todo.txt`, `done.txt`, and `report.txt` under `$HOME/Sync/Todo`,
and points todo.sh at the add-ons in `~/.todo/actions`. It sorts list output by
the `t:` threshold, with undated tasks first, and uses `filters/futureTasks` to
hide tasks whose threshold is in the future. Run `todo.sh -x` to show those
tasks.

Calling `todo.sh` without an action runs `overview`. The configured overview
views are `ls @Routine:daily`, `today`, `ls due`, and `schedule`, in that order.
Repeated task numbers are suppressed, then remaining active tasks are shown.
These settings can be changed with `TODO_OVERVIEW_VIEWS`,
`TODO_OVERVIEW_DUPLICATE_TASKS`, and
`TODO_OVERVIEW_SHOW_REMAINING_TASKS`.

## Add-ons

| Command | What it does |
| --- | --- |
| `todo.sh today [TERM...]` | Shows tasks whose threshold is today or earlier |
| `todo.sh schedule` | Lists scheduled tasks |
| `todo.sh schedule <item-list\|range> <date>` | Sets thresholds for task numbers, comma-separated selections, inclusive ranges, or mixed selections such as `2,5-7,9` |
| `todo.sh schedule <item-list\|range> mv <date>` | Moves thresholds for the selected tasks |
| `todo.sh schedule <item-list\|range> rm` | Removes thresholds from the selected tasks |
| `todo.sh schedule R <date\|rm>` | Reschedules eligible tasks of the specified priority, or removes their thresholds, after one confirmation |
| `todo.sh routine set <frequency> <task-number> [<date>\|<day>]` | Sets a routine frequency and threshold |
| `todo.sh routine show <frequency>\|all` | Lists routine tasks |
| `todo.sh overview` | Displays the configured task views, suppresses repeated task numbers by default, and shows remaining active tasks by default |
| `todo.sh repeat ITEM [DATE\|DAY]` | Completes and re-adds a task, optionally rescheduling its threshold |
| `todo.sh pace [daily\|weekly\|monthly\|annual] [count]` | Reports completed effort points per day for each period |
| `todo.sh predict pace [pace]` | Estimates the probability that total effort meets the target average pace over each calendar period; historical samples include only days with valid effort entries |
| `todo.sh popup` | Opens a dialog to add a task |
| `todo.sh kanban` | Kanban scaffold with configured contexts and layout calculations; task retrieval and board rendering are not implemented yet |

Use todo.sh's `help`, `shorthelp`, and `listaddons` commands for help and
add-on listings. Action-level help support varies: `todo.sh` requests `usage`
from add-ons, while aliases such as `help`, `-h`, and `--help` depend on the
individual action.

Priority-wide date rescheduling normally includes tasks without a threshold or
with a threshold due today or earlier. Future-scheduled tasks are skipped;
set `TODO_SCHEDULE_PRIORITY_RESCHEDULE_ALL=true` to include them. Priority-wide
operations display their affected tasks and ask for one confirmation before
making changes. Removing schedules with `todo.sh schedule R rm` includes
future schedules regardless of the setting.

`overview` uses `TODO_OVERVIEW_VIEWS` as an ordered, comma-separated list of
todo.sh commands. The config runs `ls @Routine:daily`, `today`, `ls due`, and
`schedule`. A bare `routine` entry is expanded to `routine show all`. By
default, repeated task numbers are suppressed
(`TODO_OVERVIEW_DUPLICATE_TASKS=false`) and active tasks not shown by a view are
added at the end (`TODO_OVERVIEW_SHOW_REMAINING_TASKS=true`).

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

## Tests

Run the test suite from the repository root with:

```bash
pytest
```

The suite covers `overview`, `predict`, and `schedule`.
