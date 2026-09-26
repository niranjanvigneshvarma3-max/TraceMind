from app.models import Hypothesis, Investigation, TimelineEvent
from app.providers import build_prompt, restore_ids, validate_citations


def test_unknown_citation_dropped_and_reported():
    answer = Investigation(
        summary="Possibly related", insufficient_evidence=False,
        timeline=[TimelineEvent(event="Deployment", evidence_ids=["known", "invented"])],
        hypotheses=[Hypothesis(title="Config change", explanation="Maybe", supporting_ids=["known", "invented"], contradicting_ids=[])],
        missing_information=[], next_checks=[],
    )
    evidence = [{"id": "known", "document_id": "doc", "locator": "page 1",
                 "source_kind": "pdf_page", "page_num": 1, "source_exists": True}]
    clean, checks = validate_citations(answer, evidence)
    assert checks["citation_reference_valid"] is False
    assert checks["invalid_ids"] == ["invented"]
    assert clean.hypotheses[0].supporting_ids == ["known"]


def test_short_model_ids_restore_to_stable_evidence_ids():
    evidence = [{"id": "uuid-one", "filename": "note.txt", "locator": "text, chunk 1", "content": "retry changed"}]
    assert "[E1]" in build_prompt("What changed?", evidence)
    assert "uuid-one" not in build_prompt("What changed?", evidence)
    answer = Investigation(
        summary="Possible change", insufficient_evidence=True,
        timeline=[TimelineEvent(event="Change", evidence_ids=["E1"])],
        hypotheses=[Hypothesis(title="Retry", explanation="Maybe", supporting_ids=["E1"], contradicting_ids=["E99"])],
        missing_information=[], next_checks=[],
    )
    restored = restore_ids(answer, evidence)
    assert restored.timeline[0].evidence_ids == ["uuid-one"]
    assert restored.hypotheses[0].supporting_ids == ["uuid-one"]
    assert restored.hypotheses[0].contradicting_ids == ["E99"]
