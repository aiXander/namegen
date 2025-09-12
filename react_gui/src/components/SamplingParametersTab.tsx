import React from 'react';

interface SamplingParametersTabProps {
  config: any;
  onConfigChange: (config: any) => void;
}

const SamplingParametersTab: React.FC<SamplingParametersTabProps> = ({ config, onConfigChange }) => {
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
      <h2 className="text-xl font-bold mb-4">Sampling Parameters</h2>
      
      {/* Main layout with two columns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Generation Settings */}
        <div className="card">
          <div className="card-header">Generation Settings</div>
          
          <div className="grid grid-cols-2 gap-4">
            {/* Number of Names */}
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

            {/* Length Range */}
            <div className="form-group">
              <label className="form-label">Length Range</label>
              <div className="flex items-center gap-4 mt-2">
                <div style={{ width: '70%' }}>
                  <div className="dual-range-container">
                    <div className="dual-range-track">
                      <div 
                        className="dual-range-progress"
                        style={{
                          left: `${((generationConfig.min_length || 4) - 1) / 19 * 100}%`,
                          right: `${100 - ((generationConfig.max_length || 12) - 1) / 19 * 100}%`
                        }}
                      />
                    </div>
                    <input
                      type="range"
                      min="1"
                      max="20"
                      value={generationConfig.min_length || 4}
                      onChange={(e) => {
                        const value = parseInt(e.target.value);
                        if (value <= (generationConfig.max_length || 12)) {
                          updateGenerationConfig({ min_length: value });
                        }
                      }}
                      className="dual-range-slider"
                      style={{ zIndex: 1 }}
                    />
                    <input
                      type="range"
                      min="1"
                      max="20"
                      value={generationConfig.max_length || 12}
                      onChange={(e) => {
                        const value = parseInt(e.target.value);
                        if (value >= (generationConfig.min_length || 4)) {
                          updateGenerationConfig({ max_length: value });
                        }
                      }}
                      className="dual-range-slider"
                      style={{ zIndex: 2 }}
                    />
                  </div>
                </div>
                <span className="text-sm font-medium whitespace-nowrap">
                  {generationConfig.min_length || 4} - {generationConfig.max_length || 12} letters
                </span>
              </div>
            </div>
          </div>

          {/* Content Constraints */}
          <div className="form-group">
            <label className="form-label">Content Constraints</label>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-muted">Starts with</label>
                <input
                  type="text"
                  value={generationConfig.starts_with || ''}
                  onChange={(e) => updateGenerationConfig({ starts_with: e.target.value })}
                  className="form-input"
                  placeholder="e.g., 'A' or 'St'"
                />
              </div>
              
              <div>
                <label className="text-sm text-muted">Ends with</label>
                <input
                  type="text"
                  value={generationConfig.ends_with || ''}
                  onChange={(e) => updateGenerationConfig({ ends_with: e.target.value })}
                  className="form-input"
                  placeholder="e.g., 'ing' or 'er'"
                />
              </div>
              
              <div>
                <label className="text-sm text-muted">
                  Includes
                  <span 
                    className="ml-2 text-xs text-blue-600 cursor-help" 
                    title="Pattern formats:&#10;• 'x,a' = must contain BOTH x AND a&#10;• 'x;a' = must contain EITHER x OR a&#10;• 'x,a;b,c' = must contain (x AND a) OR (b AND c)&#10;• Examples: 'an,er' = both 'an' and 'er', 'tech;bio' = either 'tech' or 'bio'"
                  >
                    ℹ️
                  </span>
                </label>
                <input
                  type="text"
                  value={generationConfig.includes || ''}
                  onChange={(e) => updateGenerationConfig({ includes: e.target.value })}
                  className="form-input"
                  placeholder="e.g., 'an,er' or 'tech;bio'"
                />
              </div>
              
              <div>
                <label className="text-sm text-muted">Excludes</label>
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

        {/* Model Parameters */}
        <div className="card">
          <div className="card-header">Model Parameters</div>
          
          {/* Model Order */}
          <div className="form-group">
            <label className="form-label">Model Order: {modelConfig.order || 3}</label>
            <p className="text-sm text-muted mb-2">
              How many letters to look back when predicting the next letter
            </p>
            <input
              type="range"
              min="1"
              max="6"
              value={modelConfig.order || 3}
              onChange={(e) => updateModelConfig({ order: parseInt(e.target.value) })}
              className="range-slider w-full"
            />
            <div className="text-sm text-muted mt-2">
              <strong>Low (1-2):</strong> More creative, less realistic<br />
              <strong>High (3-5):</strong> More realistic, follows training data closely
            </div>
          </div>

          {/* Temperature */}
          <div className="form-group">
            <label className="form-label">Temperature (Creativity Factor): {(modelConfig.temperature || 1.0).toFixed(2)}</label>
            <p className="text-sm text-muted mb-2">
              Controls randomness vs. following training patterns
            </p>
            <input
              type="range"
              min="0.1"
              max="3.0"
              step="0.1"
              value={modelConfig.temperature || 1.0}
              onChange={(e) => updateModelConfig({ temperature: parseFloat(e.target.value) })}
              className="range-slider w-full"
            />
            <div className="text-sm text-muted mt-2">
              <strong>Low (0.1-0.5):</strong> Conservative, follows training patterns<br />
              <strong>Medium (0.8-1.2):</strong> Balanced creativity<br />
              <strong>High (1.5-3.0):</strong> Very creative and varied
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
              <label className="form-label">Use Backoff</label>
            </div>
            <p className="text-sm text-muted mb-2">
              Fall back to simpler patterns when complex ones aren't found
            </p>
            <div className="text-sm text-muted">
              <strong>Enabled:</strong> More reliable generation, smoother names<br />
              <strong>Disabled:</strong> Stricter patterns, may fail occasionally
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SamplingParametersTab;