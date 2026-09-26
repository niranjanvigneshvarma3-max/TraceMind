# Evaluation notes

All case material is synthetic. These checks are measured local runs, not claims about real incidents.

## Retrieval

Run `docker compose exec api python -m app.evaluate` after seeding. Five labelled questions identify expected PDF pages, text chunks, or CSV rows. A result is a hit when one of those exact source locations appears in the top five. On one run, keyword had 3/5 questions with a hit, 0.50 source recall@5, and 0.60 MRR@5. Local `all-minilm` vectors and hybrid RRF each had 5/5, 1.00 recall@5, and 1.00 MRR@5. The corpus is too small and clean to infer general superiority.

## Local generator and manual claim audit

The initial `qwen3:1.7b` run used long UUID citation IDs. It took 106.39 seconds and produced valid JSON and 11 resolvable citation references, but two of three hypotheses were poorly supported. One implied a database pool setting had changed even though the deployment note explicitly said it had not. Another treated a disabled response-cache flag as a cause. Those answers are not valid root-cause findings.

Switching the model-facing references to short aliases such as `E1` reduced output length. A later run through the packaged Next.js/FastAPI path took 38.56 seconds, returned two hypotheses, and resolved all 28 references. Manual review found the retry-limit hypothesis plausible as a lead: the deployment note says the limit changed from 2 to 5, errors followed, and the incident note says errors became less frequent after restoration. The sequence is temporal evidence, not proof of causation. The database-pool hypothesis cited three `pool-wait` rows that support its observation, but also cited gateway-timeout rows that do not directly support a pool mechanism. Its wording that pool errors persisted after restoration was not established by the sampled rows. The summary used "due to" even though the cause remained unconfirmed.

The instructions were tightened again to ask for fewer, direct citations and cautious summary wording. This prompt change is a mitigation, not automatic factual validation. Every generated claim still needs a reviewer to open the cited source. The interface keeps an explicit “model draft” warning and shows single-source dependence when repeated rows dominate support.

## Provider comparison status

`docker compose exec api python -m app.cli compare` holds retrieved evidence and instructions fixed for Ollama and OpenAI. It prints answer JSON, generation time, schema validity, and citation-reference validity. Local Ollama is tested. The OpenAI adapter has no successful live request yet because the API key has not been set; no OpenAI output or latency is fabricated. The same manual claim-support audit must be repeated after a key is added locally.
