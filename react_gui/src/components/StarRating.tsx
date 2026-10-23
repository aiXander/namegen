import React from 'react';

interface StarRatingProps {
  rating: number;
  /** Clicking the current rating again clears it (calls onRate(0)). */
  onRate: (rating: number) => void;
  size?: 'small' | 'medium';
}

const StarRating: React.FC<StarRatingProps> = ({ rating, onRate, size = 'small' }) => (
  <div className={`star-rating star-rating-${size}`} role="radiogroup" aria-label="Your rating">
    {[1, 2, 3, 4, 5].map(star => (
      <button
        key={star}
        type="button"
        role="radio"
        aria-checked={star === rating}
        className={`star-button ${star <= rating ? 'filled' : ''}`}
        onClick={e => { e.stopPropagation(); onRate(star === rating ? 0 : star); }}
        title={star === rating ? 'Click again to clear' : `${star} star${star === 1 ? '' : 's'}`}
      >
        {star <= rating ? '★' : '☆'}
      </button>
    ))}
  </div>
);

export default StarRating;
