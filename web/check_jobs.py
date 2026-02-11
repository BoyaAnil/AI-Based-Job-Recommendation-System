import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.settings')
django.setup()

from core.models import Job

total = Job.objects.count()
print(f"Total jobs in database: {total}")

if total > 0:
    print("\nFirst 5 jobs:")
    for job in Job.objects.all()[:5]:
        print(f"  ID {job.id}: {job.title} at {job.company}")
else:
    print("\n❌ No jobs found! Database is empty.")
