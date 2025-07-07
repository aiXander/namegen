# Markov Name Generator

A Python implementation of a Markov chain-based name generator, inspired by the [markov-namegen-lib](https://github.com/Tw1ddle/markov-namegen-lib) Haxe library.

## Features

- **Markov Chain Algorithm**: Uses n-order Markov chains to generate names based on training data
- **Katz's Back-off Model**: Falls back to lower-order models when higher-order models fail
- **Dirichlet Prior**: Adds randomness through additive smoothing
- **Flexible Filtering**: Filter by length, prefix/suffix, content, and similarity to training data
- **Multiple Word Lists**: Includes 100+ word lists for training (companies, cities, fantasy names, etc.)
- **Configurable**: Easy YAML configuration for all parameters

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. **Run the GUI** (recommended):
```bash
python gui.py
```

3. Or run the command line version:
```bash
python markov_namegen.py
```

4. Or run the example:
```bash
python example.py
```

## Configuration

Edit `config.yaml` to customize generation parameters:

```yaml
model:
  order: 3          # Look back 3 characters
  prior: 0.01       # Randomness factor (0.0-1.0)
  backoff: true     # Use lower-order models as fallback

generation:
  n_words: 10       # Number of names to generate
  min_length: 4     # Minimum name length
  max_length: 12    # Maximum name length
  starts_with: ""   # Required prefix
  ends_with: ""     # Required suffix
```

## Core Components

- `MarkovModel`: Individual Markov chain model
- `Generator`: Main generation engine with backoff support
- `NameGenerator`: High-level name generation with constraints
- `MarkovNameGenerator`: Main application class with config support
- `gui.py`: Tkinter-based GUI interface with visual controls

## GUI Features

The GUI provides an easy-to-use interface with:

- **Training Data Tab**: Checkboxes for all 100+ word lists with select/deselect all
- **Model Parameters Tab**: Sliders for order and prior, checkbox for backoff
- **Generation Parameters Tab**: Input fields for all generation constraints
- **Results Tab**: Display generated names with export options (TXT, JSON, clipboard)
- **Config Management**: Save/load configuration files
- **Real-time Generation**: Generate names with current settings instantly

## How It Works

1. **Training**: Builds n-gram frequency tables from training data
2. **Chain Building**: Creates probability distributions for each context
3. **Generation**: Uses weighted random selection to pick next characters
4. **Filtering**: Applies length, content, and similarity filters
5. **Output**: Sorts and formats results according to configuration

## Training Data

The `word_lists/` directory contains 100+ curated word lists including:
- Company names
- City names
- Fantasy creatures
- Historical names
- Technical terms
- And many more...

## Example Usage

```python
from markov_namegen import MarkovNameGenerator

# Create generator
generator = MarkovNameGenerator()

# Generate names
names = generator.run()

# Custom generation
custom_names = generator.generator.generate_names(
    n=5,
    min_length=6,
    starts_with="th",
    excludes="x"
)
```

## Future Enhancements

- [ ] Add LLM-based filtering and ranking
- [ ] Implement phonetic similarity metrics
- [ ] Add domain-specific name validation
- [ ] Support for multi-language generation
- [ ] Web API interface