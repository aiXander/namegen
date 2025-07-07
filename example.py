#!/usr/bin/env python3

"""
Example usage of the Markov Name Generator
"""

from markov_namegen import MarkovNameGenerator

def main():
    # Create generator with default config
    generator = MarkovNameGenerator()
    
    # Generate names
    print("Generating names with default settings...")
    names = generator.run()
    
    print(f"\nGenerated {len(names)} names:")
    for i, name in enumerate(names, 1):
        print(f"{i:2d}. {name}")
    
    # Example of generating names with custom parameters
    print("\n" + "="*50)
    print("Generating names with custom parameters...")
    
    custom_names = generator.generator.generate_names(
        n=5,
        min_length=6,
        max_length=10,
        starts_with="th",
        ends_with="",
        includes="",
        excludes="",
        max_time_per_name=0.1
    )
    
    print(f"\nGenerated {len(custom_names)} names starting with 'th':")
    for i, name in enumerate(custom_names, 1):
        print(f"{i:2d}. {name}")

if __name__ == "__main__":
    main()