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
// prompt + brief per chunk, and a ~45-token verdict per name.
const SYSTEM_TOKENS = 420;
const TOKENS_PER_NAME_IN = 4;
const TOKENS_PER_NAME_OUT = 45;

const priceLabel = (m?: ModelInfo) =>
  m?.price ? `$${m.price.prompt.toFixed(2)} / $${m.price.completion.toFixed(2)} per M` : 'price unknown';

const AITab: React.FC<AITabProps> = ({ config, patchConfig, models, nameCount }) => {
  const llm = config.llm || {};
  const judges = llm.judges?.length ? llm.judges : DEFAULT_JUDGES;
  const maxNames = config.ai_settings?.max_names ?? 200;
  const chunkSize = llm.chunk_size ?? 20;
  const keywords = (llm.keywords || '').trim();
  const minSimilarity = llm.min_similarity ?? 0;
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
  const briefTokens = SYSTEM_TOKENS + Math.round(((llm.description || '') + (llm.guidance || '')).split(/\s+/).length * 1.4) + 300;
  const estimate = judges.reduce((sum, id) => {
    const price = byId[id]?.price;
    if (!price) return sum;
    const calls = Math.ceil(judged / chunkSize);
    const inTokens = calls * briefTokens + judged * TOKENS_PER_NAME_IN;
    return sum + (inTokens * price.prompt + judged * TOKENS_PER_NAME_OUT * price.completion) / 1e6;
  }, 0);

  return (
    <div className="judge-layout">
      <div className="space-y-4">
        <section className="card">
          <div className="card-header">The brief</div>
          <label className="form-label">What is the name for? What should it feel like, and what should it hint at?</label>
          <textarea
            className="form-textarea"
            rows={6}
            value={llm.description || ''}
            onChange={e => patchConfig('llm', { description: e.target.value })}
            placeholder="e.g. An AI agent that acts as the collective memory of a community. Warm, organic, grounded; ideally hints at many minds acting as one."
          />
          <label className="form-label mt-4">Extra guidance <span className="text-muted">(optional)</span></label>
          <textarea
            className="form-textarea"
            rows={2}
            value={llm.guidance || ''}
            onChange={e => patchConfig('llm', { guidance: e.target.value })}
            placeholder="e.g. Must be easy to say in Dutch and English. No -ify / -ly endings. Short beats long."
          />
          <p className="field-help">
            Your star ratings are sent along as taste examples (stratified, so dislikes count too). Rate a
            handful of names and the judges calibrate to you.
          </p>
        </section>

        <section className="card">
          <div className="card-header">Vibe prefilter</div>
          <label className="form-label">Vibe keywords</label>
          <input
            className="form-input"
            value={llm.keywords || ''}
            onChange={e => patchConfig('llm', { keywords: e.target.value })}
            placeholder="e.g. murmuration, mycelium, chorus, hearth"
          />
          <p className="field-help">
            Every name is embedded and compared to these anchors, which costs next to nothing. Use them to generate thousands
            of names and send only the most on-vibe ones to the judges. <strong>Vibe rank</strong> fills the Vibe
            column without judging.
          </p>
          <div className="form-group mt-4">
            <label className="form-label">
              Names per judging run: <strong>{maxNames.toLocaleString()}</strong>
              <span className="text-muted"> {keywords ? '(the top by vibe)' : '(no keywords: the first ones generated)'}</span>
            </label>
            <input type="range" className="range-slider w-full" min={10} max={2000} step={10} value={maxNames}
              onChange={e => patchConfig('ai_settings', { max_names: Number(e.target.value) })} />
          </div>
          <div className="form-group">
            <label className="form-label">
              Minimum vibe: <strong>{minSimilarity > 0 ? minSimilarity.toFixed(2) : 'off'}</strong>
            </label>
            <input type="range" className="range-slider w-full" min={0} max={1} step={0.01} value={minSimilarity}
              disabled={!keywords}
              onChange={e => patchConfig('llm', { min_similarity: Number(e.target.value) })} />
            <p className="field-help">
              Names below this never reach the judges and are dimmed in Results. Similarity scales differ per embedding
              model, so run Vibe rank first and read the Vibe column before setting this.
            </p>
          </div>
        </section>
      </div>

      <div className="space-y-4">
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

        <section className="card">
          <div className="card-header">Final round</div>
          <p className="field-help mb-2">
            One stronger model compares the best-scored names head to head, ranks them, and pitches each one.
            LLMs are much better at comparing names than at scoring them in isolation.
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
          <div className="card-header">Embedding model</div>
          <input className="form-input" value={llm.embedding_model || ''}
            onChange={e => patchConfig('llm', { embedding_model: e.target.value })}
            placeholder="openai/text-embedding-3-large" />
          <p className="field-help">
            Any OpenRouter embedding model. Must be allowed by your OpenRouter privacy settings (the old
            google/gemini-embedding-2 default is blocked by zero-data-retention).
          </p>
        </section>
      </div>
    </div>
  );
};

export default AITab;
