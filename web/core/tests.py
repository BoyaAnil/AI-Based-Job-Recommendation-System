import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Resume, Job


class CoreViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester",
            email="tester@example.com",
            password="testpass123"
        )
        self.client.login(username="tester", password="testpass123")

    def test_home_page(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)

    @patch("core.services.parse_resume")
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

    @patch("core.services.match_resume_job")
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
