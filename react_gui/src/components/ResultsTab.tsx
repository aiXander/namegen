import React, { useState, useEffect } from 'react';
import { ChevronUp, ChevronDown, Bot } from 'lucide-react';
import { apiService, ScoredName, PrefilterInfo } from '../services/api';
import StarRating from './StarRating';

interface ResultsTabProps {
  results: string[];
  aiResults: ScoredName[];
  ratings: Record<string, number>;
  onRateChange: (name: string, rating: number) => void;
  onAIScoreClick?: () => void;
  aiCost?: number;
  prefilterInfo?: PrefilterInfo | null;
  simCutoff?: number;
}

interface ResultItem {
  name: string;
  aiScore: number | null;
  similarity: number | null;
  /** Multiplicative blend of vibe similarity and AI score; null unless both exist */
  combined: number | null;
  userRating: number;
}

const ResultsTab: React.FC<ResultsTabProps> = ({
  results,
  aiResults,
  ratings,
  onRateChange,
  onAIScoreClick,
  aiCost,
  prefilterInfo,
  simCutoff
}) => {
  const [sortColumn, setSortColumn] = useState<'name' | 'aiScore' | 'similarity' | 'combined' | 'userRating'>('name');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [tableData, setTableData] = useState<ResultItem[]>([]);

  useEffect(() => {
    // Combine results with AI scores / embedding similarities
    const combinedData: ResultItem[] = results.map(name => {
      const aiResult = aiResults.find(ai => ai.name === name);
      const aiScore = aiResult?.score ?? null;
      const similarity = aiResult?.similarity ?? null;
      return {
        name,
        aiScore,
        similarity,
        combined: aiScore !== null && similarity !== null ? aiScore * similarity : null,
        userRating: ratings[name] || 0
      };
    });

    setTableData(combinedData);

    // Auto-sort by the combined ranking when both signals exist, else by AI
    // score if available, else by embedding similarity
    if (aiResults.length > 0) {
      const hasScores = aiResults.some(ai => ai.score !== undefined && ai.score !== null);
      const hasCombined = aiResults.some(ai =>
        ai.score !== undefined && ai.score !== null &&
        ai.similarity !== undefined && ai.similarity !== null);
      setSortColumn(hasCombined ? 'combined' : hasScores ? 'aiScore' : 'similarity');
      setSortDirection('desc');
    }
  }, [results, aiResults, ratings]);

  const hasSimilarities = tableData.some(item => item.similarity !== null);
  const hasCombined = tableData.some(item => item.combined !== null);

  const handleRateChange = async (name: string, rating: number) => {
    try {
      await apiService.rateName(name, rating);
      onRateChange(name, rating);
    } catch (err) {
      console.error('Failed to rate name:', err);
    }
  };

  const handleSort = (column: 'name' | 'aiScore' | 'similarity' | 'combined' | 'userRating') => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      // Default to descending for score-like columns
      setSortDirection(column === 'aiScore' || column === 'similarity' || column === 'combined' ? 'desc' : 'asc');
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
        case 'similarity':
          aValue = a.similarity ?? -1;
          bValue = b.similarity ?? -1;
          break;
        case 'combined':
          aValue = a.combined ?? -1;
          bValue = b.combined ?? -1;
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

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <h2 className="text-xl font-bold">Results</h2>
          {results.length > 0 && onAIScoreClick && aiResults.length === 0 && (
            <button
              className="btn btn-secondary"
              onClick={onAIScoreClick}
              title="Score names with AI"
            >
              <Bot size={16} />
              AI Score Names
            </button>
          )}
          {aiCost !== undefined && aiCost > 0 && (
            <div className="cost-badge">
              AI cost ${aiCost.toFixed(4)}
            </div>
          )}
          {prefilterInfo && (
            <div
              className="cost-badge"
              title={`Embedding pre-filter (${prefilterInfo.embedding_model}) kept the ${prefilterInfo.kept} names most similar to: ${prefilterInfo.keywords.join(', ')}`}
            >
              Embed filter: kept {prefilterInfo.kept}/{prefilterInfo.total}
              {(prefilterInfo.min_similarity ?? 0) > 0 && ` (sim ≥ ${prefilterInfo.min_similarity!.toFixed(2)})`}
            </div>
          )}
        </div>
        {aiResults.length > 0 && (
          <div className="status-good">
            {(() => {
              const scoredCount = aiResults.filter(ai => ai.score !== undefined && ai.score !== null).length;
              return scoredCount > 0
                ? `AI scores available for ${scoredCount} names`
                : `Embedding similarities for ${aiResults.length} names`;
            })()}
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
          <div className="max-h-128 overflow-y-auto">
            <table className="w-full">
              <thead className="sticky top-0" style={{ zIndex: 20 }}>
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
                  {hasSimilarities && (
                    <th
                      className="text-left py-3 px-4 cursor-pointer hover:bg-bg-hover w-32"
                      onClick={() => handleSort('similarity')}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-primary">Vibe Sim</span>
                        {sortColumn === 'similarity' && (
                          sortDirection === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
                        )}
                      </div>
                    </th>
                  )}
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
                  {hasCombined && (
                    <th
                      className="text-left py-3 px-4 cursor-pointer hover:bg-bg-hover w-32"
                      onClick={() => handleSort('combined')}
                      title="Vibe similarity × AI score — blends both rankings"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-primary">Sim × Score</span>
                        {sortColumn === 'combined' && (
                          sortDirection === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
                        )}
                      </div>
                    </th>
                  )}
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
                  <tr
                    key={item.name}
                    className="border-b border-border-color hover:bg-bg-hover"
                    // Dim names that fall below the vibe-sim cutoff: these will be
                    // skipped by the embedding pre-filter during "AI Score Names".
                    style={
                      simCutoff && simCutoff > 0 && item.similarity !== null && item.similarity < simCutoff
                        ? { opacity: 0.4 }
                        : undefined
                    }
                  >
                    <td className="py-3 px-4 text-sm text-muted">
                      {index + 1}
                    </td>
                    <td className="py-3 px-4">
                      <span className="name-display">{item.name}</span>
                    </td>
                    {hasSimilarities && (
                      <td className="py-3 px-4">
                        {item.similarity !== null ? (
                          <span className="text-accent-primary font-mono">
                            {item.similarity.toFixed(3)}
                          </span>
                        ) : (
                          <span className="text-muted text-sm">—</span>
                        )}
                      </td>
                    )}
                    <td className="py-3 px-4">
                      {item.aiScore !== null ? (
                        <span className="text-accent-primary font-mono font-semibold">
                          {Number.isInteger(item.aiScore) ? item.aiScore : item.aiScore.toFixed(1)}
                        </span>
                      ) : (
                        <span className="text-muted text-sm">—</span>
                      )}
                    </td>
                    {hasCombined && (
                      <td className="py-3 px-4">
                        {item.combined !== null ? (
                          <span className="text-accent-primary font-mono">
                            {item.combined.toFixed(2)}
                          </span>
                        ) : (
                          <span className="text-muted text-sm">—</span>
                        )}
                      </td>
                    )}
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