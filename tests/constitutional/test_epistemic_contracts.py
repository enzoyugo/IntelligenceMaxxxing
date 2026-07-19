"""Epistemic contract protections.

OBSERVATION_REQUIRES_AUDIT_ID / RECOMMENDATION_SCHEMA_REQUIRES_AUDIT_ID /
INFERENCE_CANNOT_DEFAULT_TO_FACT / UNKNOWN_REQUIRES_REASON
"""

import pytest
from pydantic import ValidationError

from intelligence_maxxxing.contracts.api.observations import SubmitObservationRequest
from intelligence_maxxxing.domain.beliefs import Belief
from intelligence_maxxxing.domain.common.base import Context, utc_now
from intelligence_maxxxing.domain.common.epistemic import KnowledgeClass, UnknownReason
from intelligence_maxxxing.domain.common.knowledge import KnowledgeObject
from intelligence_maxxxing.domain.observations import Observation
from intelligence_maxxxing.domain.recommendations import Recommendation


def _observation_kwargs() -> dict[str, object]:
    return {
        "id": "obs_" + "0" * 32,
        "schema_version": "1.0",
        "subject": "sleep",
        "statement": "slept",
        "knowledge_class": KnowledgeClass.OBSERVED_FACT,
        "observed_by": "human",
        "context": Context(scope="personal"),
        "created_at": utc_now(),
        "audit_id": "aud_" + "0" * 32,
    }


def test_observation_requires_audit_id() -> None:
    kwargs = _observation_kwargs()
    del kwargs["audit_id"]
    with pytest.raises(ValidationError):
        Observation(**kwargs)  # type: ignore[arg-type]


def test_recommendation_schema_requires_audit_id() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Recommendation(  # type: ignore[call-arg]
            id="rec_" + "0" * 32,
            schema_version="1.0",
            subject="sleep",
            context=Context(scope="personal"),
            created_at=utc_now(),
            statement="sleep earlier",
            explanation="based on nothing yet",
            based_on_belief_ids=("blf_" + "0" * 32,),
        )
    assert any(
        "audit_id" in str(error["loc"]) or "confidence" in str(error["loc"])
        for error in exc_info.value.errors()
    )
    # audit_id specifically must be among the missing required fields
    missing = {error["loc"][0] for error in exc_info.value.errors() if error["type"] == "missing"}
    assert "audit_id" in missing


def test_inference_cannot_default_to_fact() -> None:
    """knowledge_class has no default: nothing becomes a fact silently."""
    assert KnowledgeObject.model_fields["knowledge_class"].is_required()

    # And the public API refuses inferences submitted as observations.
    with pytest.raises(ValidationError):
        SubmitObservationRequest(
            schema_version="1.0",
            subject="sleep",
            statement="user probably sleeps badly",
            knowledge_class=KnowledgeClass.INFERENCE,
            observed_by="app",
            context=Context(scope="personal"),
        )


def test_conclusion_classes_cannot_enter_as_observations() -> None:
    for cls in (
        KnowledgeClass.SUPPORTED_CONCLUSION,
        KnowledgeClass.OPERATIONAL_BELIEF,
        KnowledgeClass.HYPOTHESIS,
        KnowledgeClass.EXPERIMENTAL_RESULT,
    ):
        with pytest.raises(ValidationError):
            SubmitObservationRequest(
                schema_version="1.0",
                subject="sleep",
                statement="smuggled conclusion",
                knowledge_class=cls,
                observed_by="app",
                context=Context(scope="personal"),
            )


def test_unknown_requires_reason() -> None:
    with pytest.raises(ValidationError):
        SubmitObservationRequest(
            schema_version="1.0",
            subject="sleep",
            statement="no idea",
            knowledge_class=KnowledgeClass.UNKNOWN,
            observed_by="app",
            context=Context(scope="personal"),
        )
    # with a reason it is valid
    request = SubmitObservationRequest(
        schema_version="1.0",
        subject="sleep",
        statement="no idea",
        knowledge_class=KnowledgeClass.UNKNOWN,
        unknown_reason=UnknownReason.MISSING_DATA,
        observed_by="app",
        context=Context(scope="personal"),
    )
    assert request.unknown_reason is UnknownReason.MISSING_DATA


def test_belief_cannot_downgrade_its_class() -> None:
    with pytest.raises(ValidationError):
        Belief(  # type: ignore[call-arg]
            id="blf_" + "0" * 32,
            schema_version="1.0",
            subject="sleep",
            statement="early sleep helps",
            knowledge_class=KnowledgeClass.OBSERVED_FACT,
            context=Context(scope="personal"),
            created_at=utc_now(),
            audit_id="aud_" + "0" * 32,
            confidence={"explanation": "test"},
            supporting_evidence_ids=("evd_" + "0" * 32,),
            revalidation_policy="review monthly",
        )
