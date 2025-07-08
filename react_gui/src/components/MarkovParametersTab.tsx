import React from 'react';

interface MarkovParametersTabProps {
  config: any;
  onConfigChange: (config: any) => void;
}

const MarkovParametersTab: React.FC<MarkovParametersTabProps> = ({ config, onConfigChange }) => {
  const modelConfig = config.model || {};
  const generationConfig = config.generation || {};

  const updateModelConfig = (updates: any) => {
    onConfigChange({
      ...config,
      model: {
        ...modelConfig,
        ...updates
      }
    });
  };

  const updateGenerationConfig = (updates: any) => {
    onConfigChange({
      ...config,
      generation: {
        ...generationConfig,
        ...updates
      }
    });
  };

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">Markov Parameters</h2>
      
      {/* Model Parameters */}
      <div className="card mb-4">
        <div className="card-header">Model Parameters</div>
        
        {/* Model Order */}
        <div className="form-group">
          <label className="form-label">
            Model Order: {modelConfig.order || 3}
            <span className="text-muted text-sm ml-2">
              (How many letters to look back when predicting the next letter)
            </span>
          </label>
          <input
            type="range"
            min="1"
            max="6"
            value={modelConfig.order || 3}
            onChange={(e) => updateModelConfig({ order: parseInt(e.target.value) })}
            className="range-slider w-full"
          />
          <div className="text-sm text-muted mt-1">
            • Low (1-2): More creative, less realistic • High (3-5): More realistic, follows training data closely
          </div>
        </div>

        {/* Prior */}
        <div className="form-group">
          <label className="form-label">
            Prior (Creativity Factor): {(modelConfig.prior || 0.01).toFixed(4)}
            <span className="text-muted text-sm ml-2">
              (Controls randomness vs. following training patterns)
            </span>
          </label>
          <input
            type="range"
            min="0.001"
            max="0.1"
            step="0.001"
            value={modelConfig.prior || 0.01}
            onChange={(e) => updateModelConfig({ prior: parseFloat(e.target.value) })}
            className="range-slider w-full"
          />
          <div className="text-sm text-muted mt-1">
            • Low (0.001-0.01): Stick to training patterns • High (0.05-0.1): More creative and varied
          </div>
        </div>

        {/* Backoff */}
        <div className="form-group">
          <div className="checkbox-container">
            <input
              type="checkbox"
              checked={modelConfig.backoff !== false}
              onChange={(e) => updateModelConfig({ backoff: e.target.checked })}
            />
            <label className="form-label">
              Use Backoff
              <span className="text-muted text-sm ml-2">
                (Fall back to simpler patterns when complex ones aren't found)
              </span>
            </label>
          </div>
          <div className="text-sm text-muted mt-1">
            • Enabled: More reliable generation, smoother names • Disabled: Stricter patterns, may fail occasionally
          </div>
        </div>
      </div>

      {/* Generation Parameters */}
      <div className="card mb-4">
        <div className="card-header">Generation Settings</div>
        
        <div className="form-group">
          <label className="form-label">Number of Names</label>
          <input
            type="number"
            min="1"
            max="100"
            value={generationConfig.n_words || 20}
            onChange={(e) => updateGenerationConfig({ n_words: parseInt(e.target.value) })}
            className="form-input"
          />
        </div>
      </div>

      {/* Length Constraints */}
      <div className="card mb-4">
        <div className="card-header">Length Constraints</div>
        
        <div className="grid grid-cols-2 gap-4">
          <div className="form-group">
            <label className="form-label">Min Length</label>
            <input
              type="number"
              min="1"
              max="20"
              value={generationConfig.min_length || 4}
              onChange={(e) => updateGenerationConfig({ min_length: parseInt(e.target.value) })}
              className="form-input"
            />
          </div>
          
          <div className="form-group">
            <label className="form-label">Max Length</label>
            <input
              type="number"
              min="1"
              max="20"
              value={generationConfig.max_length || 12}
              onChange={(e) => updateGenerationConfig({ max_length: parseInt(e.target.value) })}
              className="form-input"
            />
          </div>
        </div>
      </div>

      {/* Content Constraints */}
      <div className="card">
        <div className="card-header">Content Constraints</div>
        
        <div className="grid grid-cols-2 gap-4">
          <div className="form-group">
            <label className="form-label">Starts with</label>
            <input
              type="text"
              value={generationConfig.starts_with || ''}
              onChange={(e) => updateGenerationConfig({ starts_with: e.target.value })}
              className="form-input"
              placeholder="e.g., 'A' or 'St'"
            />
          </div>
          
          <div className="form-group">
            <label className="form-label">Ends with</label>
            <input
              type="text"
              value={generationConfig.ends_with || ''}
              onChange={(e) => updateGenerationConfig({ ends_with: e.target.value })}
              className="form-input"
              placeholder="e.g., 'ing' or 'er'"
            />
          </div>
          
          <div className="form-group">
            <label className="form-label">Includes</label>
            <input
              type="text"
              value={generationConfig.includes || ''}
              onChange={(e) => updateGenerationConfig({ includes: e.target.value })}
              className="form-input"
              placeholder="e.g., 'an' or 'tech'"
            />
          </div>
          
          <div className="form-group">
            <label className="form-label">Excludes</label>
            <input
              type="text"
              value={generationConfig.excludes || ''}
              onChange={(e) => updateGenerationConfig({ excludes: e.target.value })}
              className="form-input"
              placeholder="e.g., 'x' or 'tion'"
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default MarkovParametersTab;