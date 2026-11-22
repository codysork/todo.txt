"""Executable specification for the `predict` todo.sh action.

Run with:
    cd ~/.todo
    python -m pytest tests/test_predict.py -v
    python tests/test_predict.py

The tests use a fixed synthetic history and do not read real task data or
depend on the current date.
"""

import io
import math
import sys
import tempfile
import types
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

ACTIONS_DIR = Path(__file__).resolve().parent.parent / "actions"

DONE_LINES = (
    "x 2026-11-12 effort:3.0\n",
    "x 2026-11-13 effort:3.5\n",
    "x 2026-11-17 effort:4.0\n",
)
TOTAL_EFFORT = 10.5
SPAN_DAYS = 6
TEST_DATE = date(2026, 11, 21)

PACE_FRACTIONS = (0.0, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99)

# Multiples of MIN_EFFORT, decreasing toward the minimum.
DECREASING_PACE_FRACTIONS = (2.0, 1.75, 1.5, 1.25, 1.1, 1.05, 1.0)

# Smallest effort token in DONE_LINES (efforts 3.0, 3.5 and 4.0).
MIN_EFFORT = 3.0

# Report comparison tolerances; rows print with one decimal place.
TARGET_TOL = 0.01
REPORT_P_TOL = 0.06
ZERO_P_TOL = 0.01
ZERO_PCT_TOL = 0.11

# Report periods; period_horizons() maps them to their day counts.
HORIZON_NAMES = ("Day", "Week", "Month", "Year")


def load_predict():
    """Load the extension-less `actions/predict` script as a module."""
    path = ACTIONS_DIR / "predict"
    module = types.ModuleType("predict")
    module.__file__ = str(path)
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)
    return module


predict = load_predict()


def synthetic_posterior():
    """Return the posterior parameters for the fixed synthetic history."""
    return predict.posterior(TOTAL_EFFORT, SPAN_DAYS)


def maintained(alpha, beta, days, pace):
    """Return maintainability for the given inputs."""
    return predict.maintained_prob(alpha, beta, days, pace, MIN_EFFORT)


def period_horizons():
    """Return the report periods and their expected day counts."""
    predict.TODAY = TEST_DATE
    return {
        "Day": 1,
        "Week": 7,
        "Month": predict.month_length(TEST_DATE),
        "Year": predict.year_length(TEST_DATE),
    }


def report_rows(alpha, beta, pace):
    """Print a report and parse its Day/Week/Month/Year rows."""
    output = io.StringIO()
    with redirect_stdout(output):
        predict.print_report(alpha, beta, pace, MIN_EFFORT)

    rows = {}
    for line in output.getvalue().splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] in HORIZON_NAMES:
            rows[parts[0]] = (float(parts[1]), float(parts[2].rstrip("%")))
    return rows


def zero_pace_report_rows():
    """Return the parsed report rows of print_report(alpha, beta, 0.0)."""
    horizons = period_horizons()
    alpha, beta = synthetic_posterior()
    rows = report_rows(alpha, beta, 0.0)
    assert set(rows) == set(horizons)
    return rows


# --- Posterior ----------------------------------------------------------------


def test_posterior_derivation_from_done_history():
    """Done-file totals and span map to the history's (total, span)."""
    with tempfile.TemporaryDirectory() as tmp:
        done_file = Path(tmp) / "done.txt"
        done_file.write_text("".join(DONE_LINES), encoding="utf-8")
        history = predict.parse_done(str(done_file))

    assert history.total == TOTAL_EFFORT
    assert history.span == SPAN_DAYS
    assert history.min_effort == MIN_EFFORT


def test_posterior_maps_total_and_span_to_gamma_shape():
    """posterior() maps (total, span) to Gamma(1 + total, 1 + span)."""
    assert predict.posterior(TOTAL_EFFORT, SPAN_DAYS) == (
        1 + TOTAL_EFFORT,
        1 + SPAN_DAYS,
    )


def test_posterior_mean_matches_gamma_mean():
    """The posterior rate is the Gamma mean, alpha / beta."""
    alpha, beta = synthetic_posterior()
    assert alpha / beta == (1 + TOTAL_EFFORT) / (1 + SPAN_DAYS)


# --- Maintainability ----------------------------------------------------------


def test_pace_below_posterior_is_at_least_as_likely_as_posterior():
    """Paces below the posterior mean are no less maintainable on Day."""
    alpha, beta = synthetic_posterior()
    lam = alpha / beta
    at_mean = maintained(alpha, beta, 1, lam)

    for fraction in PACE_FRACTIONS:
        probability = maintained(alpha, beta, 1, fraction * lam)
        assert probability >= at_mean, (
            f"fraction={fraction}: P={probability:.6f} < "
            f"P at posterior mean={at_mean:.6f}"
        )


def test_maintainability_probability_is_bounded():
    """Maintainability probabilities stay within [0, 1]."""
    alpha, beta = synthetic_posterior()
    lam = alpha / beta

    for fraction in PACE_FRACTIONS:
        probability = maintained(alpha, beta, 1, fraction * lam)
        assert 0.0 <= probability <= 1.0


def test_pace_above_minimum_is_less_likely_than_minimum():
    """A pace above the minimum is less maintainable than the minimum."""
    alpha, beta = synthetic_posterior()

    assert maintained(alpha, beta, 1, MIN_EFFORT * 1.5) < maintained(
        alpha, beta, 1, MIN_EFFORT
    )


# --- Report columns ------------------------------------------------------------


def test_report_rows_cover_all_periods():
    """The report prints a row for each of the periods."""
    horizons = period_horizons()
    alpha, beta = synthetic_posterior()
    rows = report_rows(alpha, beta, alpha / beta)
    assert set(rows) == set(horizons)


def test_report_target_velocity_column_is_pace_times_horizon():
    """Each row's Target velocity is pace * horizon days."""
    horizons = period_horizons()
    alpha, beta = synthetic_posterior()
    pace = alpha / beta
    rows = report_rows(alpha, beta, pace)

    for name, days in horizons.items():
        target, _percentage = rows[name]
        assert math.isclose(target, pace * days, rel_tol=0.0, abs_tol=TARGET_TOL), (
            f"{name}: target velocity {target} != pace {pace} * horizon {days}"
        )


def test_report_p_maintain_column_matches_model():
    """Each row's P(maintain) is maintained_prob(horizon) * 100."""
    horizons = period_horizons()
    alpha, beta = synthetic_posterior()
    pace = alpha / beta
    rows = report_rows(alpha, beta, pace)

    for name, days in horizons.items():
        _target, percentage = rows[name]
        expected = maintained(alpha, beta, days, pace) * 100
        assert math.isclose(percentage, expected, rel_tol=0.0, abs_tol=REPORT_P_TOL), (
            f"{name}: P(maintain) {percentage} != expected {expected}"
        )


# --- Zero pace ------------------------------------------------------------------


def test_maintained_prob_of_zero_pace_is_one():
    """A zero pace gives 100% maintainability for every horizon."""
    alpha, beta = synthetic_posterior()
    horizons = period_horizons()

    for days in horizons.values():
        for pace in (0, 0.0, -0.0):
            assert math.isclose(
                maintained(alpha, beta, days, pace), 1.0, rel_tol=0.0, abs_tol=ZERO_P_TOL
            ), f"days={days} pace={pace}: expected P ~ 1.0"


def test_report_at_zero_pace_has_zero_target_velocity():
    """The zero-pace report prints zero Target velocity per period."""
    for name, (target, _percentage) in zero_pace_report_rows().items():
        assert math.isclose(target, 0.0, rel_tol=0.0, abs_tol=TARGET_TOL), (
            f"{name}: target velocity {target}, expected 0.0"
        )


def test_report_at_zero_pace_prints_hundred_percent():
    """The zero-pace report prints P(maintain) = 100.0% per period."""
    for name, (_target, percentage) in zero_pace_report_rows().items():
        assert math.isclose(
            percentage, 100.0, rel_tol=0.0, abs_tol=ZERO_PCT_TOL
        ), f"{name}: expected 100.0%, got {percentage}%"


# --- Minimum-effort pace ----------------------------------------------------------


def test_maintained_prob_at_min_effort_is_one():
    """A pace equal to the dataset's minimum effort is fully maintainable."""
    alpha, beta = synthetic_posterior()
    horizons = period_horizons()

    for days in horizons.values():
        probability = maintained(alpha, beta, days, MIN_EFFORT)
        assert math.isclose(
            probability, 1.0, rel_tol=0.0, abs_tol=ZERO_P_TOL
        ), f"days={days} pace={MIN_EFFORT}: expected P ~ 1.0, got {probability:.6f}"


def test_pace_below_minimum_is_fully_maintainable():
    """Every pace below the dataset minimum is fully maintainable."""
    alpha, beta = synthetic_posterior()
    horizons = period_horizons()

    for days in horizons.values():
        for pace in (0.0, 0.5 * MIN_EFFORT):
            assert math.isclose(
                maintained(alpha, beta, days, pace), 1.0, rel_tol=0.0, abs_tol=ZERO_P_TOL
            ), f"days={days} pace={pace}: expected P ~ 1.0"


def test_report_at_min_effort_prints_hundred_percent():
    """The report shows 100% for a pace equal to the minimum effort value."""
    alpha, beta = synthetic_posterior()
    horizons = period_horizons()
    rows = report_rows(alpha, beta, MIN_EFFORT)
    assert set(rows) == set(horizons)

    for name, (_target, percentage) in rows.items():
        assert math.isclose(
            percentage, 100.0, rel_tol=0.0, abs_tol=ZERO_PCT_TOL
        ), f"{name}: expected 100.0%, got {percentage}%"


# --- Decreasing pace -------------------------------------------------------------


def test_decreasing_pace_toward_minimum_increases_p():
    """Maintainability strictly increases as pace decreases toward the minimum."""
    alpha, beta = synthetic_posterior()
    ladder = [fraction * MIN_EFFORT for fraction in DECREASING_PACE_FRACTIONS]

    for higher, lower in zip(ladder, ladder[1:]):
        assert higher > lower
        assert maintained(alpha, beta, 1, lower) > maintained(
            alpha, beta, 1, higher
        ), f"decreasing pace from {higher:.4f} to {lower:.4f} did not increase P"


# --- Standalone runner (no third-party packages needed) ----------------------------


def _run_standalone():
    """Run the tests without requiring pytest."""
    tests = sorted(
        (name, fn)
        for name, fn in globals().items()
        if name.startswith("test_") and callable(fn)
    )
    failures = []

    for name, test in tests:
        try:
            test()
        except AssertionError:
            failures.append(name)
            print(f"FAIL {name}", file=sys.stderr)
        else:
            print(f"PASS {name}")

    if failures:
        print(
            f"\n{len(failures)} of {len(tests)} scenario(s) failed: "
            f"{', '.join(failures)}",
            file=sys.stderr,
        )
        return 1

    print(f"\nAll {len(tests)} scenario(s) passed.")
    return 0


if __name__ == "__main__":
    sys.exit(_run_standalone())
