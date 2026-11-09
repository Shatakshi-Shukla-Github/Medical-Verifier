import { useState } from 'react';
import { AlertCircle, ArrowUpRight, BookOpen, CheckCircle2, LoaderCircle, Search, ShieldCheck } from 'lucide-react';

const API_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export default function App() {
  const [claim, setClaim] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const handleCheck = async (event) => {
    event.preventDefault();
    if (!claim.trim()) return;

    setLoading(true);
    setError('');
    setResult(null);
    try {
      const response = await fetch(`${API_URL}/api/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ claim }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Could not verify this statement.');
      }
      setResult(data);
    } catch (requestError) {
      setError(requestError.message || 'Unable to reach the verification service. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const statusStyle = result?.status === 'Likely fact'
    ? 'text-emerald-300 bg-emerald-400/10 border-emerald-300/20'
    : result?.status === 'Likely myth'
      ? 'text-rose-300 bg-rose-400/10 border-rose-300/20'
      : 'text-amber-200 bg-amber-400/10 border-amber-300/20';

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 px-4 py-8 sm:px-6">
      <header className="mx-auto max-w-4xl mb-12 flex items-center gap-3">
        <div className="rounded-xl bg-cyan-400/10 p-2.5">
          <ShieldCheck className="h-7 w-7 text-cyan-300" />
        </div>
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">Health Claim Verifier</h1>
          <p className="text-xs sm:text-sm text-slate-400">Evidence from biomedical literature, with sources you can check</p>
        </div>
      </header>

      <main className="mx-auto max-w-4xl">
        <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 sm:p-8 shadow-2xl shadow-black/20">
          <div className="mb-5">
            <h2 className="text-lg font-semibold">Check a health statement</h2>
            <p className="mt-1 text-sm text-slate-400">
              We search Europe PMC for biomedical journal abstracts and show the evidence used.
            </p>
          </div>
          <form onSubmit={handleCheck}>
            <label htmlFor="claim" className="sr-only">Health statement to verify</label>
            <textarea
              id="claim"
              value={claim}
              onChange={(event) => setClaim(event.target.value)}
              maxLength={1000}
              placeholder="For example: Vaccines cause autism."
              className="min-h-32 w-full resize-y rounded-xl border border-slate-700 bg-slate-950 p-4 text-sm leading-6 text-slate-100 placeholder:text-slate-600 focus:border-cyan-400 focus:outline-none focus:ring-2 focus:ring-cyan-400/20"
            />
            <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <span className="text-xs text-slate-500">Up to 1,000 characters · Search uses published biomedical literature</span>
              <button
                type="submit"
                disabled={loading || !claim.trim()}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-cyan-500 px-5 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                {loading ? 'Searching sources…' : 'Verify statement'}
              </button>
            </div>
          </form>

          {error && (
            <div role="alert" className="mt-5 flex gap-2 rounded-lg border border-rose-400/20 bg-rose-400/10 p-3 text-sm text-rose-200">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </section>

        {result && (
          <section aria-live="polite" className="mt-6 space-y-5">
            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 sm:p-8">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-4">
                <h2 className="text-lg font-semibold">Assessment</h2>
                <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${statusStyle}`}>
                  {result.status}
                </span>
              </div>
              <blockquote className="mt-4 border-l-2 border-cyan-400 pl-4 text-sm leading-6 text-slate-200">
                {result.claim}
              </blockquote>

              {result.fact_score !== null && result.myth_score !== null ? (
                <div className="mt-6 grid gap-4 sm:grid-cols-2">
                  <Score label="Fact / supported" value={result.fact_score} color="bg-emerald-400" />
                  <Score label="Myth / contradicted" value={result.myth_score} color="bg-rose-400" />
                </div>
              ) : (
                <div className="mt-5 rounded-xl border border-amber-300/20 bg-amber-300/5 p-4 text-sm text-amber-100">
                  Not enough clear, relevant source evidence to calculate a fact-versus-myth percentage.
                </div>
              )}
              <p className="mt-5 text-sm leading-6 text-slate-300">{result.summary}</p>
              <p className="mt-3 text-xs leading-5 text-slate-500">
                The percentages describe agreement among retrieved sources with clear directional language; they are not a validated probability or a substitute for medical advice.
              </p>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 sm:p-8">
              <div className="mb-4 flex items-center gap-2">
                <BookOpen className="h-5 w-5 text-cyan-300" />
                <h2 className="text-lg font-semibold">Sources ({result.evidence_count})</h2>
              </div>
              {result.sources.length ? (
                <ol className="space-y-4">
                  {result.sources.map((source, index) => (
                    <li key={`${source.url}-${index}`} className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
                      <div className="flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-wide text-slate-400">
                        <span>Source {index + 1}</span>
                        <span>·</span>
                        <span>{source.provider}</span>
                        <span>·</span>
                        <span className={
                          source.direction === 'supports' ? 'text-emerald-300' :
                            source.direction === 'refutes' ? 'text-rose-300' : 'text-amber-200'
                        }>
                          {source.direction === 'supports' ? 'Supports claim' :
                            source.direction === 'refutes' ? 'Contradicts claim' : 'Direction unclear'}
                        </span>
                      </div>
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-2 inline-flex items-start gap-1 text-sm font-medium leading-6 text-cyan-200 hover:text-cyan-100 hover:underline"
                      >
                        {source.title}<ArrowUpRight className="mt-1 h-3.5 w-3.5 shrink-0" />
                      </a>
                      <p className="mt-1 text-xs text-slate-400">
                        {[source.authors, source.journal, source.year].filter(Boolean).join(' · ')}
                      </p>
                      <p className="mt-3 border-l border-slate-700 pl-3 text-xs leading-5 text-slate-300">{source.evidence}</p>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="text-sm text-slate-400">No matching article or health-topic sources were found.</p>
              )}
              <p className="mt-5 text-xs leading-5 text-slate-500">
                Source text is retrieved from PubMed/Europe PMC and MedlinePlus. Open each source to review its context.
              </p>

              {result.additional_site_searches?.length > 0 && (
                <div className="mt-6 border-t border-slate-800 pt-5">
                  <h3 className="text-sm font-medium text-slate-200">Search the other requested health sites</h3>
                  <p className="mt-1 text-xs leading-5 text-slate-500">
                    These links open each site’s own search for this statement. Their results are not included in the score unless they appear above as retrieved evidence.
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {result.additional_site_searches.map((site) => (
                      <a
                        key={site.name}
                        href={site.url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 rounded-lg border border-slate-700 px-3 py-2 text-xs text-cyan-200 hover:border-cyan-400/50 hover:bg-cyan-400/5"
                      >
                        {site.name}<ArrowUpRight className="h-3 w-3" />
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </section>
        )}

        <footer className="mt-8 flex items-start gap-2 text-xs leading-5 text-slate-500">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-slate-600" />
          <p>This tool is an evidence-finding aid. It can miss relevant research and does not provide medical advice.</p>
        </footer>
      </main>
    </div>
  );
}

function Score({ label, value, color }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-300">{label}</span>
        <strong className="text-lg text-slate-100">{value}%</strong>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-800">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}
