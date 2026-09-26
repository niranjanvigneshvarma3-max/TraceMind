# TraceMind interview guide

## Three-minute demo

1. **0:00–0:30 — Problem.** “Incident reports and logs can disagree. TraceMind gathers source passages and proposes hypotheses while keeping each claim inspectable.” State that both included cases are synthetic.
2. **0:30–1:05 — Input and retrieval.** Select the software case and ask why API errors increased. Explain that PDFs become page-labelled chunks, CSV rows keep row numbers, and text chunks keep source labels. PostgreSQL full-text search and `all-minilm` vectors are fused with reciprocal rank fusion.
3. **1:05–1:45 — Investigation.** Show the timeline, two hypotheses, missing information, and source links. Open a PDF page and a CSV row. Explain that Pydantic checks the output shape and code checks that cited IDs and locations exist. Explicitly say that this cannot prove semantic support.
4. **1:45–2:25 — Stress test.** Exclude a supporting item. The score `active support - active contradiction` and order update immediately without another model call. Show remaining contradictions and the single-source warning. The score is a heuristic, not a probability.
5. **2:25–3:00 — Tradeoffs.** Ollama runs on the M3 without API cost. The OpenAI adapter uses the same schema but needs an API key and real credits. Docker Compose runs web, API, and persistent Postgres; only the web port goes through the temporary tunnel. Mention that manual claim review caught model errors.

## Questions and concise answers

**Why hybrid retrieval?** Keyword search finds exact terms; vectors can retrieve paraphrases. RRF combines their ranks without pretending the scores are calibrated alike. On this five-question synthetic set, hybrid reached all five labelled questions, while keyword reached three. That small test does not prove general performance.

**Why pgvector?** The source records and embeddings stay in one Postgres database. This reduces moving parts for a student-scale application; it is not a claim that pgvector is always fastest.

**Why local Ollama on the host?** The M3's GPU accelerates inference. Docker containers reach it through `host.docker.internal`, while the model port is not exposed through the public tunnel.

**What does citation validation actually check?** It checks cited IDs were retrieved and their stored files/pages/rows exist. A human still checks whether those words support the model's claim.

**Why is the stress-test score simple?** It is understandable, deterministic, and updates instantly in the browser. It ignores evidence reliability and independence beyond a visible source-dependence warning, so it cannot be read as a probability.

**How are CSV numbers handled?** Python/pandas computes row counts and selected category counts during ingestion. The model only sees those stored, traceable summaries; it never executes generated analysis code.

**What happens when evidence is insufficient?** The schema has an explicit `insufficient_evidence` field plus missing information and next checks. The model may still make unsupported claims, so the interface warns that its output is a draft.

**How is private data protected in this demo?** A demo code permits sample-case access; a separate admin code is required for private uploads. Only the web port is tunneled. Request and upload limits reduce casual abuse. This is intentionally a small demo, not production authentication.

**What survives a restart?** Postgres and uploaded source files are on separate named Docker volumes. `docker compose down` retains them. A database dump alone does not include uploaded files.

**What would you improve next?** Add human-reviewed claim labels, evidence independence weighting, OCR for scanned PDFs, per-user auth, and stronger operational limits before any real-world use.

## Your understanding check

Pick one hypothesis and explain: which cited item supports it, which item weakens it, and why its score can change without calling the model again. If a citation exists but does not support the wording, say so plainly.
