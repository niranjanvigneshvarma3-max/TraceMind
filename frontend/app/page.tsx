"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type Case = { id: string; title: string; description: string; is_sample: boolean };
type Evidence = {
  id: string; document_id: string; filename: string; locator: string; content: string;
  source_kind: string; page_num: number | null; row_num: number | null; row_end: number | null;
};
type Hypothesis = { title: string; explanation: string; supporting_ids: string[]; contradicting_ids: string[] };
type Answer = {
  summary: string; insufficient_evidence: boolean;
  timeline: { event: string; evidence_ids: string[] }[];
  hypotheses: Hypothesis[]; missing_information: string[]; next_checks: string[];
};
type Result = {
  answer: Answer; evidence: Evidence[];
  metrics: { provider: string; retrieval_mode: string; generation_seconds: number;
    schema_valid: boolean; citation_reference_valid: boolean; invalid_ids: string[] };
};
type Ranked = Hypothesis & { score: number; support: number; contradict: number; sourceShare: number; changes: string[] };

const questions: Record<string, string> = {
  software: "Why did API errors increase after deployment?",
  vehicle: "What could explain brake vibration in the prototype batch?",
};

function accessHeaders(code: string): Record<string, string> {
  return { "X-Demo-Code": code, "X-Admin-Code": code };
}

export default function Home() {
  const [code, setCode] = useState("");
  const [entered, setEntered] = useState(false);
  const [cases, setCases] = useState<Case[]>([]);
  const [caseId, setCaseId] = useState("software");
  const [question, setQuestion] = useState(questions.software);
  const [provider, setProvider] = useState("ollama");
  const [mode, setMode] = useState("hybrid");
  const [result, setResult] = useState<Result | null>(null);
  const [excluded, setExcluded] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<Evidence | null>(null);
  const [sourceText, setSourceText] = useState("");
  const [pdfUrl, setPdfUrl] = useState("");
  const pdfRef = useRef("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  useEffect(() => {
    const saved = sessionStorage.getItem("tracemind-code");
    if (saved) { setCode(saved); void loadCases(saved); }
    return () => { if (pdfRef.current) URL.revokeObjectURL(pdfRef.current); };
  }, []);

  async function loadCases(accessCode: string) {
    try {
      const response = await fetch("/api/cases", { headers: accessHeaders(accessCode) });
      if (!response.ok) throw new Error("Access code invalid or API unavailable");
      const data = await response.json() as Case[];
      setCases(data);
      setEntered(true);
      setMessage("");
      sessionStorage.setItem("tracemind-code", accessCode);
    } catch (error) { setMessage((error as Error).message); setEntered(false); }
  }

  function chooseCase(id: string) {
    setCaseId(id);
    setQuestion(questions[id] ?? "What does the evidence show?");
    setResult(null); setSelected(null); setExcluded(new Set());
  }

  async function investigate() {
    setBusy(true); setMessage(""); setResult(null); setSelected(null); setExcluded(new Set());
    try {
      const response = await fetch("/api/investigate", {
        method: "POST",
        headers: { ...accessHeaders(code), "Content-Type": "application/json" },
        body: JSON.stringify({ case_id: caseId, question, provider, retrieval_mode: mode }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Investigation failed");
      setResult(data as Result);
    } catch (error) { setMessage((error as Error).message); }
    finally { setBusy(false); }
  }

  async function upload() {
    if (!uploadFile) return;
    setBusy(true); setMessage("");
    try {
      const form = new FormData(); form.append("file", uploadFile);
      const response = await fetch("/api/upload", { method: "POST", headers: accessHeaders(code), body: form });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Upload failed");
      setMessage(`Uploaded ${data.filename}: ${data.evidence_count} cited evidence items.`);
      setUploadFile(null); chooseCase("private");
    } catch (error) { setMessage((error as Error).message); }
    finally { setBusy(false); }
  }

  async function openEvidence(item: Evidence) {
    setSelected(item); setSourceText(""); setPdfUrl("");
    if (pdfRef.current) { URL.revokeObjectURL(pdfRef.current); pdfRef.current = ""; }
    try {
      const response = await fetch(`/api/documents/${item.document_id}/file`, { headers: accessHeaders(code) });
      if (!response.ok) throw new Error("Source file unavailable");
      if (item.filename.toLowerCase().endsWith(".pdf")) {
        const url = URL.createObjectURL(await response.blob());
        pdfRef.current = url;
        setPdfUrl(`${url}#page=${item.page_num ?? 1}`);
      } else {
        setSourceText(await response.text());
      }
    } catch (error) { setSourceText((error as Error).message); }
  }

  function toggle(id: string) {
    setExcluded(previous => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  const byId = useMemo(() => new Map(result?.evidence.map(item => [item.id, item]) ?? []), [result]);
  const ranked = useMemo<Ranked[]>(() => {
    if (!result) return [];
    return result.answer.hypotheses.map(hypothesis => {
      const supports = hypothesis.supporting_ids.filter(id => byId.has(id) && !excluded.has(id));
      const contradicts = hypothesis.contradicting_ids.filter(id => byId.has(id) && !excluded.has(id));
      const counts = new Map<string, number>();
      supports.forEach(id => { const source = byId.get(id)!.document_id; counts.set(source, (counts.get(source) ?? 0) + 1); });
      const largest = Math.max(0, ...counts.values());
      const changes = [...excluded].filter(id => hypothesis.supporting_ids.includes(id) || hypothesis.contradicting_ids.includes(id));
      return { ...hypothesis, score: supports.length - contradicts.length,
        support: supports.length, contradict: contradicts.length,
        sourceShare: supports.length ? largest / supports.length : 0, changes };
    }).sort((a, b) => b.score - a.score || a.title.localeCompare(b.title));
  }, [result, byId, excluded]);

  const currentCase = cases.find(item => item.id === caseId);
  const isAdmin = cases.some(item => item.id === "private");
  const lines = sourceText.split(/\r?\n/);

  function citation(id: string) {
    const item = byId.get(id);
    if (!item) return null;
    return <button key={id} onClick={() => void openEvidence(item)}
      className="rounded-md border border-teal-400/30 bg-teal-400/10 px-2 py-1 text-xs text-teal-200 hover:bg-teal-400/20">
      {item.filename} · {item.locator}
    </button>;
  }

  return <main className="min-h-screen bg-[#07131b] text-slate-100">
    <header className="border-b border-white/10 bg-[#0b1d27]">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-5">
        <div><div className="text-xs font-bold uppercase tracking-[0.3em] text-teal-300">TraceMind</div>
          <h1 className="mt-1 text-xl font-semibold">Evidence investigation workspace</h1></div>
        <span className="rounded-full border border-amber-300/30 px-3 py-1 text-xs text-amber-200">Synthetic demo data</span>
      </div>
    </header>

    {!entered ? <section className="mx-auto mt-20 max-w-md rounded-2xl border border-white/10 bg-white/5 p-7 shadow-2xl">
      <h2 className="text-2xl font-semibold">Open the evidence board</h2>
      <p className="mt-3 text-sm leading-6 text-slate-300">Enter the demo access code from the project owner. This limits expensive model calls and protects private uploads.</p>
      <label className="mt-7 block text-sm text-slate-300">Access code
        <input value={code} onChange={event => setCode(event.target.value)} type="password" autoComplete="off"
          className="mt-2 w-full rounded-lg border border-white/20 bg-[#07131b] px-4 py-3 text-white" />
      </label>
      <button onClick={() => void loadCases(code)} className="mt-4 w-full rounded-lg bg-teal-300 px-4 py-3 font-semibold text-slate-950 hover:bg-teal-200">Enter workspace</button>
      {message && <p className="mt-4 text-sm text-rose-300">{message}</p>}
    </section> : <div className="mx-auto grid max-w-7xl gap-6 px-5 py-7 lg:grid-cols-[280px_minmax(0,1fr)]">
      <aside className="space-y-5">
        <div className="rounded-xl border border-white/10 bg-white/5 p-5">
          <div className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-400">Case files</div>
          <div className="space-y-2">{cases.map(item => <button key={item.id} onClick={() => chooseCase(item.id)}
            className={`w-full rounded-lg border p-3 text-left text-sm ${caseId === item.id ? "border-teal-300 bg-teal-300/10" : "border-white/10 hover:bg-white/5"}`}>
            <span className="block font-semibold">{item.title}</span><span className="mt-1 block text-xs text-slate-400">{item.description}</span>
          </button>)}</div>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/5 p-5 text-sm leading-6 text-slate-300">
          <div className="mb-2 text-xs font-bold uppercase tracking-widest text-slate-400">How to read this board</div>
          <p>Rank = supporting items − contradicting items. Toggle evidence to recalculate immediately. Scores are heuristic support, never probabilities or causal proof.</p>
        </div>
        {isAdmin && <div className="rounded-xl border border-white/10 bg-white/5 p-5">
          <div className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-400">Private upload</div>
          <input type="file" accept=".pdf,.txt,.csv" onChange={event => setUploadFile(event.target.files?.[0] ?? null)} className="w-full text-xs" />
          <button disabled={!uploadFile || busy} onClick={() => void upload()} className="mt-3 rounded-lg bg-slate-200 px-3 py-2 text-sm font-semibold text-slate-900 disabled:opacity-50">Upload file</button>
          <p className="mt-2 text-xs text-slate-400">Admin only · PDF, TXT, CSV · max 5 MB</p>
        </div>}
        <button onClick={() => { sessionStorage.removeItem("tracemind-code"); setEntered(false); setCode(""); setResult(null); }} className="text-xs text-slate-400 underline">Leave workspace</button>
      </aside>

      <section className="min-w-0 space-y-6">
        <div className="rounded-2xl border border-white/10 bg-white/5 p-5 md:p-7">
          <div className="text-xs font-bold uppercase tracking-widest text-teal-300">{currentCase?.title ?? "Investigation"}</div>
          <h2 className="mt-2 text-2xl font-semibold">Ask a question of the evidence</h2>
          <textarea value={question} onChange={event => setQuestion(event.target.value)} rows={3}
            className="mt-5 w-full rounded-lg border border-white/20 bg-[#081922] p-4 text-sm leading-6 text-white" />
          <div className="mt-4 flex flex-wrap items-end gap-3">
            <label className="text-xs text-slate-300">Generator<select value={provider} onChange={event => setProvider(event.target.value)} className="mt-1 block rounded-lg border border-white/20 bg-[#081922] px-3 py-2 text-sm"><option value="ollama">Local Ollama</option><option value="openai">OpenAI mini</option></select></label>
            <label className="text-xs text-slate-300">Retrieval<select value={mode} onChange={event => setMode(event.target.value)} className="mt-1 block rounded-lg border border-white/20 bg-[#081922] px-3 py-2 text-sm"><option value="hybrid">Hybrid</option><option value="keyword">Keyword</option><option value="vector">Vector</option></select></label>
            <button disabled={busy || question.trim().length < 5} onClick={() => void investigate()} className="rounded-lg bg-teal-300 px-5 py-2.5 text-sm font-bold text-slate-950 hover:bg-teal-200 disabled:opacity-50">{busy ? "Investigating…" : "Investigate"}</button>
          </div>
          {message && <p className="mt-4 rounded-lg border border-rose-400/30 bg-rose-400/10 p-3 text-sm text-rose-200">{message}</p>}
        </div>

        {result && <>
          <div className="rounded-xl border border-white/10 bg-[#102631] p-5">
            <div className="flex flex-wrap items-center gap-3"><h2 className="text-xl font-semibold">Investigation summary</h2>
              <span className="rounded-full bg-sky-300/15 px-3 py-1 text-xs text-sky-200">Model draft · claim support unverified</span>
              {result.answer.insufficient_evidence && <span className="rounded-full bg-amber-300/15 px-3 py-1 text-xs text-amber-200">Insufficient evidence</span>}</div>
            <p className="mt-3 leading-7 text-slate-200">{result.answer.summary}</p>
            <p className="mt-4 text-xs text-slate-400">{result.metrics.provider} · {result.metrics.retrieval_mode} retrieval · {result.metrics.generation_seconds}s generation · schema {result.metrics.schema_valid ? "valid" : "invalid"} · citation IDs {result.metrics.citation_reference_valid ? "valid" : "invalid"}</p>
          </div>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_310px]">
            <div className="space-y-4"><div className="flex items-center justify-between gap-3"><h2 className="text-xl font-semibold">Evidence stress test</h2><div className="flex items-center gap-3"><span className="text-xs text-slate-400">{excluded.size} excluded</span><button disabled={!excluded.size} onClick={() => setExcluded(new Set())} className="rounded-md border border-white/20 px-2 py-1 text-xs text-slate-200 disabled:cursor-not-allowed disabled:opacity-40">Restore all</button></div></div>
              {ranked.length ? ranked.map((item, index) => <article key={item.title} className="rounded-xl border border-white/10 bg-white/5 p-5">
                <div className="flex flex-wrap items-start justify-between gap-3"><div><span className="text-xs font-bold uppercase tracking-widest text-teal-300">Rank {index + 1}</span><h3 className="mt-1 text-lg font-semibold">{item.title}</h3></div><div className="rounded-lg bg-[#07131b] px-3 py-2 text-center"><div className="text-xl font-bold text-teal-200">{item.score}</div><div className="text-[10px] uppercase text-slate-400">support score</div></div></div>
                <p className="mt-3 text-sm leading-6 text-slate-300">{item.explanation}</p>
                <div className="mt-4 flex flex-wrap gap-2 text-xs"><span className="rounded-full bg-emerald-400/10 px-3 py-1 text-emerald-200">{item.support} supporting</span><span className="rounded-full bg-rose-400/10 px-3 py-1 text-rose-200">{item.contradict} contradicting</span>
                  {item.support >= 2 && item.sourceShare >= .75 && <span className="rounded-full bg-amber-400/10 px-3 py-1 text-amber-200">Depends on one source ({Math.round(item.sourceShare * 100)}%)</span>}</div>
                <div className="mt-4 space-y-3"><div><div className="mb-2 text-xs font-semibold text-emerald-200">SUPPORT</div><div className="flex flex-wrap gap-2">{item.supporting_ids.map(citation)}</div></div>
                  <div><div className="mb-2 text-xs font-semibold text-rose-200">CONTRADICTIONS</div><div className="flex flex-wrap gap-2">{item.contradicting_ids.length ? item.contradicting_ids.map(citation) : <span className="text-xs text-slate-500">None cited</span>}</div></div></div>
                {item.changes.length > 0 && <p className="mt-4 border-t border-white/10 pt-3 text-xs text-amber-200">Score changed by excluded evidence: {item.changes.map(id => byId.get(id)?.locator ?? id).join(", ")}</p>}
              </article>) : <p className="rounded-xl border border-amber-300/20 bg-amber-300/5 p-5 text-sm text-amber-200">No supported hypothesis can be shown from this evidence.</p>}
            </div>
            <div className="space-y-4"><h2 className="text-xl font-semibold">Timeline</h2>
              <div className="rounded-xl border border-white/10 bg-white/5 p-5">{result.answer.timeline.length ? result.answer.timeline.map((event, index) => <div key={index} className="border-l border-teal-400/40 pb-5 pl-4 last:pb-0"><p className="text-sm leading-6">{event.event}</p><div className="mt-2 flex flex-wrap gap-1">{event.evidence_ids.map(citation)}</div></div>) : <p className="text-sm text-slate-400">No cited timeline available.</p>}</div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-5"><h3 className="font-semibold">Missing information</h3><ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-300">{result.answer.missing_information.map((item, index) => <li key={index}>{item}</li>)}</ul></div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-5"><h3 className="font-semibold">Useful next checks</h3><ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-300">{result.answer.next_checks.map((item, index) => <li key={index}>{item}</li>)}</ul></div>
            </div>
          </div>

          <div><h2 className="text-xl font-semibold">Retrieved evidence</h2><p className="mt-1 text-sm text-slate-400">Exclude an item to recalculate rankings instantly, without another model call.</p>
            <div className="mt-4 grid gap-3 md:grid-cols-2">{result.evidence.map(item => <article key={item.id} className={`rounded-xl border p-4 ${excluded.has(item.id) ? "border-white/5 bg-white/[.02] opacity-55" : "border-white/10 bg-white/5"}`}>
              <div className="flex items-start gap-3"><input type="checkbox" checked={!excluded.has(item.id)} onChange={() => toggle(item.id)} aria-label={`Include ${item.filename} ${item.locator}`} className="mt-1 accent-teal-300" />
                <div className="min-w-0"><button onClick={() => void openEvidence(item)} className="text-left text-xs font-semibold text-teal-200 underline underline-offset-2">{item.filename} · {item.locator}</button><p className="mt-2 text-sm leading-6 text-slate-300">{item.content}</p></div></div>
            </article>)}</div></div>

          <p className="rounded-lg border border-amber-300/20 bg-amber-300/5 p-4 text-xs leading-5 text-amber-100">A citation existing at the stated page or CSV row does not prove it supports the generated claim. Manually inspect claim-to-source support before trusting a conclusion.</p>
        </>}
      </section>
    </div>}

    {selected && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-3" role="dialog" aria-modal="true" aria-label="Evidence source">
      <div className="flex max-h-[90vh] w-full max-w-4xl flex-col rounded-xl border border-white/20 bg-[#0c202b] p-5 shadow-2xl">
        <div className="flex items-start justify-between gap-4"><div><div className="text-xs uppercase tracking-widest text-teal-300">Source location</div><h2 className="mt-1 text-lg font-semibold">{selected.filename} · {selected.locator}</h2></div><button onClick={() => setSelected(null)} className="rounded-lg border border-white/20 px-3 py-1 text-sm">Close</button></div>
        <p className="my-3 rounded-lg bg-teal-300/10 p-3 text-sm text-teal-100">Cited item: {selected.content}</p>
        {pdfUrl ? <iframe title="PDF source page" src={pdfUrl} className="h-[60vh] w-full rounded-lg bg-white" /> :
          <div className="max-h-[58vh] overflow-auto rounded-lg bg-[#061018] p-3 font-mono text-xs leading-6 text-slate-300">
            {lines.map((line, index) => <div key={index} className={`whitespace-pre-wrap px-2 ${selected.row_num === index + 1 ? "bg-amber-300/20 text-amber-100" : ""}`}><span className="mr-4 text-slate-500">{index + 1}</span>{line}</div>)}
          </div>}
      </div>
    </div>}
  </main>;
}
