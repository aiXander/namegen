import React, { useState, useEffect } from 'react';
import { Play, Save, FolderOpen, Bot } from 'lucide-react';
import { apiService, Config, ScoredName } from './services/api';
import TrainingDataTab from './components/TrainingDataTab';
import SamplingParametersTab from './components/SamplingParametersTab';
import ResultsTab from './components/ResultsTab';
import SavedResultsTab from './components/SavedResultsTab';
import AITab from './components/AITab';
import GenerationProgressModal from './components/GenerationProgressModal';

function App() {
  const [activeTab, setActiveTab] = useState('training');
  const [config, setConfig] = useState<Config>({});
  const [results, setResults] = useState<string[]>([]);
  const [aiResults, setAIResults] = useState<ScoredName[]>([]);
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);
  const [showGenerationModal, setShowGenerationModal] = useState(false);
  const [aiLoading, setAILoading] = useState(false);
  const [aiCost, setAICost] = useState<number>(0);
  
  // UI state that persists across tab switches
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [minScore, setMinScore] = useState(0);
  const [maxScore, setMaxScore] = useState(5);

  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    try {
      const [configData, ratingsData] = await Promise.all([
        apiService.getConfig(),
        apiService.getRatings()
      ]);
      setConfig(configData);
      setRatings(ratingsData);
      
      // Initialize UI state from config
      setSelectedSources(configData.training_data?.sources || []);
      const scoreRange = configData.training_data?.score_range;
      if (scoreRange) {
        setMinScore(scoreRange.min || 0);
        setMaxScore(scoreRange.max || 5);
      }
    } catch (err) {
      console.error('Failed to load initial data:', err);
    }
  };

  const handleConfigChange = (newConfig: Config) => {
    setConfig(newConfig);
  };

  const handleGenerateNames = async () => {
    if (!selectedSources.length) {
      setError('Please select at least one word list in the Training Data tab.');
      return;
    }

    setError(null);
    
    // Create config with current UI state
    const currentConfig = {
      ...config,
      training_data: {
        ...config.training_data,
        sources: selectedSources,
        score_range: {
          min: minScore,
          max: maxScore
        }
      }
    };
    
    // Update app config and save
    setConfig(currentConfig);
    try {
      await apiService.updateConfig(currentConfig);
    } catch (err) {
      console.error('Failed to save config before generation:', err);
    }
    
    setShowGenerationModal(true);
  };

  const handleGenerationComplete = (names: string[]) => {
    setResults(names);
    setAIResults([]); // Clear AI results when generating new names
    setAICost(0); // Clear AI cost when generating new names
    setShowGenerationModal(false);
    setActiveTab('results'); // Switch to results tab
  };

  const handleGenerationStop = () => {
    setShowGenerationModal(false);
  };

  const handleSaveConfig = async () => {
    const filename = prompt('Enter filename for config (without .yaml extension):');
    if (!filename) return;
    
    const yamlFilename = filename.endsWith('.yaml') ? filename : `${filename}.yaml`;
    
    try {
      await apiService.saveConfigAs(yamlFilename, config);
      alert(`Configuration saved successfully as ${yamlFilename}!`);
    } catch (err) {
      console.error('Failed to save config:', err);
      alert('Failed to save configuration');
    }
  };

  const handleLoadConfig = async () => {
    try {
      const availableConfigs = await apiService.getAvailableConfigs();
      
      if (availableConfigs.length === 0) {
        alert('No config files found in the current directory.');
        return;
      }
      
      const configList = availableConfigs.map((config, index) => `${index + 1}. ${config}`).join('\n');
      const selection = prompt(`Available config files:\n${configList}\n\nEnter the number of the config to load:`);
      
      if (!selection) return;
      
      const selectedIndex = parseInt(selection) - 1;
      if (selectedIndex < 0 || selectedIndex >= availableConfigs.length) {
        alert('Invalid selection.');
        return;
      }
      
      const selectedConfig = availableConfigs[selectedIndex];
      const configData = await apiService.loadConfigFrom(selectedConfig);
      setConfig(configData);
      
      // Update UI state from loaded config
      setSelectedSources(configData.training_data?.sources || []);
      const scoreRange = configData.training_data?.score_range;
      if (scoreRange) {
        setMinScore(scoreRange.min || 0);
        setMaxScore(scoreRange.max || 5);
      }
      
      alert(`Configuration loaded successfully from ${selectedConfig}!`);
    } catch (err) {
      console.error('Failed to load config:', err);
      alert('Failed to load configuration');
    }
  };

  const handleRatingsChange = (newRatings: Record<string, number>) => {
    setRatings(newRatings);
  };

  const handleRateChange = (name: string, rating: number) => {
    setRatings(prev => ({
      ...prev,
      [name]: rating
    }));
  };

  const handleAIResults = (newAIResults: ScoredName[]) => {
    setAIResults(newAIResults);
    setActiveTab('results'); // Switch to results tab to show AI results
  };

  const handleAIScoreNames = async () => {
    if (!results || results.length === 0) {
      setError('No existing results to score. Please generate names first.');
      return;
    }

    const llmConfig = config.llm || {};
    const description = llmConfig.description || '';
    const instructions = llmConfig.default_instructions || 'Based on the provided description and scored names, score the following generated name ideas on a scale of 0 to 5, where 5 is excellent and 0 is poor (use integer scores). Consider factors like memorability, relevance, uniqueness, and overall appeal. Reply with the scores as a JSON dict where keys are the actual name strings and values are the scores. Example: {"aurick": 3, "mindflow": 4, "nexus": 0, "collective": 3}';
    
    if (!description.trim()) {
      setError('Please provide a description for the names in the AI tab first.');
      return;
    }

    setAILoading(true);
    setError(null);

    try {
      // Get maxNames from config if it exists, otherwise default to 20
      const maxNames = config.ai_settings?.max_names || 20;
      const namesToScore = results.slice(0, maxNames);
      
      const response = await apiService.scoreNamesWithAI({
        names: namesToScore,
        description: description.trim(),
        instructions: instructions.trim(),
        model: llmConfig.model || 'gpt-4o-mini',
        max_chunk_size: llmConfig.max_chunk_size || 10
      });
      
      setAIResults(response.scored_names);
      setAICost(response.total_cost);
      setActiveTab('results');
      
      // Update and save config with current settings including UI state
      const updatedConfig = {
        ...config,
        ai_settings: {
          ...config.ai_settings,
          max_names: maxNames
        },
        llm: {
          ...config.llm,
          model: llmConfig.model || 'gpt-4o-mini',
          max_chunk_size: llmConfig.max_chunk_size || 10,
          description: description.trim(),
          default_instructions: instructions.trim()
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
      setConfig(updatedConfig);
      
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
      setAILoading(false);
    }
  };

  const tabs = [
    { id: 'training', label: 'Training Data' },
    { id: 'parameters', label: 'Sampling Parameters' },
    { id: 'results', label: 'Results' },
    { id: 'ai', label: 'AI' },
    { id: 'saved', label: 'Saved Results' }
  ];

  return (
    <div className="min-h-screen bg-primary text-primary p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold mb-2">Markov Name Generator</h1>
            <p className="text-muted">Generate unique names using Markov chains and AI scoring</p>
          </div>
          
          {/* Control Buttons */}
          <div className="grid grid-cols-2 gap-2 w-64">
            <button
              className="btn btn-primary btn-compact"
              onClick={handleGenerateNames}
            >
              <Play size={12} />
              Generate Names
            </button>

            <button
              className="btn btn-primary btn-compact"
              onClick={handleAIScoreNames}
              disabled={aiLoading || results.length === 0}
            >
              {aiLoading ? (
                <>
                  <div className="loading-spinner-small"></div>
                  Scoring...
                </>
              ) : (
                <>
                  <Bot size={12} />
                  AI Score Names
                </>
              )}
            </button>

            <button
              className="btn btn-secondary btn-compact"
              onClick={handleSaveConfig}
            >
              <Save size={12} />
              Save Config
            </button>

            <button
              className="btn btn-secondary btn-compact"
              onClick={handleLoadConfig}
            >
              <FolderOpen size={12} />
              Load Config
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="tab-container">
          <ul className="tab-list">
            {tabs.map(tab => (
              <li key={tab.id}>
                <button
                  className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
                  onClick={() => setActiveTab(tab.id)}
                >
                  {tab.label}
                </button>
              </li>
            ))}
          </ul>
        </div>

        {/* Tab Content */}
        <div className="tab-content">
          {activeTab === 'training' && (
            <TrainingDataTab
              config={config}
              onConfigChange={handleConfigChange}
              selectedSources={selectedSources}
              setSelectedSources={setSelectedSources}
              minScore={minScore}
              setMinScore={setMinScore}
              maxScore={maxScore}
              setMaxScore={setMaxScore}
            />
          )}

          {activeTab === 'parameters' && (
            <SamplingParametersTab
              config={config}
              onConfigChange={handleConfigChange}
            />
          )}

          {activeTab === 'results' && (
            <ResultsTab
              results={results}
              aiResults={aiResults}
              ratings={ratings}
              onRateChange={handleRateChange}
              onAIScoreClick={() => setActiveTab('ai')}
              aiCost={aiCost}
            />
          )}

          {activeTab === 'saved' && (
            <SavedResultsTab
              ratings={ratings}
              onRatingsChange={handleRatingsChange}
            />
          )}

          {activeTab === 'ai' && (
            <AITab
              config={config}
              onConfigChange={handleConfigChange}
              results={results}
              ratings={ratings}
              onAIResults={handleAIResults}
              selectedSources={selectedSources}
              minScore={minScore}
              maxScore={maxScore}
            />
          )}
        </div>


        {/* Error Display */}
        {error && (
          <div className="mt-4 p-4 bg-error-color/10 border border-error-color rounded">
            <p className="error-message">{error}</p>
          </div>
        )}

        {/* Generation Progress Modal */}
        <GenerationProgressModal
          isOpen={showGenerationModal}
          targetCount={config.generation?.n_words || 20}
          onStop={handleGenerationStop}
          onComplete={handleGenerationComplete}
          config={config}
        />
      </div>
    </div>
  );
}

export default App;
