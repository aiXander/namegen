import React, { useState } from 'react';
import { Trash2, Edit3 } from 'lucide-react';
import { apiService } from '../services/api';
import Modal from './Modal';
import StarRating from './StarRating';

interface SavedResultsTabProps {
  ratings: Record<string, number>;
  onRatingsChange: (ratings: Record<string, number>) => void;
}

const SavedResultsTab: React.FC<SavedResultsTabProps> = ({ ratings, onRatingsChange }) => {
  const [editingName, setEditingName] = useState<string | null>(null);
  const [newName, setNewName] = useState<string>('');
  const [modalOpen, setModalOpen] = useState(false);

  const sortedRatings = Object.entries(ratings)
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

  const handleEditName = (name: string) => {
    setEditingName(name);
    setNewName(name);
    setModalOpen(true);
  };

  const handleSaveEdit = async () => {
    if (editingName && newName.trim() && newName.trim() !== editingName) {
      try {
        const oldRating = ratings[editingName];
        // Delete the old rating
        await apiService.deleteRating(editingName);
        // Add the new name with the same rating
        await apiService.rateName(newName.trim(), oldRating);
        
        const newRatings = { ...ratings };
        delete newRatings[editingName];
        newRatings[newName.trim()] = oldRating;
        
        onRatingsChange(newRatings);
        setModalOpen(false);
        setEditingName(null);
        setNewName('');
      } catch (err) {
        console.error('Failed to update name:', err);
      }
    } else if (newName.trim() === editingName) {
      // No change needed, just close modal
      setModalOpen(false);
      setEditingName(null);
      setNewName('');
    }
  };

  const handleRateChange = async (name: string, rating: number) => {
    try {
      await apiService.rateName(name, rating);
      onRatingsChange({
        ...ratings,
        [name]: rating
      });
    } catch (err) {
      console.error('Failed to rate name:', err);
    }
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

          <div className="space-y-3 max-h-128 overflow-y-auto">
            {sortedRatings.map(([name, rating]) => (
              <div key={name} className="card">
                <div className="flex items-center justify-between">
                  {/* Action buttons */}
                  <div className="flex items-center gap-2">
                    <button
                      className="btn btn-small btn-danger"
                      onClick={() => handleDeleteRating(name)}
                      title="Delete"
                    >
                      <Trash2 size={14} />
                    </button>
                    
                    <button
                      className="btn btn-small btn-secondary"
                      onClick={() => handleEditName(name)}
                      title="Edit name"
                    >
                      <Edit3 size={14} />
                    </button>
                  </div>
                  
                  {/* Name versions in horizontal layout */}
                  <div className="flex items-center justify-center flex-1">
                    <span className="font-bold text-lg">{name.toLowerCase()}</span>
                    <span className="text-muted">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>
                    <span className="font-bold text-lg">{name.charAt(0).toUpperCase() + name.slice(1).toLowerCase()}</span>
                    <span className="text-muted">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>
                    <span className="font-bold text-lg">{name.toUpperCase()}</span>
                  </div>
                  
                  {/* Rating */}
                  <div className="flex items-center gap-2">
                    <StarRating
                      rating={rating}
                      onRate={(newRating) => handleRateChange(name, newRating)}
                      size="small"
                      showLabel={false}
                    />
                    <span className="text-sm text-muted">
                      {rating}/5
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Edit name modal */}
      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title={`Edit Name for "${editingName}"`}
      >
        <div className="space-y-4">
          <div className="form-group">
            <label className="form-label">
              New Name:
              <span className="text-muted ml-2">Current: {editingName}</span>
            </label>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="form-input"
              placeholder="Enter new name"
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
              disabled={!newName.trim()}
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