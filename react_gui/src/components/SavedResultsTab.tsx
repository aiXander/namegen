import React, { useState } from 'react';
import { Trash2, Edit3 } from 'lucide-react';
import { apiService } from '../services/api';
import Modal from './Modal';

interface SavedResultsTabProps {
  ratings: Record<string, number>;
  onRatingsChange: (ratings: Record<string, number>) => void;
}

const SavedResultsTab: React.FC<SavedResultsTabProps> = ({ ratings, onRatingsChange }) => {
  const [editingName, setEditingName] = useState<string | null>(null);
  const [editRating, setEditRating] = useState<number>(0);
  const [modalOpen, setModalOpen] = useState(false);

  const sortedRatings = Object.entries(ratings)
    .filter(([_, rating]) => rating > 0)
    .sort(([, a], [, b]) => b - a);

  const handleDeleteRating = async (name: string) => {
    try {
      await apiService.deleteRating(name);
      const newRatings = { ...ratings };
      delete newRatings[name];
      onRatingsChange(newRatings);
    } catch (err) {
      console.error('Failed to delete rating:', err);
    }
  };

  const handleClearAll = async () => {
    if (window.confirm('Are you sure you want to clear all saved ratings?')) {
      try {
        await apiService.clearAllRatings();
        onRatingsChange({});
      } catch (err) {
        console.error('Failed to clear ratings:', err);
      }
    }
  };

  const handleEditRating = (name: string, currentRating: number) => {
    setEditingName(name);
    setEditRating(currentRating);
    setModalOpen(true);
  };

  const handleSaveEdit = async () => {
    if (editingName && editRating >= 1 && editRating <= 5) {
      try {
        await apiService.rateName(editingName, editRating);
        onRatingsChange({
          ...ratings,
          [editingName]: editRating
        });
        setModalOpen(false);
        setEditingName(null);
      } catch (err) {
        console.error('Failed to update rating:', err);
      }
    }
  };

  const renderStars = (rating: number) => {
    return (
      <span className="text-star-color">
        {'★'.repeat(rating)}{'☆'.repeat(5 - rating)} ({rating}/5)
      </span>
    );
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold">Saved Results</h2>
        
        <div className="flex gap-2">
          <button 
            className="btn btn-secondary"
            onClick={() => window.location.reload()}
          >
            Refresh
          </button>
          <button 
            className="btn btn-danger"
            onClick={handleClearAll}
            disabled={sortedRatings.length === 0}
          >
            Clear All
          </button>
        </div>
      </div>

      {sortedRatings.length === 0 ? (
        <div className="text-center py-8">
          <p className="text-muted">No saved names yet. Rate some names in the Results tab!</p>
        </div>
      ) : (
        <div>
          <p className="text-muted mb-4">
            Saved Names ({sortedRatings.length} total):
          </p>

          <div className="space-y-3 max-h-96 overflow-y-auto">
            {sortedRatings.map(([name, rating]) => (
              <div key={name} className="card">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <button
                      className="btn btn-small btn-danger"
                      onClick={() => handleDeleteRating(name)}
                      title="Delete"
                    >
                      <Trash2 size={14} />
                    </button>
                    
                    <button
                      className="btn btn-small btn-secondary"
                      onClick={() => handleEditRating(name, rating)}
                      title="Edit rating"
                    >
                      <Edit3 size={14} />
                    </button>
                    
                    <span className="font-bold text-lg">{name}</span>
                  </div>
                  
                  <div className="text-sm">
                    {renderStars(rating)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Edit rating modal */}
      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title={`Edit Score for "${editingName}"`}
      >
        <div className="space-y-4">
          <div className="form-group">
            <label className="form-label">
              New Score (1-5):
              <span className="text-muted ml-2">Current: {ratings[editingName || ''] || 0}</span>
            </label>
            <input
              type="number"
              min="1"
              max="5"
              value={editRating}
              onChange={(e) => setEditRating(parseInt(e.target.value))}
              className="form-input"
            />
          </div>
          
          <div className="flex gap-2 justify-end">
            <button
              className="btn btn-secondary"
              onClick={() => setModalOpen(false)}
            >
              Cancel
            </button>
            <button
              className="btn btn-primary"
              onClick={handleSaveEdit}
              disabled={editRating < 1 || editRating > 5}
            >
              Save
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default SavedResultsTab;