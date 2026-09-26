"""Simple, deterministic evidence support heuristic. Never a probability."""


def rank_hypotheses(hypotheses: list[dict], evidence: list[dict], excluded: set[str] | None = None) -> list[dict]:
    excluded = excluded or set()
    by_id = {item["id"]: item for item in evidence}
    ranked = []
    for hypothesis in hypotheses:
        supporting = [
            evidence_id for evidence_id in hypothesis["supporting_ids"]
            if evidence_id in by_id and evidence_id not in excluded
        ]
        contradicting = [
            evidence_id for evidence_id in hypothesis["contradicting_ids"]
            if evidence_id in by_id and evidence_id not in excluded
        ]
        source_counts: dict[str, int] = {}
        for evidence_id in supporting:
            source = by_id[evidence_id]["document_id"]
            source_counts[source] = source_counts.get(source, 0) + 1
        largest_share = max(source_counts.values(), default=0) / len(supporting) if supporting else 0.0
        ranked.append({
            **hypothesis,
            "score": len(supporting) - len(contradicting),
            "support_count": len(supporting),
            "contradict_count": len(contradicting),
            "largest_source_share": round(largest_share, 2),
            "single_source_dependent": len(supporting) >= 2 and largest_share >= 0.75,
        })
    return sorted(ranked, key=lambda row: (-row["score"], row["title"].casefold()))

