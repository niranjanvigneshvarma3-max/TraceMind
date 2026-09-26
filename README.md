# TraceMind

TraceMind is a small evidence investigation workspace. It retrieves source passages, asks a model for **hypotheses**, and lets a reviewer remove individual evidence items to see how a simple ranking changes. The included software and vehicle cases are **synthetic**. They are not Mahindra or other private company records.

Companion repositories: [Retrieval Benchmark](https://github.com/niranjanvigneshvarma3-max/Retrieval-Benchmark) isolates labelled search evaluation; [Evidence Stress-Test Engine](https://github.com/niranjanvigneshvarma3-max/Evidence-Stress-Test-Engine) isolates citation validation and ranking changes. They reuse ideas from this app and are explicitly documented as companion exercises.

## What the app does

- Upload PDF, UTF-8 text, or CSV files to a private workspace.
- Keep PDF page and CSV row locations so citations can open the source.
- Retrieve evidence using PostgreSQL full-text search, local embeddings, or their reciprocal-rank fusion.
- Generate one shared Pydantic output shape through Ollama or the official OpenAI Python SDK.
- Validate cited IDs and stored locations; then show supporting and contradicting evidence for each hypothesis.
- Toggle evidence in the browser. The score is `active supporting items - active contradicting items`; no second model call happens.
- Warn when most supporting items come from one source. These scores are **heuristic evidence support**, not probabilities or causal proof.

A citation's existence is not proof that it supports the claim. Manual claim-to-source review is part of evaluation.

## Architecture

```text
Browser / Next.js evidence board
            |
            | /api (same-origin proxy)
            v
FastAPI: upload, retrieval, citation validation, generation
   |                      |                     |
   v                      v                     v
Postgres + pgvector   native Ollama       optional OpenAI API
   |
   v
Docker volume for DB; separate volume for uploaded files
```

The backend modules are intentionally small: `ingest.py` extracts traceable evidence, `retrieval.py` searches, `providers.py` generates and validates, and `stress.py` scores. `api.py` exposes these operations. The Next.js page recalculates the same scoring rule locally when evidence is toggled.

## Run locally on an M3 Mac

Requirements: Docker Desktop, Ollama, Node 22 for frontend development, and Python 3.11+ for backend development. Docker Compose can run the packaged app without local Node/Python installs.

1. Copy `.env.example` to `.env`. Replace `POSTGRES_PASSWORD`, `DEMO_CODE`, and `ADMIN_CODE` with different long random values. Keep `.env` private. Set `OPENAI_API_KEY` only if you already have usable API credits; never commit or paste the key into a chat.
2. Run `ollama pull all-minilm` and `ollama pull qwen3:1.7b`. The same embedding model must be used for indexing and querying. Changing it requires a database reindex.
3. Start Docker Desktop and Ollama. Run `docker compose up --build -d --wait`.
4. Run `docker compose exec api python -m app.cli seed`. This creates two clearly labelled synthetic cases.
5. Open `http://localhost:3000`, enter your local `DEMO_CODE`, and ask the suggested software or vehicle question. The `ADMIN_CODE` also enables private uploads.

Ollama runs natively for Apple GPU access. The API container reaches it through `host.docker.internal`. The local generator is `qwen3:1.7b`, an open-weight model published under Apache 2.0; the local 384-dimensional embedder is `all-minilm`. Their model pages are [Qwen3 1.7B](https://ollama.com/library/qwen3:1.7b) and [all-minilm](https://ollama.com/library/all-minilm). The OpenAI adapter uses the official Python SDK and `gpt-4o-mini` by default; API use may consume credits and is unverified until a real request succeeds with a local key.

## Useful commands

| Task | Command |
| --- | --- |
| Build and start | `docker compose up --build -d --wait` |
| Inspect containers | `docker compose ps` |
| Follow API logs | `docker compose logs -f api` |
| Stop containers, retain data | `docker compose down` |
| Update after a code change | `git pull && docker compose up --build -d --wait` |
| Compare generators with fixed retrieval | `docker compose exec api python -m app.cli compare` |
| Run backend tests | `cd backend && .venv/bin/python -m pytest -q` |
| Build frontend | `cd frontend && npm run build` |

Do not use `docker compose down -v` during normal work: `-v` removes the database and upload volumes.

### Database backup and restore

Create a backup file on the host:

```sh
docker compose exec -T db pg_dump -U tracemind -d tracemind -Fc > tracemind.dump
```

Restore only when you intentionally want to replace database contents. Stop API writes first, keep a second backup, then run:

```sh
docker compose exec -T db pg_restore -U tracemind -d tracemind --clean --if-exists < tracemind.dump
```

Uploaded source files live in the separate `uploads_data` Docker volume; back up that volume separately before moving hosts. A database dump alone does not include the uploaded files.

## Public demo access

The app is designed to expose **only the Next.js port** through a temporary HTTPS tunnel. `cloudflared tunnel --url http://localhost:3000` gives a random `trycloudflare.com` URL for testing. This URL is temporary, and the demo works only while the Mac, Docker, Ollama, internet, and tunnel are running. Quick Tunnels do not support SSE, so this app uses ordinary HTTP requests. Share the demo code privately with reviewers. Only the admin code can see private uploads. Database and model ports are not routed through the tunnel.

The API limits upload size to 5 MB, PDFs to 20 pages, CSVs to 200 rows, and model requests to five per minute per incoming IP. This is a limited interview demo, not a multi-user production service.

## Evaluation and limitations

Measured on the included five-question, synthetic labelled set with top five results (one local run):

| Retrieval | Questions with a hit | Source recall@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| PostgreSQL keyword | 3/5 | 0.50 | 0.60 |
| all-minilm vector | 5/5 | 1.00 | 1.00 |
| Hybrid RRF | 5/5 | 1.00 | 1.00 |

These tiny synthetic numbers show the evaluation method, not general search superiority. Reproduce with `docker compose exec api python -m app.evaluate` after seeding.

A local `qwen3:1.7b` investigation through the packaged web/API path took **38.56 seconds** in one measured run. Its JSON parsed against the shared schema and all 28 cited references resolved to stored source locations. Manual review still found weak claim-to-source matches: rows with gateway timeouts were cited as support for a database-pool hypothesis, and a summary used causal wording despite the source stating the cause was unconfirmed. The UI labels model output as a draft; citation-reference validity is a structural check only. See [evaluation notes](docs/evaluation.md) for the claim audit. OpenAI generation is unverified while `OPENAI_API_KEY` is unset.

Limitations: scanned PDFs need OCR; CSV summaries cover row counts and selected category counts only; small local models can omit or misread evidence; valid citation IDs do not establish factual support; the ranking ignores evidence reliability beyond a visible single-source warning; rate limiting is in memory; uploads are single-admin rather than separate user accounts.

For a three-minute walkthrough and simple design answers, read [the interview guide](docs/interview-guide.md).

## Docker terms

An **image** is the packaged app or database. A **container** is one running instance of an image. A **volume** stores data beyond container recreation. **Docker Compose** describes how the containers and volumes start together. **Hosting** means keeping the running app reachable from another network; a Compose file alone does not host it.
