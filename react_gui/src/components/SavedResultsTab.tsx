import React, { useRef, useState } from 'react';
import { Trash2, Edit3, Copy, Check } from 'lucide-react';
import { apiService, FinalEntry, Verdict } from '../services/api';
import { titleCase } from '../lib/names';
import StarRating from './StarRating';

interface SavedResultsTabProps {
  ratings: Record<string, number>;
  setRatings: React.Dispatch<React.SetStateAction<Record<string, number>>>;
  verdicts: Record<string, Verdict>;
  final: Record<string, FinalEntry>;
  onRate: (name: string, rating: number) => void;
  onError: (err: any) => void;
}

/** Every rated name, grouped by stars. These ratings are also the judges'
 *  taste examples, so curating them here improves future judging. */
const SavedResultsTab: React.FC<SavedResultsTabProps> = ({ ratings, setRatings, verdicts, final, onRate, onError }) => {
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [confirmClear, setConfirmClear] = useState(false);
  const [copied, setCopied] = useState(false);

  const groups = [5, 4, 3, 2, 1]
    .map(stars => ({
      stars,
      names: Object.keys(ratings).filter(name => ratings[name] === stars).sort()
    }))
    .filter(group => group.names.length);
  const total = Object.keys(ratings).length;

  // Submit and blur can both fire for one edit; only the first commits.
  const committing = useRef(false);
  const rename = async (oldName: string) => {
    if (committing.current) return;
    committing.current = true;
    setTimeout(() => { committing.current = false; }, 0);
    const newName = draft.trim().toLowerCase();
    setEditing(null);
    if (!newName || newName === oldName) return;
    try {
      await apiService.renameRating(oldName, newName);
      setRatings(prev => {
        const next = { ...prev, [newName]: prev[oldName] };
        delete next[oldName];
        return next;
      });
    } catch (err) {
      onError(err);
    }
  };

  const clearAll = async () => {
    if (!confirmClear) {
      setConfirmClear(true);
      setTimeout(() => setConfirmClear(false), 3000);
      return;
    }
    try {
      await apiService.clearAllRatings();
      setRatings({});
    } catch (err) {
      onError(err);
    }
    setConfirmClear(false);
  };

  const copyTop = async () => {
    const lines = groups.flatMap(g => g.names.map(name => `${titleCase(name)} (${g.stars}★)`));
    await navigator.clipboard.writeText(lines.join('\n'));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  if (total === 0) {
    return (
      <div className="empty-state">
        <h2 className="empty-title">Your shortlist is empty</h2>
        <p className="text-muted">
          Rate names in Results (click the stars, or press <kbd>1</kbd>–<kbd>5</kbd> on a row). Every rating also
          teaches the judges your taste, low ratings included.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-muted text-sm">
          {total} rated names. They double as the judges' taste examples, so low ratings are useful too.
        </p>
        <div className="flex gap-2">
          <button className="btn btn-ghost btn-small" onClick={copyTop}>
            {copied ? <Check size={13} /> : <Copy size={13} />} {copied ? 'Copied' : 'Copy all'}
          </button>
          <button className="btn btn-danger btn-small" onClick={clearAll}>
            <Trash2 size={13} /> {confirmClear ? 'Click again to clear all' : 'Clear all'}
          </button>
        </div>
      </div>

      {groups.map(group => (
        <section key={group.stars} className="shortlist-group">
          <h3 className="shortlist-heading">
            <span className="text-star-color">{'★'.repeat(group.stars)}</span>
            <span className="text-muted">{'☆'.repeat(5 - group.stars)}</span>
            <span className="tab-count">{group.names.length}</span>
          </h3>
          <div className={`shortlist-grid ${group.stars >= 4 ? 'large' : ''}`}>
            {group.names.map(name => {
              const verdict = verdicts[name];
              const note = final[name]?.pitch || verdict?.note;
              return (
                <div key={name} className="shortlist-card">
                  {editing === name ? (
                    <form onSubmit={e => { e.preventDefault(); rename(name); }}>
                      <input className="form-input" autoFocus value={draft}
                        onChange={e => setDraft(e.target.value)} onBlur={() => rename(name)}
                        onKeyDown={e => { if (e.key === 'Escape') setEditing(null); }} />
                    </form>
                  ) : (
                    <div className="shortlist-name">{titleCase(name)}</div>
                  )}
                  {group.stars >= 4 && (
                    <div className="case-treatments small">
                      <span>{name}</span><span>{name.toUpperCase()}</span>
                    </div>
                  )}
                  {note && <div className="name-note">{note}</div>}
                  <div className="shortlist-actions">
                    <StarRating rating={group.stars} onRate={r => onRate(name, r)} />
                    <div className="flex gap-2">
                      {verdict?.score != null && <span className="score-chip" title="Judge score">{verdict.score.toFixed(1)}</span>}
                      <button className="icon-button" title="Rename" onClick={() => { setEditing(name); setDraft(name); }}>
                        <Edit3 size={13} />
                      </button>
                      <button className="icon-button danger" title="Remove from shortlist" onClick={() => onRate(name, 0)}>
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
};

export default SavedResultsTab;
