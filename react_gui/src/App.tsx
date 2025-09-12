import React, { useState, useEffect } from 'react';
import { Play, Save, FolderOpen } from 'lucide-react';
import { apiService, Config, ScoredName } from './services/api';
import TrainingDataTab from './components/TrainingDataTab';
import MarkovParametersTab from './components/MarkovParametersTab';
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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showGenerationModal, setShowGenerationModal] = useState(false);

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
    } catch (err) {
      console.error('Failed to load initial data:', err);
    }
  };

  const handleConfigChange = (newConfig: Config) => {
    setConfig(newConfig);
  };

  const handleGenerateNames = async () => {
    if (!config.training_data?.sources?.length) {
      setError('Please select at least one word list in the Training Data tab.');
      return;
    }

    setError(null);
    setShowGenerationModal(true);
  };

  const handleGenerationComplete = (names: string[]) => {
    setResults(names);
    setAIResults([]); // Clear AI results when generating new names
    setShowGenerationModal(false);
    setActiveTab('results'); // Switch to results tab
  };

  const handleGenerationStop = () => {
    setShowGenerationModal(false);
  };

  const handleSaveConfig = async () => {
    try {
      await apiService.updateConfig(config);
      alert('Configuration saved successfully!');
    } catch (err) {
      console.error('Failed to save config:', err);
      alert('Failed to save configuration');
    }
  };

  const handleLoadConfig = async () => {
    try {
      const configData = await apiService.getConfig();
      setConfig(configData);
      alert('Configuration loaded successfully!');
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

  const tabs = [
    { id: 'training', label: 'Training Data' },
    { id: 'parameters', label: 'Markov Parameters' },
    { id: 'results', label: 'Results' },
    { id: 'saved', label: 'Saved Results' },
    { id: 'ai', label: 'AI' }
  ];

  return (
    <div className="min-h-screen bg-primary text-primary p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">Markov Name Generator</h1>
          <p className="text-muted">Generate unique names using Markov chains and AI scoring</p>
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
            />
          )}

          {activeTab === 'parameters' && (
            <MarkovParametersTab
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
            />
          )}
        </div>

        {/* Control Buttons */}
        <div className="flex gap-4 mt-8 pt-6 border-t border-border-color">
          <button
            className="btn btn-primary"
            onClick={handleGenerateNames}
          >
            <Play size={16} />
            Generate Names
          </button>

          <button
            className="btn btn-secondary"
            onClick={handleSaveConfig}
          >
            <Save size={16} />
            Save Config
          </button>

          <button
            className="btn btn-secondary"
            onClick={handleLoadConfig}
          >
            <FolderOpen size={16} />
            Load Config
          </button>
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
