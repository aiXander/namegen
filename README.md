# Markov Name Generator

A Python implementation of a Markov chain-based name generator with optional AI scoring capabilities.

## Algorithm

The generator uses **n-order Markov chains** to create names by learning character patterns from training data:

1. **Training Phase**: Builds n-gram frequency tables from word lists (e.g., for order=3, learns 3-character patterns)
2. **Chain Building**: Creates probability distributions for each character context using Dirichlet smoothing
3. **Generation**: Uses weighted random selection to predict next characters based on context
4. **Backoff Model**: Falls back to lower-order models when higher-order contexts fail (Katz's back-off)
5. **Filtering**: Applies length, similarity, and content constraints to results

### AI Scoring (Optional)

The `LLMScorer` class enables AI-based name evaluation:
- Sends generated names to LLM APIs (GPT-4, Claude, etc.) for quality scoring
- Uses customizable prompts with context and examples
- Parses responses to extract numerical scores (0-5 scale)
- Supports batch processing with progress tracking

## Setup and Usage

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. **Run the GUI** (recommended):
```bash
python gui.py
```

3. Or run command line:
```bash
python markov_namegen.py
```

## Configuration

Edit `config.yaml` to customize parameters:

```yaml
model:
  order: 3          # Character lookback window
  prior: 0.01       # Dirichlet smoothing factor
  backoff: true     # Enable lower-order fallback

generation:
  n_words: 10       # Number of names to generate
  min_length: 4     # Minimum name length
  max_length: 12    # Maximum name length
```

## Training Data

The `word_lists/` directory contains 100+ curated datasets including company names, cities, fantasy creatures, historical names, and technical terms for training the Markov models.