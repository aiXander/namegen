import React from 'react';

interface StarRatingProps {
  rating: number;
  onRate: (rating: number) => void;
  size?: 'small' | 'medium' | 'large';
  showLabel?: boolean;
}

const StarRating: React.FC<StarRatingProps> = ({ 
  rating, 
  onRate, 
  size = 'medium',
  showLabel = true 
}) => {
  const sizeClass = {
    small: 'text-sm',
    medium: 'text-base',
    large: 'text-lg'
  }[size];

  return (
    <div className="star-rating">
      {[0, 1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          className={`star-button ${star > 0 && star <= rating ? 'filled' : ''} ${sizeClass}`}
          onClick={() => onRate(star)}
          title={star === 0 ? 'Unrated' : `${star} star${star === 1 ? '' : 's'}`}
        >
          {star === 0 ? '✗' : star > 0 && star <= rating ? '★' : '☆'}
        </button>
      ))}
      {showLabel && (
        <span className="text-muted ml-2">({rating})</span>
      )}
    </div>
  );
};

export default StarRating;