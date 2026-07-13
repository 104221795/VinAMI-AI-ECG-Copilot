"""Golden tests for every transparent demonstration reasoning pathway."""

from vinami.reasoning.domain.engine import (
    ClinicalReasoningEngine,
    Pathway,
    ReasoningInput,
    RuleSpecification,
)


def _data(**changes: object) -> ReasoningInput:
    values = dict(
        symptoms={},
        vitals={},
        ecg_quality_acceptable=True,
        ai_findings={},
        physician_ecg_findings={},
        troponin_ratios=(0.5,),
        risk_scores={},
        unresolved_alerts=0,
        arrival_minutes=10,
    )
    values.update(changes)
    return ReasoningInput(**values)


def test_golden_pathways_and_conflict() -> None:
    engine = ClinicalReasoningEngine()
    spec = RuleSpecification("demo-v1")
    assert (
        engine.evaluate(spec, _data(physician_ecg_findings={"stemi_review": True})).pathway
        is Pathway.STEMI_REVIEW_PATHWAY
    )
    assert (
        engine.evaluate(spec, _data(unresolved_alerts=1)).pathway is Pathway.VERY_HIGH_RISK_REVIEW
    )
    assert (
        engine.evaluate(spec, _data(troponin_ratios=(0.5, 1.2))).pathway is Pathway.HIGH_RISK_REVIEW
    )
    assert engine.evaluate(spec, _data(troponin_ratios=(1.2,))).pathway is Pathway.OBSERVATION
    assert engine.evaluate(spec, _data()).pathway is Pathway.RULE_OUT_CANDIDATE_REVIEW
    assert (
        engine.evaluate(spec, _data(symptoms={"alternative_diagnosis": True})).pathway
        is Pathway.ALTERNATIVE_DIAGNOSIS_REVIEW
    )
    assert (
        engine.evaluate(spec, _data(ecg_quality_acceptable=None)).pathway
        is Pathway.INSUFFICIENT_DATA
    )
    assert engine.evaluate(
        spec, _data(ai_findings={"stemi": 1}, physician_ecg_findings={"no_stemi": True})
    ).conflicts
