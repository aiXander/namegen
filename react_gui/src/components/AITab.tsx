import React from 'react';
import { Check } from 'lucide-react';
import { Config, ModelInfo } from '../services/api';
import { formatCost, shortModel } from '../lib/names';

interface AITabProps {
  config: Config;
  patchConfig: <K extends keyof Config>(section: K, patch: Partial<NonNullable<Config[K]>>) => void;
  models: ModelInfo[];
  nameCount: number;
}

const DEFAULT_JUDGES = ['anthropic/claude-haiku-5.5', 'openai/gpt-6-luna'];

// Rough token budget per judge call, for the cost estimate: the fixed system
// prompt + brief per chunk, and a ~45-token verdict per name (~8 for the
// quick screen's bare score, 50 names per call).
const SYSTEM_TOKENS = 420;
const TOKENS_PER_NAME_IN = 4;
const TOKENS_PER_NAME_OUT = 45;
const SCREEN_TOKENS_OUT = 8;
const SCREEN_CHUNK = 50;

const priceLabel = (m?: ModelInfo) =>
  m?.price ? `$${m.price.prompt.toFixed(2)} / $${m.price.completion.toFixed(2)} per M` : 'price unknown';

const AITab: React.FC<AITabProps> = ({ config, patchConfig, models, nameCount }) => {
  const llm = config.llm || {};
  const judges = llm.judges?.length ? llm.judges : DEFAULT_JUDGES;
  const maxNames = config.ai_settings?.max_names ?? 200;
  const chunkSize = llm.chunk_size ?? 20;
  const finalModel = llm.final_model || 'anthropic/claude-sonnet-5.5';
  const finalSize = llm.final_size ?? 25;
  const byId = Object.fromEntries(models.map(m => [m.id, m]));
  const modelIds = models.length ? models.map(m => m.id) : Array.from(new Set([...judges, finalModel]));

  const toggleJudge = (id: string) => {
    const next = judges.includes(id) ? judges.filter(j => j !== id) : [...judges, id];
    if (next.length) patchConfig('llm', { judges: next });
  };

  // What one "Judge" click costs at the current settings
  const judged = Math.min(maxNames, nameCount || maxNames);
  const screened = nameCount > maxNames ? nameCount : 0;
  const briefTokens = SYSTEM_TOKENS + Math.round(((llm.description || '') + (llm.guidance || '')).split(/\s+/).length * 1.4) + 300;
  const callCost = (names: number, perCall: number, outPerName: number, price: { prompt: number; completion: number }) =>
    ((Math.ceil(names / perCall) * briefTokens + names * TOKENS_PER_NAME_IN) * price.prompt +
      names * outPerName * price.completion) / 1e6;
  const estimate = judges.reduce((sum, id) => {
    const price = byId[id]?.price;
    if (!price) return sum;
    return sum + callCost(judged, chunkSize, TOKENS_PER_NAME_OUT, price) +
      callCost(screened, SCREEN_CHUNK, SCREEN_TOKENS_OUT, price);
  }, 0);

  return (
    <div className="judge-layout">
      <div className="space-y-4">
        <section className="card">
          <div className="card-header">Quick screen</div>
          <p className="field-help mb-2">
            Generating thousands of names is free; judging them properly is not. When there are more names than
            this, every judge first gives each one a bare 0–10 score (50 per call, about a sixth of the cost of a
            full verdict) and only the best go to the panel. The brief lives in the <strong>Brief</strong> tab.
          </p>
          <div className="form-group">
            <label className="form-label">
              Names that get a full verdict: <strong>{maxNames.toLocaleString()}</strong>
              <span className="text-muted">
                {nameCount > maxNames ? ` (screened from ${nameCount.toLocaleString()})` : ' (no screen needed)'}
              </span>
            </label>
            <input type="range" className="range-slider w-full" min={10} max={2000} step={10} value={maxNames}
              onChange={e => patchConfig('ai_settings', { max_names: Number(e.target.value) })} />
            <p className="field-help">
              In testing, keeping the top sixth kept 75% of the names the panel rated 5+ and 90% of those rated 6+.
            </p>
          </div>
        </section>

        <section className="card">
          <div className="card-header">Judge panel</div>
          <p className="field-help mb-2">
            Each judge scores every name from its own shuffled batches, and a name's score is the panel mean. More judges
            means less noise. Fast, cheap models are ideal here.
          </p>
          <div className="model-list">
            {modelIds.map(id => {
              const on = judges.includes(id);
              return (
                <button key={id} className={`model-option ${on ? 'on' : ''}`} onClick={() => toggleJudge(id)}>
                  <span className="model-check">{on && <Check size={12} />}</span>
                  <span className="model-name">{shortModel(id)}</span>
                  <span className="model-meta">{id.split('/')[0]} · {priceLabel(byId[id])}</span>
                </button>
              );
            })}
          </div>
          <div className="estimate">
            {screened > 0 && `Screening ${screened.toLocaleString()} and `}
            Judging {judged.toLocaleString()} names with {judges.length} judge{judges.length > 1 ? 's' : ''} ≈{' '}
            <strong>{estimate ? formatCost(estimate) : '?'}</strong>
          </div>
          <div className="form-group mt-4">
            <label className="form-label">Names per call: <strong>{chunkSize}</strong></label>
            <input type="range" className="range-slider w-full" min={5} max={50} value={chunkSize}
              onChange={e => patchConfig('llm', { chunk_size: Number(e.target.value) })} />
            <p className="field-help">Smaller calls give more independent verdicts but repeat the brief more often.</p>
          </div>
        </section>
      </div>

      <div className="space-y-4">
        <section className="card">
          <div className="card-header">Final round</div>
          <p className="field-help mb-2">
            One stronger model compares the best-scored names head to head, ranks them, and pitches each one.
            LLMs are much better at comparing names than at scoring them in isolation. Near-duplicate spellings
            are skipped, so the shortlist compares different ideas.
          </p>
          <div className="grid grid-cols-2 gap-4">
            <div className="form-group">
              <label className="form-label">Model</label>
              <select className="form-select" value={finalModel}
                onChange={e => patchConfig('llm', { final_model: e.target.value })}>
                {modelIds.map(id => <option key={id} value={id}>{shortModel(id)}</option>)}
              </select>
              <p className="field-help">{priceLabel(byId[finalModel])}</p>
            </div>
            <div className="form-group">
              <label className="form-label">Shortlist size: <strong>{finalSize}</strong></label>
              <input type="range" className="range-slider w-full" min={5} max={60} value={finalSize}
                onChange={e => patchConfig('llm', { final_size: Number(e.target.value) })} />
            </div>
          </div>
        </section>

        <section className="card">
          <div className="card-header">Embedding model <span className="text-muted">(Vibe rank only)</span></div>
          <input className="form-input" value={llm.embedding_model || ''}
            onChange={e => patchConfig('llm', { embedding_model: e.target.value })}
            placeholder="openai/text-embedding-3-large" />
          <p className="field-help">
            Fills the optional Vibe column: similarity to your vibe words. A weak signal on invented words, so it
            no longer decides what gets judged. Any OpenRouter embedding model. Must be allowed by your OpenRouter privacy settings (the old
            google/gemini-embedding-2 default is blocked by zero-data-retention).
          </p>
        </section>
      </div>
    </div>
  );
};

export default AITab;
