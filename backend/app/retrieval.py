"""Postgres full-text + vector retrieval with reciprocal rank fusion."""

import numpy as np
from pathlib import Path

from .db import connection
from .ingest import embed_texts


SELECT_FIELDS = """SELECT e.id, e.document_id, e.locator, e.content, e.source_kind,
                          e.page_num, e.row_num, e.row_end, d.filename, d.stored_path
                   FROM evidence e JOIN documents d ON d.id = e.document_id"""


def retrieve(case_id: str, question: str, mode: str = "hybrid", limit: int = 12) -> list[dict]:
    if mode not in {"hybrid", "keyword", "vector"}:
        raise ValueError("Invalid retrieval mode")
    ranked_lists: list[list[dict]] = []
    with connection() as conn:
        if mode in {"hybrid", "keyword"}:
            rows = conn.execute(
                SELECT_FIELDS + """ WHERE d.case_id = %s
                AND to_tsvector('english', e.content) @@ plainto_tsquery('english', %s)
                ORDER BY ts_rank_cd(to_tsvector('english', e.content),
                         plainto_tsquery('english', %s)) DESC LIMIT 24""",
                (case_id, question, question),
            ).fetchall()
            ranked_lists.append(rows)
        if mode in {"hybrid", "vector"}:
            vector = embed_texts([question])[0]
            rows = conn.execute(
                SELECT_FIELDS + " WHERE d.case_id = %s ORDER BY e.embedding <=> %s LIMIT 24",
                (case_id, np.asarray(vector, dtype=np.float32)),
            ).fetchall()
            ranked_lists.append(rows)
    scores: dict[str, float] = {}
    items: dict[str, dict] = {}
    for rows in ranked_lists:
        for rank, row in enumerate(rows, start=1):
            key = str(row["id"])
            scores[key] = scores.get(key, 0) + 1 / (60 + rank)
            items[key] = {key_: (str(value) if key_ in {"id", "document_id"} else value)
                          for key_, value in row.items() if key_ != "stored_path"}
            items[key]["source_exists"] = Path(row["stored_path"]).is_file()
    ordered = sorted(items, key=lambda key: (-scores[key], key))[:limit]
    return [{**items[key], "retrieval_score": round(scores[key], 6)} for key in ordered]
