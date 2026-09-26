"""Small labelled retrieval check. Labels identify source locations, not model answers."""

import json

from .retrieval import retrieve


LABELS = [
    {"case": "software", "question": "What changed in the deployment retry configuration?",
     "expected": [("deployment_note.pdf", "page 1")]},
    {"case": "software", "question": "What evidence mentions database pool warnings?",
     "expected": [("incident_report.txt", "text"), ("api_log.csv", "CSV row 7")]},
    {"case": "software", "question": "Did gateway timeouts continue after retry revert?",
     "expected": [("incident_report.txt", "text"), ("api_log.csv", "CSV row 14")]},
    {"case": "vehicle", "question": "Which vehicles had rotor runout warnings?",
     "expected": [("test_log.csv", "CSV row 3"), ("test_log.csv", "CSV row 5")]},
    {"case": "vehicle", "question": "Was tire balance measured?",
     "expected": [("inspection_note.txt", "text")]},
]


def matches(item: dict, expected: tuple[str, str]) -> bool:
    return item["filename"] == expected[0] and item["locator"].startswith(expected[1])


def main() -> None:
    results = {}
    for mode in ("keyword", "vector", "hybrid"):
        details = []
        for label in LABELS:
            found = retrieve(label["case"], label["question"], mode, 5)
            ranks = [next((rank for rank, item in enumerate(found, start=1) if matches(item, source)), None)
                     for source in label["expected"]]
            hits = sum(rank is not None for rank in ranks)
            details.append({"question": label["question"], "case": label["case"],
                            "expected": len(ranks), "hits_at_5": hits,
                            "first_relevant_rank": min((rank for rank in ranks if rank is not None), default=None)})
        results[mode] = {
            "hit_questions_at_5": sum(row["hits_at_5"] > 0 for row in details),
            "total_questions": len(details),
            "source_recall_at_5": round(sum(row["hits_at_5"] for row in details)
                                        / sum(row["expected"] for row in details), 3),
            "mrr_at_5": round(sum(1 / row["first_relevant_rank"] if row["first_relevant_rank"] else 0
                                   for row in details) / len(details), 3),
            "details": details,
        }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

