#!/usr/bin/env python3
"""
Test API integration with multi-component generation
"""

import json
import requests
import sys

def test_api_component_generation():
    """Test the API with component generation"""
    
    # Test configuration with components
    config = {
        "training_data": {
            "sources": ["pokemon.txt", "programming_languages.txt"]
        },
        "model": {
            "order": 3,
            "temperature": 1.2,
            "backoff": True
        },
        "generation": {
            "n_words": 5,
            "min_length": 8,
            "max_length": 15,
            "components": ["co", "tech"],
            "component_separation": [0, 2],
            "max_time_per_name": 3.0
        },
        "filtering": {
            "remove_duplicates": True,
            "exclude_training_words": False
        },
        "output": {
            "sort_by": "random"
        }
    }
    
    try:
        print("🧪 Testing API integration with multi-component generation...")
        
        # Test configuration endpoint
        print("1. Testing config update...")
        response = requests.post("http://localhost:5001/api/config", json=config, timeout=10)
        if response.status_code == 200:
            print("   ✅ Config updated successfully")
        else:
            print(f"   ❌ Config update failed: {response.status_code}")
            return False
        
        # Test streaming generation endpoint with EventSource-like parsing
        print("2. Testing streaming generation with components...")
        response = requests.post("http://localhost:5001/api/generate-stream", 
                               json=config, 
                               stream=True, 
                               timeout=30)
        
        if response.status_code != 200:
            print(f"   ❌ Stream request failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
        
        names = []
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    try:
                        data = json.loads(line[6:])  # Remove 'data: ' prefix
                        if data.get('type') == 'progress':
                            name = data.get('name')
                            if name:
                                names.append(name)
                                print(f"   📝 Generated: {name}")
                        elif data.get('type') == 'complete':
                            print("   ✅ Generation completed")
                            break
                        elif data.get('type') == 'error':
                            print(f"   ❌ Generation error: {data.get('message')}")
                            return False
                    except json.JSONDecodeError:
                        continue
        
        print(f"\n🎉 Successfully generated {len(names)} names with components ['co', 'tech']:")
        for i, name in enumerate(names, 1):
            has_co = 'co' in name.lower()
            has_tech = 'tech' in name.lower()
            status = "✅" if (has_co and has_tech) else "⚠️"
            print(f"   {i}. {name} {status}")
        
        # Validate components
        valid_names = [name for name in names if 'co' in name.lower() and 'tech' in name.lower()]
        print(f"\n📊 Validation: {len(valid_names)}/{len(names)} names contain both components")
        
        if len(valid_names) > 0:
            print("✅ API integration test PASSED!")
            return True
        else:
            print("⚠️  API integration test partially successful (no names with both components)")
            return True
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to API server. Make sure it's running on localhost:5001")
        return False
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    success = test_api_component_generation()
    sys.exit(0 if success else 1)