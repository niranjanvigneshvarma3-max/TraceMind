from app.stress import rank_hypotheses


def test_excluding_support_changes_rank_without_generation():
    evidence = [
        {"id": "a", "document_id": "report"},
        {"id": "b", "document_id": "log"},
        {"id": "c", "document_id": "log"},
        {"id": "d", "document_id": "report"},
    ]
    hypotheses = [
        {"title": "Retry change", "supporting_ids": ["a", "b", "d"], "contradicting_ids": ["c"]},
        {"title": "Gateway issue", "supporting_ids": ["c"], "contradicting_ids": []},
    ]
    before = rank_hypotheses(hypotheses, evidence)
    after = rank_hypotheses(hypotheses, evidence, {"a", "b", "d"})
    assert before[0]["title"] == "Retry change"
    assert after[0]["title"] == "Gateway issue"
    assert after[1]["support_count"] == 0
    assert after[1]["contradict_count"] == 1


def test_source_dependence_is_visible():
    evidence = [{"id": "a", "document_id": "same"}, {"id": "b", "document_id": "same"}]
    hypothesis = [{"title": "One source", "supporting_ids": ["a", "b"], "contradicting_ids": []}]
    ranked = rank_hypotheses(hypothesis, evidence)
    assert ranked[0]["single_source_dependent"] is True
    assert ranked[0]["largest_source_share"] == 1.0
