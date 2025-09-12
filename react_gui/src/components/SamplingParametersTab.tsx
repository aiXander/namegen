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
              <label className="form-label">
                Number of Names
                <span 
                  className="ml-2 text-xs text-blue-600 cursor-help" 
                  title="How many names to generate:&#10;• Small batch (1-10): Quick testing and experimentation&#10;• Medium batch (20-50): Good variety for evaluation&#10;• Large batch (50-100): Comprehensive exploration&#10;• Note: Complex constraints may produce fewer results"
                >
                  ℹ️
                </span>
              </label>
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
              <label className="form-label">
                Length Range
                <span 
                  className="ml-2 text-xs text-blue-600 cursor-help" 
                  title="Control generated word length:&#10;• Short (3-6): Concise, punchy names&#10;• Medium (6-12): Balanced, most versatile&#10;• Long (12-20): Descriptive, compound-style&#10;• Components require longer lengths (8+ recommended)&#10;• Consider your use case: domains, brands, products"
                >
                  ℹ️
                </span>
              </label>
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

          {/* Multi-Component Settings */}
          <div className="form-group">
            <label className="form-label">
              Multi-Component Generation 
              <div className="tooltip ml-2 inline-block">
                <span className="text-xs text-blue-600 cursor-help">ℹ️</span>
                <span className="tooltiptext">
                  Create words with specific required components:
                  • Components: Required substrings (e.g., 'co,mind,tech')
                  • Order: Force specific arrangement (indices, e.g., '1,0' for mind,co)
                  • Separation: Control spacing between components
                  
                  Examples: Components 'co,mind' → 'cognomind', 'mindcode'
                  
                  Perfect for:
                  - Brand names with key elements
                  - Technical terms with prefixes/suffixes
                  - Creative combinations with guaranteed parts
                </span>
              </div>
            </label>
            <div className="grid grid-cols-1 gap-4">
              <div>
                <label className="text-sm text-muted">
                  Required Components
                  <div className="tooltip ml-2 inline-block">
                    <span className="text-xs text-blue-600 cursor-help">ℹ️</span>
                    <span className="tooltiptext">
                      Comma-separated list of required substrings:
                      • 'co,mind' = words must contain both 'co' and 'mind'
                      • 'tech,bio,ai' = words must contain all three components
                      • Leave empty for standard generation
                      
                      Examples:
                      - 'co,mind' → 'cognomind', 'mindcode'
                      - 'smart,tech' → 'smartech', 'techsmart'
                    </span>
                  </div>
                </label>
                <input
                  type="text"
                  value={generationConfig.components ? generationConfig.components.join(',') : ''}
                  onChange={(e) => {
                    const components = e.target.value.split(',').map(c => c.trim()).filter(c => c);
                    updateGenerationConfig({ components: components.length > 0 ? components : undefined });
                  }}
                  className="form-input"
                  placeholder="e.g., 'co,mind' or 'tech,bio,smart'"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-muted">
                    Component Order
                    <div className="tooltip ml-2 inline-block">
                      <span className="text-xs text-blue-600 cursor-help">ℹ️</span>
                      <span className="tooltiptext">
                        Force specific component ordering:
                        • Leave empty for any order
                        • '0,1' = first component, then second
                        • '1,0' = second component, then first
                        • Only works when components are specified
                        
                        Example: Components 'smart,tech' + Order '1,0' → 'techsmart...'
                      </span>
                    </div>
                  </label>
                  <input
                    type="text"
                    value={generationConfig.component_order ? generationConfig.component_order.join(',') : ''}
                    onChange={(e) => {
                      const value = e.target.value;
                      const order = value.split(',').map(i => parseInt(i.trim())).filter(i => !isNaN(i));
                      updateGenerationConfig({ component_order: order.length > 0 ? order : undefined });
                    }}
                    onKeyDown={(e) => {
                      // Allow comma input
                      if (e.key === ',') {
                        e.stopPropagation();
                      }
                    }}
                    className="form-input"
                    placeholder="e.g., '0,1' or '1,0'"
                    disabled={!generationConfig.components || generationConfig.components.length === 0}
                  />
                </div>
                
                <div>
                  <label className="text-sm text-muted">
                    Component Separation
                    <div className="tooltip ml-2 inline-block">
                      <span className="text-xs text-blue-600 cursor-help">ℹ️</span>
                      <span className="tooltiptext">
                        Control spacing between components:
                        • Format: 'min,max' characters
                        • '0,2' = 0-2 chars between components
                        • '1,3' = 1-3 chars between components
                        • Higher values = more spacing variation
                        
                        Example: '0,1' → 'cotech', 'comind'
                        Example: '2,3' → 'coabtech', 'cospmind'
                      </span>
                    </div>
                  </label>
                  <input
                    type="text"
                    value={generationConfig.component_separation ? generationConfig.component_separation.join(',') : '0,3'}
                    onChange={(e) => {
                      const value = e.target.value;
                      const sep = value.split(',').map(i => parseInt(i.trim())).filter(i => !isNaN(i));
                      if (sep.length === 2) {
                        updateGenerationConfig({ component_separation: sep });
                      }
                    }}
                    onKeyDown={(e) => {
                      // Allow comma input
                      if (e.key === ',') {
                        e.stopPropagation();
                      }
                    }}
                    className="form-input"
                    placeholder="e.g., '0,2' or '1,3'"
                    disabled={!generationConfig.components || generationConfig.components.length === 0}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Content Constraints */}
          <div className="form-group">
            <label className="form-label">Content Constraints</label>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-muted">
                  Starts with
                  <span 
                    className="ml-2 text-xs text-blue-600 cursor-help" 
                    title="Force words to begin with specific text:&#10;• 'A' = words start with 'A'&#10;• 'neo' = words start with 'neo'&#10;• Works with components too!"
                  >
                    ℹ️
                  </span>
                </label>
                <input
                  type="text"
                  value={generationConfig.starts_with || ''}
                  onChange={(e) => updateGenerationConfig({ starts_with: e.target.value })}
                  className="form-input"
                  placeholder="e.g., 'A' or 'St'"
                />
              </div>
              
              <div>
                <label className="text-sm text-muted">
                  Ends with
                  <span 
                    className="ml-2 text-xs text-blue-600 cursor-help" 
                    title="Force words to end with specific text:&#10;• 'ing' = words end with 'ing'&#10;• 'tech' = words end with 'tech'&#10;• Works with components too!"
                  >
                    ℹ️
                  </span>
                </label>
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
                  <div className="tooltip ml-2 inline-block">
                    <span className="text-xs text-blue-600 cursor-help">ℹ️</span>
                    <span className="tooltiptext">
                      Pattern formats:
                      • 'x,a' = must contain BOTH x AND a
                      • 'x;a' = must contain EITHER x OR a
                      • 'x,a;b,c' = must contain (x AND a) OR (b AND c)
                      
                      Examples: 
                      - 'an,er' = both 'an' and 'er'
                      - 'tech;bio' = either 'tech' or 'bio'
                      
                      Note: Different from Components - this is post-processing filter
                    </span>
                  </div>
                </label>
                <input
                  type="text"
                  value={generationConfig.includes || ''}
                  onChange={(e) => updateGenerationConfig({ includes: e.target.value })}
                  onKeyDown={(e) => {
                    // Allow comma and semicolon input
                    if (e.key === ',' || e.key === ';') {
                      e.stopPropagation();
                    }
                  }}
                  className="form-input"
                  placeholder="e.g., 'an,er' or 'tech;bio'"
                />
              </div>
              
              <div>
                <label className="text-sm text-muted">
                  Excludes
                  <span 
                    className="ml-2 text-xs text-blue-600 cursor-help" 
                    title="Forbidden patterns:&#10;• 'x' = no words containing 'x'&#10;• 'tion' = no words containing 'tion'&#10;• Helps filter out unwanted patterns"
                  >
                    ℹ️
                  </span>
                </label>
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
            <label className="form-label">
              Model Order: {modelConfig.order || 3}
              <span 
                className="ml-2 text-xs text-blue-600 cursor-help" 
                title="N-gram model order - how many previous characters to consider:&#10;• Order 1: Each letter depends only on the previous 1 letter&#10;• Order 2: Each letter depends on the previous 2 letters&#10;• Order 3: Each letter depends on the previous 3 letters&#10;• Higher = more realistic but less creative&#10;• Lower = more creative but less coherent&#10;• Recommended: 2-4 for most use cases"
              >
                ℹ️
              </span>
            </label>
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
              <strong>Low (1-2):</strong> More creative, less realistic, good for abstract names<br />
              <strong>Medium (3-4):</strong> Balanced realism and creativity, most versatile<br />
              <strong>High (5-6):</strong> Very realistic, follows training data closely
            </div>
          </div>

          {/* Temperature */}
          <div className="form-group">
            <label className="form-label">
              Temperature (Creativity Factor): {(modelConfig.temperature || 1.0).toFixed(2)}
              <span 
                className="ml-2 text-xs text-blue-600 cursor-help" 
                title="Controls sampling randomness:&#10;• 0.1-0.5: Conservative, follows common patterns&#10;• 0.8-1.2: Balanced mix of common and uncommon patterns&#10;• 1.5-3.0: Creative, explores unusual combinations&#10;• 1.0 = use training distribution exactly&#10;• Higher values = more surprising results&#10;• Use with components for creative arrangements"
              >
                ℹ️
              </span>
            </label>
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
              <strong>Conservative (0.1-0.5):</strong> Safe choices, predictable patterns<br />
              <strong>Balanced (0.8-1.2):</strong> Natural mix, good for most cases<br />
              <strong>Creative (1.5-3.0):</strong> Surprising combinations, experimental
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
                <span 
                  className="ml-2 text-xs text-blue-600 cursor-help" 
                  title="Intelligent fallback system:&#10;• When high-order patterns aren't found, try lower orders&#10;• Example: 'xyz' pattern not found → try 'yz' → try 'z'&#10;• Prevents generation failures with unusual constraints&#10;• Essential for component generation with tight constraints&#10;• Recommended: Keep enabled unless experimenting"
                >
                  ℹ️
                </span>
              </label>
            </div>
            <p className="text-sm text-muted mb-2">
              Fall back to simpler patterns when complex ones aren't found
            </p>
            <div className="text-sm text-muted">
              <strong>Enabled:</strong> More reliable generation, handles edge cases gracefully<br />
              <strong>Disabled:</strong> Stricter pattern matching, may fail with complex constraints
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SamplingParametersTab;