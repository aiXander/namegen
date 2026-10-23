import React, { useEffect, useRef, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { apiService, Config, NameRow } from '../services/api';
import { titleCase } from '../lib/names';

interface SamplingParametersTabProps {
  config: Config;
  patchConfig: <K extends keyof Config>(section: K, patch: Partial<NonNullable<Config[K]>>) => void;
}

const MAX_LEN = 24;
const PREVIEW_SIZE = 18;

const parseList = (text: string) => text.split(',').map(t => t.trim()).filter(Boolean);
const parseInts = (text: string) => parseList(text).map(Number).filter(n => Number.isInteger(n));

/** Comma-separated list input that keeps the raw text while typing (deriving
 *  the value from the parsed list made a trailing comma un-typable) and only
 *  re-syncs when the config changes from elsewhere, e.g. loading a config. */
const ListInput: React.FC<{
  value: (string | number)[] | undefined;
  parse: (text: string) => (string | number)[];
  onChange: (parsed: any[]) => void;
  placeholder: string;
  disabled?: boolean;
}> = ({ value, parse, onChange, placeholder, disabled }) => {
  const [text, setText] = useState((value || []).join(', '));
  useEffect(() => {
    if (JSON.stringify(parse(text)) !== JSON.stringify(value || [])) setText((value || []).join(', '));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(value)]);
  return (
    <input className="form-input" value={text} placeholder={placeholder} disabled={disabled}
      onChange={e => { setText(e.target.value); onChange(parse(e.target.value)); }} />
  );
};

const SamplingParametersTab: React.FC<SamplingParametersTabProps> = ({ config, patchConfig }) => {
  const model = { order: 3, temperature: 1.0, backoff: true, ...config.model };
  const gen = { n_words: 200, min_length: 4, max_length: 12, starts_with: '', ends_with: '', includes: '', excludes: '', ...config.generation };
  const filters = { remove_duplicates: true, exclude_training_words: true, min_edit_distance: 0, ...config.filtering };
  const setModel = (patch: Partial<typeof model>) => patchConfig('model', patch);
  const setGen = (patch: Partial<NonNullable<Config['generation']>>) => patchConfig('generation', patch);
  const setFilters = (patch: Partial<NonNullable<Config['filtering']>>) => patchConfig('filtering', patch);
  const hasComponents = !!gen.components?.length;

  // Live preview: re-sample a handful of names whenever anything that shapes
  // them changes (debounced; a newer preview aborts the stale one).
  const [preview, setPreview] = useState<NameRow[]>([]);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [nonce, setNonce] = useState(0);
  const previewAbort = useRef<AbortController | null>(null);
  const shapeKey = JSON.stringify([config.training_data, config.model, config.generation, config.filtering]);

  useEffect(() => {
    if (!config.training_data?.sources?.length) {
      setPreview([]);
      setPreviewError('Pick some word lists in Sources to see a preview.');
      return;
    }
    const timer = setTimeout(async () => {
      previewAbort.current?.abort();
      const abort = new AbortController();
      previewAbort.current = abort;
      const rows: NameRow[] = [];
      setPreviewing(true);
      try {
        await apiService.generateStream(
          { ...config, generation: { ...gen, n_words: PREVIEW_SIZE, max_time_per_name: 0.3 } },
          row => rows.push(row), abort.signal);
        setPreview(rows);
        setPreviewError(rows.length ? null : 'No names fit these constraints. Loosen them a little.');
      } catch (err: any) {
        if (err?.name !== 'AbortError') setPreviewError(err?.message || 'Preview failed');
      } finally {
        if (previewAbort.current === abort) setPreviewing(false);
      }
    }, 600);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shapeKey, nonce]);

  useEffect(() => () => previewAbort.current?.abort(), []);

  return (
    <div className="sampling-layout">
      <div className="space-y-4">
        <section className="card">
          <div className="card-header">Batch</div>
          <div className="grid grid-cols-2 gap-4">
            <div className="form-group">
              <label className="form-label">Names to generate</label>
              <input type="number" className="form-input" min={1} max={20000} value={gen.n_words}
                onChange={e => setGen({ n_words: Math.max(1, Number(e.target.value) || 1) })} />
              <p className="field-help">Generate thousands; the vibe prefilter and judges sort them out.</p>
            </div>
            <div className="form-group">
              <label className="form-label">Length: <strong>{gen.min_length}–{gen.max_length}</strong> letters</label>
              <div className="dual-range-container mt-2">
                <div className="dual-range-track">
                  <div className="dual-range-progress" style={{
                    left: `${((gen.min_length - 1) / (MAX_LEN - 1)) * 100}%`,
                    right: `${100 - ((gen.max_length - 1) / (MAX_LEN - 1)) * 100}%`
                  }} />
                </div>
                <input type="range" className="dual-range-slider" min={1} max={MAX_LEN} value={gen.min_length}
                  onChange={e => setGen({ min_length: Math.min(Number(e.target.value), gen.max_length) })} />
                <input type="range" className="dual-range-slider" min={1} max={MAX_LEN} value={gen.max_length}
                  onChange={e => setGen({ max_length: Math.max(Number(e.target.value), gen.min_length) })} />
              </div>
            </div>
          </div>
        </section>

        <section className="card">
          <div className="card-header">Shape</div>
          <div className="grid grid-cols-2 gap-4">
            <div className="form-group">
              <label className="form-label">Starts with</label>
              <input className="form-input" value={gen.starts_with} placeholder="e.g. lu"
                onChange={e => setGen({ starts_with: e.target.value })} />
            </div>
            <div className="form-group">
              <label className="form-label">Ends with</label>
              <input className="form-input" value={gen.ends_with} placeholder="e.g. a"
                onChange={e => setGen({ ends_with: e.target.value })} />
            </div>
            <div className="form-group">
              <label className="form-label">Includes</label>
              <input className="form-input" value={gen.includes} placeholder="e.g. co · an,er · tech;bio"
                onChange={e => setGen({ includes: e.target.value })} />
              <p className="field-help">
                <code>a,b</code> both · <code>a;b</code> either · a <strong>space</strong> makes two words
                (<code>co </code> + ends with <code>a</code> → “code noda”)
              </p>
            </div>
            <div className="form-group">
              <label className="form-label">Excludes</label>
              <input className="form-input" value={gen.excludes} placeholder="e.g. x, tion"
                onChange={e => setGen({ excludes: e.target.value })} />
              <p className="field-help">Comma-separated substrings that may never appear.</p>
            </div>
          </div>

          <details className="advanced" open={hasComponents}>
            <summary>Fixed components</summary>
            <p className="field-help mb-2">
              Parts that must appear verbatim, with Markov-sampled letters filling the gaps around them
              (<code>co, mind</code> → “cobramind”, “mindecor”).
            </p>
            <div className="form-group">
              <label className="form-label">Components</label>
              <ListInput value={gen.components} parse={parseList} placeholder="e.g. co, mind"
                onChange={parts => setGen({ components: parts.length ? parts : undefined })} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="form-group">
                <label className="form-label">Order <span className="text-muted">(indices)</span></label>
                <ListInput value={gen.component_order} parse={parseInts} placeholder="any order, or e.g. 1, 0"
                  disabled={!hasComponents}
                  onChange={order => setGen({ component_order: order.length ? order : undefined })} />
              </div>
              <div className="form-group">
                <label className="form-label">Letters between <span className="text-muted">(min, max)</span></label>
                <ListInput value={gen.component_separation || [0, 3]} parse={parseInts} placeholder="0, 3"
                  disabled={!hasComponents}
                  onChange={sep => { if (sep.length === 2) setGen({ component_separation: sep as [number, number] }); }} />
              </div>
            </div>
          </details>
        </section>

        <section className="card">
          <div className="card-header">Novelty filters</div>
          <div className="toggle-row">
            <label className="checkbox-container">
              <input type="checkbox" checked={filters.exclude_training_words}
                onChange={e => setFilters({ exclude_training_words: e.target.checked })} />
              <span>Drop real training words</span>
            </label>
            <label className="checkbox-container">
              <input type="checkbox" checked={filters.remove_duplicates}
                onChange={e => setFilters({ remove_duplicates: e.target.checked })} />
              <span>Drop duplicates</span>
            </label>
          </div>
          <div className="form-group mt-4">
            <label className="form-label">
              Minimum distance from any training word: <strong>{filters.min_edit_distance || 'off'}</strong>
            </label>
            <input type="range" className="range-slider w-full" min={0} max={5} value={filters.min_edit_distance || 0}
              onChange={e => setFilters({ min_edit_distance: Number(e.target.value) })} />
            <p className="field-help">
              Edits (insert, delete or swap a letter) needed to reach the nearest real word. 2 drops near-copies like
              “rayquarka”; higher forces more invention but rejects more samples.
            </p>
          </div>
        </section>
      </div>

      <div className="space-y-4">
        <section className="card">
          <div className="card-header">Model</div>
          <div className="form-group">
            <label className="form-label">Memory (order): <strong>{model.order}</strong> letters</label>
            <input type="range" className="range-slider w-full" min={1} max={6} value={model.order}
              onChange={e => setModel({ order: Number(e.target.value) })} />
            <div className="scale-labels"><span>wild, less word-like</span><span>faithful, more copying</span></div>
            <p className="field-help">How many previous letters predict the next one. 3 is the sweet spot for most lists.</p>
          </div>
          <div className="form-group">
            <label className="form-label">Temperature: <strong>{model.temperature.toFixed(2)}</strong></label>
            <input type="range" className="range-slider w-full" min={0.1} max={3} step={0.05} value={model.temperature}
              onChange={e => setModel({ temperature: Number(e.target.value) })} />
            <div className="scale-labels"><span>safe, common patterns</span><span>adventurous</span></div>
            <p className="field-help">
              1.0 samples the training statistics as-is. Higher boosts rare letter transitions, but only ones that occur
              in the data, so names stay pronounceable.
            </p>
          </div>
          <label className="checkbox-container">
            <input type="checkbox" checked={model.backoff} onChange={e => setModel({ backoff: e.target.checked })} />
            <span>Backoff to shorter memory for unseen letter combinations <span className="text-muted">(recommended)</span></span>
          </label>
        </section>

        <section className="card preview-card">
          <div className="card-header flex items-center justify-between">
            <span>Live preview</span>
            <button className="icon-button" onClick={() => setNonce(n => n + 1)} title="Resample">
              <RefreshCw size={14} className={previewing ? 'spin' : ''} />
            </button>
          </div>
          {previewError ? (
            <p className="text-muted text-sm">{previewError}</p>
          ) : (
            <div className="preview-names">
              {preview.map(row => (
                <span key={row.name} className="name-chip"
                  title={`naturalness ${row.naturalness ?? '?'}/100 · nearest training word: ${row.nearest ?? '?'} (+${row.distance ?? '?'})`}>
                  {titleCase(row.name)}
                </span>
              ))}
            </div>
          )}
          <p className="field-help mt-2">Updates as you tweak. Hover a name to see where it came from.</p>
        </section>
      </div>
    </div>
  );
};

export default SamplingParametersTab;
