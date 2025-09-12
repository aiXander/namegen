# Multi-Component Word Generation

This document describes the new multi-component word generation feature that allows you to create words containing specific required components (substrings) arranged in flexible patterns.

## Overview

The multi-component sampler creates words by:
1. **Component Selection**: Choose which components to include (e.g., ["co", "mind"])
2. **Template Generation**: Create arrangements with different component orderings and spacing
3. **Variable Segment Sampling**: Fill spaces between/around components using Markov model
4. **Constraint Validation**: Ensure final words meet all specified constraints

## Key Features

### Components
- **Required substrings**: Specify exact text that must appear in generated words
- **Flexible ordering**: Components can appear in any order unless specifically constrained
- **Multiple components**: Support for 2+ components in a single word

### Spacing Control
- **Component separation**: Control min/max characters between components
- **Variable segments**: Spaces around/between components filled with Markov-generated content
- **Template-based**: Multiple arrangement patterns tried automatically

### Integration with Existing Constraints
- **Length constraints**: min_length, max_length
- **Position constraints**: starts_with, ends_with  
- **Content constraints**: includes, excludes
- **Pattern constraints**: regex_pattern

## API Usage

### Configuration Parameters

Add these to your generation config:

```yaml
generation:
  components: ["co", "mind"]              # Required components
  component_order: [1, 0]                # Optional: specific ordering (indices)
  component_separation: [0, 3]           # Min/max chars between components
  min_length: 8                          # Total word length constraints
  max_length: 15
  # ... other existing parameters
```

### Python API

```python
from markov.name_generator import NameGenerator

generator = NameGenerator(data=training_words, order=3, temperature=1.0)

# Single name with components
name = generator.generate_name_with_components(
    components=["co", "mind"],
    min_length=8,
    max_length=15,
    component_separation=(0, 2)
)

# Multiple names
names = generator.generate_names_with_components(
    components=["co", "mind", "tech"],
    n=10,
    min_length=10,
    max_length=18,
    component_order=[2, 0, 1],  # tech, co, mind
    max_time_per_name=1.0
)
```

### REST API

```json
{
  "generation": {
    "n_words": 10,
    "min_length": 8,
    "max_length": 15,
    "components": ["co", "mind"],
    "component_order": null,
    "component_separation": [0, 3],
    "max_time_per_name": 2.0
  }
}
```

## Examples

### Basic Usage

**Input:**
- Components: ["co", "mind"]  
- Length: 8-12 chars

**Output:**
- `cocolmind` (co + col + mind)
- `mindeco` (mind + eco)
- `coramind` (co + ra + mind)

### Specific Ordering

**Input:**
- Components: ["brain", "smart"]
- Order: [1, 0] (smart first, then brain)

**Output:**
- `smartbrain`
- `smarterbrain`  
- `smartybrain`

### Triple Components

**Input:**
- Components: ["co", "mind", "tech"]
- Length: 12-18 chars

**Output:**
- `cominditech` (co + mind + i + tech)
- `techcopmind` (tech + co + p + mind)
- `comindlytech` (co + mind + ly + tech)

## Technical Architecture

### Core Classes

1. **ComponentConstraints**: Extended constraint container with component-specific parameters
2. **TemplateGenerator**: Creates arrangement templates with different component orderings  
3. **ComponentTemplate**: Defines fixed component positions and variable segment ranges
4. **SegmentSampler**: Samples variable segments using Markov model with context awareness
5. **MultiComponentSampler**: Orchestrates the complete generation process

### Algorithm Flow

1. **Template Generation**: Create multiple arrangement templates with different:
   - Component orderings (if not specified)
   - Target lengths within min/max range
   - Space distribution among variable segments

2. **Template Sampling**: For each template:
   - Sample content for each variable segment using Markov model
   - Assemble components and segments into final word
   - Validate against all constraints

3. **Constraint Validation**: Ensure final words meet:
   - All components present
   - Length requirements
   - Standard constraints (starts_with, ends_with, etc.)

### Performance Considerations

- **Template limits**: Maximum templates tried per generation (configurable)
- **Time limits**: Per-name generation timeout (configurable)  
- **Context-aware sampling**: Uses Markov model context for realistic segment content
- **Early termination**: Stops trying templates once valid word found

## Configuration Examples

### Startup/Tech Company Names
```yaml
generation:
  components: ["tech", "co"]
  min_length: 6
  max_length: 12
  component_separation: [0, 2]
```
Example outputs: `techno`, `cotech`, `techyco`

### AI/Cognitive Brands  
```yaml
generation:
  components: ["mind", "ai"]
  min_length: 8
  max_length: 14
  component_separation: [1, 3]
  starts_with: "neo"
```
Example outputs: `neomindai`, `neoaimind`

### Product Names
```yaml  
generation:
  components: ["smart", "hub", "pro"]
  min_length: 10
  max_length: 16
  component_order: [0, 1, 2]  # smart + hub + pro
```
Example outputs: `smarthubpro`, `smarterhubpro`

## Troubleshooting

### No Results Generated
- **Too restrictive**: Reduce min_length or increase max_length
- **Incompatible components**: Some component combinations may be impossible
- **Increase timeout**: Use higher max_time_per_name values

### Poor Quality Results
- **Adjust temperature**: Higher values (1.2-1.5) for more creativity
- **Check training data**: Ensure relevant vocabulary in training corpus
- **Component separation**: Experiment with different spacing ranges

### Performance Issues  
- **Reduce max_templates**: Limit template generation (default: 20)
- **Lower max_time_per_name**: Set shorter timeouts
- **Simpler components**: Use shorter, more common component strings

## Future Enhancements

- **Component overlapping**: Allow components to share characters
- **Weighted components**: Prioritize certain components over others
- **Semantic constraints**: Component relationships based on meaning
- **Multi-language support**: Component generation in different languages