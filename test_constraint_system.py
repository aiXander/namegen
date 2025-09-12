#!/usr/bin/env python3
"""
Test script for the new constraint-integrated sampling system.
Validates that constraints are properly integrated and performance is improved.
"""

import time
import os
from typing import List
from markov.name_generator import NameGenerator


def load_test_data() -> List[str]:
    """Load some test data for training"""
    test_words = [
        "alexander", "alexandra", "alex", "alice", "andrew", "anna", "anthony", "antonio",
        "barbara", "benjamin", "betty", "brian", "carlos", "carol", "charles", "charlotte",
        "christopher", "daniel", "david", "deborah", "donald", "dorothy", "edward", "elizabeth",
        "emily", "emma", "ethan", "frank", "george", "helen", "henry", "isabella", "jacob",
        "james", "jennifer", "jessica", "john", "joseph", "joshua", "karen", "kenneth",
        "linda", "lisa", "mark", "mary", "matthew", "melissa", "michael", "michelle",
        "nancy", "nicole", "patricia", "paul", "richard", "robert", "ronald", "ruth",
        "sandra", "sarah", "sharon", "susan", "thomas", "william", "amanda", "amy",
        "angela", "ashley", "brenda", "catherine", "cynthia", "donna", "frances", "janet",
        "julie", "kathleen", "kimberly", "laura", "margaret", "maria", "marie", "martha",
        "rebecca", "stephanie", "virginia", "carolyn", "debra", "rachel", "janet", "frances"
    ]
    return test_words


def test_starts_with_constraint():
    """Test starts_with constraint integration"""
    print("\n=== Testing starts_with Constraint ===")
    
    data = load_test_data()
    generator = NameGenerator(data, order=3, temperature=1.0)
    
    # Test with different prefixes
    test_prefixes = ["al", "ch", "mar", "st"]
    
    for prefix in test_prefixes:
        print(f"\nTesting prefix: '{prefix}'")
        
        # Generate several names with this prefix
        success_count = 0
        total_attempts = 10
        
        start_time = time.time()
        
        for i in range(total_attempts):
            name = generator.generate_name(
                min_length=4, 
                max_length=12, 
                starts_with=prefix
            )
            
            if name and name.startswith(prefix):
                success_count += 1
                print(f"  ✓ {name}")
            elif name:
                print(f"  ❌ {name} (doesn't start with '{prefix}')")
            else:
                print(f"  ❌ <no name generated>")
        
        elapsed = time.time() - start_time
        success_rate = success_count / total_attempts * 100
        
        print(f"  Success rate: {success_rate:.1f}% ({success_count}/{total_attempts})")
        print(f"  Time: {elapsed:.3f}s ({elapsed/total_attempts:.3f}s per name)")


def test_ends_with_constraint():
    """Test ends_with constraint integration"""
    print("\n=== Testing ends_with Constraint ===")
    
    data = load_test_data()
    generator = NameGenerator(data, order=3, temperature=1.0)
    
    # Test with different suffixes
    test_suffixes = ["er", "th", "an", "ia"]
    
    for suffix in test_suffixes:
        print(f"\nTesting suffix: '{suffix}'")
        
        # Generate several names with this suffix
        success_count = 0
        total_attempts = 10
        
        start_time = time.time()
        
        for i in range(total_attempts):
            name = generator.generate_name(
                min_length=4, 
                max_length=12, 
                ends_with=suffix
            )
            
            if name and name.endswith(suffix):
                success_count += 1
                print(f"  ✓ {name}")
            elif name:
                print(f"  ❌ {name} (doesn't end with '{suffix}')")
            else:
                print(f"  ❌ <no name generated>")
        
        elapsed = time.time() - start_time
        success_rate = success_count / total_attempts * 100
        
        print(f"  Success rate: {success_rate:.1f}% ({success_count}/{total_attempts})")
        print(f"  Time: {elapsed:.3f}s ({elapsed/total_attempts:.3f}s per name)")


def test_excludes_constraint():
    """Test excludes constraint integration"""
    print("\n=== Testing excludes Constraint ===")
    
    data = load_test_data()
    generator = NameGenerator(data, order=3, temperature=1.0)
    
    # Test excluding common patterns
    forbidden_patterns = ["ll", "th", "er", "an"]
    
    for pattern in forbidden_patterns:
        print(f"\nTesting exclusion: '{pattern}'")
        
        # Generate several names without this pattern
        success_count = 0
        total_attempts = 15
        
        start_time = time.time()
        
        for i in range(total_attempts):
            name = generator.generate_name(
                min_length=4, 
                max_length=12, 
                excludes=pattern
            )
            
            if name and pattern not in name:
                success_count += 1
                print(f"  ✓ {name}")
            elif name:
                print(f"  ❌ {name} (contains '{pattern}')")
            else:
                print(f"  ❌ <no name generated>")
        
        elapsed = time.time() - start_time
        success_rate = success_count / total_attempts * 100
        
        print(f"  Success rate: {success_rate:.1f}% ({success_count}/{total_attempts})")
        print(f"  Time: {elapsed:.3f}s ({elapsed/total_attempts:.3f}s per name)")


def test_combined_constraints():
    """Test multiple constraints working together"""
    print("\n=== Testing Combined Constraints ===")
    
    data = load_test_data()
    generator = NameGenerator(data, order=3, temperature=1.0)
    
    # Test combinations
    test_cases = [
        {"starts_with": "al", "ends_with": "er", "description": "starts with 'al', ends with 'er'"},
        {"starts_with": "ch", "excludes": "ll", "description": "starts with 'ch', excludes 'll'"},
        {"min_length": 6, "max_length": 8, "starts_with": "mar", "description": "length 6-8, starts with 'mar'"},
    ]
    
    for test_case in test_cases:
        description = test_case.pop("description")
        print(f"\nTesting: {description}")
        
        success_count = 0
        total_attempts = 8
        
        start_time = time.time()
        
        for i in range(total_attempts):
            name = generator.generate_name(**test_case)
            
            # Validate all constraints
            valid = True
            if name:
                if "starts_with" in test_case and not name.startswith(test_case["starts_with"]):
                    valid = False
                if "ends_with" in test_case and not name.endswith(test_case["ends_with"]):
                    valid = False
                if "excludes" in test_case and test_case["excludes"] in name:
                    valid = False
                if "min_length" in test_case and len(name) < test_case["min_length"]:
                    valid = False
                if "max_length" in test_case and len(name) > test_case["max_length"]:
                    valid = False
            else:
                valid = False
            
            if valid:
                success_count += 1
                print(f"  ✓ {name}")
            elif name:
                print(f"  ❌ {name} (constraint violation)")
            else:
                print(f"  ❌ <no name generated>")
        
        elapsed = time.time() - start_time
        success_rate = success_count / total_attempts * 100
        
        print(f"  Success rate: {success_rate:.1f}% ({success_count}/{total_attempts})")
        print(f"  Time: {elapsed:.3f}s ({elapsed/total_attempts:.3f}s per name)")


def performance_comparison():
    """Compare performance between old and new constraint systems"""
    print("\n=== Performance Comparison ===")
    print("(This would require implementing a direct comparison, but based on the design,")
    print("we expect significant improvements for starts_with, ends_with, and excludes constraints)")


def main():
    """Run all constraint system tests"""
    print("Testing New Constraint-Integrated Sampling System")
    print("=" * 50)
    
    try:
        test_starts_with_constraint()
        test_ends_with_constraint()
        test_excludes_constraint()
        test_combined_constraints()
        performance_comparison()
        
        print("\n" + "=" * 50)
        print("✅ All tests completed! Check results above for constraint integration success.")
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()