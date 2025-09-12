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
  const [instructions, setInstructions] = useState('');
  const [aiModels, setAIModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState('gpt-3.5-turbo');
  const [maxNames, setMaxNames] = useState(20);
  const [chunkSize, setChunkSize] = useState(10);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('Ready');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAIModels();
    
    // Load default instructions and description from config
    const llmConfig = config.llm || {};
    if (llmConfig.default_instructions) {
      setInstructions(llmConfig.default_instructions);
    } else {
      setInstructions('Based on the provided description and scored names, score the following generated name ideas on a scale of 0.0 to 5.0, where 5.0 is excellent and 0.0 is poor.');
    }
    
    if (llmConfig.description) {
      setDescription(llmConfig.description);
    }
    
    if (llmConfig.model) {
      setSelectedModel(llmConfig.model);
    }
    
    if (llmConfig.max_chunk_size) {
      setChunkSize(llmConfig.max_chunk_size);
    }
  }, [config]);

  const loadAIModels = async () => {
    try {
      const response = await apiService.getAIModels();
      setAIModels(response.models);
    } catch (err) {
      console.error('Failed to load AI models:', err);
      setAIModels(['gpt-3.5-turbo', 'gpt-4']);
    }
  };

  const handleAIScore = async () => {
    if (!description.trim()) {
      setError('Please provide a description for the names.');
      return;
    }
    
    if (!instructions.trim()) {
      setError('Please provide instructions for the LLM.');
      return;
    }
    
    if (results.length === 0) {
      setError('No existing results to score. Please generate names first in the Results tab.');
      return;
    }

    setLoading(true);
    setError(null);
    setProgress(0);
    setProgressMessage('Initializing AI scorer...');

    try {
      const namesToScore = results.slice(0, maxNames);
      
      setProgress(20);
      setProgressMessage('Scoring names with AI...');
      
      const response = await apiService.scoreNamesWithAI({
        names: namesToScore,
        description: description.trim(),
        instructions: instructions.trim(),
        model: selectedModel,
        max_chunk_size: chunkSize
      });
      
      setProgress(100);
      setProgressMessage('Complete!');
      
      onAIResults(response.scored_names);
      
      // Update and save config with current settings including UI state
      const updatedConfig = {
        ...config,
        llm: {
          ...config.llm,
          model: selectedModel,
          max_chunk_size: chunkSize,
          default_instructions: instructions.trim(),
          description: description.trim()
        },
        training_data: {
          ...config.training_data,
          sources: selectedSources,
          score_range: {
            min: minScore,
            max: maxScore
          }
        }
      };
      onConfigChange(updatedConfig);
      
      // Save config to file
      try {
        await apiService.updateConfig(updatedConfig);
      } catch (err) {
        console.error('Failed to save config after AI scoring:', err);
      }
      
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to score names with AI');
      console.error('AI scoring error:', err);
    } finally {
      setLoading(false);
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
            onChange={(e) => setDescription(e.target.value)}
            className="form-textarea"
            placeholder="Describe what these names are for..."
            rows={3}
          />
        </div>
      </div>

      {/* Instructions */}
      <div className="card mb-4">
        <div className="card-header">Instructions</div>
        <div className="form-group">
          <textarea
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
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
              onChange={(e) => setSelectedModel(e.target.value)}
              className="form-select"
            >
              {aiModels.map(model => (
                <option key={model} value={model}>{model}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Max names to score: {maxNames}</label>
            <input
              type="range"
              min="1"
              max="100"
              value={maxNames}
              onChange={(e) => setMaxNames(parseInt(e.target.value))}
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
              onChange={(e) => setChunkSize(parseInt(e.target.value))}
              className="range-slider w-full"
            />
          </div>
        </div>

        {/* Progress */}
        <div className="form-group">
          <label className="form-label">Progress</label>
          <div className="progress-bar">
            <div 
              className="progress-fill" 
              style={{ width: `${progress}%` }}
            ></div>
          </div>
          <p className="text-sm text-muted">{progressMessage}</p>
        </div>

        {/* Generate button */}
        <button
          className="btn btn-primary w-full"
          onClick={handleAIScore}
          disabled={loading || results.length === 0}
        >
          {loading ? (
            <>
              <div className="loading-spinner"></div>
              Scoring with AI...
            </>
          ) : (
            'AI Score Names'
          )}
        </button>

        {error && (
          <div className="error-message mt-2">{error}</div>
        )}
        
        {results.length === 0 && (
          <div className="text-muted text-sm mt-2">
            Generate some names first to enable AI scoring.
          </div>
        )}
      </div>
    </div>
  );
};

export default AITab;