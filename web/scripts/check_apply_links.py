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

print('Checking apply_link values:')
jobs = Job.objects.all()[:3]
for job in jobs:
    print(f"  {job.title}: {job.apply_link}")
