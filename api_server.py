#!/usr/bin/env python3

"""
API Server for Markov Name Generator React GUI
Provides REST API endpoints for the React frontend to communicate with the Python backend
"""

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os
import json
import yaml
import threading
import time
import sys
from typing import Dict, List, Any, Generator
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
    """Get available word lists with ratings and word counts"""
    word_lists = get_word_lists()
    result = []
    for word_list in word_lists:
        display_name = word_list.replace('_', ' ').replace('.txt', '').title()
        
        # Efficiently count words without loading full content
        word_count = 0
        try:
            file_path = os.path.join("word_lists", word_list)
            with open(file_path, 'r') as f:
                word_count = sum(1 for line in f if line.strip())
        except Exception as e:
            print(f"Error counting words in {word_list}: {e}")
            word_count = 0
        
        result.append({
            'filename': word_list,
            'display_name': display_name,
            'rating': word_list_ratings.get(word_list, 0),
            'selected': word_list in current_config.get('training_data', {}).get('sources', []),
            'word_count': word_count
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

@app.route('/api/config/save', methods=['POST'])
def save_config_as():
    """Save configuration to a specific file"""
    try:
        data = request.json
        filename = data.get('filename')
        config = data.get('config')
        
        if not filename or not config:
            return jsonify({'error': 'Filename and config are required'}), 400
            
        with open(filename, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
            
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/config/list', methods=['GET'])
def list_config_files():
    """List available config files"""
    try:
        config_files = []
        # Look for .yaml files in the current directory
        for file in os.listdir('.'):
            if file.endswith('.yaml'):
                config_files.append(file)
        return jsonify({'configs': sorted(config_files)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/config/load/<filename>', methods=['GET'])
def load_config_from_file(filename):
    """Load configuration from a specific file"""
    try:
        if not filename.endswith('.yaml'):
            filename += '.yaml'
            
        if not os.path.exists(filename):
            return jsonify({'error': f'Config file {filename} not found'}), 404
            
        with open(filename, 'r') as f:
            config_data = yaml.safe_load(f)
            
        return jsonify(config_data or {})
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
        scored_names, total_cost = llm_scorer.score_names(
            names=names,
            description=description,
            scored_examples=scored_examples,
            instructions=instructions
        )
        
        # Sort by score (highest first)
        scored_names.sort(key=lambda x: x[1], reverse=True)
        
        return jsonify({
            'scored_names': [{'name': name, 'score': score} for name, score in scored_names],
            'total_cost': total_cost
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

@app.route('/api/generate-stream', methods=['POST'])
def generate_names_stream():
    """Generate names with streaming progress updates"""
    global generator, cached_generator, cached_word_list_hash, cached_model_params_hash
    
    print("🔥 STREAM ENDPOINT CALLED!")
    print(f"Request method: {request.method}")
    print(f"Request headers: {dict(request.headers)}")
    
    try:
        config = request.json
        print(f"📨 Received config: {config}")
        current_config.update(config)
        print("✅ Config updated successfully")
        
        # Check if any word lists are selected
        selected_sources = config.get('training_data', {}).get('sources', [])
        print(f"📚 Selected sources: {selected_sources}")
        if not selected_sources:
            print("❌ No word lists selected!")
            def error_stream():
                yield f"data: {json.dumps({'type': 'error', 'message': 'Please select at least one word list'})}\n\n"
            return Response(error_stream(), mimetype='text/plain')
        
        # Create generator (with caching logic similar to GUI)
        print("🔨 Creating generator...")
        import hashlib
        current_word_list_hash = hashlib.md5(str(sorted(selected_sources)).encode()).hexdigest()
        model_params = config.get('model', {})
        current_model_params_hash = hashlib.md5(str(model_params).encode()).hexdigest()
        
        print(f"🔍 Hash comparison: current_wl={current_word_list_hash[:8]}, cached_wl={cached_word_list_hash[:8] if cached_word_list_hash else 'None'}")
        print(f"🔍 Hash comparison: current_mp={current_model_params_hash[:8]}, cached_mp={cached_model_params_hash[:8] if cached_model_params_hash else 'None'}")
        
        if (cached_generator is not None and
            cached_word_list_hash == current_word_list_hash and
            cached_model_params_hash == current_model_params_hash):
            print("♻️  Using cached generator")
            generator = cached_generator
        else:
            # Determine what triggered the rebuild
            reasons = []
            if cached_generator is None:
                reasons.append("no cached generator")
            if cached_word_list_hash != current_word_list_hash:
                reasons.append(f"word list changed ({cached_word_list_hash[:8] if cached_word_list_hash else 'None'} → {current_word_list_hash[:8]})")
            if cached_model_params_hash != current_model_params_hash:
                reasons.append(f"model params changed ({cached_model_params_hash[:8] if cached_model_params_hash else 'None'} → {current_model_params_hash[:8]})")
            
            print(f"🆕 Creating new generator - triggers: {', '.join(reasons)}")
            print(f"📚 Selected word lists: {selected_sources}")
            print(f"⚙️  Model parameters: order={model_params.get('order', 3)}, temp={model_params.get('temperature', 1.0)}, backoff={model_params.get('backoff', True)}")
            
            try:
                generator = MarkovNameGenerator()
                generator.config = current_config
                print("📖 Loading training data...")
                generator.training_words = generator._load_training_data()
                print(f"📊 Loaded {len(generator.training_words) if generator.training_words else 0} training words")
                
                from markov.name_generator import NameGenerator
                print("🧠 Creating NameGenerator...")
                generator.generator = NameGenerator(
                    data=generator.training_words,
                    order=model_params.get('order', 3),
                    temperature=model_params.get('temperature', 1.0),
                    backoff=model_params.get('backoff', True)
                )
                print("✅ NameGenerator created successfully")
                
                cached_generator = generator
                cached_word_list_hash = current_word_list_hash
                cached_model_params_hash = current_model_params_hash
                print("💾 Generator cached")
            except Exception as e:
                print(f"❌ ERROR creating generator: {str(e)}")
                import traceback
                traceback.print_exc()
                error_msg = f"Generator creation failed: {str(e)}"
                def error_stream():
                    yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
                return Response(error_stream(), mimetype='text/plain')
        
        # Update configuration with defaults
        if 'filtering' not in config:
            config['filtering'] = {
                'remove_duplicates': True,
                'exclude_training_words': False,
                'min_edit_distance': 0
            }
        if 'output' not in config:
            config['output'] = {
                'sort_by': 'random',
                'sort_ascending': True
            }
        
        generator.config.update(config)
        
        def generate_stream():
            print("🌊 Starting generate_stream function...")
            try:
                print("🎲 About to call generate_names_with_progress...")
                name_count = 0
                # Generate names with streaming
                for name in generate_names_with_progress(generator, config):
                    name_count += 1
                    yield f"data: {json.dumps({'type': 'progress', 'name': name})}\n\n"
                    time.sleep(0.01)  # Small delay to prevent overwhelming the frontend
                
                print(f"✅ Generation complete! Total names: {name_count}")
                yield f"data: {json.dumps({'type': 'complete'})}\n\n"
            except Exception as e:
                print(f"❌ ERROR in generate_stream: {str(e)}")
                import traceback
                traceback.print_exc()
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        return Response(generate_stream(), mimetype='text/plain')
        
    except Exception as e:
        def error_stream(error_msg):
            yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
        return Response(error_stream(str(e)), mimetype='text/plain')

def generate_names_with_progress(generator: MarkovNameGenerator, config: Dict[str, Any]) -> Generator[str, None, None]:
    """Generate names one by one, yielding each valid name as it's found"""
    print(f"🚀 Starting name generation...")
    print(f"📄 Config: {config}")
    
    gen_config = config.get('generation', {})
    print(f"⚙️  Generation config: {gen_config}")
    
    target_count = gen_config.get('n_words', 20)
    min_length = gen_config.get('min_length', 4)
    max_length = gen_config.get('max_length', 12)
    starts_with = gen_config.get('starts_with', '')
    ends_with = gen_config.get('ends_with', '')
    includes = gen_config.get('includes', '')
    excludes = gen_config.get('excludes', '')
    max_time_per_name = gen_config.get('max_time_per_name', 2.0)
    regex_pattern = gen_config.get('regex_pattern') if gen_config.get('regex_pattern') else None
    
    print(f"🎯 Target: {target_count} names")
    print(f"📏 Length: {min_length}-{max_length}")
    print(f"🔍 Constraints: starts='{starts_with}', ends='{ends_with}', includes='{includes}', excludes='{excludes}'")
    print(f"⏱️  Max time per name: {max_time_per_name}s")
    print(f"🧠 Generator ready: {generator is not None}")
    print(f"🧠 Inner generator: {generator.generator if generator else 'None'}")
    
    if generator and hasattr(generator, 'training_words'):
        print(f"📚 Training words: {len(generator.training_words) if generator.training_words else 0}")
    
    print("=" * 50)
    
    names = []
    start_time = time.time()
    last_success_time = start_time
    max_total_time = max_time_per_name * target_count
    attempts_since_last_success = 0
    max_attempts_per_name = 1000000
    
    while len(names) < target_count:
        try:
            name = generator.generator.generate_name(
                min_length=min_length,
                max_length=max_length,
                starts_with=starts_with,
                ends_with=ends_with,
                includes=includes,
                excludes=excludes,
                regex_pattern=regex_pattern
            )
            attempts_since_last_success += 1
        except Exception as e:
            print(f"\n❌ ERROR during name generation: {str(e)}")
            print(f"Exception type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            break
        
        if name is not None:
            # Apply filtering to this single name
            if should_keep_name(name, names, generator, config):
                names.append(name)
                yield name
                attempts_since_last_success = 0  # Reset attempts counter when we find a valid name
                last_success_time = time.time()  # Reset success timer
        
        # Safety check to prevent infinite loops
        current_time = time.time()
        time_since_last_success = current_time - last_success_time
        
        # Stop if we haven't found a name in too long OR total time exceeded
        if time_since_last_success > max_time_per_name * 2 or (current_time - start_time) > max_total_time:
            print(f"\n⏰ TIMEOUT: time_since_last_success={time_since_last_success:.3f}s, max_allowed={max_time_per_name * 2:.3f}s, total_time={(current_time - start_time):.3f}s, max_total={max_total_time:.3f}s, names_found={len(names)}")
            break
        
        # If we've tried many times without success, give up
        if attempts_since_last_success > max_attempts_per_name:
            print(f"\n🛑 MAX ATTEMPTS: attempts_since_last_success={attempts_since_last_success}, max_allowed={max_attempts_per_name}, names_found={len(names)}")
            break

def should_keep_name(name: str, existing_names: List[str], generator: MarkovNameGenerator, config: Dict[str, Any]) -> bool:
    """Check if a name should be kept based on filtering rules"""
    filter_config = config.get('filtering', {})
    
    # Remove duplicates
    if filter_config.get('remove_duplicates', True):
        if name in existing_names:
            return False
    
    # Remove names identical to training data
    if filter_config.get('exclude_training_words', True):
        if name in generator.training_words:
            return False
    
    # Remove names too similar to training data
    min_distance = filter_config.get('min_edit_distance', 0)
    if min_distance > 0:
        from markov_namegen import edit_distance
        for training_word in generator.training_words:
            if edit_distance(name, training_word) < min_distance:
                return False
    
    return True

if __name__ == '__main__':
    print("Starting Markov Name Generator API Server...")
    print("React frontend should connect to: http://localhost:5001")
    app.run(debug=True, host='0.0.0.0', port=5001)