import React, { useState, useEffect } from 'react';
import { ChevronUp, ChevronDown, Bot } from 'lucide-react';
import { apiService, ScoredName } from '../services/api';
import StarRating from './StarRating';

interface ResultsTabProps {
  results: string[];
  aiResults: ScoredName[];
  ratings: Record<string, number>;
  onRateChange: (name: string, rating: number) => void;
  onAIScoreClick?: () => void;
}

interface ResultItem {
  name: string;
  aiScore: number | null;
  userRating: number;
}

const ResultsTab: React.FC<ResultsTabProps> = ({ 
  results, 
  aiResults, 
  ratings, 
  onRateChange,
  onAIScoreClick 
}) => {
  const [sortColumn, setSortColumn] = useState<'name' | 'aiScore' | 'userRating'>('name');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [tableData, setTableData] = useState<ResultItem[]>([]);

  useEffect(() => {
    // Combine results with AI scores
    const combinedData: ResultItem[] = results.map(name => {
      const aiResult = aiResults.find(ai => ai.name === name);
      return {
        name,
        aiScore: aiResult ? aiResult.score : null,
        userRating: ratings[name] || 0
      };
    });
    
    setTableData(combinedData);
    
    // Auto-sort by AI score if AI results are available
    if (aiResults.length > 0) {
      setSortColumn('aiScore');
      setSortDirection('desc');
    }
  }, [results, aiResults, ratings]);

  const handleRateChange = async (name: string, rating: number) => {
    try {
      await apiService.rateName(name, rating);
      onRateChange(name, rating);
    } catch (err) {
      console.error('Failed to rate name:', err);
    }
  };

  const handleSort = (column: 'name' | 'aiScore' | 'userRating') => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection(column === 'aiScore' ? 'desc' : 'asc'); // Default to descending for AI scores
    }
  };

  const getSortedData = () => {
    return [...tableData].sort((a, b) => {
      let aValue: any, bValue: any;
      
      switch (sortColumn) {
        case 'name':
          aValue = a.name.toLowerCase();
          bValue = b.name.toLowerCase();
          break;
        case 'aiScore':
          aValue = a.aiScore ?? -1; // Treat null as lowest value
          bValue = b.aiScore ?? -1;
          break;
        case 'userRating':
          aValue = a.userRating;
          bValue = b.userRating;
          break;
        default:
          return 0;
      }
      
      if (aValue < bValue) return sortDirection === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });
  };

  const renderStars = (rating: number) => {
    const stars = [];
    for (let i = 1; i <= 5; i++) {
      stars.push(
        <span key={i} className={i <= rating ? 'text-star-color' : 'text-gray-400'}>
          ★
        </span>
      );
    }
    return stars;
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <h2 className="text-xl font-bold">Results</h2>
          {results.length > 0 && onAIScoreClick && (
            <button
              className="btn btn-secondary"
              onClick={onAIScoreClick}
              title="Score names with AI"
            >
              <Bot size={16} />
              AI Score Names
            </button>
          )}
        </div>
        {aiResults.length > 0 && (
          <div className="text-sm text-green-400">
            AI scores available for {aiResults.length} names
          </div>
        )}
      </div>

      {tableData.length === 0 ? (
        <div className="text-center py-8">
          <p className="text-muted">No names generated yet. Configure your settings and click "Generate Names".</p>
        </div>
      ) : (
        <div>
          <p className="text-muted mb-4">
            Generated names: {tableData.length} total
          </p>

          {/* Results table */}
          <div className="max-h-96 overflow-y-auto">
            <table className="w-full">
              <thead className="sticky top-0 border-b border-border-color" style={{ backgroundColor: 'var(--bg-primary)', zIndex: 20 }}>
                <tr>
                  <th className="text-left py-3 px-4 w-12">
                    <span className="text-sm font-medium text-primary">#</span>
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
                    onClick={() => handleSort('aiScore')}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-primary">AI Score</span>
                      {sortColumn === 'aiScore' && (
                        sortDirection === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
                      )}
                    </div>
                  </th>
                  <th 
                    className="text-left py-3 px-4 cursor-pointer hover:bg-bg-hover w-40"
                    onClick={() => handleSort('userRating')}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-primary">User Rating</span>
                      {sortColumn === 'userRating' && (
                        sortDirection === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
                      )}
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody>
                {getSortedData().map((item, index) => (
                  <tr key={item.name} className="border-b border-border-color hover:bg-bg-hover">
                    <td className="py-3 px-4 text-sm text-muted">
                      {index + 1}
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-medium">{item.name}</span>
                    </td>
                    <td className="py-3 px-4">
                      {item.aiScore !== null ? (
                        <span className="text-blue-400 font-bold">
                          {Number.isInteger(item.aiScore) ? item.aiScore : item.aiScore.toFixed(1)}
                        </span>
                      ) : (
                        <span className="text-muted text-sm">—</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <StarRating
                          rating={item.userRating}
                          onRate={(rating) => handleRateChange(item.name, rating)}
                          size="small"
                        />
                        <span className="text-sm text-muted">
                          {item.userRating > 0 ? `${item.userRating}/5` : ''}
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default ResultsTab;