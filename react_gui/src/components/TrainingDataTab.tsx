import React, { useState, useEffect } from 'react';
import { Eye, Shuffle } from 'lucide-react';
import { apiService, WordList, WordListContent } from '../services/api';
import StarRating from './StarRating';
import Modal from './Modal';

interface TrainingDataTabProps {
  config: any;
  onConfigChange: (config: any) => void;
}

const TrainingDataTab: React.FC<TrainingDataTabProps> = ({ config, onConfigChange }) => {
  const [wordLists, setWordLists] = useState<WordList[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedWordList, setSelectedWordList] = useState<WordListContent | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [viewMode, setViewMode] = useState<'sorted' | 'random'>('sorted');
  const [minScore, setMinScore] = useState(0);
  const [maxScore, setMaxScore] = useState(5);

  useEffect(() => {
    loadWordLists();
  }, []);

  const loadWordLists = async () => {
    try {
      setLoading(true);
      const lists = await apiService.getWordLists();
      setWordLists(lists);
    } catch (err) {
      setError('Failed to load word lists');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleWordListToggle = (filename: string) => {
    const sources = config.training_data?.sources || [];
    const newSources = sources.includes(filename)
      ? sources.filter((s: string) => s !== filename)
      : [...sources, filename];
    
    onConfigChange({
      ...config,
      training_data: {
        ...config.training_data,
        sources: newSources
      }
    });
  };

  const handleSelectAll = () => {
    const allFilenames = wordLists.map(wl => wl.filename);
    onConfigChange({
      ...config,
      training_data: {
        ...config.training_data,
        sources: allFilenames
      }
    });
  };

  const handleDeselectAll = () => {
    onConfigChange({
      ...config,
      training_data: {
        ...config.training_data,
        sources: []
      }
    });
  };

  const handleSelectByScore = () => {
    const filteredFilenames = wordLists
      .filter(wl => wl.rating >= minScore && wl.rating <= maxScore)
      .map(wl => wl.filename);
    
    onConfigChange({
      ...config,
      training_data: {
        ...config.training_data,
        sources: filteredFilenames
      }
    });
  };

  const handleRateWordList = async (filename: string, rating: number) => {
    try {
      await apiService.rateWordList(filename, rating);
      // Update local state
      setWordLists(prev => prev.map(wl => 
        wl.filename === filename ? { ...wl, rating } : wl
      ));
    } catch (err) {
      console.error('Failed to rate word list:', err);
    }
  };

  const handleViewWordList = async (filename: string) => {
    try {
      const content = await apiService.getWordListContent(filename);
      setSelectedWordList(content);
      setModalOpen(true);
    } catch (err) {
      console.error('Failed to load word list content:', err);
    }
  };

  const getDisplayedWords = () => {
    if (!selectedWordList) return [];
    const words = [...selectedWordList.words];
    return viewMode === 'sorted' ? words.sort() : words.sort(() => Math.random() - 0.5);
  };

  if (loading) {
    return (
      <div className="text-center py-8">
        <div className="loading-spinner mx-auto"></div>
        <p className="text-muted mt-2">Loading word lists...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-8">
        <p className="error-message">{error}</p>
        <button className="btn btn-primary mt-4" onClick={loadWordLists}>
          Retry
        </button>
      </div>
    );
  }

  const selectedSources = config.training_data?.sources || [];

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">Training Data Selection</h2>
      
      {/* Control buttons */}
      <div className="flex gap-2 mb-4">
        <button className="btn btn-secondary" onClick={handleSelectAll}>
          Select All
        </button>
        <button className="btn btn-secondary" onClick={handleDeselectAll}>
          Deselect All
        </button>
      </div>

      {/* Score range selection */}
      <div className="card mb-4">
        <div className="card-header">Select by Score Range</div>
        <div className="flex items-center gap-4 mb-4">
          <div className="flex items-center gap-2">
            <label className="form-label">Min:</label>
            <input
              type="range"
              min="0"
              max="5"
              value={minScore}
              onChange={(e) => setMinScore(parseInt(e.target.value))}
              className="range-slider"
            />
            <span className="text-sm w-4">{minScore}</span>
          </div>
          <div className="flex items-center gap-2">
            <label className="form-label">Max:</label>
            <input
              type="range"
              min="0"
              max="5"
              value={maxScore}
              onChange={(e) => setMaxScore(parseInt(e.target.value))}
              className="range-slider"
            />
            <span className="text-sm w-4">{maxScore}</span>
          </div>
          <button className="btn btn-primary" onClick={handleSelectByScore}>
            Apply Range
          </button>
        </div>
      </div>

      {/* Word lists */}
      <div className="space-y-2 max-h-96 overflow-y-auto">
        {wordLists.map((wordList) => (
          <div key={wordList.filename} className="card">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={selectedSources.includes(wordList.filename)}
                  onChange={() => handleWordListToggle(wordList.filename)}
                  className="w-4 h-4"
                />
                <span className="font-medium">{wordList.display_name}</span>
              </div>
              
              <div className="flex items-center gap-3">
                <button
                  className="btn btn-small btn-secondary"
                  onClick={() => handleViewWordList(wordList.filename)}
                >
                  <Eye size={14} />
                  View
                </button>
                <StarRating
                  rating={wordList.rating}
                  onRate={(rating) => handleRateWordList(wordList.filename, rating)}
                  size="small"
                />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Word list content modal */}
      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title={`View Word List - ${selectedWordList?.filename.replace('_', ' ').replace('.txt', '')}`}
      >
        {selectedWordList && (
          <div>
            <div className="flex items-center gap-4 mb-4">
              <span className="text-sm text-muted">
                Total words: {selectedWordList.total_count}
              </span>
              <div className="flex gap-2">
                <button
                  className={`btn btn-small ${viewMode === 'sorted' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setViewMode('sorted')}
                >
                  Sorted
                </button>
                <button
                  className={`btn btn-small ${viewMode === 'random' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setViewMode('random')}
                >
                  <Shuffle size={14} />
                  Random
                </button>
              </div>
            </div>
            <div className="bg-primary border border-gray-600 rounded p-4 max-h-64 overflow-y-auto">
              <pre className="text-sm whitespace-pre-wrap">
                {getDisplayedWords().join('\n')}
              </pre>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default TrainingDataTab;