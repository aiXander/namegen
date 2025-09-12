import axios from 'axios';

const API_BASE_URL = 'http://localhost:5001/api';

export interface WordList {
  filename: string;
  display_name: string;
  rating: number;
  selected: boolean;
  word_count: number;
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
  };
  llm?: {
    model: string;
    max_chunk_size: number;
    default_instructions: string;
    description: string;
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
  score: number;
}

export interface AIScoringResult {
  scored_names: ScoredName[];
}

export interface AIScoringRequest {
  names: string[];
  description: string;
  instructions: string;
  model: string;
  max_chunk_size: number;
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

  async getAIModels(): Promise<AIModelsResponse> {
    const response = await axios.get(`${this.baseURL}/ai/models`);
    return response.data;
  }
}

export const apiService = new ApiService();