import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Play, Sparkles, Gavel, Trophy, Save, FolderOpen, X } from 'lucide-react';
import {
  apiService, errorMessage, Config, NameRow, Verdict, FinalEntry, GenerationStats, PrefilterInfo, ModelInfo
} from './services/api';
import { formatCost } from './lib/names';
import TrainingDataTab from './components/TrainingDataTab';
import SamplingParametersTab from './components/SamplingParametersTab';
import ResultsTab from './components/ResultsTab';
import SavedResultsTab from './components/SavedResultsTab';
import AITab from './components/AITab';
import GenerationProgressModal from './components/GenerationProgressModal';
import ConfigFilesModal from './components/ConfigFilesModal';

// Generated names and AI verdicts only live in React state (config and ratings
// persist to the backend), so the session is mirrored to localStorage to
// survive page refreshes.
const SESSION_KEY = 'namegen_session_v2';
const LEGACY_RESULTS_KEY = 'namegen_results_v1';

interface Session {
  rows: NameRow[];
  verdicts: Record<string, Verdict>;
  similarities: Record<string, number>;
  final: Record<string, FinalEntry>;
  prefilter: PrefilterInfo | null;
  genStats: GenerationStats | null;
  cost: number;
}

const EMPTY_SESSION: Session = {
  rows: [], verdicts: {}, similarities: {}, final: {}, prefilter: null, genStats: null, cost: 0
};

function loadSession(): Session {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (raw) return { ...EMPTY_SESSION, ...JSON.parse(raw) };
    // v1 stored bare name strings and 0-5 scores; keep the names only.
    const legacy = localStorage.getItem(LEGACY_RESULTS_KEY);
    if (legacy) {
      const names: string[] = JSON.parse(legacy).results || [];
      return { ...EMPTY_SESSION, rows: names.map(name => ({ name })) };
    }
  } catch (err) {
    console.error('Failed to restore session:', err);
  }
  return EMPTY_SESSION;
}

type Tab = 'sources' | 'sampling' | 'judge' | 'results' | 'shortlist';
type Busy = null | 'vibe' | 'judge' | 'final';
interface Toast { kind: 'error' | 'info'; text: string }

const initialSession = loadSession();

function App() {
  const [tab, setTab] = useState<Tab>(initialSession.rows.length ? 'results' : 'sources');
  const [config, setConfig] = useState<Config>({});
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [session, setSession] = useState<Session>(initialSession);
  const [generating, setGenerating] = useState(false);
  const [busy, setBusy] = useState<Busy>(null);
  const [progress, setProgress] = useState<{ label: string; done: number; total: number } | null>(null);
  const [toast, setToast] = useState<Toast | null>(null);
  const [configModal, setConfigModal] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem(SESSION_KEY, JSON.stringify(session));
    } catch (err) {
      console.error('Failed to persist session:', err);
    }
  }, [session]);

  useEffect(() => {
    Promise.all([apiService.getConfig(), apiService.getRatings()])
      .then(([configData, ratingsData]) => {
        setConfig(configData);
        setRatings(ratingsData);
      })
      .catch(() => setToast({ kind: 'error', text: 'Cannot reach the API server — start it with `uv run api_server.py`.' }));
    apiService.getModels().then(r => setModels(r.models)).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (toast?.kind !== 'info') return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  // Config edits are persisted to the backend (debounced so slider drags
  // don't fire a request per tick). Only user edits mark the config dirty —
  // the initial load must not echo back.
  const dirty = useRef(false);
  const patchConfig = useCallback(<K extends keyof Config>(section: K, patch: Partial<NonNullable<Config[K]>>) => {
    dirty.current = true;
    setConfig(prev => ({ ...prev, [section]: { ...(prev[section] || {}), ...patch } }));
  }, []);
  const replaceConfig = useCallback((next: Config) => {
    dirty.current = true;
    setConfig(next);
  }, []);
  useEffect(() => {
    if (!dirty.current) return;
    const timer = setTimeout(() => {
      apiService.updateConfig(config).catch(err => console.error('Failed to save config:', err));
    }, 400);
    return () => clearTimeout(timer);
  }, [config]);

  const fail = (err: any, fallback: string) => setToast({ kind: 'error', text: errorMessage(err, fallback) });

  const rate = useCallback((name: string, stars: number) => {
    setRatings(prev => {
      const next = { ...prev };
      if (stars > 0) next[name] = stars; else delete next[name];
      return next;
    });
    apiService.rateName(name, stars)
      .catch(err => setToast({ kind: 'error', text: errorMessage(err, 'Failed to save rating') }));
  }, []);

  const llm = config.llm || {};
  const keywords = (llm.keywords || '').trim();
  const judges = llm.judges?.length ? llm.judges : ['anthropic/claude-haiku-5.5', 'openai/gpt-6-luna'];
  const judgeLimit = config.ai_settings?.max_names ?? 200;
  const finalSize = llm.final_size ?? 25;
  const names = useMemo(() => session.rows.map(r => r.name), [session.rows]);
  const judgedNames = useMemo(() => {
    const current = new Set(names);
    return Object.values(session.verdicts).filter(v => v.score !== null && current.has(v.name));
  }, [session.verdicts, names]);

  // ------------------------------------------------------------------
  // Pipeline actions
  // ------------------------------------------------------------------

  const startGeneration = async () => {
    if (!config.training_data?.sources?.length) {
      setToast({ kind: 'error', text: 'Pick at least one word list in Sources first.' });
      setTab('sources');
      return;
    }
    setToast(null);
    // Flush the config so the CLI / a reload see exactly what was generated from
    apiService.updateConfig(config).catch(() => undefined);
    setGenerating(true);
  };

  const finishGeneration = (rows: NameRow[], stats: GenerationStats | null) => {
    setGenerating(false);
    if (!rows.length) {
      if (stats) setToast({
        kind: 'error',
        text: `No names survived ${stats.attempts.toLocaleString()} attempts (${stats.failed.toLocaleString()} missed the ` +
          `constraints, ${stats.too_similar.toLocaleString()} too close to training words). Loosen the Sampling settings.`
      });
      return;
    }
    setSession({ ...EMPTY_SESSION, rows, genStats: stats });
    setTab('results');
  };

  const vibeRank = async () => {
    if (!keywords) {
      setToast({ kind: 'error', text: 'Add vibe keywords in the Judge tab — they are what names get ranked against.' });
      setTab('judge');
      return;
    }
    setBusy('vibe');
    setProgress(null);
    try {
      const result = await apiService.embedRankStream(
        { names, keywords, embedding_model: llm.embedding_model },
        (done, total) => setProgress({ label: 'embedding', done, total }));
      setSession(prev => ({
        ...prev,
        similarities: Object.fromEntries(result.ranked.map(r => [r.name, r.similarity])),
        cost: prev.cost + result.cost
      }));
      setTab('results');
    } catch (err) {
      fail(err, 'Vibe ranking failed');
    } finally {
      setBusy(null);
      setProgress(null);
    }
  };

  const judge = async () => {
    if (!(llm.description || '').trim()) {
      setToast({ kind: 'error', text: 'Write a brief in the Judge tab first: what are these names for?' });
      setTab('judge');
      return;
    }
    setBusy('judge');
    setProgress(null);
    try {
      const result = await apiService.judgeStream({
        names,
        description: llm.description || '',
        keywords,
        guidance: llm.guidance || '',
        judges,
        chunk_size: llm.chunk_size || 20,
        prefilter_keep: judgeLimit,
        embedding_model: llm.embedding_model,
        min_similarity: llm.min_similarity || 0
      }, (phase, done, total) => setProgress({
        label: phase === 'embedding' ? 'vibe prefilter' : `judging (${judges.length} judge${judges.length > 1 ? 's' : ''})`,
        done, total
      }));
      const failed = result.verdicts.filter(v => v.score === null).length;
      setSession(prev => ({
        ...prev,
        verdicts: { ...prev.verdicts, ...Object.fromEntries(result.verdicts.map(v => [v.name, v])) },
        similarities: { ...prev.similarities, ...result.similarities },
        final: {},
        prefilter: result.prefilter,
        cost: prev.cost + result.cost.total
      }));
      setToast(failed
        ? { kind: 'error', text: `${failed} names got no verdict (judge errors) — run Judge again to retry them.` }
        : { kind: 'info', text: `Judged ${result.verdicts.length} names for ${formatCost(result.cost.total)}.` });
      setTab('results');
    } catch (err) {
      fail(err, 'Judging failed');
    } finally {
      setBusy(null);
      setProgress(null);
    }
  };

  const finalRound = async () => {
    const shortlist = [...judgedNames]
      .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
      .slice(0, finalSize)
      .map(v => v.name);
    setBusy('final');
    setProgress(null);
    try {
      const result = await apiService.finalRound({
        names: shortlist,
        description: llm.description || '',
        keywords,
        guidance: llm.guidance || '',
        model: llm.final_model || 'anthropic/claude-sonnet-5.5'
      });
      setSession(prev => ({
        ...prev,
        final: Object.fromEntries(result.ranking.map(entry => [entry.name, entry])),
        cost: prev.cost + result.cost
      }));
      setToast({ kind: 'info', text: `Final round ranked the top ${shortlist.length} for ${formatCost(result.cost)}.` });
      setTab('results');
    } catch (err) {
      fail(err, 'Final round failed');
    } finally {
      setBusy(null);
    }
  };

  // ⌘/Ctrl+Enter generates from anywhere
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && !generating && !busy) {
        e.preventDefault();
        startGeneration();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const shortlistCount = Object.keys(ratings).length;
  const nWords = config.generation?.n_words || 20;
  const tabs: { id: Tab; label: string; step?: number; count?: number }[] = [
    { id: 'sources', label: 'Sources', step: 1 },
    { id: 'sampling', label: 'Sampling', step: 2 },
    { id: 'judge', label: 'Judge', step: 3 },
    { id: 'results', label: 'Results', count: session.rows.length },
    { id: 'shortlist', label: 'Shortlist', count: shortlistCount }
  ];

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1 className="app-title">The Name<span className="title-accent">forge</span></h1>
          <p className="app-subtitle">
            Statistics invent the names, AI judges them, and you pick.
          </p>
        </div>
        <div className="session-chips">
          <span className="chip"><strong>{session.rows.length.toLocaleString()}</strong> names</span>
          <span className="chip"><strong>{judgedNames.length.toLocaleString()}</strong> judged</span>
          <span className="chip"><strong>{shortlistCount}</strong> shortlisted</span>
          <span className="chip" title="AI spend this session (embeddings + judges + final round)">
            <strong>{formatCost(session.cost)}</strong> spent
          </span>
        </div>
      </header>

      <div className="action-bar">
        <div className="action-group">
          <button className="btn btn-primary" onClick={startGeneration} disabled={generating}
            title="Sample a fresh batch from the Markov model (⌘/Ctrl+Enter)">
            <Play size={14} /> Generate {nWords.toLocaleString()}
          </button>
          <span className="action-arrow">→</span>
          <button className="btn btn-secondary" onClick={vibeRank} disabled={!names.length || !!busy}
            title="Rank every name by embedding similarity to your vibe keywords — near-free, no LLM">
            {busy === 'vibe' ? <span className="loading-spinner-small" /> : <Sparkles size={14} />} Vibe rank
          </button>
          <span className="action-arrow">→</span>
          <button className="btn btn-primary" onClick={judge} disabled={!names.length || !!busy}
            title={`Score names with the judge panel (${judges.length} model${judges.length > 1 ? 's' : ''})` +
              (keywords ? `; the vibe prefilter picks the top ${judgeLimit}` : '')}>
            {busy === 'judge' ? <span className="loading-spinner-small" /> : <Gavel size={14} />}
            Judge {keywords ? `top ${Math.min(judgeLimit, names.length || judgeLimit)}` : Math.min(judgeLimit, names.length || judgeLimit)}
          </button>
          <span className="action-arrow">→</span>
          <button className="btn btn-secondary" onClick={finalRound} disabled={judgedNames.length < 2 || !!busy}
            title="A stronger model compares the best-scored names head to head and pitches each">
            {busy === 'final' ? <span className="loading-spinner-small" /> : <Trophy size={14} />}
            Final round{judgedNames.length >= 2 && ` (top ${Math.min(finalSize, judgedNames.length)})`}
          </button>
        </div>
        <div className="action-group">
          <button className="btn btn-ghost" onClick={() => setConfigModal(true)} title="Save or load a named config">
            <Save size={14} /><FolderOpen size={14} /> Configs
          </button>
        </div>
        {busy && (
          <div className="action-progress">
            <div className="progress-meta">
              <span>{progress ? `${progress.label} ${progress.done}/${progress.total}` : busy === 'final' ? 'the jury is deliberating…' : 'working…'}</span>
              <span>{progress ? `${Math.round((progress.done / Math.max(progress.total, 1)) * 100)}%` : ''}</span>
            </div>
            <div className="progress-track">
              <div className={`progress-fill ${progress ? '' : 'indeterminate'}`}
                style={{ width: progress ? `${Math.min((progress.done / Math.max(progress.total, 1)) * 100, 100)}%` : '30%' }} />
            </div>
          </div>
        )}
      </div>

      {toast && (
        <div className={`toast toast-${toast.kind}`} role="status">
          <span>{toast.text}</span>
          <button className="toast-close" onClick={() => setToast(null)} aria-label="Dismiss"><X size={14} /></button>
        </div>
      )}

      <nav className="tab-container">
        <ul className="tab-list">
          {tabs.map(t => (
            <li key={t.id}>
              <button className={`tab-button ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>
                {t.step && <span className="tab-step">{t.step}</span>}
                {t.label}
                {t.count !== undefined && t.count > 0 && <span className="tab-count">{t.count.toLocaleString()}</span>}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <main className="tab-content">
        {tab === 'sources' && <TrainingDataTab config={config} patchConfig={patchConfig} />}
        {tab === 'sampling' && <SamplingParametersTab config={config} patchConfig={patchConfig} />}
        {tab === 'judge' && <AITab config={config} patchConfig={patchConfig} models={models} nameCount={names.length} />}
        {tab === 'results' && (
          <ResultsTab
            rows={session.rows}
            verdicts={session.verdicts}
            similarities={session.similarities}
            final={session.final}
            ratings={ratings}
            onRate={rate}
            genStats={session.genStats}
            prefilter={session.prefilter}
            simCutoff={llm.min_similarity}
            onGoTo={setTab}
          />
        )}
        {tab === 'shortlist' && (
          <SavedResultsTab ratings={ratings} setRatings={setRatings} verdicts={session.verdicts}
            final={session.final} onRate={rate} onError={err => fail(err, 'Shortlist update failed')} />
        )}
      </main>

      {generating && (
        <GenerationProgressModal config={config} onFinish={finishGeneration} />
      )}

      {configModal && (
        <ConfigFilesModal
          config={config}
          onClose={() => setConfigModal(false)}
          onLoaded={(loaded, filename) => {
            replaceConfig(loaded);
            setToast({ kind: 'info', text: `Loaded ${filename}.` });
          }}
          onSaved={filename => setToast({ kind: 'info', text: `Saved as ${filename}.` })}
          onError={err => fail(err, 'Config operation failed')}
        />
      )}
    </div>
  );
}

export default App;
