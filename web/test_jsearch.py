import os
import django
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.settings')
django.setup()

from django.conf import settings

api_key = settings.JSEARCH_API_KEY
print(f"API Key: {api_key[:20]}...")

headers = {
    "x-rapidapi-key": api_key,
    "x-rapidapi-host": "jsearch.p.rapidapi.com"
}

url = "https://jsearch.p.rapidapi.com/search"
params = {
    "query": "developer",
    "page": 1,
    "num_pages": 1,
    "location": "India"
}

print("\nTesting API request...")
print(f"URL: {url}")
print(f"Headers: x-rapidapi-host={headers['x-rapidapi-host']}, x-rapidapi-key=***")
print(f"Params: {params}")

try:
    response = requests.get(url, headers=headers, params=params, timeout=10)
    print(f"\nResponse Status: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"\nResponse Body:\n{response.text}")
except Exception as e:
    print(f"\nError: {e}")
