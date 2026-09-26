"""Seed synthetic cases and compare generators against fixed retrieval."""

import argparse
import json
from pathlib import Path

import pymupdf

from .db import connection, ensure_case, init_schema
from .ingest import ingest_file
from .providers import get_provider, validate_citations
from .retrieval import retrieve


SAMPLES = Path(__file__).resolve().parents[1] / "samples"


def pdf_from_text(text: str) -> bytes:
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_textbox(pymupdf.Rect(50, 50, 545, 790), text, fontsize=11)
    return pdf.tobytes()


def seed() -> None:
    init_schema()
    examples = [
        ("software", "Software incident", "Synthetic API errors after a deployment.", [
            ("deployment_note.pdf", pdf_from_text((SAMPLES / "software" / "deployment_note.txt").read_text())),
            ("incident_report.txt", (SAMPLES / "software" / "incident_report.txt").read_bytes()),
            ("api_log.csv", (SAMPLES / "software" / "api_log.csv").read_bytes()),
        ]),
        ("vehicle", "Vehicle inspection", "Synthetic brake vibration investigation.", [
            ("inspection_note.txt", (SAMPLES / "vehicle" / "inspection_note.txt").read_bytes()),
            ("test_log.csv", (SAMPLES / "vehicle" / "test_log.csv").read_bytes()),
        ]),
    ]
    for case_id, title, description, files in examples:
        ensure_case(case_id, title, description, True)
        for filename, raw in files:
            with connection() as conn:
                existing = conn.execute(
                    "SELECT stored_path FROM documents WHERE case_id = %s AND filename = %s", (case_id, filename)
                ).fetchone()
            # A seed created on the host may point at a path absent inside Docker.
            # Re-ingest only that sample so source links work in the running app.
            if not existing or not Path(existing["stored_path"]).is_file():
                result = ingest_file(case_id, filename, raw, True)
                print(f"Seeded {case_id}: {filename} ({result['evidence_count']} evidence items)")


def compare(case_id: str, question: str) -> None:
    evidence = retrieve(case_id, question, "hybrid")
    print(f"Fixed retrieval: {len(evidence)} evidence items")
    for name in ("ollama", "openai"):
        try:
            answer, seconds = get_provider(name).generate(question, evidence)
            clean, validity = validate_citations(answer, evidence)
            print(json.dumps({"provider": name, "generation_seconds": round(seconds, 2),
                              **validity, "answer": clean.model_dump()}, indent=2))
        except Exception as exc:
            print(json.dumps({"provider": name, "verified": False,
                              "error": f"{type(exc).__name__}: {exc}"}, indent=2))
    print("Manual claim-support review is required; valid IDs alone do not prove support.")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed")
    comparison = sub.add_parser("compare")
    comparison.add_argument("--case", default="software")
    comparison.add_argument("--question", default="Why did API errors increase after deployment?")
    args = parser.parse_args()
    if args.command == "seed":
        seed()
    else:
        compare(args.case, args.question)


if __name__ == "__main__":
    main()
