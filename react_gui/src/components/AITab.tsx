import React, { useState, useEffect } from 'react';
import { apiService, ScoredName } from '../services/api';

interface AITabProps {
  config: any;
  onConfigChange: (config: any) => void;
  results: string[];
  ratings: Record<string, number>;
  onAIResults: (results: ScoredName[]) => void;
  selectedSources: string[];
  minScore: number;
  maxScore: number;
}

const AITab: React.FC<AITabProps> = ({ 
  config, 
  onConfigChange, 
  results, 
  ratings,
  onAIResults,
  selectedSources,
  minScore,
  maxScore 
}) => {
  const [description, setDescription] = useState('');
  const [keywords, setKeywords] = useState('');
  const [instructions, setInstructions] = useState('');
  const [aiModels, setAIModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState('google/gemini-3.1-flash-lite-preview');
  const [maxNames, setMaxNames] = useState(20);
  const [chunkSize, setChunkSize] = useState(10);
  const [minSimilarity, setMinSimilarity] = useState(0);

  // Initialize local state from config once on mount. Depending on `config`
  // here caused the effect (including the loadAIModels API call) to re-run on
  // every keystroke, since each onChange pushes a new config object upstream.
  useEffect(() => {
    loadAIModels();

    // Load default instructions and description from config
    const llmConfig = config.llm || {};
    if (llmConfig.default_instructions) {
      setInstructions(llmConfig.default_instructions);
    } else {
      setInstructions('Based on the provided description and scored names, score the following generated name ideas on a scale of 0 to 5, where 5 is excellent and 0 is poor (use integer scores). Consider factors like memorability, relevance, uniqueness, and overall appeal. Reply with the scores as a JSON dict where keys are the actual name strings and values are the scores. Example: {"aurick": 3, "mindflow": 4, "nexus": 0, "collective": 3}');
    }
    
    if (llmConfig.description) {
      setDescription(llmConfig.description);
    }

    if (llmConfig.keywords) {
      setKeywords(llmConfig.keywords);
    }

    if (llmConfig.min_similarity) {
      setMinSimilarity(llmConfig.min_similarity);
    }

    if (llmConfig.model) {
      setSelectedModel(llmConfig.model);
    } else {
      // If no model is set in config, set the default and update config
      const defaultModel = 'google/gemini-3.1-flash-lite-preview';
      setSelectedModel(defaultModel);
      const updatedConfig = {
        ...config,
        llm: {
          ...config.llm,
          model: defaultModel
        }
      };
      onConfigChange(updatedConfig);
    }
    
    if (llmConfig.max_chunk_size) {
      setChunkSize(llmConfig.max_chunk_size);
    }
    
    // Load max_names from config
    if (config.ai_settings?.max_names) {
      setMaxNames(config.ai_settings.max_names);
    } else if (llmConfig.max_names) {
      setMaxNames(llmConfig.max_names);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadAIModels = async () => {
    try {
      const response = await apiService.getAIModels();
      setAIModels(response.models);
    } catch (err) {
      console.error('Failed to load AI models:', err);
      setAIModels(['google/gemini-3.1-flash-lite-preview']);
    }
  };


  return (
    <div>
      <h2 className="text-xl font-bold mb-4">AI-Powered Name Scoring</h2>

      {/* Description */}
      <div className="card mb-4">
        <div className="card-header">Description</div>
        <div className="form-group">
          <label className="form-label">
            What are these names for? (e.g., company, website, product)
          </label>
          <textarea
            value={description}
            onChange={(e) => {
              setDescription(e.target.value);
              // Update config when description changes
              const updatedConfig = {
                ...config,
                llm: {
                  ...config.llm,
                  description: e.target.value
                }
              };
              onConfigChange(updatedConfig);
            }}
            className="form-textarea"
            placeholder="Describe what these names are for..."
            rows={3}
          />
        </div>
      </div>

      {/* Vibe Keywords (embedding prefilter) */}
      <div className="card mb-4">
        <div className="card-header">Vibe Keywords (embedding pre-filter)</div>
        <div className="form-group">
          <label className="form-label">
            Comma-separated keywords matching the vibe/meaning you want. Trigger via
            the "Embed Rank" button (top-right) to rank all generated names by
            embedding similarity to these anchors — cheap, no LLM cost. They also
            act as a pre-filter for "AI Score Names": only the top "Max names to
            score" reach the LLM, so you can generate hundreds of candidates.
          </label>
          <input
            type="text"
            value={keywords}
            onChange={(e) => {
              setKeywords(e.target.value);
              const updatedConfig = {
                ...config,
                llm: {
                  ...config.llm,
                  keywords: e.target.value
                }
              };
              onConfigChange(updatedConfig);
            }}
            className="form-input"
            placeholder="e.g. murmuration, chorus, collective dreaming, organic"
          />
        </div>
        <div className="form-group">
          <label className="form-label">
            Min vibe similarity cutoff: {minSimilarity > 0 ? minSimilarity.toFixed(2) : 'off'}
          </label>
          <input
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={minSimilarity}
            onChange={(e) => {
              const value = parseFloat(e.target.value);
              setMinSimilarity(value);
              const updatedConfig = {
                ...config,
                llm: {
                  ...config.llm,
                  min_similarity: value
                }
              };
              onConfigChange(updatedConfig);
            }}
            className="range-slider w-full"
          />
          <div className="text-muted text-sm">
            Names below this embedding similarity never reach the LLM during
            "AI Score Names" — even if fewer than "Max names to score" remain.
            Run "Embed Rank" first and check the Vibe Sim column to pick a sensible
            value. 0 disables the cutoff.
          </div>
        </div>
      </div>

      {/* Instructions */}
      <div className="card mb-4">
        <div className="card-header">Instructions</div>
        <div className="form-group">
          <textarea
            value={instructions}
            onChange={(e) => {
              setInstructions(e.target.value);
              // Update config when instructions change
              const updatedConfig = {
                ...config,
                llm: {
                  ...config.llm,
                  default_instructions: e.target.value
                }
              };
              onConfigChange(updatedConfig);
            }}
            className="form-textarea"
            rows={4}
          />
        </div>
      </div>

      {/* Settings */}
      <div className="card mb-4">
        <div className="card-header">Settings</div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="form-group">
            <label className="form-label">LLM Model</label>
            <select
              value={selectedModel}
              onChange={(e) => {
                const newModel = e.target.value;
                setSelectedModel(newModel);
                // Update config when model changes
                const updatedConfig = {
                  ...config,
                  llm: {
                    ...config.llm,
                    model: newModel
                  }
                };
                onConfigChange(updatedConfig);
              }}
              className="form-select"
            >
              {/* Keep the configured model selectable even if it's not in the
                  list served from config.yaml's llm.available_models */}
              {(aiModels.includes(selectedModel) ? aiModels : [selectedModel, ...aiModels]).map(model => (
                <option key={model} value={model}>{model}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Max names to score: {maxNames}</label>
            <input
              type="range"
              min="1"
              max="1000"
              value={maxNames}
              onChange={(e) => {
                const value = parseInt(e.target.value);
                setMaxNames(value);
                // Update config immediately
                const updatedConfig = {
                  ...config,
                  ai_settings: {
                    ...config.ai_settings,
                    max_names: value
                  }
                };
                onConfigChange(updatedConfig);
              }}
              className="range-slider w-full"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Max chunk size: {chunkSize}</label>
            <input
              type="range"
              min="1"
              max="50"
              value={chunkSize}
              onChange={(e) => {
                const value = parseInt(e.target.value);
                setChunkSize(value);
                // Update config when chunk size changes
                const updatedConfig = {
                  ...config,
                  llm: {
                    ...config.llm,
                    max_chunk_size: value
                  }
                };
                onConfigChange(updatedConfig);
              }}
              className="range-slider w-full"
            />
          </div>
        </div>


        {/* AI Score button is now in the main header */}
        <div className="text-muted text-sm">
          Use the "AI Score Names" button in the top-right corner to score generated names.
          {results.length === 0 && (
            <span> Generate some names first to enable AI scoring.</span>
          )}
        </div>

      </div>
    </div>
  );
};

export default AITab;