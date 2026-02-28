import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import RequestFactory
from django.test import TestCase, override_settings
from django.urls import reverse

from . import views
from .models import Resume, Job, Recommendation


@override_settings(AUTO_DAILY_JOB_REFRESH=False)
class CoreViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester",
            email="tester@example.com",
            password="testpass123"
        )
        self.factory = RequestFactory()
        self.client.login(username="tester", password="testpass123")

    def test_home_page(self):
        request = self.factory.get(reverse("home"))
        request.user = self.user
        with patch("core.views.render", return_value=HttpResponse("ok")):
            response = views.home(request)
        self.assertEqual(response.status_code, 200)

    @patch("core.views.parse_resume")
    def test_resume_upload(self, mock_parse_resume):
        mock_parse_resume.return_value = {
            "raw_text": "Sample resume text",
            "skills": ["python", "sql"],
            "education": [],
            "experience": [],
            "projects": []
        }
        uploaded = SimpleUploadedFile("resume.pdf", b"dummy", content_type="application/pdf")
        response = self.client.post(reverse("resume_upload"), {"original_file": uploaded})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Resume.objects.count(), 1)
        self.assertEqual(Resume.objects.first().raw_text, "Sample resume text")

    @patch("core.views.match_resume_job")
    def test_match_job(self, mock_match_job):
        mock_match_job.return_value = {
            "score": 80,
            "matched_skills": ["python"],
            "missing_skills": ["django"],
            "summary": "Good match",
            "improvement_tips": ["Add Django"]
        }
        job = Job.objects.create(
            title="Backend Engineer",
            company="Acme",
            location="Remote",
            level="Mid",
            salary_range="100k-120k",
            description="Looking for Django",
            required_skills=["python", "django"]
        )
        resume = Resume.objects.create(
            user=self.user,
            original_file=SimpleUploadedFile("resume.pdf", b"dummy"),
            raw_text="Python developer"
        )
        response = self.client.post(
            reverse("match_job", args=[job.id]),
            data=json.dumps({"resume_id": resume.id}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["score"], 80)

    def test_toggle_saved_job(self):
        job = Job.objects.create(
            title="Backend Engineer",
            company="Acme",
            location="Remote",
            level="Mid",
            salary_range="100k-120k",
            description="Looking for Django",
            required_skills=["python", "django"]
        )
        response = self.client.post(reverse("toggle_saved_job", args=[job.id]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["saved"])

    def test_job_list_shows_only_matching_jobs_for_uploaded_resume(self):
        resume = Resume.objects.create(
            user=self.user,
            original_file=SimpleUploadedFile("resume.pdf", b"dummy"),
            raw_text="Python developer",
            extracted_json={"skills": ["python", "django"]},
        )
        matching_job = Job.objects.create(
            title="Python Developer",
            company="Acme",
            location="Remote",
            level="Mid",
            salary_range="100k-120k",
            description="Python role",
            required_skills=["python", "django"],
        )
        Job.objects.create(
            title="UI Designer",
            company="Design Co",
            location="Remote",
            level="Mid",
            salary_range="90k-110k",
            description="Design role",
            required_skills=["figma", "ux"],
        )

        request = self.factory.get(reverse("job_list"))
        request.user = self.user
        captured_context = {}

        def fake_render(_request, _template, context):
            captured_context.update(context)
            return HttpResponse("ok")

        with patch("core.views.render", side_effect=fake_render):
            response = views.job_list(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured_context["selected_resume"], resume)
        listed_ids = {job.id for job in captured_context["jobs"]}
        self.assertEqual(listed_ids, {matching_job.id})

    @patch("core.views.recommend_jobs")
    def test_recommendations_persist_only_skill_matches(self, mock_recommend_jobs):
        resume = Resume.objects.create(
            user=self.user,
            original_file=SimpleUploadedFile("resume.pdf", b"dummy"),
            raw_text="Python developer",
            extracted_json={"skills": ["python", "django"]},
        )
        matching_job = Job.objects.create(
            title="Python Developer",
            company="Acme",
            location="Remote",
            level="Mid",
            salary_range="100k-120k",
            description="Python role",
            required_skills=["python", "django"],
        )
        non_matching_job = Job.objects.create(
            title="UI Designer",
            company="Design Co",
            location="Remote",
            level="Mid",
            salary_range="90k-110k",
            description="Design role",
            required_skills=["figma", "ux"],
        )
        mock_recommend_jobs.return_value = {
            "recommendations": [
                {"job_id": matching_job.id, "score": 90, "reason": "Matched skills: python, django"},
                {"job_id": non_matching_job.id, "score": 80, "reason": "Based on overall text similarity."},
            ]
        }

        request = self.factory.get(
            reverse("recommendations"),
            {"resume_id": resume.id, "include_api": 0},
        )
        request.user = self.user
        request.session = self.client.session
        with patch("core.views.render", return_value=HttpResponse("ok")):
            response = views.recommendations(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Recommendation.objects.filter(resume=resume).count(), 1)
        self.assertEqual(Recommendation.objects.get(resume=resume).job_id, matching_job.id)
