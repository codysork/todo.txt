# Test plan: `todo predict KEY`

*Plan only — no test code or production code is changed, and no test commands
were run. This plan reflects the clarified spec: any numeric `key:value`
field is a separate metric; `todo predict KEY` selects one explicitly named
metric and reports its known historical statistics. Bare `todo predict` does
not list all keys. Non-numeric metadata such as dates is skipped. Signed
values, exponent notation, leading `+`, and leading or trailing decimal points
are valid; infinity, `NaN`, and malformed numeric values raise errors. Every
key aggregates by completion date, and a key without observations is identified
as having no data.*

## 1. Scope and current behavior

Subject: `actions/predict`, especially `parse_done`, `History`, report
statistics, and CLI mode handling.

The current implementation:

- Reads completed tasks from `DONE_FILE`.
- Only recognizes tokens named exactly `effort:<nonnegative decimal>`.
- Aggregates matching efforts by completion date; different dates with valid
  effort entries become separate observations.
- Reports historical average, median, population deviation, zero-effort-entry
  frequency, and effort-entry-day count, as well as bootstrap probabilities.
- Accepts `todo predict pace [pace]`; other modes fail as unknown.
- Rejects bare `todo predict` with a missing-mode error and does not list keys.

Consequently, the generic `KEY` selection and `physical-exertion` / `pe`
metrics are unimplemented. A test for a custom key should fail because the
action rejects that key as an unknown mode, not because of a broken fixture or
test setup.

`tests/test_predict.py` currently covers `effort:` parsing, same-date
aggregation, invalid/future record exclusion, history statistics, and report
output. It does not cover selecting an arbitrary key or keeping separate keys'
data isolated. Existing tests that invoke the old `predict pace` interface will
need updating once R7 rejects the trailing target-pace argument; that test
rewrite is outside this plan.

## 2. Confirmed requirements

- **R1 — Key selection:** `todo predict KEY` selects the exact metadata key
  `KEY`.
- **R2 — Separate metrics:** each key has its own history and prediction.
  Values from `effort`, `physical-exertion`, and `pe` must not be merged.
- **R3 — Numeric key-value data:** effort metrics are represented as numeric
  `key:value` tokens. The sample
  `effort:3.0 physical-exertion:2.9 pe:2.9` contains three separate values.
- **R4 — Summary statistics:** for the selected key, report the currently
  available historical statistics: average, median, population deviation,
  zero-value frequency, and number of valid observation days.
- **R5 — Explicit key required:** `todo predict` does not report statistics for
  all keys. The user must name a key; a bare invocation does not list per-key
  summaries. Because there is no all-key output, labeling every key in one
  report is not required. (Assumption: bare invocation fails with a usage
  error; confirm in §6.)
- **R6 — Duplicate key rejection:** if one completed-task line contains the
  same key more than once, `predict` reports an error rather than silently
  summing, choosing one occurrence, or counting the line.
- **R7 — No legacy target-pace argument:** `todo predict pace <number>` is
  rejected because the new interface expects a key name, not a target pace.
  A single `todo predict pace` selects a metadata key named `pace`.
- **R8 — Signed numeric values:** negative numeric values are valid
  observations and contribute to the selected key's history and statistics.
- **R9 — No-data response:** when the selected key has no valid observations,
  output clearly says there is no data for that key; do not substitute another
  key or report fabricated zero statistics.
- **R10 — Numeric notation:** exponent notation, leading-decimal notation
  such as `.5`, leading `+` such as `+2.0`, and trailing decimal point such as
  `2.` are valid numeric values.
- **R11 — Infinity rejection:** positive and negative infinity are not valid
  numeric observations; encountering either value raises an error and does not
  produce a partial statistics report.
- **R12 — Per-key daily aggregation:** every key aggregates its values by
  completion date, as the current implementation does for `effort`. Multiple
  completions of one key on one date produce one daily observation.
- **R13 — NaN and malformed rejection:** a `NaN` value or a malformed numeric
  value raises an error that identifies the problem (NaN versus malformed);
  no partial statistics report is printed.
- **R14 — Non-numeric metadata skipped:** non-numeric metadata values, such as
  dates in `due:` or `t:` fields or text tags, are skipped. They do not create
  observations and do not raise malformed-value errors.

## 3. Deterministic fixture

Use a scratch done file; do not read or change real task data. Pin `TODAY` for
unit-level parsing tests, and use fixed dates in the past for CLI smoke tests.

**F1 — three distinct metrics with deliberately different histories**

```text
x 2020-11-12 effort:3.0 physical-exertion:2.9 pe:2.9
x 2020-11-13 effort:4.0 physical-exertion:3.0 pe:0
x 2020-11-14 effort:5.0 physical-exertion:3.1 pe:3.1
```

Expected statistics, treating each date with a valid selected key as one
observation:

| Key | Daily observations | Total | Average | Median | Population deviation | Zero frequency | Observation days |
|---|---|---:|---:|---:|---:|---:|---:|
| `effort` | 3.0, 4.0, 5.0 | 12.0 | 4.0 | 4.0 | sqrt(2/3) | 0% | 3 |
| `physical-exertion` | 2.9, 3.0, 3.1 | 9.0 | 3.0 | 3.0 | sqrt(1/150) | 0% | 3 |
| `pe` | 2.9, 0.0, 3.1 | 6.0 | 2.9 | 2.0 | sqrt(6.02/3) | 1/3 | 3 |

F1 makes accidental cross-key mixing observable: every key has a distinct
history, and `pe` checks that a zero is retained as a numeric observation.

**F2 — same-date aggregation by selected key**

```text
x 2020-11-12 effort:1.0 physical-exertion:1.25
x 2020-11-12 effort:2.0 physical-exertion:2.5
```

Each key aggregates by completion date (R12): selecting `effort` produces one
observation, 3.0; selecting `physical-exertion` produces one observation,
3.75. Neither selected history includes the other key's values.

**F3 — missing selected key does not borrow another key**

```text
x 2020-11-12 effort:3.0
x 2020-11-13 pe:2.0
```

Selecting `physical-exertion` must not use either `effort` or `pe` as a
substitute; per R9 it must report that there is no data for
`physical-exertion`.

**F4 — metadata key named `pace`**

```text
x 2020-11-15 pace:2.0
```

Selecting `todo predict pace` must select this metadata key and summarize its
single valid observation: average 2.0, median 2.0, deviation 0.0, zero
frequency 0%, one observation day.

**F5 — negative values and zero remain observations**

```text
x 2020-11-16 effort:-2.0
x 2020-11-17 effort:0
x 2020-11-18 effort:1.0
```

Expected selected-key observations are `[-2.0, 0.0, 1.0]`: total -1.0,
average -1/3, median 0.0, population deviation sqrt(14/9), zero frequency
1/3, and 3 observation days.

**F6 — exponent and leading-decimal notation**

```text
x 2020-11-19 effort:1e1
x 2020-11-20 effort:.5
x 2020-11-21 effort:-2.5e-1
```

Expected observations are `[10.0, 0.5, -0.25]`: total 10.25, average 41/12,
median 0.5, population deviation sqrt(1567/72), zero frequency 0%, and 3
observation days.

**F7 — positive infinity**

```text
x 2020-11-22 effort:2.0
x 2020-11-23 effort:inf
```

Parsing F7 for `effort` must raise an error that identifies infinity and must
not return the earlier finite observation as usable statistics; `todo predict
effort` must not print a partial report.

**F8 — negative infinity**

```text
x 2020-11-22 effort:2.0
x 2020-11-23 effort:-inf
```

Parsing F8 for `effort` must raise an error that identifies infinity; negative
infinity is not a valid numeric observation, and the finite observation must
not be reported as statistics.

**F9 — leading plus and trailing decimal point**

```text
x 2020-11-25 effort:+2.0
x 2020-11-26 effort:3.
x 2020-11-27 effort:-1.5
```

Expected observations are `[2.0, 3.0, -1.5]`: total 3.5, average 7/6, median
2.0, population deviation sqrt(67/18), zero frequency 0%, and 3 observation
days.

**F10 — NaN value**

```text
x 2020-11-28 effort:2.0
x 2020-11-29 effort:nan
```

`todo predict effort` must raise an error that identifies NaN and must not
print the partial statistics report for the earlier finite observation; the
parser must raise the same error rather than silently ignoring `effort:nan`.

**F11 — malformed numeric value**

```text
x 2020-11-30 effort:2.0
x 2020-12-01 effort:1.2.3
```

`todo predict effort` must raise an error that identifies a malformed numeric
value and must not print a statistics report for the finite observation; the
parser must raise the same error rather than silently ignoring
`effort:1.2.3`. Other malformed shapes such as `effort:1e`, `effort:--1`, or
an empty `effort:` follow the same rule; one representative shape is
sufficient for this scenario.

**F12 — non-numeric date metadata skipped**

```text
x 2020-12-02 effort:2.0 due:2020-12-10
x 2020-12-03 effort:3.0 due:2020-12-11
```

Selecting `effort` yields observations `[2.0, 3.0]`: average/median 2.5,
population deviation 0.5, zero frequency 0%, 2 observation days. The `due:`
dates are skipped and do not raise malformed-value errors. Selecting `due`
yields no data (R9), because date metadata never becomes a numeric
observation.

## 4. Scenario matrix

Status labels: **existing** means the underlying behavior is implemented for
the hard-coded `effort:` key; **fail-first** means the new behavior is absent
and the test should initially fail for that application-level reason;
**guard** means a regression check that should pass today and must keep
passing.

| ID | Requirement | Scenario | Expected observable result | Status |
|---|---|---|---|---|
| K1 | R1, R4 | `todo predict effort` using F1 | Succeeds and reports `effort` statistics from F1 only: average/median 4.0, deviation sqrt(2/3), zero frequency 0%, 3 observation days | fail-first: `effort` is currently treated as a mode, not a key |
| K2 | R1–R4 | `todo predict physical-exertion` using F1 | Succeeds and reports average/median 3.0, deviation sqrt(1/150), zero frequency 0%, 3 observation days | fail-first: unknown mode today |
| K3 | R1–R4 | `todo predict pe` using F1 | Succeeds and reports average 2.0, median 2.9, deviation sqrt(6.02/3), zero frequency 1/3, 3 observation days | fail-first: unknown mode today |
| K4 | R2 | Select each F1 key independently | Each result matches its own table row; changing the selected key changes reported statistics; no values from other keys appear in its computed history | fail-first for key selection/isolation |
| K5 | R2, R3 | Parse F1 where all three numeric tokens share a line | A line containing all three keys contributes its three values to three separate keyed histories, never a single summed observation | fail-first |
| K6 | R2, R12 | Parse F2 and select either key | Values on the same completion date sum within that key only; each key's history contains one observation | existing for `effort`, fail-first for arbitrary keys |
| K7 | R2, R3, R9 | Parse F3 and select `physical-exertion` | The two tasks with other keys do not enter this history; selecting one key never falls back to a different key; output says there is no data for `physical-exertion` | fail-first; no-data behavior per R9 |
| K8 | R3 | Put fields in different token orders on otherwise equivalent completed lines | Selected key is found regardless of its position among metadata fields | fail-first for custom keys; current parser scans tokens but only recognizes `effort:` |
| K9 | R3 | Use a numeric zero for the selected key (F1 `pe:0`) | Zero is kept as an observation and contributes to zero frequency, mean, median, deviation, and count | existing for `effort:0`; fail-first for a custom key |
| K10 | R4 | Compare summary fields with F1's expected values for each key | Average, median, population deviation, zero frequency, and valid observation-day count match the fixture table | existing statistics calculation, fail-first when applied to arbitrary keys |
| K11 | R5 | Invoke bare `todo predict` using F1 | Does not print statistics for `effort`, `physical-exertion`, or `pe`; an explicit key is required | existing guard: current action already rejects a bare invocation; must not gain all-key output |
| K12 | R14 | Parse F12 with the existing `effort` key | History is `[2.0, 3.0]`; the `due:` dates are skipped and cause no malformed-value error | existing for hard-coded `effort`; guard for generic parsing |
| K13 | R9 | Invoke `todo predict not-present` with F1 | Output says there is no data for `not-present`; it does not silently use another key or report zero-filled statistics | fail-first after key selection; current action rejects the token as an unknown mode |
| K14 | R6 | Unit-level parse of a completed line `effort:2.0 effort:3.0` | Parser raises a controlled duplicate-key error; it does not silently choose or sum either occurrence | fail-first: current parser accepts the first `effort:` and ignores the second |
| K15 | R6 | After generic key parsing is implemented, select `pe` on `pe:2.0 pe:3.0` | Exits nonzero with duplicate-key error; neither value is silently selected or summed | prerequisite: generic key selection; then fail-first for duplicate detection |
| K16 | R6 | After generic key parsing is implemented, select `pe` on `pe:2.0 pe:2.0` | Exits nonzero; equal duplicate values are also rejected | prerequisite: generic key selection; then fail-first |
| K17 | R6, R14 | Parse `effort:2.0 due:2020-12-01 effort:3.0` with `effort` | Duplicate-key error for `effort`; the intervening date metadata does not hide the duplicate | fail-first: current parser takes the first `effort:` and ignores the second |
| K18 | R2, R3 | Run `todo predict effort` on F1, where each line has different keys once each | Succeeds; different key names on one line are not considered duplicates | fail-first for key selection; guards against overbroad duplicate detection |
| K19 | R7 | Run `todo predict pace 3.0` | Exits nonzero with an error because the selected key accepts no trailing target-pace argument | fail-first; current action accepts `pace` as mode and `3.0` as target |
| K20 | R1 | Run `todo predict pace` using F4 | Succeeds and reports statistics for the `pace` key: average/median 2.0, deviation 0.0, zero frequency 0%, one observation day | fail-first today: `pace` is treated as a mode, not a metadata key |
| K21 | R1–R14 | Run selected-key summaries repeatedly on fixed fixtures | Historical summary values and output remain deterministic | existing statistics are deterministic; new key paths need coverage |
| K22 | R8 | Parse F5 with the existing `effort` key | History includes `[-2.0, 0.0, 1.0]`; report statistics match F5 | fail-first: current parser rejects `effort:-2.0` |
| K23 | R8, R4 | Summarize F5 for key `effort` | Average -1/3, median 0.0, deviation sqrt(14/9), zero frequency 1/3, and 3 observation days | fail-first until signed values are accepted |
| K24 | R9 | Select a valid key that occurs only on invalid-date, future-date, or unfinished lines | Output says no data for the selected key; records outside the existing completed/valid-date/past-date rules do not create observations | fail-first after generic key selection; exact status/stream unspecified |
| K25 | R10 | Parse F6 using the existing `effort` key | History includes exactly `[10.0, 0.5, -0.25]`; statistics match F6 | fail-first: current value regex rejects exponent and leading-decimal notation |
| K26 | R11 | Parse F7 with the existing `effort` key | Raises an error that identifies infinity; the finite observation is not returned as statistics | fail-first: current parser ignores `effort:inf` and returns the finite observation |
| K27 | R11 | Parse F8 with the existing `effort` key | Raises an error that identifies infinity; the finite observation is not returned as statistics | fail-first: current parser ignores `effort:-inf` and returns the finite observation |
| K28 | R10 | Parse F9 using the existing `effort` key | History includes exactly `[2.0, 3.0, -1.5]`; statistics match F9 | fail-first: current value regex rejects `+2.0` and `3.` |
| K29 | R13 | Parse F10 with the existing `effort` key | Raises an error that identifies NaN; the finite observation is not reported as statistics | fail-first: current parser ignores `effort:nan` and returns the finite observation |
| K30 | R13 | Parse F11 with the existing `effort` key | Raises an error that identifies a malformed numeric value; the finite observation is not reported as statistics | fail-first: current parser ignores `effort:1.2.3` and returns the finite observation |
| K31 | R9, R14 | Run `todo predict due` on F12 | Output says there is no data for `due`; date metadata is skipped rather than parsed or reported as malformed | fail-first after key selection; current action rejects `due` as an unknown mode |
| K32 | R6, R14 | Parse `effort:2.0 effort:high` with `effort` | Duplicate-key error for `effort`; a repeated key is rejected even when the second value is non-numeric | fail-first: current parser takes the first `effort:` and ignores the second |

## 5. Existing parsing boundaries to preserve

These scenarios reuse existing behavior without expanding the new requirement:

- Only completed (`x`) lines with a valid date are candidates.
- Future-dated completions are excluded.
- A selected key absent from a line does not contribute an observation.
- Non-numeric metadata values, such as `due:` and `t:` dates or text tags, are
  skipped and never create observations.
- Multiple task completions on one date aggregate into one daily total for the
  selected key.
- No matching valid records must not cause an unrelated task/config/file error
  to masquerade as successful statistics.

Negative numbers, exponent notation, leading-decimal notation, leading `+`,
and a trailing decimal point are explicitly valid. Positive and negative
infinity, `NaN`, and malformed numeric values are invalid and raise errors.
Non-numeric metadata is skipped rather than treated as malformed. The current
`effort:` parser accepts nonnegative integer or decimal forms such as `3`,
`3.0`, and `0`, but does not meet the newly specified forms.

## 6. Questions and assumptions to confirm

1. **Malformed versus non-numeric:** Non-numeric metadata such as `due:` and
   `t:` dates or text tags is skipped (R14), while `NaN` and malformed numeric
   values error (R13). What distinguishes a malformed numeric-looking value
   such as `1.2.3`, `1e`, or `--1` from a non-numeric metadata value? How
   should an empty value (`effort:`) be classified? F11 uses `effort:1.2.3`.
   K32 assumes R6 duplicate rejection wins when a repeated key's second value
   is non-numeric; confirm that ordering.
2. **Bare command:** R5 assumes bare `todo predict` fails with a usage error
   and prints no per-key statistics. Confirm the exit behavior and whether the
   error should suggest `todo predict KEY`.
3. **Multiple keys per invocation:** The confirmed syntax is `todo predict KEY`
   (one key). Should `todo predict effort pe` accept multiple keys and label
   each, or must each invocation name exactly one key? This plan assumes one
   key.
4. **No-data response details:** The output must say there is no data for the
   selected key. Exact wording, output stream, and exit status are unspecified;
   tests should assert a key-specific no-data message and absence of fabricated
   statistics without guessing these details.
5. **Duplicate error details:** Duplicate occurrences must error (R6), but
   exact wording and whether the error identifies line number/key are
   unspecified. Assert nonzero exit and a duplicate-related diagnostic unless
   exact text is decided.
6. **Prediction output/model:** Confirmed requirement is the summary of known
   statistics. Should the current bootstrap probability table also be retained
   for selected-key summaries, or should the command report statistics only?
   Also confirm how bootstrap probabilities should be interpreted when
   observations may be negative. Core assertions cover the historical
   statistics named in R4.

## 7. Fail-first expectations

The key-selection cases K1–K3 should initially fail because `main()` currently
accepts only the `pace` mode and rejects the selected key as an unknown mode.
After the feature is implemented, they should reach the relevant history and
report path and match F1's per-key statistics.

K4–K8 are behavioral regression cases for key separation and aggregation.
Their failures should identify missing generic-key selection or incorrect
cross-key parsing, not syntax, imports, fixture paths, or access to real task
data. K11 is a guard rather than fail-first: the current action already rejects
a bare invocation, and it must not gain all-key output. K12 uses the existing
`effort` key and passes today because the parser ignores `due:`; it guards that
generic parsing skips non-numeric metadata. K14 isolates duplicate detection on
the currently supported `effort` key: today it fails because the parser
silently accepts the first occurrence. K15–K17 depend on key selection first,
then verify duplicate-specific rejection; K17 also confirms date metadata
between duplicates does not hide the conflict. K18 guards against overbroad
duplicate detection when different keys share a line. K19 fails because the
current action still accepts the old pace mode and numeric target. K20 fails
because the current action interprets `pace` as a mode rather than selecting
the `pace:` key. K13, K24, and K31 should fail only after key selection reaches
the no-data path; today the command instead rejects the key as an unknown mode.
K22–K23 fail because the current parser rejects the negative `effort:` value
while keeping the zero and positive entries. The no-data tests should assert a
clear key-specific message, not an unconfirmed exact string, stream, or exit
status. K25 fails because the current value regex rejects exponent and
leading-decimal notation. K28 fails because the current value regex rejects a
leading `+` and a trailing decimal point. K26–K27 use the existing `effort` key
and fail today because the parser ignores `effort:inf` and `effort:-inf`,
reporting the finite observation instead of an infinity-specific diagnostic.
K29–K30 use the existing `effort` key and fail today because the parser ignores
`effort:nan` and `effort:1.2.3`, reporting the finite observation instead of a
NaN- or malformed-value diagnostic. K31 additionally confirms that date
metadata is skipped rather than treated as malformed. K32 fails today for the
same first-occurrence reason as K14 and confirms that duplicate rejection takes
priority over skipping a non-numeric second value. K6's same-date aggregation
is confirmed for every key by R12; only the arbitrary-key path remains
fail-first.

The plan is intentionally limited to the clarified requirements and existing
predict statistics. It does not prescribe new algorithms, task-file formats,
error wording, or compatibility behavior.
