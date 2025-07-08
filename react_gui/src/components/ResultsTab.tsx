import React, { useState } from 'react';
import { apiService, ScoredName } from '../services/api';
import StarRating from './StarRating';

interface ResultsTabProps {
  results: string[];
  aiResults: ScoredName[];
  ratings: Record<string, number>;
  onRateChange: (name: string, rating: number) => void;
}

const ResultsTab: React.FC<ResultsTabProps> = ({ 
  results, 
  aiResults, 
  ratings, 
  onRateChange 
}) => {
  const [currentView, setCurrentView] = useState<'generated' | 'ai'>('generated');

  const handleRateChange = async (name: string, rating: number) => {
    try {
      await apiService.rateName(name, rating);
      onRateChange(name, rating);
    } catch (err) {
      console.error('Failed to rate name:', err);
    }
  };

  const displayResults = currentView === 'ai' && aiResults.length > 0 ? aiResults : 
    results.map(name => ({ name, score: 0 }));

  const showAIScores = currentView === 'ai' && aiResults.length > 0;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold">Results</h2>
        
        {aiResults.length > 0 && (
          <div className="flex gap-2">
            <button
              className={`btn ${currentView === 'generated' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setCurrentView('generated')}
            >
              Generated Names
            </button>
            <button
              className={`btn ${currentView === 'ai' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setCurrentView('ai')}
            >
              AI Scored Names
            </button>
          </div>
        )}
      </div>

      {displayResults.length === 0 ? (
        <div className="text-center py-8">
          <p className="text-muted">No names generated yet. Configure your settings and click "Generate Names".</p>
        </div>
      ) : (
        <div>
          <p className="text-muted mb-4">
            {currentView === 'ai' ? 'AI-scored names' : 'Generated names'}: {displayResults.length} total
          </p>

          {/* Column headers for AI view */}
          {showAIScores && (
            <div className="flex items-center justify-between mb-4 pb-2 border-b border-gray-600">
              <span className="font-semibold">Name</span>
              <span className="font-semibold">AI Score</span>
              <span className="font-semibold">User Rating</span>
            </div>
          )}

          <div className="space-y-3 max-h-96 overflow-y-auto">
            {displayResults.map((item, index) => (
              <div key={`${item.name}-${index}`} className="card">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <span className="text-muted text-sm w-8">{index + 1}.</span>
                    <span className="font-medium text-lg">{item.name}</span>
                    
                    {showAIScores && (
                      <span className="text-blue-400 font-bold">
                        {Number.isInteger(item.score) ? item.score : item.score.toFixed(1)}
                      </span>
                    )}
                  </div>
                  
                  <StarRating
                    rating={ratings[item.name] || 0}
                    onRate={(rating) => handleRateChange(item.name, rating)}
                    size="medium"
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ResultsTab;