import inspect

from app.matching import agent
from app.matching.agent import Candidate, match_lawyers


def c(id, areas, city="Delhi", fee=1000, hearing=5000, hours=12, years=5):
    return Candidate(id, city, "", frozenset(areas), fee, hearing, hours, years)


def test_area_fit_is_required_when_specialists_exist():
    out = match_lawyers("Criminal", "Delhi", 100000, [c("a", {"Criminal"}), c("b", {"Family"})], set())
    assert [m.lawyer_id for m in out] == ["a"]


def test_reasons_recorded_for_every_match():
    out = match_lawyers("Criminal", "Delhi", 100000, [c("a", {"Criminal"}, years=12, hours=3)], {"a"})
    assert out[0].reasons == ["Verified Criminal practice", "Based in Delhi", "Handled a closely related, verified case",
                              "12 years of practice", "Indicative fee fits your budget", "Usually replies within 3h"]


def test_indicative_fee_estimate():
    out = match_lawyers("Criminal", "", 0, [c("a", {"Criminal"}, fee=1000, hearing=5000)], set())
    assert out[0].estimate == (1000 + 5000 * 2, 1000 + 5000 * 6)


def test_no_outcome_or_rating_based_ranking():
    # The matcher cannot see ratings, win rates or personal attributes: they are not inputs at all.
    params = set(inspect.signature(Candidate).parameters)
    assert not params & {"rating", "reviews", "success_rate", "gender", "religion", "caste", "age"}
    assert "guarantee" in agent.DISCLAIMER


def test_scores_bounded():
    out = match_lawyers("Criminal", "Delhi", 10**9, [c("a", {"Criminal"}, years=40, hours=1)], {"a"})
    assert 5 <= out[0].score <= 97
