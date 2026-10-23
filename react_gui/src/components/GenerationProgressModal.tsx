import React, { useEffect, useRef, useState } from 'react';
import { apiService, Config, GenerationStats, NameRow } from '../services/api';

interface GenerationProgressModalProps {
  config: Config;
  /** Called once with whatever was generated (possibly partial when stopped). */
  onFinish: (rows: NameRow[], stats: GenerationStats | null) => void;
}

const LETTERS = 'abcdefghijklmnopqrstuvwxyz';

/** Streams a generation run, showing live progress; mounted only while running. */
const GenerationProgressModal: React.FC<GenerationProgressModalProps> = ({ config, onFinish }) => {
  const target = config.generation?.n_words || 20;
  const [rows, setRows] = useState<NameRow[]>([]);
  const [ticker, setTicker] = useState('');
  const [error, setError] = useState<string | null>(null);

  // Refs avoid stale closures in the streaming callbacks and make sure
  // onFinish fires exactly once per run.
  const rowsRef = useRef<NameRow[]>([]);
  const finished = useRef(false);
  const controller = useRef<AbortController | null>(null);

  const finish = (stats: GenerationStats | null) => {
    if (finished.current) return;
    finished.current = true;
    onFinish(rowsRef.current, stats);
  };

  useEffect(() => {
    // `cancelled` marks a run torn down by unmount (incl. StrictMode's dev
    // double-mount) — only a user Stop should deliver partial results.
    let cancelled = false;
    const abort = new AbortController();
    controller.current = abort;
    rowsRef.current = [];
    // Batch React updates: thousands of names can arrive within a second.
    const flush = setInterval(() => setRows([...rowsRef.current]), 100);
    apiService.generateStream(config, row => { rowsRef.current.push(row); }, abort.signal)
      .then(({ stats }) => { if (!cancelled) finish(stats); })
      .catch(err => {
        if (cancelled) return;
        if (err?.name === 'AbortError') finish(null);
        else setError(err?.message || 'Generation failed');
      })
      .finally(() => clearInterval(flush));
    return () => {
      cancelled = true;
      abort.abort();
      clearInterval(flush);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (error) return;
    const length = config.generation?.max_length || 10;
    const timer = setInterval(() => {
      setTicker(Array.from({ length }, () => LETTERS[Math.floor(Math.random() * LETTERS.length)]).join(''));
    }, 90);
    return () => clearInterval(timer);
  }, [error, config.generation?.max_length]);

  const stop = () => {
    if (error) onFinish([], null);
    else controller.current?.abort();
  };

  const percent = Math.min((rows.length / target) * 100, 100);

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ width: '560px', maxWidth: '90vw' }}>
        <div className="modal-header">
          <h2 className="modal-title">Forging names…</h2>
          <button onClick={stop} className="btn btn-danger btn-small">{error ? 'Close' : 'Stop'}</button>
        </div>
        <div className="space-y-6">
          {error && <div className="error-banner"><p className="error-message">{error}</p></div>}
          {!error && <div className="sampling-ticker">{ticker}</div>}
          <div>
            <div className="progress-meta">
              <span>forging {rows.length.toLocaleString()}/{target.toLocaleString()}</span>
              <span>{Math.round(percent)}%</span>
            </div>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${percent}%`, minWidth: percent > 0 ? '4px' : 0 }} />
            </div>
          </div>
          {rows.length > 0 && (
            <div className="recent-names-panel">
              <div className="panel-label">Fresh from the forge</div>
              <div className="fresh-names">
                {rows.slice(-8).reverse().map(row => (
                  <span key={row.name} className="name-chip">{row.name}</span>
                ))}
              </div>
            </div>
          )}
          <p className="text-muted text-xs">Stopping keeps everything forged so far.</p>
        </div>
      </div>
    </div>
  );
};

export default GenerationProgressModal;
