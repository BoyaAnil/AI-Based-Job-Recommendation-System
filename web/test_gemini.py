import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.settings')
django.setup()

from core.services import fetch_gemini_jobs, fetch_jobs_auto

print("Testing fetch_jobs_auto with Gemini fallback...")
try:
    jobs, source = fetch_jobs_auto(query='python developer', location='India', limit=5)
    print(f'SUCCESS: Got {len(jobs)} jobs from {source}')
    for job in jobs[:2]:
        print(f"  - {job.get('title')} at {job.get('company')}")
except Exception as e:
    print(f'ERROR: {type(e).__name__}: {e}')

print("\nTesting fetch_gemini_jobs directly...")
try:
    jobs = fetch_gemini_jobs(query='python developer', location='India', limit=5)
    print(f'SUCCESS: Got {len(jobs)} jobs from Gemini')
    for job in jobs[:2]:
        print(f"  - {job.get('title')} at {job.get('company')}")
except Exception as e:
    print(f'ERROR: {type(e).__name__}: {e}')
