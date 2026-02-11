import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so the 'web' package can be imported
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.settings')
import django
django.setup()
from core.models import Resume, Job
from core.services import parse_resume, match_resume_job, AIServiceError

resume = Resume.objects.filter(pk=1).first()
job = Job.objects.first()
print('Resume id:', resume.id)
print('Raw text length before:', len((resume.raw_text or '').strip()))
if not (resume.raw_text or '').strip():
    try:
        parsed = parse_resume(resume.original_file.path, resume.original_file.name.split('.')[-1].lower())
        resume.raw_text = parsed.get('raw_text', '')
        resume.extracted_json = parsed
        resume.save()
        print('Parsed and saved resume. Raw text length now:', len((resume.raw_text or '').strip()))
    except AIServiceError as exc:
        print('Parse failed:', exc)

job_payload = {"title": job.title, "description": job.description, "required_skills": job.required_skills}
try:
    result = match_resume_job(resume.raw_text, job_payload)
    print('Match result:', result)
except AIServiceError as exc:
    print('AI service error calling match:', exc)
