import React, { useEffect, useMemo, useState } from 'react';
import { Eye, Shuffle, ChevronUp, ChevronDown, Search } from 'lucide-react';
import { apiService, Config, Weighting, WordList, WordListContent } from '../services/api';
import StarRating from './StarRating';
import Modal from './Modal';

interface TrainingDataTabProps {
  config: Config;
  patchConfig: <K extends keyof Config>(section: K, patch: Partial<NonNullable<Config[K]>>) => void;
}

type SortColumn = 'name' | 'word_count' | 'rating' | 'health';

const WEIGHTINGS: Record<Weighting, { label: string; help: string }> = {
  natural: { label: 'Natural', help: 'Every word counts once, so big lists dominate the letter statistics.' },
  balanced: { label: 'Balanced', help: 'Every selected list contributes equally, whatever its size.' },
  rating: { label: 'By rating', help: 'Balanced, then scaled by your star rating (unrated lists count as 3★).' }
};
const UNRATED_STARS = 3;
const MIX_COLORS = ['#e0a458', '#9db8c4', '#a4bd84', '#de7361', '#c49bd4', '#e9c46a', '#7fb7a4'];

// Markov-health badge: green = good novel-name statistics, red = the model
// will mostly replay training words (low branching / high memorization).
const healthClass = (score: number) => score >= 50 ? 'health-good' : score >= 30 ? 'health-mid' : 'health-bad';

const TrainingDataTab: React.FC<TrainingDataTabProps> = ({ config, patchConfig }) => {
  const [wordLists, setWordLists] = useState<WordList[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewing, setViewing] = useState<WordListContent | null>(null);
  const [shuffled, setShuffled] = useState(false);
  const [sortColumn, setSortColumn] = useState<SortColumn>('name');
  const [sortDesc, setSortDesc] = useState(false);
  const [minHealth, setMinHealth] = useState(0);
  const [query, setQuery] = useState('');
  const [range, setRange] = useState<[number, number]>([
    config.training_data?.score_range?.min ?? 3, config.training_data?.score_range?.max ?? 5]);

  const selected = useMemo(() => config.training_data?.sources || [], [config.training_data?.sources]);
  const weighting: Weighting = config.training_data?.weighting || 'natural';
  const setSources = (sources: string[]) => patchConfig('training_data', { sources });

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      setWordLists(await apiService.getWordLists());
    } catch (err) {
      setError('Failed to load word lists. Is the API server running?');
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const key = (wl: WordList): string | number =>
      sortColumn === 'name' ? wl.display_name.toLowerCase()
        : sortColumn === 'word_count' ? wl.word_count
          : sortColumn === 'rating' ? wl.rating
            : wl.health?.score ?? -1;
    return wordLists
      .filter(wl => (wl.health?.score ?? 0) >= minHealth && (!q || wl.display_name.toLowerCase().includes(q)))
      .sort((a, b) => {
        const cmp = key(a) < key(b) ? -1 : key(a) > key(b) ? 1 : 0;
        return sortDesc ? -cmp : cmp;
      });
  }, [wordLists, query, minHealth, sortColumn, sortDesc]);

  // Share of the training statistics each selected list ends up with, after
  // the brief lexicon and the breeding gene pool take their fixed shares
  // (mirrors extra_sources() in markov_namegen.py, incl. the 90% cap).
  const training = config.training_data;
  const mix = useMemo(() => {
    const extras = [
      { name: 'Brief lexicon', share: training?.lexicon?.length ? training.lexicon_share ?? 0.5 : 0 },
      { name: 'Gene pool', share: training?.breed && training.seeds?.length ? training.seed_share ?? 0.2 : 0 }
    ].filter(e => e.share > 0);
    const extraTotal = extras.reduce((sum, e) => sum + e.share, 0);
    const scale = extraTotal > 0.9 ? 0.9 / extraTotal : 1;
    const listShare = 1 - extraTotal * scale;
    const chosen = wordLists.filter(wl => selected.includes(wl.filename) && wl.word_count > 0);
    const weight = (wl: WordList) =>
      weighting === 'natural' ? wl.word_count : weighting === 'balanced' ? 1 : (wl.rating || UNRATED_STARS);
    const total = chosen.reduce((sum, wl) => sum + weight(wl), 0);
    return [
      ...extras.map(e => ({ name: e.name, share: e.share * scale })),
      ...chosen.map(wl => ({ name: wl.display_name, share: total ? listShare * weight(wl) / total : 0 }))
    ].sort((a, b) => b.share - a.share);
  }, [wordLists, selected, weighting, training]);

  const totalWords = wordLists.filter(wl => selected.includes(wl.filename)).reduce((s, wl) => s + wl.word_count, 0);

  const toggle = (filename: string) =>
    setSources(selected.includes(filename) ? selected.filter(s => s !== filename) : [...selected, filename]);

  const rate = async (filename: string, rating: number) => {
    setWordLists(prev => prev.map(wl => wl.filename === filename ? { ...wl, rating } : wl));
    try {
      await apiService.rateWordList(filename, rating);
    } catch (err) {
      console.error('Failed to rate word list:', err);
    }
  };

  const view = async (filename: string) => {
    try {
      setViewing(await apiService.getWordListContent(filename));
    } catch (err) {
      console.error('Failed to load word list content:', err);
    }
  };

  const sortBy = (column: SortColumn) => {
    if (column === sortColumn) setSortDesc(d => !d);
    else { setSortColumn(column); setSortDesc(column !== 'name'); }
  };

  const viewedWords = useMemo(() => {
    if (!viewing) return [];
    const words = [...viewing.words];
    if (!shuffled) return words.sort();
    for (let i = words.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [words[i], words[j]] = [words[j], words[i]];
    }
    return words;
  }, [viewing, shuffled]);

  if (loading) {
    return <div className="text-center py-8"><div className="loading-spinner mx-auto" /><p className="text-muted mt-2">Loading word lists…</p></div>;
  }
  if (error) {
    return <div className="text-center py-8"><p className="error-message">{error}</p><button className="btn btn-primary mt-4" onClick={load}>Retry</button></div>;
  }

  const th = (column: SortColumn, label: string, className = '') => (
    <th className={`sortable ${className}`} onClick={() => sortBy(column)}>
      <span className="th-inner">{label}{sortColumn === column && (sortDesc ? <ChevronDown size={13} /> : <ChevronUp size={13} />)}</span>
    </th>
  );

  return (
    <div className="space-y-4">
      <section className="card">
        <div className="sources-summary">
          <div>
            <div className="big-number">{selected.length} <span>lists</span></div>
            <div className="text-muted text-sm">{totalWords.toLocaleString()} training words</div>
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <span className="form-label" style={{ margin: 0 }}>Mix</span>
              <div className="segmented">
                {(Object.keys(WEIGHTINGS) as Weighting[]).map(w => (
                  <button key={w} className={weighting === w ? 'active' : ''}
                    onClick={() => patchConfig('training_data', { weighting: w })}>{WEIGHTINGS[w].label}</button>
                ))}
              </div>
              <span className="text-muted text-sm">{WEIGHTINGS[weighting].help}</span>
            </div>
            {mix.length > 0 ? (
              <>
                <div className="mix-bar">
                  {mix.map((m, i) => (
                    <span key={m.name} title={`${m.name}: ${(m.share * 100).toFixed(1)}%`}
                      style={{ width: `${m.share * 100}%`, background: MIX_COLORS[i % MIX_COLORS.length], opacity: i < MIX_COLORS.length ? 1 : 0.5 }} />
                  ))}
                </div>
                <div className="mix-legend">
                  {mix.slice(0, 6).map((m, i) => (
                    <span key={m.name}><i style={{ background: MIX_COLORS[i] }} />{m.name} {(m.share * 100).toFixed(0)}%</span>
                  ))}
                  {mix.length > 6 && <span className="text-muted">+{mix.length - 6} more</span>}
                </div>
              </>
            ) : (
              <p className="text-muted text-sm">Select lists below whose words <em>sound</em> like the names you want.</p>
            )}
          </div>
        </div>
      </section>

      <section className="card">
        <div className="sources-controls">
          <div className="search-box">
            <Search size={14} />
            <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search lists…" />
          </div>
          <div className="control-cluster">
            <span className="text-sm text-muted">Rated</span>
            <select className="form-select compact-select" value={range[0]} onChange={e => setRange([Number(e.target.value), Math.max(range[1], Number(e.target.value))])}>
              {[0, 1, 2, 3, 4, 5].map(n => <option key={n} value={n}>{n}★</option>)}
            </select>
            <span className="text-sm text-muted">to</span>
            <select className="form-select compact-select" value={range[1]} onChange={e => setRange([Math.min(range[0], Number(e.target.value)), Number(e.target.value)])}>
              {[0, 1, 2, 3, 4, 5].map(n => <option key={n} value={n}>{n}★</option>)}
            </select>
            <button className="btn btn-secondary btn-small" onClick={() => {
              patchConfig('training_data', {
                sources: visible.filter(wl => wl.rating >= range[0] && wl.rating <= range[1]).map(wl => wl.filename),
                score_range: { min: range[0], max: range[1] }
              });
            }}>Select</button>
          </div>
          <div className="control-cluster">
            <span className="text-sm text-muted" title="Hide lists whose statistics mostly replay their own words">Min health {minHealth}</span>
            <input type="range" className="range-slider" style={{ width: 110 }} min={0} max={100} value={minHealth}
              onChange={e => setMinHealth(Number(e.target.value))} />
          </div>
          <div className="toolbar-spacer" />
          <button className="btn btn-ghost btn-small" onClick={() => setSources(Array.from(new Set([...selected, ...visible.map(wl => wl.filename)])))}>Select shown</button>
          <button className="btn btn-ghost btn-small" onClick={() => setSources([])}>Clear</button>
        </div>

        <div className="results-table-wrap tall">
          <table className="results-table">
            <thead>
              <tr>
                <th className="col-index" />
                {th('name', 'List')}
                {th('word_count', 'Words', 'col-num')}
                {th('health', 'Health', 'col-num')}
                {th('rating', 'Your rating')}
                <th />
              </tr>
            </thead>
            <tbody>
              {visible.map(wl => {
                const isSelected = selected.includes(wl.filename);
                const h = wl.health;
                return (
                  <tr key={wl.filename} className={`result-row ${isSelected ? 'selected-row' : ''}`} onClick={() => toggle(wl.filename)}>
                    <td className="col-index">
                      <input type="checkbox" checked={isSelected} onChange={() => toggle(wl.filename)} onClick={e => e.stopPropagation()} />
                    </td>
                    <td><span className="font-medium">{wl.display_name}</span></td>
                    <td className="col-num mono">{wl.word_count.toLocaleString()}</td>
                    <td className="col-num">
                      {h ? (
                        <span className={`health-badge ${healthClass(h.score)}`}
                          title={`Branching: ${(h.branching_factor * 100).toFixed(0)}% of contexts have ≥2 possible next letters\n` +
                            `Memorization: ${(h.memorization_rate * 100).toFixed(0)}% of samples replay a real word\n` +
                            `${h.unique_contexts} contexts / ${h.unique_words} unique words`}>
                          {h.score}
                        </span>
                      ) : <span className="text-muted">—</span>}
                    </td>
                    <td onClick={e => e.stopPropagation()}>
                      <StarRating rating={wl.rating} onRate={r => rate(wl.filename, r)} />
                    </td>
                    <td onClick={e => e.stopPropagation()}>
                      <button className="icon-button" title="View words" onClick={() => view(wl.filename)}><Eye size={14} /></button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <Modal isOpen={!!viewing} onClose={() => setViewing(null)}
        title={viewing ? viewing.filename.replace(/_/g, ' ').replace('.txt', '') : ''}>
        {viewing && (
          <div>
            <div className="flex items-center gap-4 mb-4">
              <span className="text-sm text-muted">{viewing.total_count.toLocaleString()} words</span>
              <div className="segmented">
                <button className={!shuffled ? 'active' : ''} onClick={() => setShuffled(false)}>Sorted</button>
                <button className={shuffled ? 'active' : ''} onClick={() => setShuffled(true)}><Shuffle size={12} /> Shuffled</button>
              </div>
            </div>
            <div className="word-list-view">
              {viewedWords.map((word, i) => <span key={i}>{word}</span>)}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default TrainingDataTab;
