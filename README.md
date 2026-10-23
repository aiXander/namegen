# 🎯 Markov Name Generator

> **Intelligent name generation powered by character n-grams, advanced constraints, and AI scoring**

[Python](https://python.org)
[React](https://reactjs.org)
[License](LICENSE)

Transform word lists into endless creative possibilities using statistical learning and intelligent sampling.



---

## 🚀 What Makes This Special?

This isn't just another random name generator. It's a sophisticated **statistical learning system** that:

- 🧠 **Learns character sequence patterns** from your training words using n-order Markov chains
- 🎛️ **Respects complex constraints** through integrated constraint sampling
- 🤖 **Leverages AI scoring** to rank generated names by quality and relevance based on a natural language description 
- ⚡ **Generates in real-time** with a sleek React interface
- 📊 **Provides 69 curated datasets** covering everything from company names to fantasy creatures

---

## 🔬 The Algorithm Explained

### 🧬 Character N-Gram Learning

```
Training: "apple" → extract trigrams: "##a", "#ap", "app", "ppl", "ple", "le#"
Learning: "##a" → 'p' (100%), "#ap" → 'p' (100%), "app" → 'l' (67%)
```



This system builds **probability distributions** for each character context:

1. **📖 Training Phase**: Extracts n-gram patterns from word lists
  - For order=3: learns 3-character contexts → next character mappings
  - Builds frequency tables: `"app" → ['l':4, 'r':2, 'e':1]`
2. **🔗 Chain Building**: Converts frequencies to probabilities
  - Applies **temperature scaling** for creativity control (zeros preserved — unseen transitions stay impossible)
  - Unseen contexts are handled by **backing off** to lower-order models
3. **🎲 Markov Sampling**: Generates characters step-by-step
  - Looks at last N characters as context
  - Samples next character from learned distribution
  - Continues until termination character '#'
4. **🔄 Backoff Strategy**: Handles sparse contexts gracefully
  - Falls back to lower-order models when context unseen
  - Ensures robust generation even with limited training data

### ⚡ Constraint-Integrated Generation

Unlike naive "generate-then-filter" approaches, our **constraint sampler** integrates requirements **during generation**:

```python
# Smart constraint handling
starts_with="tech" + ends_with="corp" + length=8-12
# → Guides sampling toward "techcorp", "technicorp", etc.
```

- **Prefix/Suffix Constraints**: Seeds generation with required text
- **Length Bounds**: Terminates generation within specified ranges  
- **Content Filters**: Includes/excludes specific substrings
- **Regex Patterns**: Matches complex structural requirements



### 🤖 AI Judging: statistics invent, AI judges

LLMs are bad at *inventing* names: they reach for the predictable, internet-average token. Here the Markov chains invent, and AI only looks up words and judges:

1. **Brief lexicon**: from your brief, an LLM collects real words and roots in many languages (koru, noos, lokahi…). They get mixed into the Markov training data, so invented names carry echoes of meaning. In testing this doubled the names the judges rated 5+.
2. **Quick screen**: every judge gives every name a bare score, 50 names per call, and only the best few hundred get a full verdict. It keeps ~75% of the gems where the old embedding prefilter kept ~30%.
3. **Judge panel**: several fast models (default Claude Haiku 5.5 + GPT-6 Luna) each score every name 0–10 for sound, fit and distinctiveness, with a one-line note on what it evokes and a flag for existing brands or unfortunate meanings. The panel mean is the score.
4. **Final round**: a stronger model compares the top ~30 (near-duplicate spellings skipped) head to head, ranks them, and pitches each.
5. **Breed**: tick *breed* and the next round trains on the winners and your 4–5★ names, exploring around them (re-spellings of a winner are rejected).
6. **Your taste**: your star ratings are sent to the judges as examples, so they calibrate to you.

A round (3000 names screened, 500 judged, final round) costs about $0.09.

---

## 🎨 Interactive React Interface

Launch the **sleek web GUI** for the full experience:

```bash
# Start React frontend + Python API
uv run api_server.py &
cd react_gui && npm start
```

**Features:**

- 📊 **Training Data Explorer** - Browse and rate 69 curated word lists
- ⚙️ **Parameter Tuning** - Real-time adjustment of model settings
- 🎯 **Constraint Builder** - Visual constraint configuration
- 📈 **Results** - Keyboard triage (↑↓ to move, 1–5 to rate), search and filters, CSV export, per-name naturalness and "nearest real word"
- 🤖 **Judge** - Brief, vibe keywords, pick your judge panel with a live cost estimate
- ⭐ **Shortlist** - Rated names grouped by stars, with case treatments

---

## 📚 Rich Training Data (69 Curated Datasets)

Curated for *sound*: every list shares a distinctive phonetic character, and plain-English vocabulary lists were removed because they only teach the model to mangle English. Some examples:

- **Myth & fantasy:** `theological_angels`, `theological_demons`, `roman_deities`, `egyptian_deities`, `brythonic_deities`, `hindu_deities`, `tolkienesque_forenames`, `fantasy_creatures`, `pokemon`
- **Forenames by culture:** `icelandic_forenames`, `irish_forenames`, `japanese_forenames`, `swedish_forenames`, `italian_forenames`, and more
- **Places:** `greek_islands`, `roman_place_names`, `norwegian_fjords`, `german_towns`, `world_places`, `cumbrian_places`
- **Nature & science:** `dinosaurs`, `minerals`, `flowers_common_names`, `satellites_natural`, `stars_and_constellations`, `pharmaceuticals`
- **Brands:** `websites`, `consumer_brands`, `american_companies`, `cryptocurrencies`

Each list shows a **Markov health** score in the GUI: whether its statistics produce novel names or mostly replay its own words.

---

## 🛠️ Quick Start

### 1️⃣ Install Dependencies

```bash
git clone https://github.com/your-username/namegen.git
cd namegen
pip install -r requirements.txt
```

### 2️⃣ Launch the Interface

```bash
# React GUI (recommended)
python api_server.py &
cd react_gui && npm install && npm start

# Or command line
python markov_namegen.py
```

### 3️⃣ Configure Your Model

Edit `config.yaml` or use the web interface:

```yaml
model:
  order: 3              # N-gram size (2-5 recommended)
  temperature: 1.0      # Creativity (0.5=conservative, 2.0=wild)  
  backoff: true         # Handle sparse contexts

generation:
  n_words: 50           # Names to generate
  min_length: 4         # Minimum character count
  max_length: 12        # Maximum character count
  starts_with: "tech"   # Required prefix
  ends_with: ""         # Required suffix
  includes: ""          # Must contain substring  
  excludes: ""          # Cannot contain substring

training_data:
  sources:              # Select from 69 available datasets
    - "tech_companies.txt"
    - "startups.txt"
```

---

## 🎯 Example Outputs

**Training on `tech_companies.txt` + `startups.txt`:**

```
Generated: techflow, datacore, cloudnex, apibase, devtools, 
           streamify, codeforge, netscale, appvault, digitech
```

**With constraints `starts_with="app"` + `length=6-8`:**  

```
Generated: appflow, appcore, appnex, appbase, appify
```

**AI Scored (context: "mobile app startup"):**

```
appflow: 4/5 ⭐ "Suggests smooth user experience"
appcore: 4/5 ⭐ "Strong technical foundation vibe"  
appnex: 2/5 ⭐ "Modern but slightly generic"
```

---

## 🧪 Advanced Features

### Multi-Component Generation

Combine different training sources for hybrid names:

```python
components = ["tech_prefixes.txt", "business_suffixes.txt"]
# → "DataCorp", "TechFlow", "CloudBase"
```

### Statistical Analysis

Built-in metrics for model evaluation:

- **Perplexity scoring** - Model confidence measurement
- **Edit distance filtering** - Similarity to training data
- **N-gram coverage** - Training pattern utilization

### API Integration

REST endpoints for programmatic access:

```bash
curl -X POST http://localhost:5001/api/generate-stream \
  -H "Content-Type: application/json" \
  -d '{"generation": {"n_words": 10, "min_length": 6}}'
```

---

## 📈 Performance & Scalability

- **Fast Training**: Models build in seconds on typical datasets
- **Real-time Generation**: Sub-millisecond name generation  
- **Memory Efficient**: Optimized data structures for large vocabularies
- **Streaming Output**: Progressive results for better UX
- **Caching**: Intelligent model caching prevents redundant computation

---

## 🤝 Contributing

I welcome contributions! Areas of interest:

- 📚 **New datasets** - Add better, domain-specific word lists
- 🧠 **Algorithm improvements** - Better sampling strategies, add a fast word-evaluation model that leverages already scored names.
- 🎨 **UI enhancements** - React component improvements
- 🔧 **Performance optimization** - Faster markov sampling under constraints

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

**Ready to generate amazing names?** Star this repo and start creating! ⭐