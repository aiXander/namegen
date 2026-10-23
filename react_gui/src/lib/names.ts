import { FinalEntry, NameRow, Verdict } from '../services/api';

/** "noomura" -> "Noomura", "mind of us" -> "Mind Of Us" */
export const titleCase = (name: string) =>
  name.replace(/(^|\s)(\S)/g, (_, space, ch) => space + ch.toUpperCase());

export const formatCost = (usd: number) =>
  usd === 0 ? '$0' : usd < 0.01 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(2)}`;

/** Short label for an OpenRouter model id: "anthropic/claude-haiku-5.5" -> "claude-haiku-5.5" */
export const shortModel = (id: string) => id.split('/').pop() || id;

/** Everything the results table knows about one name. */
export interface ResultItem extends NameRow {
  verdict?: Verdict;
  similarity?: number;
  final?: FinalEntry;
  rating: number;
}

/** Default "best first" ordering: final-round rank, then panel score, then
 *  vibe similarity, then naturalness — each signal only breaks ties of the
 *  stronger one before it. */
export function compareBest(a: ResultItem, b: ResultItem): number {
  const finalA = a.final?.rank ?? Infinity;
  const finalB = b.final?.rank ?? Infinity;
  if (finalA !== finalB) return finalA - finalB;
  const scoreA = a.verdict?.score ?? -1;
  const scoreB = b.verdict?.score ?? -1;
  if (scoreA !== scoreB) return scoreB - scoreA;
  const simA = a.similarity ?? -1;
  const simB = b.similarity ?? -1;
  if (simA !== simB) return simB - simA;
  return (b.naturalness ?? -1) - (a.naturalness ?? -1);
}

/** Levenshtein similarity in [0, 1] (1 = identical). */
function similarity(a: string, b: string): number {
  if (a === b) return 1;
  let prev = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const row = [i];
    for (let j = 1; j <= b.length; j++) {
      row[j] = Math.min(prev[j] + 1, row[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
    prev = row;
  }
  return 1 - prev[b.length] / Math.max(a.length, b.length);
}

// Names at least this similar are re-spellings of each other ("murmurata" /
// "murmurat", "koino" / "koinoo"): one is enough in a shortlist.
const NEAR_DUPLICATE = 0.75;

/** The first `n` names of a best-first list, skipping near-duplicates of a
 *  name already taken, so the final round compares ideas, not spellings. */
export function diverseTop(names: string[], n: number): string[] {
  const picked: string[] = [];
  for (const name of names) {
    if (picked.length >= n) break;
    if (!picked.some(p => similarity(p, name) >= NEAR_DUPLICATE)) picked.push(name);
  }
  return picked;
}

export function downloadCsv(items: ResultItem[], filename = 'names.csv') {
  const escape = (value: unknown) => {
    const text = value === undefined || value === null ? '' : String(value);
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  const header = ['name', 'score', 'sound', 'fit', 'distinct', 'final_rank', 'vibe', 'naturalness',
    'nearest_training_word', 'distance', 'your_rating', 'note', 'flag', 'pitch'];
  const rows = items.map(item => [
    item.name, item.verdict?.score, item.verdict?.sound, item.verdict?.fit, item.verdict?.distinct,
    item.final?.rank, item.similarity?.toFixed(3), item.naturalness, item.nearest, item.distance,
    item.rating || '', item.verdict?.note, item.verdict?.flag, item.final?.pitch
  ]);
  const csv = [header, ...rows].map(row => row.map(escape).join(',')).join('\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
