from collections import defaultdict, deque
from pathlib import Path
import os
import secrets
import time

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .config import settings
from .db import connection, ensure_case, get_case, init_schema
from .ingest import MAX_UPLOAD_BYTES, ingest_file
from .models import InvestigateRequest
from .providers import get_provider, validate_citations
from .retrieval import retrieve
from .stress import rank_hypotheses


app = FastAPI(title="TraceMind", version="0.1.0")
rate_windows: dict[str, deque[float]] = defaultdict(deque)


@app.on_event("startup")
def start() -> None:
    init_schema()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    ensure_case("private", "Private uploads", "Only the admin code can access this case.", False)


def access_role(
    x_demo_code: str = Header(default=""), x_admin_code: str = Header(default="")
) -> str:
    if settings.admin_code and secrets.compare_digest(x_admin_code, settings.admin_code):
        return "admin"
    if settings.demo_code and secrets.compare_digest(x_demo_code, settings.demo_code):
        return "demo"
    raise HTTPException(401, "Enter a valid demo code")


def allow_case(case_id: str, role: str) -> dict:
    case = get_case(case_id)
    if not case or (not case["is_sample"] and role != "admin"):
        raise HTTPException(404, "Case not found")
    return case


def limit_expensive(request: Request, action: str, max_calls: int = 5) -> None:
    key = f"{request.client.host if request.client else 'unknown'}:{action}"
    now = time.monotonic()
    window = rate_windows[key]
    while window and window[0] <= now - 60:
        window.popleft()
    if len(window) >= max_calls:
        raise HTTPException(429, "Too many requests; retry in a minute")
    window.append(now)


@app.get("/api/health")
def health() -> dict:
    with connection() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}


@app.get("/api/cases")
def cases(role: str = Depends(access_role)) -> list[dict]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT id, title, description, is_sample FROM cases WHERE is_sample OR %s = 'admin' ORDER BY is_sample DESC, id",
            (role,),
        ).fetchall()
    return rows


@app.post("/api/investigate")
def investigate(body: InvestigateRequest, request: Request, role: str = Depends(access_role)) -> dict:
    allow_case(body.case_id, role)
    limit_expensive(request, "investigate")
    if body.provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(503, "OpenAI adapter is configured but no API key is set")
    try:
        evidence = retrieve(body.case_id, body.question, body.retrieval_mode)
        if not evidence:
            return {
                "answer": {"summary": "No matching evidence was retrieved.", "insufficient_evidence": True,
                           "timeline": [], "hypotheses": [], "missing_information": ["Relevant source evidence"],
                           "next_checks": ["Upload or select more relevant documents."]},
                "evidence": [], "ranked_hypotheses": [],
                "metrics": {"provider": body.provider, "retrieval_mode": body.retrieval_mode,
                            "generation_seconds": 0, "schema_valid": True, "citation_reference_valid": True,
                            "references_checked": 0, "invalid_ids": []},
            }
        answer, seconds = get_provider(body.provider).generate(body.question, evidence)
        answer, validity = validate_citations(answer, evidence)
    except (ValueError, KeyError) as exc:
        raise HTTPException(502, f"Generation failed validation: {exc}") from exc
    except Exception as exc:
        raise HTTPException(503, f"Model or embedding service unavailable: {type(exc).__name__}") from exc
    data = answer.model_dump()
    return {
        "answer": data,
        "evidence": evidence,
        "ranked_hypotheses": rank_hypotheses(data["hypotheses"], evidence),
        "metrics": {"provider": body.provider, "retrieval_mode": body.retrieval_mode,
                    "generation_seconds": round(seconds, 2), **validity},
    }


@app.get("/api/evidence/{evidence_id}")
def evidence_detail(evidence_id: str, role: str = Depends(access_role)) -> dict:
    with connection() as conn:
        row = conn.execute(
            """SELECT e.id, e.document_id, e.locator, e.content, e.source_kind,
                      e.page_num, e.row_num, e.row_end, d.filename, d.case_id
               FROM evidence e JOIN documents d ON d.id = e.document_id WHERE e.id::text = %s""",
            (evidence_id,),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Evidence not found")
    allow_case(row["case_id"], role)
    return {key: str(value) if key in {"id", "document_id"} else value for key, value in row.items()}


@app.get("/api/documents/{document_id}/file")
def document_file(document_id: str, role: str = Depends(access_role)):
    with connection() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id::text = %s", (document_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Document not found")
    allow_case(row["case_id"], role)
    path = Path(row["stored_path"])
    if not path.is_file():
        raise HTTPException(404, "Stored file missing")
    return FileResponse(path, media_type=row["mime_type"], filename=row["filename"],
                        content_disposition_type="inline")


@app.post("/api/upload")
async def upload(request: Request, file: UploadFile = File(...), role: str = Depends(access_role)) -> dict:
    if role != "admin":
        raise HTTPException(403, "Uploads require the private admin code")
    limit_expensive(request, "upload", 10)
    with connection() as conn:
        count = conn.execute("SELECT count(*) AS n FROM documents WHERE case_id = 'private'").fetchone()["n"]
    if count >= 20:
        raise HTTPException(413, "Private workspace is limited to 20 documents")
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        return ingest_file("private", file.filename or "upload", raw)
    except (UnicodeError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc

