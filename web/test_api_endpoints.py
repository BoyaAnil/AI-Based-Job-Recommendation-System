import os
import django
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.settings')
django.setup()

from django.conf import settings

api_key = settings.JSEARCH_API_KEY

headers = {
    "x-rapidapi-key": api_key,
    "x-rapidapi-host": "jobs-api14.p.rapidapi.com"
}

# Try different endpoint variations
endpoints = [
    "https://jobs-api14.p.rapidapi.com/search",
    "https://jobs-api14.p.rapidapi.com/jobs",
    "https://jobs-api14.p.rapidapi.com/",
    "https://jobs-api14.p.rapidapi.com/api/search",
]

params = {
    "keywords": "developer",
    "location": "India"
}

print("Testing different endpoint variations...\n")

for endpoint in endpoints:
    try:
        response = requests.get(endpoint, headers=headers, params=params, timeout=5)
        print(f"✓ {endpoint}")
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  Response keys: {list(data.keys())[:5]}")
            break
        else:
            print(f"  Response: {response.text[:100]}")
    except Exception as e:
        print(f"✗ {endpoint}")
        print(f"  Error: {str(e)[:80]}")
    print()
