#!/usr/bin/env python3
"""
Test script for multi-component name generation.
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from markov.name_generator import NameGenerator
from markov.multi_component_sampler import ComponentConstraints

def test_component_generation():
    """Test multi-component name generation with some sample data"""
    
    # Create sample training data
    sample_words = [
        "cognitive", "mind", "brain", "neural", "think", "know", "learn",
        "memory", "recall", "focus", "attention", "awareness", "insight",
        "wisdom", "smart", "clever", "bright", "genius", "intellect",
        "concept", "idea", "thought", "notion", "theory", "logic",
        "reason", "rational", "analyze", "understand", "comprehend",
        "perceive", "recognize", "realize", "discover", "explore"
    ]
    
    print("🧠 Creating NameGenerator with sample cognitive words...")
    generator = NameGenerator(
        data=sample_words,
        order=3,
        temperature=1.0,
        backoff=True
    )
    
    print("\n🎯 Testing single component generation...")
    components_single = ["co"]
    names = generator.generate_names_with_components(
        components=components_single,
        n=5,
        min_length=6,
        max_length=12,
        max_time_per_name=1.0
    )
    print(f"Generated names with component '{components_single[0]}': {names}")
    
    print("\n🎯 Testing dual component generation...")
    components_dual = ["co", "mind"]
    names = generator.generate_names_with_components(
        components=components_dual,
        n=5,
        min_length=8,
        max_length=15,
        component_separation=(0, 2),
        max_time_per_name=2.0
    )
    print(f"Generated names with components {components_dual}: {names}")
    
    print("\n🎯 Testing with specific component order...")
    names = generator.generate_names_with_components(
        components=components_dual,
        n=3,
        min_length=10,
        max_length=16,
        component_order=[1, 0],  # mind first, then co
        component_separation=(1, 3),
        max_time_per_name=2.0
    )
    print(f"Generated names with order [mind, co]: {names}")
    
    print("\n🎯 Testing triple component generation...")
    components_triple = ["co", "mind", "think"]
    names = generator.generate_names_with_components(
        components=components_triple,
        n=3,
        min_length=12,
        max_length=20,
        component_separation=(0, 2),
        max_time_per_name=3.0
    )
    print(f"Generated names with components {components_triple}: {names}")
    
    print("\n🎯 Testing with additional constraints...")
    names = generator.generate_names_with_components(
        components=["co", "brain"],
        n=3,
        min_length=10,
        max_length=15,
        starts_with="neo",
        component_separation=(1, 2),
        max_time_per_name=2.0
    )
    print(f"Generated names starting with 'neo' and containing ['co', 'brain']: {names}")

if __name__ == "__main__":
    test_component_generation()