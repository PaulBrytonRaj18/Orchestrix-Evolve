import React, { useState } from 'react';
import { MessageSquare, Loader2 } from 'lucide-react';
import { api } from '../api';
import type { AnswerResponse } from '../types/api';

interface Props {
  sessionId: string;
}

/** Turn "[3]" markers into links to the cited passage. */
function renderAnswer(answer: string): React.ReactNode[] {
  return answer.split(/(\[\d+\])/g).map((part, i) => {
    const m = part.match(/^\[(\d+)\]$/);
    return m ? (
      <a key={i} href={`#passage-${m[1]}`} className="citation-ref" style={{ fontSize: '0.75em', verticalAlign: 'super' }}>
        [{m[1]}]
      </a>
    ) : (
      <span key={i} style={{ whiteSpace: 'pre-wrap' }}>{part}</span>
    );
  });
}

function AskPanel({ sessionId }: Props) {
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<AnswerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (question.trim().length < 3) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await api.ask(sessionId, question.trim()));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not answer');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="ask-panel" style={{ display: 'grid', gap: 'var(--space-5)' }}>
      <form onSubmit={submit} style={{ display: 'flex', gap: 'var(--space-2)' }}>
        <input
          className="form-input ask-input"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question about these papers…"
          disabled={busy}
          style={{ flex: 1 }}
        />
        <button className="btn btn-primary" type="submit" disabled={busy || question.trim().length < 3}>
          {busy ? <Loader2 size={16} style={{ animation: 'spin 0.8s linear infinite' }} /> : <MessageSquare size={16} />}
          Ask
        </button>
      </form>
      {busy && !result && (
        <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
          The first question indexes the papers' full texts; this can take up to a minute.
        </p>
      )}
      {error && <p style={{ color: 'var(--error-primary)' }}>{error}</p>}
      {result && (
        <>
          <div className="card answer" style={{ padding: 'var(--space-5)' }}>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', marginBottom: 'var(--space-2)' }}>
              {result.mode === 'llm' ? 'Answer generated from the passages below' : 'Most relevant evidence (no LLM configured)'} ·{' '}
              {result.coverage.fulltext} full texts, {result.coverage.abstract_only} abstracts searched
            </div>
            <div style={{ lineHeight: 1.6 }}>{renderAnswer(result.answer)}</div>
          </div>
          <ol style={{ listStyle: 'none', padding: 0, display: 'grid', gap: 'var(--space-2)' }}>
            {result.passages.map((p) => (
              <li
                key={p.n}
                id={`passage-${p.n}`}
                className="card"
                style={{ padding: 'var(--space-3)', fontSize: 'var(--text-sm)', opacity: p.cited ? 1 : 0.75 }}
              >
                <div style={{ display: 'flex', gap: 'var(--space-2)', marginBottom: 'var(--space-1)' }}>
                  <span className="badge">[{p.n}]</span>
                  <strong style={{ flex: 1 }}>{p.title}</strong>
                  <span style={{ color: 'var(--text-tertiary)' }}>{p.source === 'fulltext' ? 'full text' : 'abstract'}</span>
                </div>
                <p style={{ color: 'var(--text-secondary)', margin: 0 }}>{p.text}</p>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}

export default AskPanel;
