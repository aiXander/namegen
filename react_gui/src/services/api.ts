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

export interface Config {
  training_data?: {
    sources: string[];
    score_range?: {
      min: number;
      max: number;
    };
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
  llm?: {
    model?: string;
    max_chunk_size?: number;
    default_instructions?: string;
    description?: string;
    keywords?: string;
    embedding_model?: string;
    min_similarity?: number;
  };
  ai_settings?: {
    max_names?: number;
  };
  word_list_ratings?: Record<string, number>;
  saved_ratings?: Record<string, number>;
}

export interface GenerationResult {
  names: string[];
  count: number;
}

export interface ScoredName {
  name: string;
  score?: number;
  similarity?: number;
}

export interface PrefilterInfo {
  keywords: string[];
  total: number;
  kept: number;
  dropped: number;
  min_similarity?: number;
  embedding_model: string;
  cost: number;
}

export interface AIScoringResult {
  scored_names: ScoredName[];
  prefilter: PrefilterInfo | null;
  total_cost: number;
}

export interface AIScoringRequest {
  names: string[];
  description: string;
  instructions: string;
  model: string;
  max_chunk_size: number;
  keywords?: string;
  prefilter_keep?: number;
  embedding_model?: string;
  min_similarity?: number;
}

export interface EmbedRankRequest {
  names: string[];
  keywords: string;
  embedding_model?: string;
}

export interface EmbedRankResult {
  ranked: { name: string; similarity: number }[];
  total: number;
  embedding_model: string;
  cost: number;
}

export interface AIModelsResponse {
  models: string[];
}

class ApiService {
  private baseURL: string;

  constructor() {
    this.baseURL = API_BASE_URL;
  }

  // Word Lists
  async getWordLists(): Promise<WordList[]> {
    const response = await axios.get(`${this.baseURL}/word-lists`);
    return response.data;
  }

  async getWordListContent(filename: string): Promise<WordListContent> {
    const response = await axios.get(`${this.baseURL}/word-lists/${filename}`);
    return response.data;
  }

  async rateWordList(filename: string, rating: number): Promise<void> {
    await axios.post(`${this.baseURL}/word-lists/${filename}/rate`, { rating });
  }

  // Configuration
  async getConfig(): Promise<Config> {
    const response = await axios.get(`${this.baseURL}/config`);
    return response.data;
  }

  async updateConfig(config: Config): Promise<void> {
    await axios.post(`${this.baseURL}/config`, config);
  }

  async saveConfigAs(filename: string, config: Config): Promise<void> {
    await axios.post(`${this.baseURL}/config/save`, { filename, config });
  }

  async getAvailableConfigs(): Promise<string[]> {
    const response = await axios.get(`${this.baseURL}/config/list`);
    return response.data.configs;
  }

  async loadConfigFrom(filename: string): Promise<Config> {
    const response = await axios.get(`${this.baseURL}/config/load/${filename}`);
    return response.data;
  }


  // Ratings
  async getRatings(): Promise<Record<string, number>> {
    const response = await axios.get(`${this.baseURL}/ratings`);
    return response.data;
  }

  async rateName(name: string, rating: number): Promise<void> {
    await axios.post(`${this.baseURL}/ratings/${name}`, { rating });
  }

  async deleteRating(name: string): Promise<void> {
    await axios.delete(`${this.baseURL}/ratings/${name}`);
  }

  async clearAllRatings(): Promise<void> {
    await axios.delete(`${this.baseURL}/ratings`);
  }

  // AI Scoring
  async scoreNamesWithAI(request: AIScoringRequest): Promise<AIScoringResult> {
    const response = await axios.post(`${this.baseURL}/ai/score`, request);
    return response.data;
  }

  async embedRankNames(request: EmbedRankRequest): Promise<EmbedRankResult> {
    const response = await axios.post(`${this.baseURL}/ai/embed-rank`, request);
    return response.data;
  }

  /** POST to an SSE endpoint; forwards intermediate events to onEvent,
   *  resolves with the `complete` event, throws on `error` events. */
  private async streamSSE(
    path: string,
    body: any,
    onEvent: (event: any) => void
  ): Promise<any> {
    const response = await fetch(`${this.baseURL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!response.ok || !response.body) {
      throw new Error(`Request failed (HTTP ${response.status})`);
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
        if (event.type === 'complete') {
          return event;
        } else if (event.type === 'error') {
          throw new Error(event.message || 'Request failed');
        } else {
          onEvent(event);
        }
      }
    }
    throw new Error('Stream ended without a result');
  }

  /** Streaming variant of embedRankNames: reports embedding progress via
   *  onProgress(done, total) as batches complete, resolves with the result. */
  async embedRankNamesStream(
    request: EmbedRankRequest,
    onProgress: (done: number, total: number) => void
  ): Promise<EmbedRankResult> {
    return this.streamSSE('/ai/embed-rank-stream', request, (event) => {
      if (event.type === 'progress') onProgress(event.done, event.total);
    });
  }

  /** Streaming variant of scoreNamesWithAI: reports two-phase progress —
   *  'embedding' (prefilter texts) then 'scoring' (completed LLM chunks). */
  async scoreNamesWithAIStream(
    request: AIScoringRequest,
    onProgress: (phase: 'embedding' | 'scoring', done: number, total: number) => void
  ): Promise<AIScoringResult> {
    return this.streamSSE('/ai/score-stream', request, (event) => {
      if (event.type === 'embed_progress') onProgress('embedding', event.done, event.total);
      else if (event.type === 'score_progress') onProgress('scoring', event.done, event.total);
    });
  }

  async getAIModels(): Promise<AIModelsResponse> {
    const response = await axios.get(`${this.baseURL}/ai/models`);
    return response.data;
  }
}

export const apiService = new ApiService();