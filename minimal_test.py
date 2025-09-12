#!/usr/bin/env python3
"""
Minimal test for multi-component generation
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from markov.name_generator import NameGenerator

def test_minimal():
    """Test with minimal setup"""
    print("🧪 Testing minimal multi-component generation...")
    
    # Very simple training data
    words = ["hello", "world", "code", "mind", "think", "brain", "smart", "cool"]
    
    print("Creating generator...")
    generator = NameGenerator(data=words, order=2, temperature=1.0)
    
    print("Testing single component...")
    try:
        name = generator.generate_name_with_components(
            components=["co"],
            min_length=5,
            max_length=8
        )
        print(f"Single component result: {name}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\nTesting dual components...")
    try:
        name = generator.generate_name_with_components(
            components=["co", "mind"],
            min_length=8,
            max_length=12
        )
        print(f"Dual component result: {name}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\nTesting multiple generation...")
    try:
        names = generator.generate_names_with_components(
            components=["co", "mind"],
            n=3,
            min_length=8,
            max_length=12,
            max_time_per_name=1.0
        )
        print(f"Multiple results: {names}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_minimal()