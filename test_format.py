"""
Test using the correct GooseAI API format
"""
import requests
import os


def main():
    api_key = os.getenv("GOOSEAI_API_KEY")
    if not api_key:
        raise SystemExit("Missing GOOSEAI_API_KEY env var")

    headers = {
        'Authorization': f'Bearer {api_key}'
    }

    # Test using the engine completion format
    data = {
        "prompt": "Hello world",
        "max_tokens": 10,
        "temperature": 0.7
    }

    print("Testing engine completion format...")
    response = requests.post(
        "https://api.goose.ai/v1/engines/gpt-neo-1-3b/completions",
        headers=headers,
        json=data
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")

    if response.status_code == 200:
        print("SUCCESS! GooseAI is working")
    else:
        print("Trying alternative format...")

        # Try direct model parameter in different format
        alt_data = {
            "engine": "gpt-neo-1-3b",
            "prompt": "Hello world",
            "max_tokens": 10
        }

        response = requests.post(
            "https://api.goose.ai/v1/completions",
            headers=headers,
            json=alt_data
        )

        print(f"Alternative Status: {response.status_code}")
        print(f"Alternative Response: {response.text}")


if __name__ == '__main__':
    main()