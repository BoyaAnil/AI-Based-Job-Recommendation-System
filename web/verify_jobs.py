import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.settings')
django.setup()

from core.models import Job

print(f'Total jobs in database: {Job.objects.count()}')
remote_jobs = Job.objects.filter(location='Remote')
print(f'Remote jobs from Remotive API: {remote_jobs.count()}')

print(f'\nSample real jobs fetched:')
for i, job in enumerate(remote_jobs[:5], 1):
    print(f'\n{i}. {job.title}')
    print(f'   Company: {job.company}')
    print(f'   Skills: {", ".join(job.required_skills[:3]) if job.required_skills else "N/A"}')
    print(f'   Apply: {job.apply_link[:50]}...' if job.apply_link else '   Apply: N/A')
