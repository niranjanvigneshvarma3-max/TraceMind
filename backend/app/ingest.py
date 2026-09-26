"""Controlled ingestion. Source locations are stored before generation."""

import io
import re
import uuid
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pymupdf

from .config import settings
from .db import connection


MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGES = 20
MAX_CSV_ROWS = 200
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".csv"}


def _text_chunks(text: str, label: str, page_num: int | None = None) -> list[dict]:
    clean = re.sub(r"\s+", " ", text).strip()
    chunks = []
    start = 0
    while start < len(clean):
        end = min(start + 700, len(clean))
        if end < len(clean):
            boundary = clean.rfind(" ", start + 450, end)
            if boundary > start:
                end = boundary
        chunk = clean[start:end].strip()
        if chunk:
            number = len(chunks) + 1
            chunks.append({
                "locator": f"{label}, chunk {number}",
                "content": chunk,
                "source_kind": "pdf_page" if page_num else "text_chunk",
                "page_num": page_num,
                "row_num": None,
                "row_end": None,
            })
        start = end
    return chunks


def extract_evidence(filename: str, raw: bytes) -> list[dict]:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Only PDF, TXT, and CSV files are supported")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError("Upload exceeds 5 MB")
    if suffix == ".txt":
        text = raw.decode("utf-8-sig")
        chunks = _text_chunks(text, "text")
        if not chunks:
            raise ValueError("Text file has no content")
        return chunks
    if suffix == ".pdf":
        with pymupdf.open(stream=raw, filetype="pdf") as pdf:
            if len(pdf) > MAX_PDF_PAGES:
                raise ValueError("PDF exceeds 20 pages")
            result = []
            for index, page in enumerate(pdf):
                result.extend(_text_chunks(page.get_text(), f"page {index + 1}", index + 1))
            if not result:
                raise ValueError("PDF has no extractable text; scanned PDFs need OCR")
            return result
    frame = pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False, nrows=MAX_CSV_ROWS + 1)
    if len(frame) > MAX_CSV_ROWS:
        raise ValueError("CSV exceeds 200 data rows")
    if len(frame.columns) > 30:
        raise ValueError("CSV exceeds 30 columns")
    rows = []
    for index, row in frame.iterrows():
        fields = "; ".join(f"{name}: {str(value)[:100]}" for name, value in row.items())
        rows.append({
            "locator": f"CSV row {index + 2}",
            "content": fields[:700],
            "source_kind": "csv_row",
            "page_num": None,
            "row_num": int(index + 2),
            "row_end": int(index + 2),
        })
    if frame.empty:
        raise ValueError("CSV has no data rows")
    # These are Python/pandas calculations. The LLM never runs code or invents aggregates.
    summaries = [f"Calculated row count: {len(frame)} data rows."]
    for column in frame.columns:
        if column.lower() in {"status", "result", "phase", "component", "error_type"}:
            counts = frame[column].value_counts().head(8)
            summaries.append(f"{column} counts: " + ", ".join(f"{value}={count}" for value, count in counts.items()))
    rows.append({
        "locator": f"CSV rows 2-{len(frame) + 1}, calculated summary",
        "content": " ".join(summaries)[:700],
        "source_kind": "csv_summary",
        "page_num": None,
        "row_num": 2,
        "row_end": len(frame) + 1,
    })
    return rows


def embed_texts(texts: list[str]) -> list[np.ndarray]:
    vectors: list[np.ndarray] = []
    with httpx.Client(timeout=120) as client:
        for start in range(0, len(texts), 24):
            response = client.post(
                f"{settings.ollama_url}/api/embed",
                json={"model": settings.embedding_model, "input": texts[start:start + 24]},
            )
            response.raise_for_status()
            batch = response.json()["embeddings"]
            for vector in batch:
                if len(vector) != 384:
                    raise ValueError("Embedding model must produce 384 dimensions; reindex on model change")
                vectors.append(np.asarray(vector, dtype=np.float32))
    return vectors


def ingest_file(case_id: str, filename: str, raw: bytes, is_sample: bool = False) -> dict:
    safe_name = Path(filename).name
    evidence = extract_evidence(safe_name, raw)
    vectors = embed_texts([item["content"] for item in evidence])
    doc_id = uuid.uuid5(uuid.NAMESPACE_URL, f"tracemind:{case_id}:{safe_name}")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    stored_path = settings.upload_dir / f"{doc_id}{Path(safe_name).suffix.lower()}"
    stored_path.write_bytes(raw)
    with connection() as conn:
        conn.execute(
            """INSERT INTO documents(id, case_id, filename, mime_type, stored_path, is_sample)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (case_id, filename) DO UPDATE SET
                 mime_type = EXCLUDED.mime_type, stored_path = EXCLUDED.stored_path,
                 is_sample = EXCLUDED.is_sample""",
            (doc_id, case_id, safe_name,
             {".pdf": "application/pdf", ".txt": "text/plain", ".csv": "text/csv"}[Path(safe_name).suffix.lower()],
             str(stored_path), is_sample),
        )
        conn.execute("DELETE FROM evidence WHERE document_id = %s", (doc_id,))
        for item, vector in zip(evidence, vectors, strict=True):
            evidence_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}:{item['locator']}:{item['content']}")
            conn.execute(
                """INSERT INTO evidence(id, document_id, locator, content, source_kind,
                       page_num, row_num, row_end, embedding)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (evidence_id, doc_id, item["locator"], item["content"], item["source_kind"],
                 item["page_num"], item["row_num"], item["row_end"], vector),
            )
    return {"document_id": str(doc_id), "filename": safe_name, "evidence_count": len(evidence)}
