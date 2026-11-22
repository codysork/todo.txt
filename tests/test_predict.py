"""Executable specification for the bootstrap-based `predict` action.

Run with pytest or `python tests/test_predict.py`. Histories, dates and random
seeds are fixed; no real task data is read.
"""

import io
import math
import os
import random
import subprocess
import sys
import traceback
import types
from contextlib import redirect_stdout
from datetime import date
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


def load_predict():
    module = types.ModuleType("predict")
    module.__file__ = str(ACTION)
    exec(compile(ACTION.read_text(), str(ACTION), "exec"), module.__dict__)
    return module


predict = load_predict()


def parse_history(text=DONE_TEXT):
    with (
        patch.object(predict, "TODAY", TEST_DATE),
        patch("builtins.open", mock_open(read_data=text)),
        patch.object(predict.os.path, "isfile", return_value=True),
        patch.object(predict.os, "access", return_value=True),
    ):
        return predict.parse_done("synthetic-done.txt")


def simulate(daily, days, pace):
    return predict.simulate_probability(
        daily, days, pace, SIMULATIONS, random.Random(predict.RANDOM_SEED)
    )


def report(pace):
    output = io.StringIO()
    with (
        patch.object(predict, "TODAY", TEST_DATE),
        patch.object(predict, "SIMULATIONS", SIMULATIONS),
        redirect_stdout(output),
    ):
        predict.print_report(parse_history(), pace)
    return output.getvalue()


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


def test_history_excludes_dates_without_effort_entries():
    assert parse_history().daily == EFFORT_DAYS


def test_history_total_and_effort_entry_day_count():
    history = parse_history()
    assert (history.total, history.start, history.span) == (
        10.5, date(2026, 11, 12), 3
    )


def test_history_statistics_use_effort_entry_days():
    history = parse_history()
    assert (history.mean, history.median, history.zero_days,
            history.zero_frequency) == (3.5, 3.5, 0, 0.0)


def test_history_population_deviation():
    assert math.isclose(parse_history().stdev, math.sqrt(1 / 6))


def test_same_day_effort_is_aggregated():
    history = parse_history(
        "x 2026-11-21 effort:1.25\nx 2026-11-21 effort:2.5\n"
    )
    assert history.daily == [3.75]


def test_invalid_and_future_records_are_excluded():
    history = parse_history(
        "unfinished effort:9\n"
        "x bad-date effort:9\n"
        "x 2026-11-20 missing-effort\n"
        "x 2026-11-20 effort:-1\n"
        "x 2026-11-20 effort:bad effort:9\n"
        "x 2026-11-22 effort:9\n"
        "x 2026-11-21 effort:2 effort:9\n"
    )
    assert history.daily == [2.0]


def test_history_without_valid_effort_is_rejected():
    with patch.object(predict, "fail", side_effect=ValueError) as fail:
        try:
            parse_history("x 2026-11-21 no-effort\n")
        except ValueError:
            pass
    assert fail.call_args.args == (
        "No valid effort records found in done file: synthetic-done.txt",
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
    assert simulate(EFFORT_DAYS, 30, 1.0) == simulate(EFFORT_DAYS, 30, 1.0)


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
    assert report(1.0) == report(1.0)


def test_report_describes_average_pace_and_recorded_days():
    text = report(1.0)
    assert "Effort-entry days:  3" in text
    assert "Extra effort can compensate" in text


def test_direct_execution_help_needs_no_history():
    result = subprocess.run(
        [str(ACTION), "usage"], capture_output=True, text=True,
        env={**os.environ, "DONE_FILE": "/nonexistent/predict-history"},
    )
    assert result.returncode == 0 and "predict pace" in result.stdout


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
