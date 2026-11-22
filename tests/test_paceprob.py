"""Executable specification for the `paceprob` todo.sh action (actions/paceprob).

Scenarios describe the expected behavior of the pace/maintainability model.
Run with:

    cd ~/.todo
    python -m pytest tests/test_paceprob.py -v     # pytest runner
    python tests/test_paceprob.py                 # standalone runner (same checks)

Status (2026-11-21): the user reports the spec suite fails; expected to be
revisited when the behavior is adjusted (see S7: a pace of 0 or 0.0 should
give a P of 100% for all periods).

Determinism: the model is exercised through synthetic histories written to a
temporary directory and through direct function calls with fixed inputs. No
real task data, network access, or current-date dependence is involved.

Assumptions:

1. "A pace below the posterior" means pace < lam, where lam = alpha / beta is
   the posterior mean daily rate. This is the tool's default target: main()
   sets `pace = lam` when no pace is given.
2. "Maintainable" is the probability returned by
   maintained_prob(alpha, beta, days, pace, tol): the probability that the
   realized effort V over `days` days falls inside the band
   [pace * days * (1 - tol), pace * days * (1 + tol)], where V is the
   negative-binomial marginal of the Poisson-Gamma model.
3. The encoded behavior for paces below the posterior:
   maintained_prob(..., p, ...) >= maintained_prob(..., lam, ...) for every
   p < lam on the Day horizon (days = 1). The user's "MORE likely to be
   maintainable, not less" is expressed as this not-less (>=) form; if the
   intended property is strictly greater for every pace below the posterior,
   tighten `>=` to `>` in S2 after the behavior has been adjusted.
4. Synthetic posterior: alpha = 1 + 10.5, beta = 1 + 6, i.e. a history of
   three completions (effort 3.0, 3.5, 4.0) spanning 2026-11-12..2026-11-17.
   This history is fixed so the spec is deterministic; no real data is read.
5. Report scenarios pin `paceprob.TODAY` to date(2026, 11, 21) for
   determinism (Month horizon = 30 days; 2026 is not a leap year, so the
   Year horizon = 365 days).
6. The "pace below the posterior is at least as likely to be maintained as
   the posterior" requirement (S2) is asserted for the Day horizon. It is
   not asserted for the other periods; whether it should be extended there
   is an open question.
7. A pace of 0, 0.0 or -0.0 gives a P of 100% for all periods:
   maintained_prob(alpha, beta, horizon, pace, tol) ~ 1.0 for pace in
   (0, 0.0, -0.0) and horizon in {1, 7, month_length(TODAY),
   year_length(TODAY)}, and print_report(alpha, beta, 0.0, tol) reports
   P(maintain) = 100.0% for the Day, Week, Month and Year rows. Note:
   main() currently rejects a pace of 0 ("Pace must be > 0."); the spec
   asserts the model/report level behavior.

Scenarios:

S1  test_posterior_derivation_from_done_history
    parse_done() maps a done file to (total effort, span days); posterior()
    maps that to Gamma(1 + total, 1 + span).

S2  test_pace_below_posterior_is_at_least_as_likely_as_posterior
    Any pace below the posterior is at least as likely to be maintained as
    the posterior pace: maintained_prob(p) >= maintained_prob(lam) for
    p in PACE_FRACTIONS * lam on the Day horizon (days = 1).

S3  test_maintainability_probability_is_bounded
    maintained_prob returns a probability in [0, 1] for the checked paces.

S4  test_posterior_mean_matches_gamma_mean
    The posterior rate equals the Gamma mean alpha / beta.

S5  test_pace_below_posterior_is_more_likely_than_the_posterior
    A pace strictly below the posterior is strictly more likely to be
    maintained: maintained_prob(0.75 * lam) > maintained_prob(lam).

S6  test_period_column_semantics
    The Period column is explicit: Day = probability of maintaining the
    pace for one day, Week for one week, Month for the current month,
    Year for the current year. Each row reports
    maintained_prob(alpha, beta, horizon, pace, tol) with horizon = 1, 7,
    month_length(TODAY), year_length(TODAY); the Target velocity column is
    pace * horizon.

S7  test_pace_of_zero_gives_hundred_percent_maintain
    A pace of 0 or 0.0 gives a P of 100% for all periods:
    maintained_prob(alpha, beta, horizon, pace, tol) ~ 1.0 for pace in
    (0, 0.0, -0.0) and horizon in {1, 7, month_length(TODAY),
    year_length(TODAY)}; print_report(alpha, beta, 0.0, tol) reports
    P(maintain) = 100.0% for the Day, Week, Month and Year rows.
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

# Synthetic done history: completions of effort 3.0 + 3.5 + 4.0 = 10.5 on
# 2026-11-12, 2026-11-13 and 2026-11-17 -> span 6 days, posterior mean 11.5/7.
SYNTHETIC_DONE_LINES = (
    "x 2026-11-12 effort:3.0\n",
    "x 2026-11-13 effort:3.5\n",
    "x 2026-11-17 effort:4.0\n",
)
SYNTHETIC_TOTAL_EFFORT = 10.5
SYNTHETIC_SPAN_DAYS = 6

# Fractions of the posterior mean used as "paces below the posterior".
PACE_FRACTIONS = (0.0, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99)

# Fraction whose maintained probability is asserted strictly greater than at
# the posterior (S5), with the assumption that the current behavior satisfies
# it (hand check: P_maintain(0.75 * lam) ~ 0.31 > P_maintain(lam) = 0).
STRICT_FRAC = 0.75


def load_paceprob():
    """Load the extension-less ``actions/paceprob`` script as a module."""
    path = ACTIONS_DIR / "paceprob"
    module = types.ModuleType("paceprob")
    module.__file__ = str(path)
    code = compile(path.read_text(encoding="utf-8"), str(path), "exec")
    exec(code, module.__dict__)
    return module


paceprob = load_paceprob()


def synthetic_posterior():
    """Return (alpha, beta) of the posterior for the synthetic history."""
    return paceprob.posterior(SYNTHETIC_TOTAL_EFFORT, SYNTHETIC_SPAN_DAYS)


def maintained_at(alpha, beta, days, pace):
    """maintained_prob() at the default tolerance."""
    return paceprob.maintained_prob(alpha, beta, days, pace, paceprob.DEFAULT_TOL)


# --- S1 --------------------------------------------------------------------


def test_posterior_derivation_from_done_history():
    """S1: parse_done + posterior map a done file to Gamma(1 + total, 1 + span)."""
    with tempfile.TemporaryDirectory() as tmp:
        done = Path(tmp) / "done.txt"
        done.write_text("".join(SYNTHETIC_DONE_LINES), encoding="utf-8")
        total, span = paceprob.parse_done(str(done))
    assert total == SYNTHETIC_TOTAL_EFFORT
    assert span == SYNTHETIC_SPAN_DAYS
    alpha, beta = paceprob.posterior(total, span)
    assert alpha == 1 + SYNTHETIC_TOTAL_EFFORT
    assert beta == 1 + SYNTHETIC_SPAN_DAYS


# --- S2 --------------------------------------------------------------------


def test_pace_below_posterior_is_at_least_as_likely_as_posterior():
    """S2: any pace below the posterior is at least as likely to be maintained.

    For every p in PACE_FRACTIONS * lam:
    maintained_prob(alpha, beta, 1, p, DEFAULT_TOL) >=
    maintained_prob(alpha, beta, 1, lam, DEFAULT_TOL).
    """
    alpha, beta = synthetic_posterior()
    lam = alpha / beta
    p_at_posterior = maintained_at(alpha, beta, 1, lam)
    for frac in PACE_FRACTIONS:
        pace = lam * frac
        p_pace = maintained_at(alpha, beta, 1, pace)
        assert p_pace >= p_at_posterior, (
            f"pace={pace:.4f} (lam={lam:.4f}): "
            f"P_maintain={p_pace:.6f} < P_maintain(lam)={p_at_posterior:.6f}"
        )


# --- S3 --------------------------------------------------------------------


def test_maintainability_probability_is_bounded():
    """S3: maintained_prob returns a probability in [0, 1] at the checked paces."""
    alpha, beta = synthetic_posterior()
    lam = alpha / beta
    for frac in PACE_FRACTIONS:
        p = maintained_at(alpha, beta, 1, lam * frac)
        assert 0.0 <= p <= 1.0


# --- S4 --------------------------------------------------------------------


def test_posterior_mean_matches_gamma_mean():
    """S4: the posterior rate is the Gamma mean, alpha / beta."""
    alpha, beta = synthetic_posterior()
    lam = alpha / beta
    assert lam == (1 + SYNTHETIC_TOTAL_EFFORT) / (1 + SYNTHETIC_SPAN_DAYS)


# --- S5 --------------------------------------------------------------------


def test_pace_below_posterior_is_more_likely_than_the_posterior():
    """S5: a pace strictly below the posterior is strictly more likely.

    maintained_prob(alpha, beta, 1, STRICT_FRAC * lam, DEFAULT_TOL) >
    maintained_prob(alpha, beta, 1, lam, DEFAULT_TOL).
    """
    alpha, beta = synthetic_posterior()
    lam = alpha / beta
    p_at_posterior = maintained_at(alpha, beta, 1, lam)
    p_pace = maintained_at(alpha, beta, 1, STRICT_FRAC * lam)
    assert p_pace > p_at_posterior, (
        f"pace={STRICT_FRAC * lam:.4f} (lam={lam:.4f}): "
        f"P_maintain={p_pace:.6f} <= P_maintain(lam)={p_at_posterior:.6f}"
    )


# --- S6 --------------------------------------------------------------------


def test_period_column_semantics():
    """S6: Period column semantics.

    Day is the probability of maintaining the pace for one day, Week for
    one week, Month for the current month, and Year for the current year.
    Each row reports maintained_prob(alpha, beta, horizon, pace, tol) with
    horizon = 1, 7, month_length(TODAY), year_length(TODAY); the Target
    velocity column is pace * horizon.
    """
    paceprob.TODAY = date(2026, 11, 21)
    alpha, beta = synthetic_posterior()
    lam = alpha / beta

    expected_horizons = {
        "Day": 1,
        "Week": 7,
        "Month": paceprob.month_length(paceprob.TODAY),
        "Year": paceprob.year_length(paceprob.TODAY),
    }

    buf = io.StringIO()
    with redirect_stdout(buf):
        paceprob.print_report(alpha, beta, lam, paceprob.DEFAULT_TOL)

    rows = {}
    for line in buf.getvalue().splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] in expected_horizons:
            rows[parts[0]] = (float(parts[1]), float(parts[2].rstrip("%")))

    assert set(rows) == set(expected_horizons), f"parsed rows: {sorted(rows)}"
    for name, (target, pct) in sorted(rows.items()):
        horizon = expected_horizons[name]
        assert math.isclose(target, lam * horizon, rel_tol=0.0, abs_tol=0.01), (
            f"{name}: target velocity {target} != pace {lam} * horizon {horizon}"
        )
        expected_pct = maintained_at(alpha, beta, horizon, lam) * 100.0
        assert math.isclose(pct, expected_pct, rel_tol=0.0, abs_tol=0.06), (
            f"{name}: P(maintain) {pct} != maintained_prob over "
            f"{horizon} day(s) ({expected_pct})"
        )


# --- S7 --------------------------------------------------------------------


def test_pace_of_zero_gives_hundred_percent_maintain():
    """S7: a pace of 0 or 0.0 gives a P of 100% for all periods.

    For each horizon in {1, 7, month_length(TODAY), year_length(TODAY)}:
    maintained_prob(alpha, beta, horizon, pace, tol) ~ 1.0 for
    pace in (0, 0.0, -0.0). Via the report: print_report(alpha, beta,
    0.0, tol) reports P(maintain) = 100.0% for the Day, Week, Month and
    Year rows.
    """
    paceprob.TODAY = date(2026, 11, 21)
    alpha, beta = synthetic_posterior()
    tol = paceprob.DEFAULT_TOL
    horizons = (
        1,
        7,
        paceprob.month_length(paceprob.TODAY),
        paceprob.year_length(paceprob.TODAY),
    )
    for days in horizons:
        for pace in (0, 0.0, -0.0):
            p = maintained_at(alpha, beta, days, pace)
            assert math.isclose(p, 1.0, rel_tol=0.0, abs_tol=0.01), (
                f"days={days} pace={pace}: P_maintain={p}, expected ~1.0"
            )

    buf = io.StringIO()
    with redirect_stdout(buf):
        paceprob.print_report(alpha, beta, 0.0, tol)
    rows = {}
    for line in buf.getvalue().splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] in {"Day", "Week", "Month", "Year"}:
            rows[parts[0]] = (float(parts[1]), float(parts[2].rstrip("%")))
    assert set(rows) == {"Day", "Week", "Month", "Year"}, f"parsed rows: {sorted(rows)}"
    for name, (target, pct) in sorted(rows.items()):
        assert math.isclose(target, 0.0, rel_tol=0.0, abs_tol=0.01), (
            f"{name}: target velocity {target}, expected 0.0"
        )
        assert math.isclose(pct, 100.0, rel_tol=0.0, abs_tol=0.11), (
            f"{name}: P(maintain)={pct}, expected 100.0"
        )


# --- Standalone runner (no third-party packages needed) -------------------


def _run_standalone():
    scenarios = sorted(
        (name, fn)
        for name, fn in globals().items()
        if name.startswith("test_") and callable(fn)
    )
    failures = []
    for name, fn in scenarios:
        try:
            fn()
        except AssertionError:
            failures.append(name)
            print(f"FAIL {name}", file=sys.stderr)
        else:
            print(f"PASS {name}")
    if failures:
        print(
            f"\n{len(failures)} of {len(scenarios)} scenario(s) failed: "
            f"{', '.join(failures)}",
            file=sys.stderr,
        )
        return 1
    print(f"\nAll {len(scenarios)} scenario(s) passed.")
    return 0


if __name__ == "__main__":
    sys.exit(_run_standalone())
