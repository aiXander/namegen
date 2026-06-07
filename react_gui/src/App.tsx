import React, { useState, useEffect, useRef } from 'react';
import { Play, Save, FolderOpen, Bot, Sparkles } from 'lucide-react';
import { apiService, Config, ScoredName, PrefilterInfo } from './services/api';
import TrainingDataTab from './components/TrainingDataTab';
import SamplingParametersTab from './components/SamplingParametersTab';
import ResultsTab from './components/ResultsTab';
import SavedResultsTab from './components/SavedResultsTab';
import AITab from './components/AITab';
import GenerationProgressModal from './components/GenerationProgressModal';

// Generated names + AI scores only live in React state (config and ratings
// already persist to the backend), so persist them to localStorage to survive
// page refreshes.
const RESULTS_STORAGE_KEY = 'namegen_results_v1';

interface StoredResults {
  results?: string[];
  aiResults?: ScoredName[];
  aiCost?: number;
  prefilterInfo?: PrefilterInfo | null;
}

function loadStoredResults(): StoredResults {
  try {
    const raw = localStorage.getItem(RESULTS_STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (err) {
    console.error('Failed to restore results from localStorage:', err);
    return {};
  }
}

const storedResults = loadStoredResults();

function App() {
  // Land on the results tab when a previous session's results were restored
  const [activeTab, setActiveTab] = useState(storedResults.results?.length ? 'results' : 'training');
  const [config, setConfig] = useState<Config>({});
  const [results, setResults] = useState<string[]>(storedResults.results ?? []);
  const [aiResults, setAIResults] = useState<ScoredName[]>(storedResults.aiResults ?? []);
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);
  const [showGenerationModal, setShowGenerationModal] = useState(false);
  const [aiLoading, setAILoading] = useState(false);
  const [embedLoading, setEmbedLoading] = useState(false);
  // Live progress of the embed-rank / AI-scoring SSE streams, shown as a
  // small bar under the control buttons
  const [taskProgress, setTaskProgress] = useState<{ label: string; done: number; total: number } | null>(null);
  const [aiCost, setAICost] = useState<number>(storedResults.aiCost ?? 0);
  const [prefilterInfo, setPrefilterInfo] = useState<PrefilterInfo | null>(storedResults.prefilterInfo ?? null);

  // Persist results state so a page refresh doesn't wipe it
  useEffect(() => {
    try {
      localStorage.setItem(RESULTS_STORAGE_KEY,
        JSON.stringify({ results, aiResults, aiCost, prefilterInfo }));
    } catch (err) {
      console.error('Failed to persist results to localStorage:', err);
    }
  }, [results, aiResults, aiCost, prefilterInfo]);
  
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

  // Persist config changes to the backend (debounced so slider drags don't
  // fire a request per tick). Without this, parameter changes were lost on reload.
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleConfigChange = (newConfig: Config) => {
    setConfig(newConfig);
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    saveTimeoutRef.current = setTimeout(() => {
      apiService.updateConfig(newConfig).catch(err => {
        console.error('Failed to save config:', err);
      });
    }, 500);
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
    setPrefilterInfo(null);
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
    setTaskProgress(null);
    setError(null);

    try {
      // Get maxNames from config if it exists, otherwise default to 20
      const maxNames = config.ai_settings?.max_names || 20;
      const keywords = (llmConfig.keywords || '').trim();
      // With vibe keywords set, send ALL generated names: the cheap embedding
      // prefilter funnels them down to maxNames before the expensive LLM pass.
      const namesToScore = keywords ? results : results.slice(0, maxNames);

      const response = await apiService.scoreNamesWithAIStream({
        names: namesToScore,
        description: description.trim(),
        instructions: instructions.trim(),
        model: llmConfig.model || 'gpt-4o-mini',
        max_chunk_size: llmConfig.max_chunk_size || 10,
        keywords,
        prefilter_keep: maxNames,
        embedding_model: llmConfig.embedding_model,
        min_similarity: llmConfig.min_similarity || 0
      }, (phase, done, total) => setTaskProgress({
        label: phase === 'embedding' ? 'embedding' : 'scoring chunk',
        done,
        total
      }));
      
      setAIResults(response.scored_names);
      setAICost(response.total_cost);
      setPrefilterInfo(response.prefilter);
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
      setError(err.response?.data?.error || err.message || 'Failed to score names with AI');
      console.error('AI scoring error:', err);
    } finally {
      setAILoading(false);
      setTaskProgress(null);
    }
  };

  // Embedding-only ranking: rank ALL current results against the vibe keywords
  // (cheap, no LLM call) and surface the similarities in the Results tab.
  const handleEmbedRank = async () => {
    if (!results || results.length === 0) {
      setError('No existing results to rank. Please generate names first.');
      return;
    }
    const keywords = (config.llm?.keywords || '').trim();
    if (!keywords) {
      setError('Set some vibe keywords in the AI tab first — they are the anchors names get ranked against.');
      setActiveTab('ai');
      return;
    }

    setEmbedLoading(true);
    setTaskProgress(null);
    setError(null);
    try {
      const response = await apiService.embedRankNamesStream({
        names: results,
        keywords,
        embedding_model: config.llm?.embedding_model
      }, (done, total) => setTaskProgress({ label: 'embedding', done, total }));
      // Merge similarities into AI results, preserving any existing LLM scores.
      const existingScores = new Map(aiResults.map(r => [r.name, r.score]));
      setAIResults(response.ranked.map(r => ({
        name: r.name,
        score: existingScores.get(r.name),
        similarity: r.similarity
      })));
      setAICost(prev => prev + response.cost);
      setActiveTab('results');
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Failed to rank names by embedding similarity');
      console.error('Embedding rank error:', err);
    } finally {
      setEmbedLoading(false);
      setTaskProgress(null);
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
            <h1 className="app-title">The Name<span className="title-accent">forge</span></h1>
            <p className="app-subtitle">Markov-chain name generation, distilled &amp; scored</p>
          </div>
          
          {/* Control Buttons */}
          <div className="w-64">
          <div className="grid grid-cols-2 gap-2">
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
              onClick={handleEmbedRank}
              disabled={embedLoading || results.length === 0}
              title="Rank current results by embedding similarity to the vibe keywords (AI tab) — no LLM cost"
            >
              {embedLoading ? (
                <>
                  <div className="loading-spinner-small"></div>
                  Ranking...
                </>
              ) : (
                <>
                  <Sparkles size={12} />
                  Embed Rank
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

          {/* Live progress (SSE) during Embed Rank and AI Score Names */}
          {(embedLoading || aiLoading) && (
            <div className="mt-2">
              <div className="progress-meta">
                <span>
                  {taskProgress
                    ? `${taskProgress.label} ${taskProgress.done}/${taskProgress.total}`
                    : 'working…'}
                </span>
                <span>
                  {taskProgress
                    ? `${Math.round((taskProgress.done / taskProgress.total) * 100)}%`
                    : ''}
                </span>
              </div>
              <div className="progress-track">
                <div
                  className="progress-fill"
                  style={{
                    width: taskProgress
                      ? `${Math.min((taskProgress.done / taskProgress.total) * 100, 100)}%`
                      : '0%',
                    minWidth: '4px'
                  }}
                />
              </div>
            </div>
          )}
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
              prefilterInfo={prefilterInfo}
              simCutoff={config.llm?.min_similarity}
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
          <div className="mt-4 error-banner">
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
