import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.settings')
import django
django.setup()
from core.models import Job

cities = ['bengaluru', 'bangalore', 'hyderabad', 'chennai', 'mumbai', 'delhi', 'pune', 'bangalore', 'bangalore, karnataka']

print('Searching for jobs in Indian cities:', ', '.join(cities))
qs = Job.objects.all()
matches = []
for job in qs:
    loc = (job.location or '').lower()
    for city in cities:
        if city in loc:
            matches.append(job)
            break

if not matches:
    print('No jobs found for those cities in the database.')
else:
    for j in matches:
        print(f"- {j.title} | {j.company} | {j.location} | Apply: {j.apply_link or 'N/A'} | Detail: /jobs/{j.id}/")
    print(f"\nTotal: {len(matches)} job(s) found.")
