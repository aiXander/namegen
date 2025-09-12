import React, { useState, useEffect } from 'react';
import { Eye, Shuffle, ChevronUp, ChevronDown } from 'lucide-react';
import { apiService, WordList, WordListContent } from '../services/api';
import StarRating from './StarRating';
import Modal from './Modal';

interface TrainingDataTabProps {
  config: any;
  onConfigChange: (config: any) => void;
  selectedSources: string[];
  setSelectedSources: (sources: string[]) => void;
  minScore: number;
  setMinScore: (score: number) => void;
  maxScore: number;
  setMaxScore: (score: number) => void;
}

const TrainingDataTab: React.FC<TrainingDataTabProps> = ({ 
  config, 
  onConfigChange, 
  selectedSources, 
  setSelectedSources, 
  minScore, 
  setMinScore, 
  maxScore, 
  setMaxScore 
}) => {
  const [wordLists, setWordLists] = useState<WordList[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedWordList, setSelectedWordList] = useState<WordListContent | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [viewMode, setViewMode] = useState<'sorted' | 'random'>('sorted');
  const [sortColumn, setSortColumn] = useState<'name' | 'word_count' | 'rating'>('name');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

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
    const newSources = selectedSources.includes(filename)
      ? selectedSources.filter((s: string) => s !== filename)
      : [...selectedSources, filename];
    
    setSelectedSources(newSources);
  };

  const handleSelectAll = () => {
    const allFilenames = wordLists.map(wl => wl.filename);
    setSelectedSources(allFilenames);
  };

  const handleDeselectAll = () => {
    setSelectedSources([]);
  };

  const handleSelectByScore = () => {
    const filteredFilenames = wordLists
      .filter(wl => wl.rating >= minScore && wl.rating <= maxScore)
      .map(wl => wl.filename);
    
    setSelectedSources(filteredFilenames);
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

  const handleSort = (column: 'name' | 'word_count' | 'rating') => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
  };

  const getSortedWordLists = () => {
    const sorted = [...wordLists].sort((a, b) => {
      let aValue, bValue;
      
      switch (sortColumn) {
        case 'name':
          aValue = a.display_name.toLowerCase();
          bValue = b.display_name.toLowerCase();
          break;
        case 'word_count':
          aValue = a.word_count;
          bValue = b.word_count;
          break;
        case 'rating':
          aValue = a.rating;
          bValue = b.rating;
          break;
        default:
          return 0;
      }
      
      if (aValue < bValue) return sortDirection === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });
    
    return sorted;
  };

  const getTotalSelectedWords = () => {
    return wordLists
      .filter(wordList => selectedSources.includes(wordList.filename))
      .reduce((total, wordList) => total + wordList.word_count, 0);
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


  return (
    <div>
      {/* Total training words indicator */}
      <div className="card mb-4">
        <div className="flex items-center gap-3">
          <span className="text-lg font-semibold text-primary">
            Total Training Words: {getTotalSelectedWords().toLocaleString()}
          </span>
          <span className="text-sm text-muted">
            ({selectedSources.length} file{selectedSources.length !== 1 ? 's' : ''} selected)
          </span>
        </div>
      </div>

      {/* Score range selection */}
      <div className="card mb-4">
        <div className="card-header">Select by Score Range</div>
        <div className="flex items-center gap-4 mb-4">
          <div style={{ width: '50%' }}>
            <div className="dual-range-container">
              <div className="dual-range-track">
                <div 
                  className="dual-range-progress"
                  style={{
                    left: `${(minScore / 5) * 100}%`,
                    right: `${100 - (maxScore / 5) * 100}%`
                  }}
                />
              </div>
              <input
                type="range"
                min="0"
                max="5"
                value={minScore}
                onChange={(e) => {
                  const value = parseInt(e.target.value);
                  if (value <= maxScore) {
                    setMinScore(value);
                  }
                }}
                className="dual-range-slider"
                style={{ zIndex: 1 }}
              />
              <input
                type="range"
                min="0"
                max="5"
                value={maxScore}
                onChange={(e) => {
                  const value = parseInt(e.target.value);
                  if (value >= minScore) {
                    setMaxScore(value);
                  }
                }}
                className="dual-range-slider"
                style={{ zIndex: 2 }}
              />
            </div>
          </div>
          <span className="text-sm font-medium whitespace-nowrap">
            Range: {minScore} - {maxScore}
          </span>
          <button className="btn btn-primary" onClick={handleSelectByScore}>
            Apply Range
          </button>
          <button className="btn btn-secondary" onClick={handleSelectAll}>
            Select All
          </button>
          <button className="btn btn-secondary" onClick={handleDeselectAll}>
            Deselect All
          </button>
        </div>
      </div>

      {/* Word lists table */}
      <div className="max-h-96 overflow-y-auto">
        <table className="w-full">
          <thead className="sticky top-0 border-b border-border-color" style={{ backgroundColor: '#1a1a1a', zIndex: 20 }}>
            <tr>
              <th className="text-left py-3 px-4 w-12">
                <span className="text-sm font-medium text-primary">Select</span>
              </th>
              <th className="text-left py-3 px-4 w-24">
                <span className="text-sm font-medium text-primary">View</span>
              </th>
              <th 
                className="text-left py-3 px-4 cursor-pointer hover:bg-bg-hover"
                onClick={() => handleSort('name')}
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-primary">Name</span>
                  {sortColumn === 'name' && (
                    sortDirection === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
                  )}
                </div>
              </th>
              <th 
                className="text-left py-3 px-4 cursor-pointer hover:bg-bg-hover w-32"
                onClick={() => handleSort('word_count')}
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-primary">Word Count</span>
                  {sortColumn === 'word_count' && (
                    sortDirection === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
                  )}
                </div>
              </th>
              <th 
                className="text-left py-3 px-4 cursor-pointer hover:bg-bg-hover w-32"
                onClick={() => handleSort('rating')}
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-primary">Rating</span>
                  {sortColumn === 'rating' && (
                    sortDirection === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
                  )}
                </div>
              </th>
            </tr>
          </thead>
          <tbody>
            {getSortedWordLists().map((wordList) => {
              const isSelected = selectedSources.includes(wordList.filename);
              return (
                <tr key={wordList.filename} className={`border-b border-border-color hover:bg-bg-hover ${isSelected ? 'selected-row' : ''}`}>
                  <td className="py-3 px-4">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => handleWordListToggle(wordList.filename)}
                      className="w-4 h-4"
                    />
                  </td>
                  <td className="py-3 px-4">
                    <button
                      className="btn btn-small btn-secondary"
                      onClick={() => handleViewWordList(wordList.filename)}
                    >
                      <Eye size={14} />
                      View
                    </button>
                  </td>
                  <td className="py-3 px-4">
                    <span className="font-medium">{wordList.display_name}</span>
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-sm">{wordList.word_count.toLocaleString()}</span>
                  </td>
                  <td className="py-3 px-4">
                    <StarRating
                      rating={wordList.rating}
                      onRate={(rating) => handleRateWordList(wordList.filename, rating)}
                      size="small"
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
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