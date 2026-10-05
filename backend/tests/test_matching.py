"""Тесты ранжирования и объяснимости."""

from __future__ import annotations

from app.services.matching import (
    WEIGHTS,
    CandidateSignals,
    rank_candidates,
    score_candidate,
)


def test_weights_sum_to_one() -> None:
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_full_signals_score_in_unit_range() -> None:
    result = score_candidate(
        CandidateSignals(
            candidate_id="c1",
            test_strength=1.0,
            fsp_achievements=3,
            days_since_last_task=1,
            semantic_fit=1.0,
        )
    )
    # Вклад достижений насыщается асимптотически, поэтому верхняя граница < 1.0
    assert 0.9 <= result.score <= 1.0
    assert not result.missing
    codes = {r.code for r in result.reasons}
    assert {"test_strength", "fsp_achievements", "freshness", "semantic_fit"} <= codes


def test_missing_data_is_not_imputed() -> None:
    """Отсутствующие данные не додумываются: вклад 0 и явный признак."""
    result = score_candidate(CandidateSignals(candidate_id="c2"))
    assert result.score == 0.0
    assert len(result.missing) == 4
    assert not result.reasons


def test_candidate_without_fsp_history_is_handled() -> None:
    """Кандидат без истории ФСП обрабатывается корректно, а не отбрасывается."""
    result = score_candidate(
        CandidateSignals(
            candidate_id="c3",
            test_strength=0.6,
            fsp_achievements=0,
            days_since_last_task=10,
            semantic_fit=0.5,
        )
    )
    fsp = next(r for r in result.reasons if r.code == "fsp_achievements")
    assert fsp.contribution == 0.0
    assert "нет" in fsp.text.lower()
    assert "нет данных о достижениях" not in " ".join(result.missing)
    assert result.score > 0


def test_ranking_is_deterministic_and_sorted() -> None:
    signals = [
        CandidateSignals(candidate_id="b", test_strength=0.9, semantic_fit=0.9),
        CandidateSignals(candidate_id="a", test_strength=0.9, semantic_fit=0.9),
        CandidateSignals(candidate_id="c", test_strength=0.2, semantic_fit=0.2),
    ]
    first = rank_candidates(signals)
    second = rank_candidates(list(reversed(signals)))
    assert [c.candidate_id for c in first] == [c.candidate_id for c in second]
    assert [c.candidate_id for c in first] == ["a", "b", "c"]
    assert first[0].score >= first[-1].score


def test_freshness_degrades_over_time() -> None:
    recent = score_candidate(CandidateSignals("r", days_since_last_task=5))
    old = score_candidate(CandidateSignals("o", days_since_last_task=200))
    assert recent.score > old.score
