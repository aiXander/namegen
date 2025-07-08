#!/usr/bin/env python3

"""
API Server for Markov Name Generator React GUI
Provides REST API endpoints for the React frontend to communicate with the Python backend
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
import yaml
import threading
from typing import Dict, List, Any
from markov_namegen import MarkovNameGenerator
from ai.llm_scorer import LLMScorer

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

# Global variables to store state
current_config = {}
saved_ratings = {}
word_list_ratings = {}
generator = None
cached_generator = None
cached_word_list_hash = None
cached_model_params_hash = None

def load_config() -> Dict[str, Any]:
    """Load configuration from YAML file"""
    try:
        with open("config.yaml", 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {}

def save_config(config: Dict[str, Any]):
    """Save configuration to YAML file"""
    try:
        with open("config.yaml", 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
    except Exception as e:
        print(f"Failed to save config: {str(e)}")

def load_saved_ratings():
    """Load saved ratings from file"""
    global saved_ratings
    try:
        if os.path.exists("saved_ratings.json"):
            with open("saved_ratings.json", 'r') as f:
                saved_ratings = json.load(f)
    except Exception as e:
        print(f"Error loading saved ratings: {e}")
        saved_ratings = {}

def save_ratings_to_file():
    """Save ratings to file"""
    try:
        with open("saved_ratings.json", 'w') as f:
            json.dump(saved_ratings, f, indent=2)
    except Exception as e:
        print(f"Error saving ratings: {e}")

def get_word_lists() -> List[str]:
    """Get list of available word lists"""
    word_lists = []
    if os.path.exists("word_lists"):
        word_lists = [f for f in os.listdir("word_lists") if f.endswith('.txt')]
    return sorted(word_lists)

# Initialize on startup
current_config = load_config()
load_saved_ratings()
word_list_ratings = current_config.get('word_list_ratings', {})

@app.route('/api/word-lists', methods=['GET'])
def get_word_lists_api():
    """Get available word lists with ratings"""
    word_lists = get_word_lists()
    result = []
    for word_list in word_lists:
        display_name = word_list.replace('_', ' ').replace('.txt', '').title()
        result.append({
            'filename': word_list,
            'display_name': display_name,
            'rating': word_list_ratings.get(word_list, 0),
            'selected': word_list in current_config.get('training_data', {}).get('sources', [])
        })
    return jsonify(result)

@app.route('/api/word-lists/<filename>', methods=['GET'])
def get_word_list_content(filename):
    """Get content of a specific word list"""
    try:
        file_path = os.path.join("word_lists", filename)
        with open(file_path, 'r') as f:
            words = [line.strip() for line in f if line.strip()]
        return jsonify({
            'filename': filename,
            'words': words,
            'total_count': len(words)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/word-lists/<filename>/rate', methods=['POST'])
def rate_word_list(filename):
    """Rate a word list"""
    try:
        data = request.json
        rating = data.get('rating', 0)
        word_list_ratings[filename] = rating
        current_config['word_list_ratings'] = word_list_ratings
        save_config(current_config)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    return jsonify(current_config)

@app.route('/api/config', methods=['POST'])
def update_config():
    """Update configuration"""
    global current_config
    try:
        current_config = request.json
        save_config(current_config)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate', methods=['POST'])
def generate_names():
    """Generate names based on configuration"""
    global generator, cached_generator, cached_word_list_hash, cached_model_params_hash
    
    try:
        config = request.json
        current_config.update(config)
        
        # Check if any word lists are selected
        selected_sources = config.get('training_data', {}).get('sources', [])
        if not selected_sources:
            return jsonify({'error': 'Please select at least one word list'}), 400
        
        # Create generator (with caching logic similar to GUI)
        import hashlib
        current_word_list_hash = hashlib.md5(str(sorted(selected_sources)).encode()).hexdigest()
        model_params = config.get('model', {})
        current_model_params_hash = hashlib.md5(str(model_params).encode()).hexdigest()
        
        if (cached_generator is not None and
            cached_word_list_hash == current_word_list_hash and
            cached_model_params_hash == current_model_params_hash):
            generator = cached_generator
        else:
            generator = MarkovNameGenerator()
            generator.config = current_config
            generator.training_words = generator._load_training_data()
            
            from markov.name_generator import NameGenerator
            generator.generator = NameGenerator(
                data=generator.training_words,
                order=model_params.get('order', 3),
                prior=model_params.get('prior', 0.01),
                backoff=model_params.get('backoff', True)
            )
            
            cached_generator = generator
            cached_word_list_hash = current_word_list_hash
            cached_model_params_hash = current_model_params_hash
        
        # Generate names
        names = generator.generate_names()
        
        return jsonify({
            'names': names,
            'count': len(names)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ratings', methods=['GET'])
def get_ratings():
    """Get all saved ratings"""
    return jsonify(saved_ratings)

@app.route('/api/ratings/<name>', methods=['POST'])
def rate_name(name):
    """Rate a name"""
    try:
        data = request.json
        rating = data.get('rating', 0)
        saved_ratings[name] = rating
        save_ratings_to_file()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ratings/<name>', methods=['DELETE'])
def delete_rating(name):
    """Delete a rating"""
    try:
        if name in saved_ratings:
            del saved_ratings[name]
            save_ratings_to_file()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ratings', methods=['DELETE'])
def clear_all_ratings():
    """Clear all ratings"""
    try:
        saved_ratings.clear()
        save_ratings_to_file()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/score', methods=['POST'])
def ai_score_names():
    """Score names using AI"""
    try:
        data = request.json
        names = data.get('names', [])
        description = data.get('description', '')
        instructions = data.get('instructions', '')
        model = data.get('model', 'gpt-3.5-turbo')
        max_chunk_size = data.get('max_chunk_size', 10)
        
        if not names:
            return jsonify({'error': 'No names provided'}), 400
        if not description:
            return jsonify({'error': 'Description is required'}), 400
        if not instructions:
            return jsonify({'error': 'Instructions are required'}), 400
        
        # Get scored examples from saved ratings
        scored_examples = []
        for name, rating in saved_ratings.items():
            if rating > 0:
                scored_examples.append((name, rating))
        scored_examples.sort(key=lambda x: x[1], reverse=True)
        scored_examples = scored_examples[:20]  # Limit to top 20
        
        # Initialize LLM scorer
        llm_scorer = LLMScorer(model=model, max_chunk_size=max_chunk_size)
        
        # Score names
        scored_names = llm_scorer.score_names(
            names=names,
            description=description,
            scored_examples=scored_examples,
            instructions=instructions
        )
        
        # Sort by score (highest first)
        scored_names.sort(key=lambda x: x[1], reverse=True)
        
        return jsonify({
            'scored_names': [{'name': name, 'score': score} for name, score in scored_names]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/models', methods=['GET'])
def get_ai_models():
    """Get available AI models"""
    try:
        models = LLMScorer.get_available_models()
        return jsonify({'models': models})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("Starting Markov Name Generator API Server...")
    print("React frontend should connect to: http://localhost:5001")
    app.run(debug=True, host='0.0.0.0', port=5001)