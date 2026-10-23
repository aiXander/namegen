import React, { useState } from 'react';
import { BookOpen, Plus, X } from 'lucide-react';
import { apiService, Config, errorMessage, LexiconEntry } from '../services/api';
import { formatCost } from '../lib/names';

interface BriefTabProps {
  config: Config;
  patchConfig: <K extends keyof Config>(section: K, patch: Partial<NonNullable<Config[K]>>) => void;
  onSpend: (usd: number, message: string) => void;
  onError: (message: string) => void;
}

const DEFAULT_SHARE = 0.5;

const BriefTab: React.FC<BriefTabProps> = ({ config, patchConfig, onSpend, onError }) => {
  const llm = config.llm || {};
  const lexicon: LexiconEntry[] = config.training_data?.lexicon || [];
  const share = config.training_data?.lexicon_share ?? DEFAULT_SHARE;
  const [collecting, setCollecting] = useState(false);

  const setLexicon = (next: LexiconEntry[]) => patchConfig('training_data', { lexicon: next });

  const collect = async () => {
    if (!(llm.description || '').trim()) {
      onError('Write the brief first: the lexicon is collected from it.');
      return;
    }
    setCollecting(true);
    try {
      const result = await apiService.lexicon({
        description: llm.description || '',
        keywords: llm.keywords || '',
        guidance: llm.guidance || '',
        exclude: lexicon.map(e => e.word)
      });
      setLexicon([...lexicon, ...result.words]);
      onSpend(result.cost, `Added ${result.words.length} words to the lexicon for ${formatCost(result.cost)}.`);
    } catch (err) {
      onError(errorMessage(err, 'Collecting the lexicon failed'));
    } finally {
      setCollecting(false);
    }
  };

  return (
    <div className="judge-layout">
      <section className="card">
        <div className="card-header">The brief</div>
        <label className="form-label">What is the name for? What should it feel like, and what should it hint at?</label>
        <textarea
          className="form-textarea"
          rows={7}
          value={llm.description || ''}
          onChange={e => patchConfig('llm', { description: e.target.value })}
          placeholder="e.g. An AI agent that acts as the collective memory of a community. Warm, organic, grounded; ideally hints at many minds acting as one."
        />
        <label className="form-label mt-4">Vibe words</label>
        <input
          className="form-input"
          value={llm.keywords || ''}
          onChange={e => patchConfig('llm', { keywords: e.target.value })}
          placeholder="e.g. murmuration, mycelium, chorus, hearth"
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
          The brief steers everything: the lexicon below, the judges, and the final round. Your star ratings go
          along as taste examples (dislikes too), so rating a handful of names calibrates the judges to you.
        </p>
      </section>

      <section className="card">
        <div className="card-header">Brief lexicon</div>
        <p className="field-help mb-2">
          Real words and roots for the brief's ideas, in many languages. They get mixed into the Markov training
          data, so the invented names carry echoes of meaning (<em>flokahi</em> from Old Norse <em>flokkr</em> and
          Hawaiian <em>lokahi</em>). The model still invents every name; the AI only looks up words. In testing
          this doubled the names the judges rated 5+.
        </p>
        <div className="flex items-center gap-2 mb-2">
          <button className="btn btn-primary btn-small" onClick={collect} disabled={collecting}>
            {collecting ? <span className="loading-spinner-small" /> : lexicon.length ? <Plus size={13} /> : <BookOpen size={13} />}
            {lexicon.length ? 'More words' : 'Collect words from the brief'}
          </button>
          {lexicon.length > 0 && (
            <button className="btn btn-ghost btn-small" onClick={() => setLexicon([])}>Clear</button>
          )}
          <div className="toolbar-spacer" />
          <span className="text-muted text-sm">{lexicon.length} words</span>
        </div>
        <div className="form-group">
          <label className="form-label">
            Share of the training data: <strong>{Math.round(share * 100)}%</strong>
            {!lexicon.length && <span className="text-muted"> (no words yet)</span>}
          </label>
          <input type="range" className="range-slider w-full" min={0} max={0.9} step={0.05} value={share}
            onChange={e => patchConfig('training_data', { lexicon_share: Number(e.target.value) })} />
          <p className="field-help">
            The word lists in Sources share the rest. Around 50% worked best; above ~70% names start to read as
            respellings of real words.
          </p>
        </div>
        {lexicon.length > 0 && (
          <div className="lexicon-chips">
            {lexicon.map(entry => (
              <span key={entry.word} className="lexicon-chip"
                title={[entry.lang, entry.meaning].filter(Boolean).join(': ')}>
                {entry.word}
                <button aria-label={`Remove ${entry.word}`}
                  onClick={() => setLexicon(lexicon.filter(e => e.word !== entry.word))}><X size={11} /></button>
              </span>
            ))}
          </div>
        )}
      </section>
    </div>
  );
};

export default BriefTab;
