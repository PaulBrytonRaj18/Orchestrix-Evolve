import { useEffect, useMemo, useState } from 'react';
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from 'd3-force';
import { Network, Search } from 'lucide-react';
import { api } from '../api';
import type { GraphResponse } from '../types/api';

interface Props {
  sessionId: string;
  onSearch?: (query: string) => void;
}

type Node = SimulationNodeDatum & { id: string; title: string; r: number; cited: number };
type Link = SimulationLinkDatum<Node>;

const W = 720;
const H = 420;

/** Who-cites-whom among the session's papers (lazy-loaded with its tab). */
function CitationGraph({ sessionId, onSearch }: Props) {
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .getGraph(sessionId)
      .then((g) => alive && setGraph(g))
      .catch((e) => alive && setError(e instanceof Error ? e.message : 'Could not load the graph'));
    return () => {
      alive = false;
    };
  }, [sessionId]);

  // Settle the force layout once, synchronously (no animation loop to manage).
  const layout = useMemo(() => {
    if (!graph) return null;
    const maxRank = Math.max(...graph.nodes.map((n) => n.pagerank), 1e-9);
    const nodes: Node[] = graph.nodes.map((n) => ({
      id: n.id,
      title: n.title,
      cited: n.cited_by_in_session,
      r: 5 + 13 * Math.sqrt(n.pagerank / maxRank),
    }));
    const links: Link[] = graph.edges.map((e) => ({ source: e.source, target: e.target }));
    const sim = forceSimulation(nodes)
      .force('link', forceLink<Node, Link>(links).id((d) => d.id).distance(70))
      .force('charge', forceManyBody().strength(-60 - 600 / Math.max(nodes.length, 1)))
      .force('center', forceCenter(W / 2, H / 2))
      .force('collide', forceCollide<Node>().radius((d) => d.r + 4))
      .stop();
    for (let i = 0; i < 300; i++) sim.tick();
    // Fit the settled layout into the frame (uniform scale, so the shape is kept)
    // instead of clamping, which piles overflowing nodes up along the edges.
    const pad = 22;
    const xs = nodes.map((n) => n.x ?? 0);
    const ys = nodes.map((n) => n.y ?? 0);
    const [minX, maxX, minY, maxY] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const scale = Math.min((W - 2 * pad) / Math.max(maxX - minX, 1), (H - 2 * pad) / Math.max(maxY - minY, 1), 1.5);
    const offX = (W - (maxX - minX) * scale) / 2;
    const offY = (H - (maxY - minY) * scale) / 2;
    for (const n of nodes) {
      n.x = offX + ((n.x ?? 0) - minX) * scale;
      n.y = offY + ((n.y ?? 0) - minY) * scale;
    }
    return { nodes, links };
  }, [graph]);

  if (error) return <p style={{ color: 'var(--error-primary)' }}>{error}</p>;
  if (!graph || !layout) return <div className="loading-spinner" />;

  const hovered = layout.nodes.find((n) => n.id === hover);

  return (
    <div className="citation-graph" style={{ display: 'grid', gap: 'var(--space-6)' }}>
      <div className="card" style={{ padding: 'var(--space-4)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-2)' }}>
          <Network size={16} />
          <strong>Citation graph</strong>
          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
            {graph.coverage.edges} citations among {graph.coverage.papers} papers · size = PageRank
          </span>
        </div>
        {graph.coverage.edges === 0 ? (
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
            None of these papers cite each other ({graph.coverage.with_references} of {graph.coverage.papers} have
            reference data).
          </p>
        ) : (
          <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Citation graph of the session's papers" style={{ width: '100%', height: 'auto' }}>
            <defs>
              <marker id="cg-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                <path d="M0 0L10 5L0 10z" fill="var(--text-tertiary)" />
              </marker>
            </defs>
            {layout.links.map((l, i) => {
              const s = l.source as Node;
              const t = l.target as Node;
              const dx = (t.x ?? 0) - (s.x ?? 0);
              const dy = (t.y ?? 0) - (s.y ?? 0);
              const len = Math.hypot(dx, dy) || 1;
              return (
                <line
                  key={i}
                  x1={s.x}
                  y1={s.y}
                  x2={(t.x ?? 0) - (dx / len) * (t.r + 2)}
                  y2={(t.y ?? 0) - (dy / len) * (t.r + 2)}
                  stroke="var(--text-tertiary)"
                  strokeOpacity={0.5}
                  markerEnd="url(#cg-arrow)"
                />
              );
            })}
            {layout.nodes.map((n) => (
              <circle
                key={n.id}
                cx={n.x}
                cy={n.y}
                r={n.r}
                fill="var(--accent-primary)"
                fillOpacity={n.id === hover ? 0.9 : 0.55}
                stroke="var(--accent-primary)"
                onMouseEnter={() => setHover(n.id)}
                onMouseLeave={() => setHover(null)}
              >
                <title>{`${n.title} — cited by ${n.cited} paper(s) here`}</title>
              </circle>
            ))}
          </svg>
        )}
        {hovered && <p style={{ fontSize: 'var(--text-sm)', marginTop: 'var(--space-2)' }}>{hovered.title}</p>}
      </div>

      {graph.foundational.length > 0 && (
        <div>
          <h3 style={{ fontSize: 'var(--text-lg)', marginBottom: 'var(--space-2)' }}>Foundational in this session <span style={{ fontSize: 'var(--text-sm)', fontWeight: 400, color: 'var(--text-tertiary)' }}>by PageRank (influence through the citation network)</span></h3>
          <ol style={{ paddingLeft: 'var(--space-5)', display: 'grid', gap: 'var(--space-1)' }}>
            {graph.foundational.map((f) => (
              <li key={f.paper_id} style={{ fontSize: 'var(--text-sm)' }}>
                {f.title} <span style={{ color: 'var(--text-tertiary)' }}>· cited by {f.cited_by_in_session} here</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {graph.missing_key_papers.length > 0 && (
        <div>
          <h3 style={{ fontSize: 'var(--text-lg)', marginBottom: 'var(--space-2)' }}>Key papers you are missing</h3>
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', marginBottom: 'var(--space-2)' }}>
            Cited by several of your papers, but not in this session.
          </p>
          <ul style={{ listStyle: 'none', padding: 0, display: 'grid', gap: 'var(--space-2)' }}>
            {graph.missing_key_papers.map((m) => (
              <li key={m.openalex_id} className="card" style={{ padding: 'var(--space-3)', display: 'flex', gap: 'var(--space-3)', alignItems: 'center' }}>
                <span style={{ flex: 1, fontSize: 'var(--text-sm)' }}>
                  <strong>{m.title ?? m.openalex_id}</strong>
                  <span style={{ color: 'var(--text-tertiary)' }}>
                    {m.year ? ` · ${m.year}` : ''} · cited by {m.cited_by_session_papers} of your papers
                  </span>
                </span>
                {onSearch && m.title && (
                  <button className="btn btn-ghost btn-sm" onClick={() => onSearch(m.title!)}>
                    <Search size={14} /> Search for it
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {graph.disconnected_clusters.length > 1 && (
        <div>
          <h3 style={{ fontSize: 'var(--text-lg)', marginBottom: 'var(--space-2)' }}>Groups that never cite each other</h3>
          <ul style={{ paddingLeft: 'var(--space-5)' }}>
            {graph.disconnected_clusters.map((c) => (
              <li key={c.cluster} style={{ fontSize: 'var(--text-sm)' }}>
                {c.size} papers around “{c.anchor_title}”
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default CitationGraph;
