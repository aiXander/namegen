import axios from 'axios';

const API_BASE_URL = 'http://localhost:5001/api';

export interface DatasetHealth {
  score: number;
  branching_factor: number;
  memorization_rate: number;
  unique_contexts: number;
  unique_words: number;
}

export interface WordList {
  filename: string;
  display_name: string;
  rating: number;
  selected: boolean;
  word_count: number;
  health: DatasetHealth | null;
}

export interface WordListContent {
  filename: string;
  words: string[];
  total_count: number;
}

export type Weighting = 'natural' | 'balanced' | 'rating';

export interface Config {
  training_data?: {
    sources: string[];
    weighting?: Weighting;
    score_range?: { min: number; max: number };
  };
  model?: {
    order: number;
    temperature: number;
    backoff: boolean;
  };
  generation?: {
    n_words: number;
    min_length: number;
    max_length: number;
    starts_with: string;
    ends_with: string;
    includes: string;
    excludes: string;
    max_time_per_name?: number;
    regex_pattern?: string;
    components?: string[];
    component_order?: number[];
    component_separation?: [number, number];
  };
  filtering?: {
    remove_duplicates?: boolean;
    exclude_training_words?: boolean;
    min_edit_distance?: number;
  };
  llm?: {
    description?: string;
    keywords?: string;
    guidance?: string;
    judges?: string[];
    final_model?: string;
    final_size?: number;
    chunk_size?: number;
    embedding_model?: string;
    min_similarity?: number;
    available_models?: string[];
  };
  ai_settings?: {
    max_names?: number;
  };
  word_list_ratings?: Record<string, number>;
  [key: string]: any;
}

/** A generated name plus the free local metrics computed while sampling. */
export interface NameRow {
  name: string;
  /** 0-100 percentile of per-letter likelihood among the model's own fluent samples */
  naturalness?: number;
  /** closest training word and its edit distance — where the name came from */
  nearest?: string | null;
  distance?: number | null;
}

export interface GenerationStats {
  attempts: number;
  accepted: number;
  failed: number;
  duplicate: number;
  training_word: number;
  too_similar: number;
  elapsed: number;
}

/** One name's verdict from the judge panel (all scores 0-10, means over judges). */
export interface Verdict {
  name: string;
  score: number | null;
  sound: number | null;
  fit: number | null;
  distinct: number | null;
  note: string;
  notes: Record<string, string>;
  flag: string;
  judges: Record<string, number | null>;
}

export interface FinalEntry {
  name: string;
  rank: number;
  pitch: string;
  concern: string;
}

export interface PrefilterInfo {
  total: number;
  kept: number;
  min_similarity: number;
}

export interface JudgeResult {
  verdicts: Verdict[];
  similarities: Record<string, number>;
  prefilter: PrefilterInfo | null;
  judges: string[];
  cost: { embedding: number; judging: number; total: number };
}

export interface JudgeRequest {
  names: string[];
  description: string;
  keywords: string;
  guidance: string;
  judges: string[];
  chunk_size: number;
  prefilter_keep: number;
  embedding_model?: string;
  min_similarity?: number;
}

export interface ModelInfo {
  id: string;
  /** USD per million tokens */
  price?: { prompt: number; completion: number };
}

export interface ModelsResponse {
  models: ModelInfo[];
  default_judges: string[];
  default_final_model: string;
}

/** POST to an SSE endpoint; forwards intermediate events to onEvent,
 *  resolves with the `complete` event, throws on `error` events. */
export async function streamSSE(
  path: string,
  body: any,
  onEvent: (event: any) => void,
  signal?: AbortSignal
): Promise<any> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal
  });
  if (!response.ok || !response.body) {
    throw new Error(`Request failed (HTTP ${response.status}) — is the API server running on :5001?`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  // Buffer partial chunks so SSE events split across reads aren't dropped
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const event = JSON.parse(line.slice(6));
      if (event.type === 'complete') return event;
      if (event.type === 'error') throw new Error(event.message || 'Request failed');
      onEvent(event);
    }
  }
  throw new Error('Stream ended without a result');
}

/** Pull a readable message out of an axios / fetch error. */
export function errorMessage(err: any, fallback: string): string {
  return err?.response?.data?.error || err?.message || fallback;
}

class ApiService {
  private baseURL = API_BASE_URL;

  // Word lists
  async getWordLists(): Promise<WordList[]> {
    return (await axios.get(`${this.baseURL}/word-lists`)).data;
  }

  async getWordListContent(filename: string): Promise<WordListContent> {
    return (await axios.get(`${this.baseURL}/word-lists/${encodeURIComponent(filename)}`)).data;
  }

  async rateWordList(filename: string, rating: number): Promise<void> {
    await axios.post(`${this.baseURL}/word-lists/${encodeURIComponent(filename)}/rate`, { rating });
  }

  // Configuration
  async getConfig(): Promise<Config> {
    return (await axios.get(`${this.baseURL}/config`)).data;
  }

  async updateConfig(config: Config): Promise<void> {
    await axios.post(`${this.baseURL}/config`, config);
  }

  async saveConfigAs(filename: string, config: Config): Promise<void> {
    await axios.post(`${this.baseURL}/config/save`, { filename, config });
  }

  async getAvailableConfigs(): Promise<string[]> {
    return (await axios.get(`${this.baseURL}/config/list`)).data.configs;
  }

  async loadConfigFrom(filename: string): Promise<Config> {
    return (await axios.get(`${this.baseURL}/config/load/${encodeURIComponent(filename)}`)).data;
  }

  // Ratings (the shortlist). Rating 0 removes the name.
  async getRatings(): Promise<Record<string, number>> {
    return (await axios.get(`${this.baseURL}/ratings`)).data;
  }

  async rateName(name: string, rating: number): Promise<void> {
    await axios.post(`${this.baseURL}/ratings`, { name, rating });
  }

  async renameRating(oldName: string, newName: string): Promise<void> {
    await axios.post(`${this.baseURL}/ratings/rename`, { old: oldName, new: newName });
  }

  async clearAllRatings(): Promise<void> {
    await axios.delete(`${this.baseURL}/ratings`);
  }

  // Generation
  generateStream(
    config: Config,
    onName: (row: NameRow) => void,
    signal?: AbortSignal
  ): Promise<{ stats: GenerationStats }> {
    return streamSSE('/generate-stream', config, (event) => {
      if (event.type === 'name') {
        const { type, ...row } = event;
        onName(row);
      }
    }, signal);
  }

  // AI
  embedRankStream(
    request: { names: string[]; keywords: string; embedding_model?: string },
    onProgress: (done: number, total: number) => void
  ): Promise<{ ranked: { name: string; similarity: number }[]; cost: number }> {
    return streamSSE('/ai/embed-rank-stream', request, (event) => {
      if (event.type === 'progress') onProgress(event.done, event.total);
    });
  }

  /** Vibe prefilter (when keywords are set) then the judge panel; reports
   *  'embedding' progress (texts) then 'judging' progress (LLM chunks). */
  judgeStream(
    request: JudgeRequest,
    onProgress: (phase: 'embedding' | 'judging', done: number, total: number) => void
  ): Promise<JudgeResult> {
    return streamSSE('/ai/judge-stream', request, (event) => {
      if (event.type === 'embed_progress') onProgress('embedding', event.done, event.total);
      else if (event.type === 'judge_progress') onProgress('judging', event.done, event.total);
    });
  }

  async finalRound(request: {
    names: string[];
    description: string;
    keywords: string;
    guidance: string;
    model: string;
  }): Promise<{ ranking: FinalEntry[]; model: string; cost: number }> {
    return (await axios.post(`${this.baseURL}/ai/final-round`, request)).data;
  }

  async getModels(): Promise<ModelsResponse> {
    return (await axios.get(`${this.baseURL}/ai/models`)).data;
  }
}

export const apiService = new ApiService();
