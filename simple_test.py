#!/usr/bin/env python3
"""
Simple test for multi-component system
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from markov.multi_component_sampler import ComponentConstraints, TemplateGenerator

def test_template_generation():
    """Test just template generation"""
    print("🧪 Testing template generation...")
    
    constraints = ComponentConstraints(
        min_length=8,
        max_length=12,
        components=["co", "mind"],
        component_separation=(0, 2)
    )
    
    generator = TemplateGenerator()
    templates = generator.generate_templates(constraints)
    
    print(f"Generated {len(templates)} templates:")
    for i, template in enumerate(templates):
        print(f"  {i+1}. {template.template_string}")
        print(f"     Components at positions: {template.component_positions}")
        print(f"     Variable segments: {len(template.variable_segments)}")
        print(f"     Total length: {template.total_length}")
        print()

if __name__ == "__main__":
    test_template_generation()