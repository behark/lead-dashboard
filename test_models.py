"""
Quick test to find valid GooseAI models
"""
import requests
import os

def test_models():
    api_key = "sk-R2q7k7e8daaPYerM63O5wzfNRz74V8E5EPLWtabsNsDUHwtv"
    
    headers = {
        'Authorization': f'Bearer {api_key}'
    }
    
    # Try different model names
    models_to_test = [
        'gpt-neo-1.3b',
        'gpt-neo-125m',
        'gpt-neo-2.7b',
        'gpt-j-6b',
        'fairseq-13b',
        'gpt-neox-20b',
        'neo-1.3b',
        'gpt_neo_1.3b',
        'gptneo-1.3b'
    ]
    
    test_prompt = "Hello world"
    
    for model in models_to_test:
        print(f"Testing model: {model}")
        
        data = {
            "model": model,
            "prompt": test_prompt,
            "max_tokens": 10
        }
        
        response = requests.post(
            "https://api.goose.ai/v1/completions",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"✓ {model} works!")
            print(f"Response: {response.json()['choices'][0]['text']}")
            break
        else:
            print(f"✗ {model} failed: {response.status_code}")
            print(f"Error: {response.text}")
        print("---")

if __name__ == '__main__':
    test_models()