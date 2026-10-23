import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronUp, ChevronDown, Copy, Download, Search, AlertTriangle, Trophy } from 'lucide-react';
import { FinalEntry, GenerationStats, NameRow, PrefilterInfo, Verdict } from '../services/api';
import { compareBest, downloadCsv, ResultItem, shortModel, titleCase } from '../lib/names';
import StarRating from './StarRating';

interface ResultsTabProps {
  rows: NameRow[];
  verdicts: Record<string, Verdict>;
  similarities: Record<string, number>;
  final: Record<string, FinalEntry>;
  ratings: Record<string, number>;
  onRate: (name: string, rating: number) => void;
  genStats: GenerationStats | null;
  prefilter: PrefilterInfo | null;
  simCutoff?: number;
  onGoTo: (tab: 'sources' | 'sampling' | 'judge') => void;
}

type SortKey = 'best' | 'score' | 'vibe' | 'natural' | 'novelty' | 'name' | 'length' | 'rating';
type Filter = 'all' | 'judged' | 'unjudged' | 'flagged' | 'rated' | 'unrated';

const PAGE = 200;

const SORTS: Record<SortKey, { label: string; value: (i: ResultItem) => number | string; desc: boolean }> = {
  best: { label: 'Best first', value: () => 0, desc: true },
  score: { label: 'Judge score', value: i => i.verdict?.score ?? -1, desc: true },
  vibe: { label: 'Vibe', value: i => i.similarity ?? -1, desc: true },
  natural: { label: 'Natural', value: i => i.naturalness ?? -1, desc: true },
  novelty: { label: 'Novelty', value: i => i.distance ?? -1, desc: true },
  name: { label: 'Name', value: i => i.name, desc: false },
  length: { label: 'Length', value: i => i.name.length, desc: false },
  rating: { label: 'Your rating', value: i => i.rating, desc: true }
};

const FILTERS: Record<Filter, { label: string; test: (i: ResultItem) => boolean }> = {
  all: { label: 'All', test: () => true },
  judged: { label: 'Judged', test: i => i.verdict?.score != null },
  unjudged: { label: 'Not judged', test: i => i.verdict?.score == null },
  flagged: { label: 'Flagged', test: i => !!i.verdict?.flag },
  rated: { label: 'Rated', test: i => i.rating > 0 },
  unrated: { label: 'Unrated', test: i => i.rating === 0 }
};

const scoreClass = (score: number) => score >= 7 ? 'score-hi' : score >= 5 ? 'score-mid' : 'score-lo';

function rejectionSummary(stats: GenerationStats): string {
  const parts = [
    stats.too_similar && `${stats.too_similar.toLocaleString()} too close to a training word`,
    stats.training_word && `${stats.training_word.toLocaleString()} were real training words`,
    stats.duplicate && `${stats.duplicate.toLocaleString()} duplicates`,
    stats.failed && `${stats.failed.toLocaleString()} missed the constraints`
  ].filter(Boolean);
  return parts.length ? `Rejected along the way: ${parts.join(', ')}.` : '';
}

const ResultsTab: React.FC<ResultsTabProps> = ({
  rows, verdicts, similarities, final, ratings, onRate, genStats, prefilter, simCutoff, onGoTo
}) => {
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<Filter>('all');
  const [sortKey, setSortKey] = useState<SortKey>('best');
  const [desc, setDesc] = useState(true);
  const [limit, setLimit] = useState(PAGE);
  const [focus, setFocus] = useState(0);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const rowRefs = useRef<Record<string, HTMLTableRowElement | null>>({});

  const items: ResultItem[] = useMemo(() => rows.map(row => ({
    ...row,
    verdict: verdicts[row.name],
    similarity: similarities[row.name],
    final: final[row.name],
    rating: ratings[row.name] || 0
  })), [rows, verdicts, similarities, final, ratings]);

  const has = useMemo(() => ({
    vibe: items.some(i => i.similarity !== undefined),
    score: items.some(i => i.verdict?.score != null),
    final: items.some(i => i.final),
    natural: items.some(i => i.naturalness !== undefined),
    nearest: items.some(i => i.nearest)
  }), [items]);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = items.filter(i => FILTERS[filter].test(i) && (!q || i.name.includes(q)));
    if (sortKey === 'best') return filtered.sort((a, b) => desc ? compareBest(a, b) : compareBest(b, a));
    const value = SORTS[sortKey].value;
    return filtered.sort((a, b) => {
      const va = value(a), vb = value(b);
      const cmp = va < vb ? -1 : va > vb ? 1 : 0;
      return desc ? -cmp : cmp;
    });
  }, [items, query, filter, sortKey, desc]);

  const visible = shown.slice(0, limit);
  const columnCount = 3 + [has.score, has.final, has.vibe, has.natural, has.nearest].filter(Boolean).length;

  useEffect(() => { setFocus(0); setLimit(PAGE); }, [query, filter, sortKey, desc]);

  const sortBy = (key: SortKey) => {
    if (key === sortKey) setDesc(d => !d);
    else { setSortKey(key); setDesc(SORTS[key].desc); }
  };

  // Keyboard triage: ↑/↓ (or j/k) move, 1-5 rate, 0 clears, Enter expands, / searches
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || e.metaKey || e.ctrlKey || e.altKey) return;
      const current = visible[focus];
      if (e.key === 'ArrowDown' || e.key === 'j') {
        e.preventDefault();
        setFocus(f => Math.min(f + 1, visible.length - 1));
      } else if (e.key === 'ArrowUp' || e.key === 'k') {
        e.preventDefault();
        setFocus(f => Math.max(f - 1, 0));
      } else if (/^[0-5]$/.test(e.key) && current) {
        onRate(current.name, Number(e.key));
      } else if (e.key === 'Enter' && current) {
        setExpanded(x => x === current.name ? null : current.name);
      } else if (e.key === '/') {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [visible, focus, onRate]);

  useEffect(() => {
    const name = visible[focus]?.name;
    if (name) rowRefs.current[name]?.scrollIntoView({ block: 'nearest' });
  }, [focus, visible]);

  const copyNames = async () => {
    await navigator.clipboard.writeText(shown.map(i => i.name).join('\n'));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  if (rows.length === 0) {
    return (
      <div className="empty-state">
        <h2 className="empty-title">Nothing forged yet</h2>
        <ol className="empty-steps">
          <li><button className="link-button" onClick={() => onGoTo('sources')}>Pick word lists</button> whose
            <em> sound</em> you like. Their letter patterns are all the model learns.</li>
          <li><button className="link-button" onClick={() => onGoTo('sampling')}>Shape the output</button>:
            length, prefixes and suffixes, how adventurous the sampling is.</li>
          <li>Hit <strong>Generate</strong>, then <button className="link-button" onClick={() => onGoTo('judge')}>
            brief the judges</button> and let them find the gems.</li>
        </ol>
      </div>
    );
  }

  const header = (key: SortKey, label: string, title?: string, className = '') => (
    <th className={`sortable ${className}`} onClick={() => sortBy(key)} title={title}>
      <span className="th-inner">
        {label}
        {sortKey === key && (desc ? <ChevronDown size={13} /> : <ChevronUp size={13} />)}
      </span>
    </th>
  );

  return (
    <div>
      <div className="results-summary">
        {genStats && (
          <p>
            Forged <strong>{genStats.accepted.toLocaleString()}</strong> names from{' '}
            {genStats.attempts.toLocaleString()} attempts in {genStats.elapsed}s. {rejectionSummary(genStats)}
          </p>
        )}
        {prefilter && (
          <p>
            Vibe prefilter sent the top <strong>{prefilter.kept.toLocaleString()}</strong> of{' '}
            {prefilter.total.toLocaleString()} names to the judges
            {prefilter.min_similarity > 0 && ` (vibe ≥ ${prefilter.min_similarity.toFixed(2)})`}.
          </p>
        )}
      </div>

      <div className="toolbar">
        <div className="search-box">
          <Search size={14} />
          <input ref={searchRef} value={query} onChange={e => setQuery(e.target.value)}
            placeholder="Filter names…  ( / )" />
        </div>
        <div className="segmented">
          {(Object.keys(FILTERS) as Filter[]).map(f => (
            <button key={f} className={filter === f ? 'active' : ''} onClick={() => setFilter(f)}>
              {FILTERS[f].label}
            </button>
          ))}
        </div>
        <select className="form-select compact-select" value={sortKey} onChange={e => sortBy(e.target.value as SortKey)}>
          {(Object.keys(SORTS) as SortKey[]).map(key => <option key={key} value={key}>{SORTS[key].label}</option>)}
        </select>
        <div className="toolbar-spacer" />
        <span className="text-muted text-sm">{shown.length.toLocaleString()} shown</span>
        <button className="btn btn-ghost btn-small" onClick={copyNames} title="Copy the shown names, one per line">
          <Copy size={13} /> {copied ? 'Copied' : 'Copy'}
        </button>
        <button className="btn btn-ghost btn-small" onClick={() => downloadCsv(shown)} title="Download the shown names with all scores">
          <Download size={13} /> CSV
        </button>
      </div>

      <p className="kbd-hint">
        <kbd>↑</kbd><kbd>↓</kbd> move · <kbd>1</kbd>–<kbd>5</kbd> rate · <kbd>0</kbd> clear · <kbd>Enter</kbd> details · click a row for details
      </p>

      <div className="results-table-wrap">
        <table className="results-table">
          <thead>
            <tr>
              <th className="col-index">#</th>
              {header('name', 'Name')}
              {has.score && header('score', 'Score', 'Mean overall score from the judge panel (0–10)', 'col-num')}
              {has.final && <th className="col-num" title="Rank in the head-to-head final round">Final</th>}
              {has.vibe && header('vibe', 'Vibe', 'Embedding similarity to your vibe keywords', 'col-num')}
              {has.natural && header('natural', 'Natural',
                'How fluent the letter sequence is: percentile among the model’s own samples (50 = typical)', 'col-num')}
              {has.nearest && header('novelty', 'From', 'Closest training word and how many edits away it is')}
              {header('rating', 'You')}
            </tr>
          </thead>
          <tbody>
            {visible.map((item, index) => {
              const v = item.verdict;
              const isOpen = expanded === item.name;
              const belowCutoff = !!simCutoff && item.similarity !== undefined && item.similarity < simCutoff;
              return (
                <React.Fragment key={item.name}>
                  <tr
                    ref={el => { rowRefs.current[item.name] = el; }}
                    className={`result-row ${index === focus ? 'focused' : ''} ${belowCutoff ? 'dimmed' : ''} ${isOpen ? 'open' : ''}`}
                    onClick={() => { setFocus(index); setExpanded(isOpen ? null : item.name); }}
                  >
                    <td className="col-index">{index + 1}</td>
                    <td>
                      <div className="name-cell">
                        <span className="name-display">{titleCase(item.name)}</span>
                        {v?.flag && (
                          <span className="flag-chip" title={v.flag}><AlertTriangle size={11} /> {v.flag}</span>
                        )}
                      </div>
                      {item.final?.pitch ? (
                        <div className="name-note"><Trophy size={11} /> {item.final.pitch}</div>
                      ) : v?.note ? (
                        <div className="name-note">{v.note}</div>
                      ) : null}
                    </td>
                    {has.score && (
                      <td className="col-num">
                        {v?.score != null ? (
                          <span className={`score-pill ${scoreClass(v.score)}`}
                            title={`sound ${v.sound ?? '–'} · fit ${v.fit ?? '–'} · distinct ${v.distinct ?? '–'}\n` +
                              Object.entries(v.judges).map(([m, s]) => `${shortModel(m)}: ${s ?? '–'}`).join('\n')}>
                            {v.score.toFixed(1)}
                          </span>
                        ) : <span className="text-muted">—</span>}
                      </td>
                    )}
                    {has.final && (
                      <td className="col-num">
                        {item.final ? <span className="final-badge">#{item.final.rank}</span> : <span className="text-muted">—</span>}
                      </td>
                    )}
                    {has.vibe && (
                      <td className="col-num mono">
                        {item.similarity !== undefined ? item.similarity.toFixed(2) : <span className="text-muted">—</span>}
                      </td>
                    )}
                    {has.natural && (
                      <td className="col-num">
                        {item.naturalness !== undefined && (
                          <span className="meter" title={`${item.naturalness}/100`}>
                            <span className="meter-fill" style={{ width: `${item.naturalness}%` }} />
                          </span>
                        )}
                      </td>
                    )}
                    {has.nearest && (
                      <td className="from-cell">
                        {item.nearest && (
                          <><span className="mono">{item.nearest}</span> <span className="distance">+{item.distance}</span></>
                        )}
                      </td>
                    )}
                    <td><StarRating rating={item.rating} onRate={r => onRate(item.name, r)} /></td>
                  </tr>
                  {isOpen && (
                    <tr className="detail-row">
                      <td />
                      <td colSpan={columnCount - 1}>
                        <div className="detail-grid">
                          <div className="case-treatments">
                            <span>{item.name}</span><span>{titleCase(item.name)}</span><span>{item.name.toUpperCase()}</span>
                          </div>
                          {v && v.score != null && (
                            <div className="criteria">
                              {(['sound', 'fit', 'distinct'] as const).map(c => (
                                <div key={c} className="criterion">
                                  <span className="criterion-label">{c}</span>
                                  <span className="meter wide"><span className="meter-fill" style={{ width: `${(v[c] ?? 0) * 10}%` }} /></span>
                                  <span className="mono">{v[c] ?? '–'}</span>
                                </div>
                              ))}
                            </div>
                          )}
                          {v && Object.entries(v.notes).map(([model, note]) => (
                            <p key={model} className="judge-note">
                              <span className="judge-name">{shortModel(model)} · {v.judges[model] ?? '–'}</span> {note}
                            </p>
                          ))}
                          {item.final && (
                            <p className="judge-note">
                              <span className="judge-name">final round · #{item.final.rank}</span> {item.final.pitch}
                              {item.final.concern && <span className="text-muted"> Risk: {item.final.concern}</span>}
                            </p>
                          )}
                          {item.nearest && (
                            <p className="text-muted text-sm">
                              Closest training word: <span className="mono">{item.nearest}</span> ({item.distance} edit{item.distance === 1 ? '' : 's'} away)
                              {item.naturalness !== undefined && ` · naturalness ${item.naturalness}/100`}
                            </p>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      {shown.length > limit && (
        <div className="text-center mt-4">
          <button className="btn btn-secondary" onClick={() => setLimit(l => l + PAGE)}>
            Show {Math.min(PAGE, shown.length - limit)} more ({(shown.length - limit).toLocaleString()} hidden)
          </button>
        </div>
      )}
    </div>
  );
};

export default ResultsTab;
