#!/usr/bin/env python3
"""
Test the full multi-component system integration
"""

import sys
import os
import yaml
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from markov_namegen import MarkovNameGenerator

def create_test_config():
    """Create a test configuration with components"""
    config = {
        'training_data': {
            'sources': ['test_words.txt'],
            'filter_special_chars': True
        },
        'model': {
            'order': 3,
            'temperature': 1.0,
            'backoff': True
        },
        'generation': {
            'n_words': 5,
            'min_length': 8,
            'max_length': 15,
            'components': ['co', 'mind'],
            'component_separation': [0, 2],
            'max_time_per_name': 2.0
        },
        'filtering': {
            'remove_duplicates': True,
            'exclude_training_words': False,
            'min_edit_distance': 0
        },
        'output': {
            'sort_by': 'random',
            'save_to_file': False
        }
    }
    return config

def create_test_words():
    """Create a test word list file"""
    words = [
        "cognitive", "mind", "brain", "neural", "think", "know", "learn",
        "memory", "recall", "focus", "attention", "awareness", "insight",
        "wisdom", "smart", "clever", "bright", "genius", "intellect",
        "concept", "idea", "thought", "notion", "theory", "logic",
        "reason", "rational", "analyze", "understand", "comprehend",
        "perceive", "recognize", "realize", "discover", "explore",
        "science", "technology", "innovation", "creative", "design"
    ]
    
    # Create word_lists directory if it doesn't exist
    os.makedirs("word_lists", exist_ok=True)
    
    with open("word_lists/test_words.txt", "w") as f:
        for word in words:
            f.write(word + "\n")

def test_full_system():
    """Test the complete system with components"""
    print("🧪 Testing full multi-component system...")
    
    # Create test files
    create_test_words()
    config = create_test_config()
    
    # Save config to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config, f)
        config_path = f.name
    
    try:
        print("Creating MarkovNameGenerator...")
        generator = MarkovNameGenerator(config_path)
        
        print("Generating names with components...")
        names = generator.generate_names()
        
        print(f"\n✅ Generated {len(names)} names with components ['co', 'mind']:")
        for i, name in enumerate(names, 1):
            print(f"  {i}. {name}")
            
        # Verify all names contain components
        print("\n🔍 Validation:")
        for name in names:
            has_co = 'co' in name
            has_mind = 'mind' in name
            print(f"  {name}: co=✅ mind=✅" if has_co and has_mind else f"  {name}: co={'✅' if has_co else '❌'} mind={'✅' if has_mind else '❌'}")
        
    finally:
        # Clean up
        os.unlink(config_path)
        if os.path.exists("word_lists/test_words.txt"):
            os.unlink("word_lists/test_words.txt")
        if os.path.exists("word_lists") and not os.listdir("word_lists"):
            os.rmdir("word_lists")

def test_different_configurations():
    """Test different component configurations"""
    print("\n🧪 Testing different component configurations...")
    
    create_test_words()
    
    configs = [
        {
            'components': ['brain'],
            'description': 'Single component'
        },
        {
            'components': ['co', 'mind', 'brain'],
            'component_separation': [1, 1],
            'description': 'Triple components with tight spacing'
        },
        {
            'components': ['think', 'smart'],
            'component_order': [1, 0],  # smart first, then think
            'description': 'Dual components with forced order'
        }
    ]
    
    base_config = {
        'training_data': {
            'sources': ['test_words.txt'],
            'filter_special_chars': True
        },
        'model': {
            'order': 3,
            'temperature': 1.2,
            'backoff': True
        },
        'generation': {
            'n_words': 3,
            'min_length': 8,
            'max_length': 16,
            'max_time_per_name': 1.5
        },
        'filtering': {
            'remove_duplicates': True,
            'exclude_training_words': False
        },
        'output': {
            'sort_by': 'random',
            'save_to_file': False
        }
    }
    
    try:
        for i, test_config in enumerate(configs, 1):
            print(f"\n--- Test {i}: {test_config['description']} ---")
            
            # Merge configurations
            config = base_config.copy()
            config['generation'].update({k: v for k, v in test_config.items() if k != 'description'})
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(config, f)
                config_path = f.name
            
            try:
                generator = MarkovNameGenerator(config_path)
                names = generator.generate_names()
                
                print(f"Generated names: {names}")
                
            finally:
                os.unlink(config_path)
                
    finally:
        # Clean up
        if os.path.exists("word_lists/test_words.txt"):
            os.unlink("word_lists/test_words.txt")
        if os.path.exists("word_lists") and not os.listdir("word_lists"):
            os.rmdir("word_lists")

if __name__ == "__main__":
    test_full_system()
    test_different_configurations()
    print("\n🎉 All tests completed!")