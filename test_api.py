"""
Check GooseAI engines and API structure
"""
import requests
import json

api_key = "sk-R2q7k7e8daaPYerM63O5wzfNRz74V8E5EPLWtabsNsDUHwtv"

headers = {
    'Authorization': f'Bearer {api_key}'
}

# Try engines endpoint (like OpenAI)
print("Testing /engines endpoint...")
response = requests.get("https://api.goose.ai/v1/engines", headers=headers)
print(f"Engines endpoint: {response.status_code}")
if response.status_code == 200:
    print(json.dumps(response.json(), indent=2))
else:
    print(f"Error: {response.text}")

print("\n" + "="*50 + "\n")

# Try models endpoint
print("Testing /models endpoint...")
response = requests.get("https://api.goose.ai/v1/models", headers=headers)
print(f"Models endpoint: {response.status_code}")
if response.status_code == 200:
    print(json.dumps(response.json(), indent=2))
else:
    print(f"Error: {response.text}")

print("\n" + "="*50 + "\n")

# Try a different completion format
print("Testing different completion format...")
data = {
    "model": "gpt-neo-1.3b",
    "prompt": "Hello",
    "max_tokens": 5
}

response = requests.post(
    "https://api.goose.ai/v1/engines/gpt-neo-1.3b/completions",
    headers=headers,
    json=data
)
print(f"Engines completion: {response.status_code}")
if response.status_code == 200:
    print(json.dumps(response.json(), indent=2))
else:
    print(f"Error: {response.text}")