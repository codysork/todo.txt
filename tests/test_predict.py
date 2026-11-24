"""Executable specification for the `predict` action.

Covers the historical bootstrap model plus key selection, summary statistics,
numeric grammar, metadata skipping, and error handling. Histories, dates and
random seeds are fixed; no real task data is read.
"""

import io
import math
import os
import random
import re
import subprocess
import sys
import tempfile
import traceback
import types
from contextlib import redirect_stdout
from datetime import date
from functools import lru_cache
from pathlib import Path
from unittest.mock import mock_open, patch

ACTION = Path(__file__).resolve().parent.parent / "actions" / "predict"
TEST_DATE = date(2026, 11, 21)
DONE_TEXT = (
    "x 2026-11-12 effort:3.0\n"
    "x 2026-11-13 effort:3.5\n"
    "x 2026-11-17 effort:4.0\n"
)
EFFORT_DAYS = [3.0, 3.5, 4.0]
HORIZONS = {"Day": 1, "Week": 7, "Month": 30, "Year": 365}
SIMULATIONS = 1000

# AI-generated code (unreviewed by a human)
F1 = (
    "x 2020-11-12 effort:3.0 physical-exertion:2.9 pe:2.9\n"
    "x 2020-11-13 effort:4.0 physical-exertion:3.0 pe:0\n"
    "x 2020-11-14 effort:5.0 physical-exertion:3.1 pe:3.1\n"
)
F2 = (
    "x 2020-11-12 effort:1.0 physical-exertion:1.25\n"
    "x 2020-11-12 effort:2.0 physical-exertion:2.5\n"
)
F3 = (
    "x 2020-11-12 effort:3.0\n"
    "x 2020-11-13 pe:2.0\n"
)
F4 = "x 2020-11-15 pace:2.0\n"
F5 = (
    "x 2020-11-16 effort:-2.0\n"
    "x 2020-11-17 effort:0\n"
    "x 2020-11-18 effort:1.0\n"
)
F6 = (
    "x 2020-11-19 effort:1e1\n"
    "x 2020-11-20 effort:.5\n"
    "x 2020-11-21 effort:-2.5e-1\n"
)
F7 = (
    "x 2020-11-22 effort:2.0\n"
    "x 2020-11-23 effort:inf\n"
)
F8 = (
    "x 2020-11-22 effort:2.0\n"
    "x 2020-11-23 effort:-inf\n"
)
F9 = (
    "x 2020-11-25 effort:+2.0\n"
    "x 2020-11-26 effort:3.\n"
    "x 2020-11-27 effort:-1.5\n"
)
F10 = (
    "x 2020-11-28 effort:2.0\n"
    "x 2020-11-29 effort:nan\n"
)
F11 = (
    "x 2020-11-30 effort:2.0\n"
    "x 2020-12-01 effort:1.2.3\n"
)
F12 = (
    "x 2020-12-02 effort:2.0 due:2020-12-10\n"
    "x 2020-12-03 effort:3.0 due:2020-12-11\n"
)
INVALID_KEY_RECORDS = (
    "unfinished key:9\n"
    "x bad-date key:9\n"
    "x 2099-01-01 key:9\n"
)


# AI-generated code (unreviewed by a human)
class PredictFailure(Exception):
    """Raised by the patched fail() helper during unit tests."""


# AI-generated code (unreviewed by a human)
def _raise_failure(message):
    raise PredictFailure(message)

# AI-generated code (unreviewed by a human)
def load_predict():
    module = types.ModuleType("predict")
    module.__file__ = str(ACTION)
    exec(compile(ACTION.read_text(), str(ACTION), "exec"), module.__dict__)
    return module

predict = load_predict()

# AI-generated code (unreviewed by a human)
DEFAULT_KEY = "effort"


# AI-generated code (unreviewed by a human)
def parse_history_raw(text=DONE_TEXT):
    with (
        patch.object(predict, "TODAY", TEST_DATE),
        patch("builtins.open", mock_open(read_data=text)),
        patch.object(predict.os.path, "isfile", return_value=True),
        patch.object(predict.os, "access", return_value=True),
    ):
        return predict.parse_done("synthetic-done.txt", DEFAULT_KEY)


# AI-generated code (unreviewed by a human)
@lru_cache(maxsize=None)
def parse_history(text=DONE_TEXT):
    with patch.object(predict, "fail", side_effect=_raise_failure):
        return parse_history_raw(text)


# AI-generated code (unreviewed by a human)
@lru_cache(maxsize=None)
def parse_error(text):
    try:
        parse_history(text)
    except AssertionError:
        raise
    except Exception as exc:
        return str(exc)
    raise AssertionError("expected predict to fail")

# AI-generated code (unreviewed by a human)
def simulate_uncached(daily, days, pace):
    results = predict.simulate_probabilities(
        daily, (days,), pace, SIMULATIONS,
        random.Random(predict.RANDOM_SEED),
    )
    return results[days]


# AI-generated code (unreviewed by a human)
@lru_cache(maxsize=None)
def _simulate_cached(daily, days, pace):
    return simulate_uncached(daily, days, pace)


# AI-generated code (unreviewed by a human)
def simulate(daily, days, pace):
    return _simulate_cached(tuple(daily), days, pace)


# AI-generated code (unreviewed by a human)
def report_uncached(pace):
    output = io.StringIO()
    with (
        patch.object(predict, "TODAY", TEST_DATE),
        patch.object(predict, "SIMULATIONS", SIMULATIONS),
        redirect_stdout(output),
    ):
        predict.print_report(parse_history(), pace)
    return output.getvalue()


# AI-generated code (unreviewed by a human)
@lru_cache(maxsize=None)
def report(pace):
    return report_uncached(pace)

# AI-generated code (unreviewed by a human)
def report_rows(text):
    rows = {}
    for line in text.splitlines():
        parts = line.replace("±", "").split()
        if parts and parts[0] in HORIZONS:
            rows[parts[0]] = (
                float(parts[1]),
                float(parts[2].rstrip("%")),
                float(parts[3]),
            )
    return rows


# AI-generated code (unreviewed by a human)
def run_predict_uncached(done_text, *args):
    with tempfile.TemporaryDirectory(prefix="predict-", dir="/tmp/opencode") as temp:
        done_file = Path(temp) / "done.txt"
        done_file.write_text(done_text, encoding="utf-8")
        env = {**os.environ, "DONE_FILE": str(done_file)}
        return subprocess.run(
            [sys.executable, str(ACTION), *args],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )


# AI-generated code (unreviewed by a human)
@lru_cache(maxsize=None)
def run_predict(done_text, *args):
    return run_predict_uncached(done_text, *args)


# AI-generated code (unreviewed by a human)
@lru_cache(maxsize=None)
def report_stats(text):
    stats = {}
    for line in text.splitlines():
        label, separator, value = line.partition(":")
        if not separator:
            continue
        label = label.strip().lower()
        if "block" in label:
            continue
        number = re.search(r"-?\d+(?:\.\d+)?", value)
        if not number:
            continue
        if "average" in label:
            stats["average"] = float(number.group())
        elif "median" in label:
            stats["median"] = float(number.group())
        elif "deviation" in label:
            stats["deviation"] = float(number.group())
        elif "zero" in label:
            stats["zero"] = float(number.group())
        elif "days" in label:
            stats["days"] = float(number.group())
    return stats


# AI-generated code (unreviewed by a human)
def assert_report_stats(result, *, average=None, median=None, deviation=None,
                        zero=None, days=None):
    assert result.returncode == 0, result.stderr
    stats = report_stats(result.stdout)
    checks = (
        ("average", average, 0.01),
        ("median", median, 0.01),
        ("deviation", deviation, 0.01),
        ("zero", zero, 0.1),
        ("days", days, 0.01),
    )
    for name, expected, tolerance in checks:
        if expected is None:
            continue
        assert name in stats, (name, result.stdout)
        assert abs(stats[name] - expected) <= tolerance, (
            name, stats[name], expected
        )


# AI-generated code (unreviewed by a human)
def assert_no_data(result, key):
    output = (result.stdout + result.stderr).lower()
    assert any(
        phrase in output
        for phrase in ("no data", "no observations", "not enough data")
    ), output
    assert key.lower() in output
    assert not report_stats(result.stdout), result.stdout


# AI-generated code (unreviewed by a human)
def assert_error_mentions(message, *words):
    lowered = message.lower()
    assert any(word in lowered for word in words), message


# AI-generated code (unreviewed by a human)
@lru_cache(maxsize=None)
def probability_rows(text):
    rows = {}
    for line in text.splitlines():
        parts = line.replace("±", "").split()
        if not parts or parts[0].rstrip(":") not in HORIZONS:
            continue
        percentages = re.findall(r"(\d+(?:\.\d+)?)%", line)
        if percentages:
            rows[parts[0].rstrip(":")] = float(percentages[0])
    return rows


# AI-generated code (unreviewed by a human)
def assert_probability_report(result, expected=None):
    assert result.returncode == 0, result.stderr
    rows = probability_rows(result.stdout)
    assert set(rows) == set(HORIZONS), result.stdout
    assert all(0.0 <= probability <= 100.0 for probability in rows.values()), rows
    if expected is not None:
        assert all(abs(rows[name] - expected) <= 0.1 for name in HORIZONS), rows
    return rows

# AI-generated code (unreviewed by a human)
def test_history_excludes_dates_without_effort_entries():
    assert parse_history().daily == EFFORT_DAYS


# AI-generated code (unreviewed by a human)
def test_history_total_and_effort_entry_day_count():
    history = parse_history()
    assert (history.total, history.start, history.span) == (
        10.5, date(2026, 11, 12), 3
    )

# AI-generated code (unreviewed by a human)
def test_history_statistics_use_effort_entry_days():
    history = parse_history()
    assert (history.mean, history.median, history.zero_days,
            history.zero_frequency) == (3.5, 3.5, 0, 0.0)

# AI-generated code (unreviewed by a human)
def test_history_population_deviation():
    assert math.isclose(parse_history().stdev, math.sqrt(1 / 6))

# AI-generated code (unreviewed by a human)
def test_same_day_effort_is_aggregated():
    history = parse_history(
        "x 2026-11-21 effort:1.25\nx 2026-11-21 effort:2.5\n"
    )
    assert history.daily == [3.75]

# AI-generated code (unreviewed by a human)
def test_invalid_and_future_records_are_excluded():
    history = parse_history(
        "unfinished effort:9\n"
        "x bad-date effort:9\n"
        "x 2026-11-20 missing-effort\n"
        "x 2026-11-22 effort:9\n"
        "x 2026-11-21 effort:2\n"
    )
    assert history.daily == [2.0]

# AI-generated code (unreviewed by a human)
def test_history_without_valid_effort_is_rejected():
    with patch.object(predict, "fail", side_effect=PredictFailure) as fail:
        try:
            parse_history_raw("x 2026-11-21 no-effort\n")
        except PredictFailure:
            pass
    assert fail.call_args.args == (
        "No data for key 'effort' in done file: synthetic-done.txt",
    )


def test_calendar_horizons():
    assert (
        predict.month_length(TEST_DATE), predict.year_length(TEST_DATE),
        predict.month_length(date(2024, 2, 1)),
        predict.year_length(date(2024, 2, 1)),
    ) == (30, 365, 29, 366)


def test_bootstrap_preserves_contiguous_blocks():
    # Every two-day block alternates, unlike independent daily draws.
    rng = random.Random(0)
    paths = [list(predict.bootstrap_days([0, 10, 0, 10], 4, 2, rng))
             for _ in range(100)]
    assert all(path[i:i + 2] in ([0, 10], [10, 0])
               for path in paths for i in (0, 2))


def test_bootstrap_truncates_final_block():
    assert list(predict.bootstrap_days(
        [2.0] * 7, 10, 7, random.Random(0)
    )) == [2.0] * 10


def test_block_can_start_on_last_historical_day():
    rng = random.Random(0)
    with patch.object(rng, "randrange", return_value=2):
        path = list(predict.bootstrap_days([1.0, 2.0, 3.0], 3, 3, rng))
    assert path == [3.0, 1.0, 2.0]


def test_excess_effort_compensates_for_a_low_effort_day():
    # Both possible circular blocks total 6 over two days.
    assert simulate([0.0, 6.0], 2, 3.0) == (1.0, 0.0)


def test_average_target_can_be_met_after_a_low_effort_day():
    rng = random.Random(0)
    with patch.object(predict, "bootstrap_days", return_value=iter([0, 6, 6])):
        results = predict.simulate_probabilities([0, 6], (1, 2, 3), 3, 1, rng)
    assert results == {1: (0.0, 0.0), 2: (1.0, 0.0), 3: (1.0, 0.0)}


def test_shared_paths_have_known_average_pace_probabilities():
    paths = [iter([3, 0, 6]), iter([3, 3, 0]), iter([3, 3, 3]), iter([0, 6, 6])]
    with patch.object(predict, "bootstrap_days", side_effect=paths):
        results = predict.simulate_probabilities(
            [0, 3, 6], (1, 2, 3), 3, 4, random.Random(0)
        )
    assert [results[days][0] for days in (1, 2, 3)] == [0.75, 0.75, 0.75]


def test_short_history_supports_long_horizons():
    assert simulate([2.0], 365, 2.0) == (1.0, 0.0)


def test_zero_pace_is_certain():
    assert all(simulate(EFFORT_DAYS, days, 0.0) == (1.0, 0.0)
               for days in HORIZONS.values())


def test_constant_effort_meets_equal_target():
    assert simulate([2.0] * 10, 30, 2.0) == (1.0, 0.0)


def test_target_above_every_observation_is_impossible():
    assert simulate(EFFORT_DAYS, 30, 4.1) == (0.0, 0.0)


def test_all_zero_history_has_no_positive_capacity():
    assert simulate([0.0] * 10, 7, 0.1) == (0.0, 0.0)


def test_day_probability_matches_known_frequency():
    # Two of three effort-entry days meet a target of 3.5.
    probability, _ = simulate(EFFORT_DAYS, 1, 3.5)
    assert abs(probability - 2 / 3) < 0.05


def test_probability_and_mc_error_are_bounded():
    results = [simulate(EFFORT_DAYS, days, pace)
               for days in HORIZONS.values() for pace in (0.0, 0.5, 1.5, 4.1)]
    assert all(0 <= p <= 1 and 0 <= error <= 0.5 / math.sqrt(SIMULATIONS)
               for p, error in results)


def test_mc_error_matches_binomial_sampling_error():
    probability, error = simulate(EFFORT_DAYS, 1, 3.5)
    assert math.isclose(
        error, math.sqrt(probability * (1 - probability) / SIMULATIONS)
    )


def test_predictions_are_reproducible():
    assert simulate_uncached(EFFORT_DAYS, 30, 1.0) == simulate_uncached(
        EFFORT_DAYS, 30, 1.0
    )


def test_lower_targets_never_reduce_probability():
    # Resetting the seed compares targets against identical simulated futures.
    ladder = (4.1, 3.5, 3.0, 1.5, 1.0, 0.5, 0.0)
    probabilities = [[simulate(EFFORT_DAYS, days, pace)[0] for pace in ladder]
                     for days in HORIZONS.values()]
    assert all(lower >= higher for values in probabilities
               for higher, lower in zip(values, values[1:]))


def test_discrete_observations_allow_probability_plateaus():
    assert simulate(EFFORT_DAYS, 1, 3.1) == simulate(EFFORT_DAYS, 1, 3.2)


def test_report_covers_all_periods():
    assert set(report_rows(report(1.0))) == set(HORIZONS)


def test_report_target_effort_scales_with_calendar_horizon():
    rows = report_rows(report(1.5))
    assert all(rows[name][0] == 1.5 * days
               for name, days in HORIZONS.items())


def test_report_probabilities_and_errors_match_simulation():
    rows = report_rows(report(1.0))
    rng = random.Random(predict.RANDOM_SEED)
    expected = predict.simulate_probabilities(
        EFFORT_DAYS, HORIZONS.values(), 1.0, SIMULATIONS, rng
    )
    assert all(abs(rows[name][1] - p * 100) <= 0.051
               and abs(rows[name][2] - error * 100) <= 0.0051
               for name, days in HORIZONS.items()
               for p, error in (expected[days],))


def test_zero_pace_report():
    assert set(report_rows(report(0.0)).values()) == {(0.0, 100.0, 0.0)}


def test_report_is_reproducible():
    assert report_uncached(1.0) == report_uncached(1.0)


def test_report_describes_average_pace_and_recorded_days():
    text = report(1.0)
    assert "Effort-entry days:  3" in text
    assert "Extra effort can compensate" in text


def test_direct_execution_help_needs_no_history():
    result = subprocess.run(
        [str(ACTION), "usage"], capture_output=True, text=True,
        env={**os.environ, "DONE_FILE": "/nonexistent/predict-history"},
    )
    assert result.returncode == 0 and "predict" in result.stdout


# AI-generated code (unreviewed by a human)
def test_predict_effort_key_reports_f1_statistics():
    result = run_predict(F1, "effort")
    assert_report_stats(
        result, average=4.0, median=4.0,
        deviation=math.sqrt(2 / 3), zero=0.0, days=3,
    )


# AI-generated code (unreviewed by a human)
def test_predict_physical_exertion_key_reports_f1_statistics():
    result = run_predict(F1, "physical-exertion")
    assert_report_stats(
        result, average=3.0, median=3.0,
        deviation=math.sqrt(1 / 150), zero=0.0, days=3,
    )


# AI-generated code (unreviewed by a human)
def test_predict_pe_key_reports_f1_statistics():
    result = run_predict(F1, "pe")
    assert_report_stats(
        result, average=2.0, median=2.9,
        deviation=math.sqrt(6.02 / 3), zero=100 / 3, days=3,
    )


# AI-generated code (unreviewed by a human)
def test_each_f1_key_keeps_its_own_history():
    expected = {
        "effort": (4.0, 4.0),
        "physical-exertion": (3.0, 3.0),
        "pe": (2.0, 2.9),
    }
    for key, (average, median) in expected.items():
        assert_report_stats(
            run_predict(F1, key), average=average, median=median, days=3
        )


# AI-generated code (unreviewed by a human)
def test_shared_line_values_are_not_merged():
    result = run_predict(F1, "pe")
    assert_report_stats(result, average=2.0, days=3)
    assert abs(report_stats(result.stdout)["average"] - 9.0) > 0.1


# AI-generated code (unreviewed by a human)
def test_same_day_values_aggregate_within_each_key():
    assert_report_stats(
        run_predict(F2, "effort"),
        average=3.0, median=3.0, deviation=0.0, days=1,
    )
    assert_report_stats(
        run_predict(F2, "physical-exertion"),
        average=3.75, median=3.75, deviation=0.0, days=1,
    )


# AI-generated code (unreviewed by a human)
def test_missing_key_reports_no_data():
    assert_no_data(run_predict(F3, "physical-exertion"), "physical-exertion")


# AI-generated code (unreviewed by a human)
def test_key_is_found_regardless_of_token_order():
    result = run_predict("x 2020-11-12 due:2020-12-01 effort:3.0\n", "effort")
    assert_report_stats(result, average=3.0, median=3.0, days=1)


# AI-generated code (unreviewed by a human)
def test_bare_predict_requires_a_key():
    result = run_predict(F1)
    output = (result.stdout + result.stderr).lower()
    assert result.returncode != 0
    assert "historical average" not in output
    assert "effort-entry days" not in output


# AI-generated code (unreviewed by a human)
def test_date_metadata_is_skipped_when_parsing_effort():
    assert parse_history(F12).daily == [2.0, 3.0]


# AI-generated code (unreviewed by a human)
def test_absent_key_reports_no_data():
    assert_no_data(run_predict(F1, "not-present"), "not-present")


# AI-generated code (unreviewed by a human)
def test_repeated_effort_key_is_rejected():
    message = parse_error("x 2020-11-12 effort:2.0 effort:3.0\n")
    assert_error_mentions(message, "duplicate", "repeated")


# AI-generated code (unreviewed by a human)
def test_repeated_custom_key_is_rejected():
    result = run_predict("x 2020-11-12 pe:2.0 pe:3.0\n", "pe")
    output = (result.stdout + result.stderr).lower()
    assert result.returncode != 0
    assert_error_mentions(output, "duplicate", "repeated")


# AI-generated code (unreviewed by a human)
def test_equal_duplicate_values_are_rejected():
    result = run_predict("x 2020-11-12 pe:2.0 pe:2.0\n", "pe")
    output = (result.stdout + result.stderr).lower()
    assert result.returncode != 0
    assert_error_mentions(output, "duplicate", "repeated")


# AI-generated code (unreviewed by a human)
def test_repeated_key_survives_intervening_metadata():
    message = parse_error(
        "x 2020-11-12 effort:2.0 due:2020-12-01 effort:3.0\n"
    )
    assert_error_mentions(message, "duplicate", "repeated")


# AI-generated code (unreviewed by a human)
def test_different_keys_on_one_line_are_not_duplicates():
    assert_report_stats(run_predict(F1, "effort"), average=4.0, days=3)


# AI-generated code (unreviewed by a human)
def test_pace_key_accepts_target_value():
    assert_probability_report(run_predict(F4, "pace", "3.0"), expected=0.0)


# AI-generated code (unreviewed by a human)
def test_pace_metadata_key_is_selectable():
    assert_report_stats(
        run_predict(F4, "pace"),
        average=2.0, median=2.0, deviation=0.0, zero=0.0, days=1,
    )


# AI-generated code (unreviewed by a human)
def test_selected_key_reports_are_deterministic():
    first = run_predict_uncached(F1, "effort")
    second = run_predict_uncached(F1, "effort")
    assert first.returncode == 0
    assert first.stdout == second.stdout


# AI-generated code (unreviewed by a human)
def test_signed_values_are_observations():
    assert parse_history(F5).daily == [-2.0, 0.0, 1.0]


# AI-generated code (unreviewed by a human)
def test_signed_values_are_reported():
    assert_report_stats(
        run_predict(F5, "effort"),
        average=-1 / 3, median=0.0,
        deviation=math.sqrt(14 / 9), zero=100 / 3, days=3,
    )


# AI-generated code (unreviewed by a human)
def test_key_only_on_invalid_records_reports_no_data():
    assert_no_data(run_predict(INVALID_KEY_RECORDS, "key"), "key")


# AI-generated code (unreviewed by a human)
def test_exponent_and_leading_decimal_values_are_parsed():
    assert parse_history(F6).daily == [10.0, 0.5, -0.25]


# AI-generated code (unreviewed by a human)
def test_positive_infinity_is_rejected():
    message = parse_error(F7)
    assert_error_mentions(message, "inf", "infinite")


# AI-generated code (unreviewed by a human)
def test_negative_infinity_is_rejected():
    message = parse_error(F8)
    assert_error_mentions(message, "inf", "infinite")


# AI-generated code (unreviewed by a human)
def test_leading_plus_and_trailing_decimal_values_are_parsed():
    assert parse_history(F9).daily == [2.0, 3.0, -1.5]


# AI-generated code (unreviewed by a human)
def test_nan_is_rejected():
    message = parse_error(F10)
    assert_error_mentions(message, "nan")


# AI-generated code (unreviewed by a human)
def test_malformed_value_is_rejected():
    message = parse_error(F11)
    assert_error_mentions(message, "malformed", "invalid number")


# AI-generated code (unreviewed by a human)
def test_date_metadata_key_reports_no_data():
    assert_no_data(run_predict(F12, "due"), "due")


# AI-generated code (unreviewed by a human)
def test_repeated_key_with_non_numeric_value_is_rejected():
    message = parse_error("x 2020-11-12 effort:2.0 effort:high\n")
    assert_error_mentions(message, "duplicate", "repeated")


# AI-generated code (unreviewed by a human)
def test_target_at_or_below_every_observation_is_certain():
    result = run_predict(F1, "effort", "3.0")
    assert_probability_report(result, expected=100.0)
    assert_report_stats(result, average=4.0, days=3)


# AI-generated code (unreviewed by a human)
def test_target_above_every_observation_is_impossible():
    assert_probability_report(run_predict(F1, "effort", "6.0"), expected=0.0)


# AI-generated code (unreviewed by a human)
def test_target_is_evaluated_only_for_selected_key():
    effort = assert_probability_report(
        run_predict(F1, "effort", "3.0"), expected=100.0
    )
    pe = assert_probability_report(run_predict(F1, "pe", "3.0"))
    assert pe["Day"] < effort["Day"], (pe, effort)


# AI-generated code (unreviewed by a human)
def test_target_uses_same_day_aggregated_history():
    assert_probability_report(run_predict(F2, "effort", "3.0"), expected=100.0)


# AI-generated code (unreviewed by a human)
def test_target_with_missing_key_reports_no_data():
    result = run_predict(F1, "not-present", "3.0")
    assert_no_data(result, "not-present")
    assert not probability_rows(result.stdout)


# AI-generated code (unreviewed by a human)
def test_invalid_target_is_rejected():
    result = run_predict(F1, "effort", "abc")
    output = (result.stdout + result.stderr).lower()
    assert result.returncode != 0
    assert_error_mentions(output, "number", "numeric", "invalid")
    assert not probability_rows(result.stdout)


# AI-generated code (unreviewed by a human)
def test_extra_argument_after_target_is_rejected():
    result = run_predict(F1, "effort", "3.0", "extra")
    output = (result.stdout + result.stderr).lower()
    assert result.returncode != 0
    assert_error_mentions(output, "argument", "usage", "many")
    assert not probability_rows(result.stdout)


# AI-generated code (unreviewed by a human)
def test_nan_target_is_rejected():
    result = run_predict(F1, "effort", "nan")
    output = (result.stdout + result.stderr).lower()
    assert result.returncode != 0
    assert "nan" in output
    assert not probability_rows(result.stdout)


# AI-generated code (unreviewed by a human)
def test_infinite_target_is_rejected():
    result = run_predict(F1, "effort", "inf")
    output = (result.stdout + result.stderr).lower()
    assert result.returncode != 0
    assert_error_mentions(output, "inf", "finite")
    assert not probability_rows(result.stdout)


# AI-generated code (unreviewed by a human)
def test_target_report_is_deterministic():
    first = run_predict_uncached(F1, "effort", "4.0")
    second = run_predict_uncached(F1, "effort", "4.0")
    assert_probability_report(first)
    assert first.stdout == second.stdout


# AI-generated code (unreviewed by a human)
def test_negative_target_is_certain_with_signed_observations():
    assert_probability_report(
        run_predict(F5, "effort", "-3.0"), expected=100.0
    )


# AI-generated code (unreviewed by a human)
def _run_standalone():
    tests = sorted(
        (name, fn) for name, fn in globals().items()
        if name.startswith("test_") and callable(fn)
    )
    failures = []
    for name, test in tests:
        try:
            test()
        except Exception:
            failures.append(name)
            traceback.print_exc()
            print(f"FAIL {name}", file=sys.stderr)
        else:
            print(f"PASS {name}")
    print(f"\n{len(tests) - len(failures)}/{len(tests)} tests passed.")
    return int(bool(failures))

if __name__ == "__main__":
    sys.exit(_run_standalone())
