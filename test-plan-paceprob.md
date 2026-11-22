# Test plan: `todo paceprob` (comprehensive, includes extremes)

*Plan-only document — derived from `actions/paceprob`, `tests/test_paceprob.py`, and the previous
`test-plan-paceprob.md`. Expectations were verified against the implementation with scratch runs
(§3); rows/cells quoted as `name (velocity, P%)` come from those runs. Scenarios marked
**fail-first** are expected to fail today and pass after the behavior change described in §9.
This plan changes nothing: no tests, production code, or configuration.*

## 1. Subject under test

`actions/paceprob` — a Python 3 todo.sh add-on (read-only; it only reads `done.txt`). Behavior
implemented today:

- `parse_done(path)`: scans `path`; sums the value of the first `effort:VALUE` token per line
  (regex `^effort:([0-9]+(?:\.[0-9]+)?)$`) over lines whose first field is `x` and whose second
  field is a valid ISO date; returns `(total, span)` with span = (last − first).days + 1 over the
  completed days. Lines whose date is invalid still count toward the span if their first field is
  `x` and they have ≥ 2 fields; lines with fewer than 2 fields or a non-`x` first field do not.
- `posterior(total, span)`: alpha = 1 + total, beta = 1 + span (conjugate Gamma prior, Gamma(1, 1)).
- `maintained_prob(alpha, beta, days, pace, tol)`: `target = pace * days`; the realized effort `V`
  is the negative-binomial marginal of the Poisson–Gamma model:
  `P = Σ_{v = lo}^{hi} C(alpha + v − 1, v) · A^alpha · B^v` with `A = beta / (beta + days)`,
  `B = days / (beta + days)`, over the integer band `[lo, hi] = [ceil(target·(1−tol)), floor(target·(1+tol))]`
  (`lo` clamped to 0 when negative). When `hi − lo > MAX_BAND` (100000) the band is capped to
  `hi = lo + MAX_BAND`; when `hi < lo`, `P = 0.0`.
- Default target pace = `alpha / beta` (posterior mean). Default tolerance `0.20`.
- `print_report`: header
  `Target pace:    {pace:.2f} effort/day (tolerance {tol*100:.0f}%)` and
  `Posterior rate: {lam:.3f} effort/day (alpha={alpha:.2f}, beta={beta:.2f})`; table rows
  `Day` (days=1), `Week` (days=7), `Month` (days=`month_length(TODAY)`),
  `Year` (days=`year_length(TODAY)`) with columns `Target velocity` = pace × days and
  `P(maintain)` = P × 100 (one decimal).

## 2. Status of the existing suite

`tests/test_paceprob.py` (scenarios S1–S8) — current run (`python -m pytest tests/test_paceprob.py`):
**6 passed, 2 failed** (observed 2026-11-21):

- `test_pace_of_zero_gives_hundred_percent_maintain` (S7) — FAILS. Today, with the suite's
  synthetic posterior (a = 11.5, b = 7): `maintained_prob(a, b, 1, 0, 0.2)` = 0.2153,
  `maintained_prob(a, b, 30, 0, 0.2)` = 4.83e-09, `maintained_prob(a, b, 365, 0, 0.2)` = 1.44e-20 —
  none is ~1.0 as S7 expects (the band around a zero pace contains no positive integer on most
  horizons).
- `test_decreasing_pace_always_increases_p` (S8) — FAILS. Today the ladder gives `P(pace=1.6264)`
  = 0.0 and `P(pace=1.6429)` = 0.0; the strict `P_low > P_high` assertion fails.

Other existing scenarios pass: S1 (posterior from done history), S2 (pace below posterior is at
least as likely: `maintained_prob(a, b, 1, 0.75·lam)` = 0.3095 > `maintained_prob(a, b, 1, lam)` = 0.0),
S3 (bounded), S4 (posterior mean), S5 (0.75·lam > lam), S6 (period column semantics).

This plan complements the suite at the CLI/observable level and corrects where the old plan
diverged from observed behavior (F5 span; report row values; V12).

## 3. Scratch setup

Per `~/.todo/AGENTS.md`: a scratch config so real tasks/data are untouched; direct and
through-todo.sh invocation both covered. All values quoted in this plan were verified by running
against this scratch (todo.sh runs use the `cfg` files below).

```
/tmp/opencode/paceprob-plan/
├── todo-test.cfg
├── todo-test/done.txt     # F1
├── f2/done.txt            # F2
├── f3/done.txt            # F3
├── f4/done.txt            # F4
├── f5/done.txt            # F5
├── dirB/done.txt          # tiny history
├── home/done.txt          # $HOME fallback history
├── empty.txt              # zero-byte file (no completions)
├── no-completions.txt     # done file with only ignored lines
└── *.cfg                  # per-fixture scratch configs
```

- `todo-test.cfg`:
  ```sh
  export TODO_DIR="/tmp/opencode/paceprob-plan/todo-test"
  export DONE_FILE="$TODO_DIR/done.txt"
  ```
- Through todo.sh: `todo.sh -d /tmp/opencode/paceprob-plan/todo-test.cfg paceprob ...`
- Direct: `./actions/paceprob ...` with `DONE_FILE`/`TODO_DIR`/`HOME` set to scratch paths.

## 4. Fixtures

**F1 — synthetic history** (matches `tests/test_paceprob.py` constants: total 11.5, span 6):

```
x 2026-11-12 effort:3.0
x 2026-11-13 effort:3.5
x 2026-11-14 effort:1.0
x 2026-11-17 effort:4.0
```

Expected: total 11.5, span 6 → alpha = 12.50, beta = 7.00, lam ≈ 1.786.

**F2 — parse semantics:**

```
(A) Some task not completed
x 2026-11-12 effort:3.0
x not-a-date effort:99
x 2026-11-14
x 2026-11-16 effort:7.5
```

Expected: total 10.5, span 5 (the invalid-date line contributes nothing; `x 2026-11-14` has no
effort token but still counts toward the span) → alpha = 11.50, beta = 6.00.

**F3 — effort token edges:**

```
x 2026-11-12 effort:1 effort:100
x 2026-11-13 effort:abc
x 2026-11-14
x 2026-11-15 effort:2.5
x 2026-11-16 effort:2.
x 2026-11-17 effort:.5
x 2026-11-18 effort:2.5x
```

Expected: total 3.5 (first matching token per line wins — `effort:1` of `effort:1 effort:100`;
`effort:abc`, `effort:2.`, `effort:.5`, `effort:2.5x` are not counted), span 7
(2026-11-12..2026-11-18) → alpha = 4.50, beta = 8.00.

**F4 — duplicate dates:**

```
x 2026-11-12 effort:1
x 2026-11-12 effort:2
x 2026-11-12 effort:3
x 2026-11-15 effort:4
```

Expected: total 10, span 4 (duplicate dates do not extend the span) → alpha = 11.00, beta = 5.00.

**F5 — year-boundary span:**

```
x 2026-12-31 effort:1
x 2027-01-01 effort:1
```

Expected: total 2, span 2 ((2027-01-01 − 2026-12-31).days + 1 = 2) → alpha = 3.00, beta = 3.00.
(Corrected from the earlier draft, which said span 3/beta 4; observed parse is `(2.0, 2)` and
`todo.sh -d f5.cfg paceprob` prints `Posterior rate: 1.000 effort/day (alpha=3.00, beta=3.00)`.)

**F6 — zero-effort lines, valid spans:**

```
x 2026-11-12
x 2026-11-13
```

Expected: total 0.0, span 2.

**F7 — unparseable effort tokens on valid lines:**

```
x 2026-11-12 effort:+2
x 2026-11-13 effort:2.5x
```

Expected: total 0.0, span 2 (neither token matches; both lines still count toward the span).

**F8 — leap-day span:** `x 2024-02-29 effort:1` → total 1.0, span 1 → alpha = 2.00, beta = 2.00.

**F10 — long span:** 4001 lines `x 2000-01-01 + i effort:0.5` for i in 0..4000 → total 2000.5,
span 4001 → alpha = 2001.50, beta = 4002.00.

Other files:

- `dirB/done.txt` = `x 2026-11-12 effort:1` → total 1, span 1 → alpha = 2.00, beta = 2.00.
- `home/done.txt` = `x 2026-11-12 effort:1`.
- `empty.txt` = zero bytes.
- `no-completions.txt` = `(A) Some task not completed` + `x not-a-date effort:1`.

## 5. Requirements

- **R1 Help contract** — every help style exits 0 and prints indented usage to stdout.
- **R2 Data reading** — `parse_done` sums the first `effort:VALUE` token per line over `x` lines
  with valid ISO dates; span = last − first + 1 over completed days; invalid lines contribute nothing.
- **R3 Error handling** — missing/unreadable done file → exit 1, stderr
  `Error: Cannot read done file: <path>`; no completions → exit 1, stderr
  `Error: No completions found in done file: <path>`.
- **R4 Posterior model** — `alpha = 1 + total`, `beta = 1 + span`; default pace = alpha/beta.
- **R5 Argument validation** — pace/tolerance: numeric, > 0, finite; tolerance validated before
  pace; exit 1 with `Error: <message>` on stderr; exit 0 when valid.
- **R6 Report format** — header `Target pace:`/`Posterior rate:` lines as implemented; table rows
  Day/Week/Month/Year with `Target velocity` = pace × days and `P(maintain)` = P × 100
  (one decimal).
- **R7 Horizon lengths** — Day = 1, Week = 7, Month = `month_length(TODAY)`,
  Year = `year_length(TODAY)`.
- **R8 Monotonicity (user rule, see §6.9)** — every increase in period length decreases P
  (except when the earlier period's P is 0).
- **R9 Determinism** — identical inputs → identical output.
- **R10 Environment resolution** — `DONE_FILE` > `TODO_DIR/done.txt` > `$HOME/done.txt`;
  `TODO_FILE` never read.
- **R11 CLI contract** — `todo.sh paceprob` == `./actions/paceprob`; help via
  `todo.sh help`/`shorthelp`/`listaddons`/`usage` argument.
- **R12 Read-only** — running the action does not modify `todo.txt`/`done.txt`.
- **R13 Extremes** — see §8: validation and `maintained_prob` behave predictably at extreme inputs
  (§8.1, §8.2), `parse_done` parses token/date edges without surprises (§8.3), reports print
  expected rows at extreme paces (§8.4), and horizon helpers are correct at month/year extremes
  (§8.5).

## 6. Scenarios

Columns: **ID | Req | Scenario | Expected result | Status** (`existing` = already covered by the
plan; `fail-first` = missing behavior). Row values are quoted from the scratch runs in §3.

### 6.1 Help (R1)

| ID | Req | Scenario | Expected result | Status |
| --- | --- | --- | --- | --- |
| H1 | R1 | `todo.sh -d cfg paceprob usage` | exit 0; stdout contains `  paceprob` and `Print the probability (%) of keeping a pace, from done.txt history.` | existing |
| H2 | R1 | `todo.sh -d cfg paceprob help` / `-h` / `--help` / `USAGE` | exit 0; stdout contains the usage block | existing |
| H3 | R1 | Direct `./actions/paceprob usage` / `help` / `-h` / `--help` / `paceprob usage` (with `DONE_FILE=F1`); direct `./actions/paceprob` (report, exit 0); direct `./actions/paceprob paceprob` (report, exit 0) | exit 0; usage on stdout, or report for the no-help invocations | existing |
| H4 | R11 | `todo.sh help`, `todo.sh shorthelp`, `todo.sh listaddons` | exit 0; output contains `paceprob` | existing |

### 6.2 Data reading (R2/R4)

| ID | Req | Scenario | Expected result | Status |
| --- | --- | --- | --- | --- |
| D1 | R2/R4 | `todo.sh -d cfg paceprob` with F1 | exit 0; stdout contains `Target pace:    1.79 effort/day (tolerance 20%)` and `Posterior rate: 1.786 effort/day (alpha=12.50, beta=7.00)` | existing (corrected) |
| D2 | R2 | `todo.sh -d f2.cfg paceprob` (F2) | `Posterior rate: 1.917 effort/day (alpha=11.50, beta=6.00)`; `Target pace:    1.92 effort/day (tolerance 20%)` | existing (corrected) |
| D3 | R2 | `todo.sh -d f3.cfg paceprob` (F3 — token edges) | `Posterior rate: 0.562 effort/day (alpha=4.50, beta=8.00)`; header `Target pace:    0.56 effort/day (tolerance 20%)` | existing (corrected) |
| D4 | R2 | `todo.sh -d f4.cfg paceprob` (F4 — duplicate dates) | `Posterior rate: 2.200 effort/day (alpha=11.00, beta=5.00)`; `Target pace:    2.20 effort/day (tolerance 20%)` | existing (corrected) |
| D5 | R2 | `todo.sh -d f5.cfg paceprob` (F5 — year-boundary span) | `Posterior rate: 1.000 effort/day (alpha=3.00, beta=3.00)`; `Target pace:    1.00 effort/day (tolerance 20%)` | existing (corrected) |

### 6.3 Errors (R3)

| ID | Scenario | Expected result | Status |
| --- | --- | --- | --- |
| E1 | `DONE_FILE=/tmp/opencode/paceprob-plan/does-not-exist.txt ./actions/paceprob` | exit 1; stderr `Error: Cannot read done file: /tmp/opencode/paceprob-plan/does-not-exist.txt` | existing |
| E2 | `DONE_FILE=/tmp/opencode/paceprob-plan/empty.txt ./actions/paceprob` | exit 1; stderr `Error: No completions found in done file: /tmp/opencode/paceprob-plan/empty.txt` | existing |
| E3 | `DONE_FILE=/tmp/opencode/paceprob-plan/no-completions.txt ./actions/paceprob` | exit 1; stderr `Error: No completions found in done file: /tmp/opencode/paceprob-plan/no-completions.txt` | existing |

### 6.4 Validation (R5) — through `todo.sh` on F1; assert stderr text and nonzero exit

| ID | Scenario | Expected stderr | Status |
| --- | --- | --- | --- |
| V1 | `todo.sh -d cfg paceprob abc` | `Error: Pace must be a number: abc` | existing |
| V2 | `todo.sh -d cfg paceprob 0` | `Error: Pace must be > 0.` | existing |
| V3 | `todo.sh -d cfg paceprob -0`; `todo.sh -d cfg paceprob -3` | `Error: Pace must be > 0.` | existing |
| V4 | `todo.sh -d cfg paceprob inf` | `Error: Pace must be finite.` | existing |
| V5 | `todo.sh -d cfg paceprob nan` | `Error: Pace must be > 0.` | existing |
| V6 | `todo.sh -d cfg paceprob 3.5 abc` | `Error: Tolerance must be a number: abc` | existing |
| V7 | `todo.sh -d cfg paceprob 3.5 0` | `Error: Tolerance must be > 0.` | existing |
| V8 | `todo.sh -d cfg paceprob 3.5 nan` | `Error: Tolerance must be > 0.` | existing |
| V9 | `todo.sh -d cfg paceprob 3.5 inf` | `Error: Tolerance must be finite.` | existing |
| V10 | `todo.sh -d cfg paceprob 0 abc` → `Error: Tolerance must be a number: abc`; `todo.sh -d cfg paceprob abc 0` → `Error: Tolerance must be > 0.` (tolerance validated before pace) | `Error: Tolerance must be a number: abc` / `Error: Tolerance must be > 0.` | existing |
| V11 | `todo.sh -d cfg paceprob 2 0.5` | exit 0; `Target pace:    2.00 effort/day (tolerance 50%)` | existing |
| V12 | `todo.sh -d cfg paceprob 0.0001` | exit 0; header `Target pace:    0.00 effort/day (tolerance 20%)`; Day row target `0.00`, Day P(maintain) = `0.0%`; Year row target `0.04`, P `0.0%` | existing (corrected) |

### 6.5 Reports (R6/R7) on F1 — parse rows like existing S6: `line.split()`; rows whose first
field is `Day`/`Week`/`Month`/`Year` map to `(Target velocity, P(maintain))` (P% stripped of `%`);
verify target = pace × horizon days (±0.01) and P = maintained_prob(alpha, beta, horizon, pace,
tol) × 100 (±0.1).

| ID | Req | Scenario | Expected result | Status |
| --- | --- | --- | --- | --- |
| R1 | R6 | `todo.sh -d cfg paceprob` | exit 0; header `Target pace:    1.79 effort/day (tolerance 20%)`, `Posterior rate: 1.786 effort/day (alpha=12.50, beta=7.00)`; rows `Day` (1.79, 24.8), `Week` (12.50, 45.2), `Month` (53.57, 48.8), `Year` (651.79, 51.9) | existing (corrected) |
| R2 | R6 | `todo.sh -d cfg paceprob` (Month/Year targets) | Month row target = pace × month_length(TODAY) = 1.7857×30 ≈ 53.57; Year row target = pace × year_length(TODAY) = 1.7857×365 ≈ 651.79 | existing |
| R3 | R6, R7 | `todo.sh -d cfg paceprob` (run-date assumption 2026-11-21: Month = 30 days, Year = 365 days) | Month target ≈ `53.57`, Year target ≈ `651.79`; P values per the model, matching within 0.1 | existing (corrected) |
| R4 | R6 | `todo.sh -d cfg paceprob 0.5 0.15` | exit 0; `Target pace:    0.50 effort/day (tolerance 15%)` | existing |

### 6.6 Determinism (R9)

| ID | Scenario | Expected result | Status |
| --- | --- | --- | --- |
| D1 | `todo.sh -d cfg paceprob` twice on F1 | stdout byte-identical between runs | existing |

### 6.7 Environment resolution (R10)

| ID | Scenario | Expected result | Status |
| --- | --- | --- | --- |
| E1 | `env -u DONE_FILE TODO_DIR=/tmp/opencode/paceprob-plan/todo-test ./actions/paceprob` | report from `todo-test/done.txt` (F1): `Posterior rate: 1.786 effort/day (alpha=12.50, beta=7.00)` | existing |
| E2 | `TODO_DIR=/tmp/opencode/paceprob-plan/dirB DONE_FILE=/tmp/opencode/paceprob-plan/todo-test/done.txt ./actions/paceprob` | F1 values — DONE_FILE wins; `dirB` alone would give `Posterior rate: 1.000 effort/day (alpha=2.00, beta=2.00)` | existing |
| E3 | `TODO_DIR=/tmp/opencode/paceprob-plan/dirB DONE_FILE= ./actions/paceprob` | `Posterior rate: 1.000 effort/day (alpha=2.00, beta=2.00)` (empty DONE_FILE falls back to `TODO_DIR/done.txt`) | existing |
| E4 | `env -u DONE_FILE -u TODO_DIR HOME=/tmp/opencode/paceprob-plan/home ./actions/paceprob` | `Posterior rate: 1.000 effort/day (alpha=2.00, beta=2.00)` ($HOME/done.txt) | existing |
| E5 | `TODO_FILE=/nonexistent TODO_DIR=/tmp/opencode/paceprob-plan/todo-test DONE_FILE=/tmp/opencode/paceprob-plan/todo-test/done.txt ./actions/paceprob` | F1 report — `TODO_FILE` is never read | existing |

### 6.8 Read-only (R12)

| ID | Scenario | Expected result | Status |
| --- | --- | --- | --- |
| X1 | Checksums of `todo-test/done.txt` and `todo-test/todo.txt` before/after `todo.sh -d cfg paceprob` | identical (also at extreme paces/tolerances from §8) | existing |

### 6.9 Monotonicity rule (R8)

Rule (user rule): **every increase in period length decreases P (except when P is 0)**. Operational
form for adjacent rows Day→Week→Month→Year: `P_next < P_prev or P_prev == 0.0` — an increase is
allowed only when the earlier row's P is 0.

Today's behavior on F1 (α = 12.5, β = 7, tol = 0.20; observed):

| pace | Day | Week | Month | Year | Rule today |
| --- | --- | --- | --- | --- | --- |
| 0.5 | 0.0% | 2.6% | 0.4% | 0.1% | holds (Day P = 0 exception) |
| 1.0 | 29.4% | 16.1% | 13.4% | 10.6% | holds (strictly decreasing) |
| 1.4 | 0.0% | 30.5% | 36.1% | 37.6% | fails (Week→Month increase, Week P ≠ 0) |
| default (lam) | 24.8% | 45.2% | 48.8% | 51.9% | fails (P increases with period) |
| 2.0 | 24.8% | 34.1% | 47.7% | 49.4% | fails |

| ID | Scenario | Expected result | Status |
| --- | --- | --- | --- |
| N0 | `todo.sh -d cfg paceprob 1.0` on F1 | exit 0; Day 29.4%, Week 16.1%, Month 13.4%, Year 10.6% — strictly decreasing, all > 0. Also `todo.sh -d cfg paceprob 0.5` — Day 0.0%, Week 2.6%, Month 0.4%, Year 0.1% — increase Day→Week allowed (Day P = 0) | passes today |
| N1 | `todo.sh -d cfg paceprob` (default, F1) | exit 0 today; today's rows violate the rule (Day 24.8% → Week 45.2% → Month 48.8% → Year 51.9%). After the behavior change: assert the rule holds (adjacent increases only where the earlier P is 0) | **fails today** |
| N1b | `todo.sh -d cfg paceprob 1.4` on F1 | exit 0 today; today's rows: Day 0.0%, Week 30.5%, Month 36.1%, Year 37.6% — rule violated (Week→Month). After the behavior change: assert the rule holds | **fails today** |
| N2 | `todo.sh -d cfg paceprob 100` on F1 | exit 0; Day 100.00/0.0%, Week 700.00/0.0%, Month 3000.00/0.0%, Year 36500.00/0.0% — the "except when P is 0" applies (assert all rows print `0.0%`) | passes today |

## 7. Boundaries and edge cases (summary)

- pace: `0` → `Error: Pace must be > 0.`; `-0`, `-3` → `Error: Pace must be > 0.`; `inf` →
  `Error: Pace must be finite.`; `nan` → `Error: Pace must be > 0.`; `0.0001` accepted;
  `1e-300`, `5e-324` accepted (§8.1).
- tolerance: `0`, negatives → `Error: Tolerance must be > 0.`; `nan` → `> 0` error; `inf` →
  `Error: Tolerance must be finite.`; `0.999`, `1e-9`, `0.999999` accepted; `{tol*100:.0f}` prints
  the integer percent.
- effort tokens: `effort:abc`, `effort:+1`, `effort:1e3`, `effort: 1`, `effort:0.`, `effort:2.5x`
  not counted; `effort:0`, `effort:00`, `effort:0.0`, `effort:999999999999` counted as 0/their
  value; first matching token per line counts (§8.3).
- lines: `X`/`x` case sensitivity (`X 2026-11-12 effort:1` → no completions); bare `x` line
  ignored; unpadded dates (`2026-1-5`) invalid; `2023-02-29` invalid, `2024-02-29` valid;
  `9999-12-31` valid; duplicate dates don't extend the span; `x` lines with valid dates and no
  effort tokens count toward the span (F2, F6); valid `x` lines with zero effort give total 0.0
  (F6, F10).
- report: `P(maintain)` prints one decimal (`0.0%`–`100.0%`); target velocity prints `pace × days`
  with two decimals; `Target velocity` can be `0.04` while `Target pace:` prints `0.00`.
- horizon helpers: `month_length(2026-11-21) = 30`, `month_length(2026-12-21) = 31`,
  `month_length(2026-01-15) = 31`, `month_length(2026-02-15) = 28`, `month_length(2024-02-15) = 29`;
  `year_length(2026-01-01) = 365`, `year_length(2024-01-01) = 366` (§8.5).

## 8. Extremes

**8.1 Validation extremes (through `todo.sh -d cfg`, F1)** — observed behavior; exit code 1 with a
traceback on stderr is current behavior:

| ID | Scenario | Expected result | Status |
| --- | --- | --- | --- |
| XE-V1 | `todo.sh -d cfg paceprob 1e308` | rc=1; stdout contains the `Target pace:` header with the huge value and the table header; stderr is a traceback ending `OverflowError: math range error` (from `math.lgamma(alpha + lo)` in `maintained_prob`) | current behavior |
| XE-V2 | `todo.sh -d cfg paceprob 1e308 0.9` | rc=1; stderr traceback `OverflowError: cannot convert float infinity to integer` (from `math.floor(target * (1.0 + tol))`) | current behavior |
| XE-V3 | `todo.sh -d cfg paceprob 1e308 0.75` / `0.5` / `0.2` / `0.1` | rc=1; stderr traceback `OverflowError: math range error` (from `math.lgamma`) | current behavior |
| XE-V4 | `todo.sh -d cfg paceprob 1e-300` | rc=0; Day/Week/Month/Year rows all `0.0%` | current behavior |
| XE-V5 | `todo.sh -d cfg paceprob 5e-324` | rc=0; header `Target pace:    0.00 effort/day (tolerance 20%)`; all rows `0.0%` | current behavior |
| XE-V6 | `todo.sh -d cfg paceprob 3.5 0.999` | rc=0; header `Target pace:    3.50 effort/day (tolerance 100%)`; rows: Day 80.6%, Week 100.0%, Month 100.0%, Year 100.0% | current behavior |

**8.2 `maintained_prob` extremes (function level; α = 12.5, β = 7, observed):**

| ID | Call | Expected result | Status |
| --- | --- | --- | --- |
| XE-M1 | `maintained_prob(12.5, 7, 0, 1.7857142857142856, 0.2)` | ValueError (math domain error family; observed `ValueError: expected a positive input, got 0.0`) — the zero-days path computes `B = 0` | current behavior |
| XE-M2 | `maintained_prob(12.5, 7, -1, 1.7857142857142856, 0.2)` | 0.0 | current behavior |
| XE-M3 | `maintained_prob(12.5, 7, -0.5, 1.7857142857142856, 0.2)` | 0.0 | current behavior |
| XE-M4 | `maintained_prob(12.5, 7, 200000, 1.7857142857142856, 0.2)` | 0.3909378966623726, in [0, 1] (MAX_BAND cap: hi − lo = 142856 > 100000) | current behavior |
| XE-M5 | `maintained_prob(12.5, 7, 10**9, 1.7857142857142856, 0.2)` | 7.34440043099697e-05, in [0, 1] | current behavior |
| XE-M6 | `maintained_prob(12.5, 7, 10**12, 1.7857142857142856, 0.2)` | 7.350672379501422e-08, in [0, 1] | current behavior |
| XE-M7 | `maintained_prob(12.5, 7, 1, 1e308, 0.2)` | OverflowError: math range error | current behavior |
| XE-M8 | `maintained_prob(12.5, 7, 1, 1e-300, 0.2)` | 0.0 | current behavior |
| XE-M9 | `maintained_prob(12.5, 7, 1, 5e-324, 0.2)` | 0.0 | current behavior |
| XE-M10 | `maintained_prob(12.5, 7, 1, 1.7857142857142856, 1e-9)` | 0.0 | current behavior |
| XE-M11 | `maintained_prob(12.5, 7, 1, 1.7857142857142856, 0.999)` | 0.6928476922206408 | current behavior |
| XE-M12 | `maintained_prob(12.5, 7, 1, 1e308, 0.9)` | OverflowError: cannot convert float infinity to integer | current behavior |

**8.3 `parse_done` extremes (observed):**

| ID | Fixture | Expected result | Status |
| --- | --- | --- | --- |
| XE-P1 | `x 2026-11-12 effort:0` | (0.0, 1) — zero-valued effort still extends the span | current behavior |
| XE-P2 | `x 2026-11-12 effort:00`; `x 2026-11-13 effort:0.0` | (0.0, 2) — zero-valued effort tokens count as 0.0 and still extend the span | current behavior |
| XE-P2b | `x 2026-11-12 effort:0.`; `x 2026-11-13 effort:+2`; `x 2026-11-14 effort:2.5x` | (0.0, 3) — the tokens do not match `^effort:([0-9]+(?:\.[0-9]+)?)$`; the lines still count toward the span | current behavior |
| XE-P3 | `x 2026-11-12 effort:999999999999` | (999999999999.0, 1) | current behavior |
| XE-P4 | `X 2026-11-12 effort:1` | SystemExit 1 ("No completions found") — first field must be `x` (lowercase) | current behavior |
| XE-P5 | `x` (bare line) | SystemExit 1 — fewer than 2 fields, ignored | current behavior |
| XE-P6 | `x 2026-1-5 effort:1`; `x 2023-02-29 effort:1` | SystemExit 1 — unpadded/invalid dates not counted | current behavior |
| XE-P6b | `x 2024-02-29 effort:1`; `x 9999-12-31 effort:1` | (1.0, 1) | current behavior |
| XE-P7 | `x 2026-11-12`, `x 2026-11-12` | (0.0, 1) — duplicate date, no effort | current behavior |
| XE-P7b | `x 2026-11-12`, `x 2026-11-13` | (0.0, 2) — valid lines, zero total | current behavior |
| XE-P8 | `x 2026-11-12 effort:abc effort:5` | (5.0, 1) — first matching token wins | current behavior |
| XE-P9 | F10 (4001 lines) | (2000.5, 4001) | current behavior |

**8.4 Report extremes (F1, observed):**

| ID | Scenario | Expected result | Status |
| --- | --- | --- | --- |
| XE-R1 | `todo.sh -d cfg paceprob 0.0001` | rc=0; Day/Week/Month rows `0.0%` (targets 0.00); Year row target `0.04`, `0.0%` | current behavior |
| XE-R2 | `todo.sh -d cfg paceprob 100` | rc=0; Day/Week/Month/Year rows all `0.0%` (Day target 100.00, Week 700.00, Month 3000.00, Year 36500.00) | current behavior |
| XE-R3 | `todo.sh -d cfg paceprob 2 0.5` | rc=0; header `Target pace:    2.00 effort/day (tolerance 50%)`; Day 69.3%, Week 85.0%, Month 91.8%, Year 94.2% | current behavior |

**8.5 Horizon extremes (function level, observed):**

| ID | Call | Expected result | Status |
| --- | --- | --- | --- |
| XE-H1 | `month_length(date(2026, 12, 21))` | 31 | current behavior |
| XE-H2 | `month_length(date(2026, 1, 15))` | 31 | current behavior |
| XE-H3 | `month_length(date(2026, 2, 15))` | 28 (2026 is not a leap year) | current behavior |
| XE-H4 | `month_length(date(2024, 2, 15))` | 29 | current behavior |
| XE-H5 | `year_length(date(2024, 1, 1))` | 366 | current behavior |
| XE-H6 | `year_length(date(2026, 1, 1))` | 365 | current behavior |

**8.6 Determinism extremes:**

| ID | Scenario | Expected result | Status |
| --- | --- | --- | --- |
| XE-D1 | `todo.sh -d cfg paceprob` × 10 on F1 | stdout byte-identical between runs | current behavior |
| XE-D2 | `todo.sh -d cfg paceprob 0.0001` and `todo.sh -d cfg paceprob 100` × 2 each | stdout byte-identical between runs | current behavior |

**8.7 Read-only extremes:**

| ID | Scenario | Expected result | Status |
| --- | --- | --- | --- |
| XE-RO1 | `chmod 444` on `todo-test/done.txt` (and `todo.txt`); run `todo.sh -d cfg paceprob` (default and extreme paces `1e308`, `0.0001`, `100`) | rc=0 for valid invocations; checksums of `todo-test/done.txt` and `todo-test/todo.txt` before/after identical (R12) | current behavior |

**8.8 Environment extremes:**

| ID | Scenario | Expected result | Status |
| --- | --- | --- | --- |
| XE-E1 | `DONE_FILE=/tmp/opencode/paceprob-plan/dir-done ./actions/paceprob` (a directory) | rc=1; stderr `Error: Cannot read done file: /tmp/opencode/paceprob-plan/dir-done` | current behavior |

## 9. Unimplemented behavior — fail-first

- **R8** — the user rule (§6.9). Fail-first scenarios: **N1** (`todo.sh -d cfg paceprob`, default
  on F1) and **N1b** (`todo.sh -d cfg paceprob 1.4`) violate the rule today (P increases with
  period where the earlier P ≠ 0). After the behavior change: N1 and N1b must pass (assert the
  rule holds; adjacent increases only where the earlier P is 0). All other scenarios (R1–R8, R10,
  V1–V12, E1–E5, X1, §8 extremes) must be unaffected.
- **XE-V1–XE-V3** — extreme-pace validation currently crashes with an unhandled
  `OverflowError` traceback instead of a clean `Error:` message (§8.1). After hardening: exit 1
  with a clean error (or documented behavior) instead of a traceback.

Plan-level determinism notes: scenarios assert on stable strings (e.g. `Target pace:    1.79
effort/day (tolerance 20%)`) and use the fixed fixtures above; Month/Year expectations are
parameterized by `month_length`/`year_length` of the assumed run date (2026-11-21); direct
invocations always set `DONE_FILE`/`TODO_DIR`/`HOME` to scratch paths; no scenario depends on real
task data, network, or behavior of unrelated components (the plan re-expresses the R8 rule at the
CLI level rather than duplicating coverage of existing S1–S8 beyond S7/S8 which are reflected in
§2 and §9).

## 10. Observation

`~/.todo/AGENTS.md`'s "Current actions" list (kanban, pace, popup, repeat, routine, schedule,
today) omits `paceprob` although `actions/paceprob` exists. Noted for context; not addressed in
this plan.
