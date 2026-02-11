import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so 'web' package is importable when
# this script is executed from the scripts/ directory.
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.settings')
import django
django.setup()
from core.models import Job, Resume

print('JOB_COUNT:', Job.objects.count())
resumes = Resume.objects.all()
print('RESUME_COUNT:', resumes.count())
for r in resumes[:5]:
    print(r.id, r.uploaded_at, len((r.raw_text or '').strip()))
