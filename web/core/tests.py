import json
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import RequestFactory
from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import reverse

from . import views
from .models import Resume, Job, Recommendation, MatchResult, JobRefreshState
from .services import AIServiceError, recommend_jobs as recommend_jobs_service, start_interview_simulator, advance_interview_simulator
from .job_refresh import DAILY_REFRESH_STATE_KEY, refresh_jobs_daily_if_needed


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

    def test_resume_delete_removes_resume_for_owner(self):
        resume = Resume.objects.create(
            user=self.user,
            original_file=SimpleUploadedFile("resume.pdf", b"dummy"),
            raw_text="Python developer",
        )

        response = self.client.post(reverse("resume_delete", args=[resume.id]))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("profile"))
        self.assertFalse(Resume.objects.filter(id=resume.id).exists())

    def test_resume_delete_rejects_other_users_resume(self):
        other_user = get_user_model().objects.create_user(
            username="other",
            email="other@example.com",
            password="testpass123",
        )
        resume = Resume.objects.create(
            user=other_user,
            original_file=SimpleUploadedFile("resume.pdf", b"dummy"),
            raw_text="Other resume",
        )

        response = self.client.post(reverse("resume_delete", args=[resume.id]))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Resume.objects.filter(id=resume.id).exists())


    @patch("core.views.match_resume_job")
    def test_match_job(self, mock_match_job):
        mock_match_job.return_value = {
            "score": 80,
            "ats_score": 80,
            "matched_skills": ["python"],
            "missing_skills": ["django"],
            "matched_keywords": ["python", "backend"],
            "missing_keywords": ["django"],
            "score_breakdown": [
                {"key": "keywords_match", "label": "Keywords Match", "weight": 35, "score": 80, "weighted_score": 28}
            ],
            "mistakes": ["Add missing role skills: django."],
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
        self.assertIn("mistakes", data)
        match_record = MatchResult.objects.get(id=data["match_id"])
        self.assertEqual(match_record.analysis_details.get("ats_score"), 80)
        self.assertTrue(match_record.analysis_details.get("score_breakdown"))

    @patch("core.views.match_resume_job")
    def test_resume_ats_check(self, mock_match_job):
        mock_match_job.return_value = {
            "score": 76,
            "ats_score": 76,
            "matched_skills": ["python", "sql"],
            "missing_skills": ["django"],
            "matched_keywords": ["python"],
            "missing_keywords": ["django"],
            "score_breakdown": [
                {"key": "keywords_match", "label": "Keywords Match", "weight": 35, "score": 70, "weighted_score": 24.5}
            ],
            "mistakes": ["Add missing role skills: django."],
            "summary": "ATS score 76/100.",
            "improvement_tips": ["Add Django project experience."],
        }
        resume = Resume.objects.create(
            user=self.user,
            original_file=SimpleUploadedFile("resume.pdf", b"dummy"),
            raw_text="Python SQL resume text",
        )
        response = self.client.post(
            reverse("resume_ats_check", args=[resume.id]),
            data=json.dumps({
                "job_title": "Backend Developer",
                "job_description": "Need python sql django",
                "required_skills": "python, sql, django",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["ats_score"], 76)
        self.assertIn("mistakes", data)

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

    def test_job_list_location_filter_matches_india_state_aliases(self):
        karnataka_job = Job.objects.create(
            title="Backend Engineer",
            company="Acme",
            location="Bengaluru, KA",
            level="Mid",
            salary_range="",
            description="Python role",
            required_skills=["python", "django"],
        )
        Job.objects.create(
            title="Backend Engineer",
            company="Elsewhere",
            location="Austin, TX",
            level="Mid",
            salary_range="",
            description="Python role",
            required_skills=["python", "django"],
        )

        request = self.factory.get(reverse("job_list"), {"location": "Karnataka", "show_all": "1"})
        request.user = self.user
        captured_context = {}

        def fake_render(_request, _template, context):
            captured_context.update(context)
            return HttpResponse("ok")

        with patch("core.views.render", side_effect=fake_render):
            response = views.job_list(request)

        self.assertEqual(response.status_code, 200)
        listed_ids = {job.id for job in captured_context["jobs"]}
        self.assertEqual(listed_ids, {karnataka_job.id})

    def test_job_list_location_filter_matches_remote_foreign_jobs(self):
        remote_job = Job.objects.create(
            title="Platform Engineer",
            company="Remote Co",
            location="Berlin, Germany (Remote)",
            level="Mid",
            salary_range="",
            description="Remote platform role",
            required_skills=["python", "docker"],
        )
        Job.objects.create(
            title="Platform Engineer",
            company="Onsite Co",
            location="Berlin, Germany",
            level="Mid",
            salary_range="",
            description="Onsite platform role",
            required_skills=["python", "docker"],
        )

        request = self.factory.get(reverse("job_list"), {"location": "Remote", "show_all": "1"})
        request.user = self.user
        captured_context = {}

        def fake_render(_request, _template, context):
            captured_context.update(context)
            return HttpResponse("ok")

        with patch("core.views.render", side_effect=fake_render):
            response = views.job_list(request)

        self.assertEqual(response.status_code, 200)
        listed_ids = {job.id for job in captured_context["jobs"]}
        self.assertEqual(listed_ids, {remote_job.id})

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

    @patch("core.views.recommend_jobs")
    @patch("core.views.fetch_jobs_for_location_targets")
    def test_recommendations_import_remote_and_india_jobs(self, mock_fetch_jobs_for_targets, mock_recommend_jobs):
        resume = Resume.objects.create(
            user=self.user,
            original_file=SimpleUploadedFile("resume.pdf", b"dummy"),
            raw_text="Python developer",
            extracted_json={"skills": ["python", "django", "docker"]},
        )
        mock_fetch_jobs_for_targets.return_value = ([
            {
                "title": "Remote Python Engineer",
                "company": "Global Remote",
                "location": "Remote - Germany",
                "level": "Mid",
                "salary_range": "",
                "description": "Remote python role",
                "required_skills": ["python", "docker"],
                "apply_link": "https://example.com/remote",
            },
            {
                "title": "India Backend Engineer",
                "company": "India Tech",
                "location": "Bengaluru, KA",
                "level": "Mid",
                "salary_range": "",
                "description": "India backend role",
                "required_skills": ["python", "django"],
                "apply_link": "https://example.com/india",
            },
        ], "remotive, themuse")
        mock_recommend_jobs.return_value = {"recommendations": []}

        request = self.factory.get(
            reverse("recommendations"),
            {"resume_id": resume.id, "include_api": 1, "api_location": "Remote | India"},
        )
        request.user = self.user
        request.session = self.client.session
        captured_context = {}

        def fake_render(_request, _template, context):
            captured_context.update(context)
            return HttpResponse("ok")

        with patch("core.views.messages.info"), patch("core.views.render", side_effect=fake_render):
            response = views.recommendations(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured_context["api_jobs_added"], 2)
        self.assertEqual(Job.objects.filter(title="Remote Python Engineer").count(), 1)
        self.assertEqual(Job.objects.filter(title="India Backend Engineer").count(), 1)
        self.assertEqual(
            mock_fetch_jobs_for_targets.call_args.kwargs["location"],
            "Remote | India",
        )

    @override_settings(AI_SERVICE_URL="http://127.0.0.1:5000", AI_SERVICE_FALLBACK_LOCAL=True)
    @patch("core.services.ai_post")
    def test_recommend_jobs_falls_back_for_local_405(self, mock_ai_post):
        mock_ai_post.side_effect = AIServiceError("AI service error (405): Method Not Allowed", status_code=405)

        result = recommend_jobs_service(
            "Python Django developer",
            [{
                "id": 1,
                "title": "Python Developer",
                "description": "Looking for Python and Django experience",
                "required_skills": ["python", "django"],
            }],
            top_n=5,
        )

        self.assertEqual(len(result["recommendations"]), 1)
        self.assertEqual(result["recommendations"][0]["job_id"], 1)


    def test_fake_job_detector_page_flags_suspicious_listing(self):
        response = self.client.post(
            reverse("fake_job_detector"),
            {
                "job_title": "Remote Data Entry Executive",
                "company": "",
                "description": "Urgent hiring. No interview. Earn money from home with daily payout. Pay registration fee and contact on WhatsApp now.",
            },
        )
        self.assertEqual(response.status_code, 200)
        analysis = response.context["analysis"]
        self.assertEqual(analysis["risk_level"], "high")
        self.assertGreaterEqual(analysis["risk_score"], 60)

    @patch("core.services.requests.get")
    def test_fake_job_detector_accepts_link_without_scheme(self, mock_get):
        mock_response = Mock()
        mock_response.url = "https://jobs.lever.co/acme/software-engineer"
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.text = "<html><title>Software Engineer | Acme</title><body>Acme is hiring a Python Django engineer for product work.</body></html>"
        mock_get.return_value = mock_response

        response = self.client.post(
            reverse("fake_job_detector"),
            {
                "apply_link": "jobs.lever.co/acme/software-engineer",
            },
        )
        self.assertEqual(response.status_code, 200)
        analysis = response.context["analysis"]
        self.assertEqual(analysis["link_analysis"]["domain"], "jobs.lever.co")
        self.assertEqual(analysis["link_analysis"]["submitted_url"], "https://jobs.lever.co/acme/software-engineer")

    def test_job_fake_check_endpoint_returns_json(self):
        job = Job.objects.create(
            title="Remote Data Entry Executive",
            company="",
            location="Remote",
            level="Entry",
            salary_range="",
            description="Urgent hiring. No interview. Earn money from home and pay a security deposit on WhatsApp.",
            required_skills=["communication"],
            apply_link="",
        )
        response = self.client.post(reverse("job_fake_check", args=[job.id]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["risk_level"], "high")
        self.assertGreaterEqual(data["risk_score"], 60)


    def test_interview_simulator_start_service_returns_opening_prompt(self):
        state, payload = start_interview_simulator(
            {
                "name": "Test User",
                "skills": ["python", "django", "sql"],
                "projects": [{"name": "Order Service"}],
                "experience": [{"title": "Backend Engineer"}],
            },
            role="Backend Engineer",
            company="Acme",
            focus="backend",
            total_rounds=6,
        )
        self.assertEqual(state["status"], "active")
        self.assertEqual(payload["difficulty"], 2)
        self.assertIn("Order Service", payload["question"])
        self.assertGreaterEqual(len(state["question_bank"]), 50)
        self.assertGreaterEqual(payload["progress"]["total"], 50)
        self.assertIn(payload["question_details"]["kind"], ["text", "radio", "checkbox"])

    def test_interview_simulator_increases_difficulty_for_strong_answer(self):
        state, _ = start_interview_simulator(
            {
                "skills": ["python", "django", "postgres"],
                "projects": [{"name": "Payments Platform"}],
                "experience": [{"title": "Backend Engineer"}],
            },
            role="Backend Engineer",
            focus="backend",
        )
        answer = (
            "I led the rollout for our payments platform. First, I profiled the API and found a 42% latency spike caused by slow queries. "
            "Then I added indexes, rewrote the hottest query, and put a rollback plan in place because checkout errors were affecting customers. "
            "The result was a 38% drop in latency, a 24% improvement in conversion, and a safer release process."
        )
        new_state, payload = advance_interview_simulator(state, answer)
        self.assertGreaterEqual(new_state["difficulty"], 3)
        self.assertGreaterEqual(payload["evaluation"]["depth"], 70)

    def test_interview_simulator_triggers_pressure_for_weak_answer(self):
        state, _ = start_interview_simulator(
            {
                "skills": ["python"],
                "projects": [{"name": "Analytics Dashboard"}],
            },
            role="Software Engineer",
            focus="general",
        )
        new_state, payload = advance_interview_simulator(state, "I worked on it. It was good. We did some things and it went okay.")
        self.assertIsNotNone(payload["pressure_event"])
        self.assertLessEqual(new_state["difficulty"], 2)
        self.assertEqual(payload["status"], "active")

    def test_interview_simulator_page_loads(self):
        resume = Resume.objects.create(
            user=self.user,
            original_file=SimpleUploadedFile("resume.pdf", b"dummy"),
            raw_text="Python Django developer",
            extracted_json={"skills": ["python", "django"]},
        )
        response = self.client.get(reverse("interview_simulator"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AI Interview Simulator")
        self.assertContains(response, str(resume.id))

    def test_interview_simulator_endpoints_return_session_payloads(self):
        resume = Resume.objects.create(
            user=self.user,
            original_file=SimpleUploadedFile("resume.pdf", b"dummy"),
            raw_text="Python Django developer",
            extracted_json={
                "skills": ["python", "django", "sql"],
                "projects": [{"name": "Risk Engine"}],
                "experience": [{"title": "Software Engineer"}],
            },
        )
        start_response = self.client.post(
            reverse("interview_simulator_start"),
            data=json.dumps({
                "resume_id": resume.id,
                "role": "Backend Engineer",
                "company": "Acme",
                "focus": "backend",
                "rounds": 5,
            }),
            content_type="application/json",
        )
        self.assertEqual(start_response.status_code, 200)
        start_data = start_response.json()
        self.assertEqual(start_data["status"], "active")
        self.assertTrue(start_data["question"])
        self.assertGreaterEqual(start_data["progress"]["total"], 50)
        self.assertIn(start_data["question_details"]["kind"], ["text", "radio", "checkbox"])

        answer_response = self.client.post(
            reverse("interview_simulator_answer"),
            data=json.dumps({
                "answer": "I owned a Django API migration, cut query time by 35%, and documented the rollback plan before release.",
            }),
            content_type="application/json",
        )
        self.assertEqual(answer_response.status_code, 200)
        answer_data = answer_response.json()
        self.assertIn("evaluation", answer_data)
        self.assertTrue(answer_data["transcript"])


    def test_interview_simulator_scores_radio_question(self):
        state, _ = start_interview_simulator(
            {
                "skills": ["python", "django", "postgres"],
                "projects": [{"name": "Payments Platform"}],
            },
            role="Backend Engineer",
            focus="backend",
        )
        radio_question = next(question for question in state["question_bank"] if question["kind"] == "radio")
        state["current_question"] = radio_question
        best_option = max(radio_question["options"], key=lambda option: option["score"])
        new_state, payload = advance_interview_simulator(state, selected_options=[best_option["id"]])
        self.assertGreaterEqual(payload["evaluation"]["overall"], 80)
        self.assertTrue(new_state["turns"])
        self.assertEqual(new_state["turns"][0]["question_kind"], "radio")

    def test_interview_simulator_scores_checkbox_question(self):
        state, _ = start_interview_simulator(
            {
                "skills": ["python", "sql"],
                "projects": [{"name": "Risk Engine"}],
            },
            role="Data Analyst",
            focus="data",
        )
        checkbox_question = next(question for question in state["question_bank"] if question["kind"] == "checkbox")
        state["current_question"] = checkbox_question
        correct_ids = [option["id"] for option in checkbox_question["options"] if option.get("correct")]
        _, payload = advance_interview_simulator(state, selected_options=correct_ids)
        self.assertGreaterEqual(payload["evaluation"]["overall"], 75)
        self.assertEqual(payload["transcript"][0]["question_kind"], "checkbox")


    @override_settings(AUTO_DAILY_JOB_REFRESH=True, AUTO_DAILY_JOB_QUERY="backend engineer", AUTO_DAILY_JOB_LOCATION="India", AUTO_DAILY_JOB_LIMIT=10)
    @patch("core.job_refresh.fetch_jobs_auto")
    def test_refresh_jobs_daily_if_needed_imports_jobs_when_due(self, mock_fetch_jobs):
        mock_fetch_jobs.return_value = ([
            {
                "title": "Backend Engineer",
                "company": "Acme",
                "location": "India",
                "level": "Mid",
                "salary_range": "",
                "description": "Python Django role",
                "required_skills": ["python", "django"],
                "apply_link": "https://example.com/job",
            }
        ], "auto")

        result = refresh_jobs_daily_if_needed(force=True)

        self.assertTrue(result["executed"])
        self.assertEqual(result["status"], "refreshed")
        self.assertEqual(result["added"], 1)
        self.assertEqual(Job.objects.filter(title="Backend Engineer", company="Acme").count(), 1)
        state = JobRefreshState.objects.get(key=DAILY_REFRESH_STATE_KEY)
        self.assertEqual(state.last_source, "auto")
        self.assertTrue(state.last_success_at)

    @override_settings(AUTO_DAILY_JOB_REFRESH=True, AUTO_DAILY_JOB_REFRESH_HOURS=24)
    @patch("core.job_refresh.fetch_jobs_auto")
    def test_refresh_jobs_daily_if_needed_skips_recent_success(self, mock_fetch_jobs):
        JobRefreshState.objects.create(
            key=DAILY_REFRESH_STATE_KEY,
            last_success_at=timezone.now(),
            last_source="auto",
        )

        result = refresh_jobs_daily_if_needed()

        self.assertFalse(result["executed"])
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "refresh window not reached")
        mock_fetch_jobs.assert_not_called()

    @override_settings(
        AUTO_DAILY_JOB_REFRESH=True,
        AUTO_DAILY_JOB_QUERY="backend engineer",
        AUTO_DAILY_JOB_LOCATION="Remote | India",
        AUTO_DAILY_JOB_LIMIT=10,
    )
    @patch("core.job_refresh.fetch_jobs_auto")
    def test_refresh_jobs_daily_if_needed_imports_remote_and_india_targets(self, mock_fetch_jobs):
        def fetch_side_effect(*, query, location, limit):
            if location == "Remote":
                return ([
                    {
                        "title": "Remote Backend Engineer",
                        "company": "Global Remote",
                        "location": "Remote - Canada",
                        "level": "Mid",
                        "salary_range": "",
                        "description": "Remote backend role",
                        "required_skills": ["python", "docker"],
                        "apply_link": "https://example.com/remote-role",
                    }
                ], "remotive")
            if location == "India":
                return ([
                    {
                        "title": "India Backend Engineer",
                        "company": "India Tech",
                        "location": "Pune, Maharashtra",
                        "level": "Mid",
                        "salary_range": "",
                        "description": "India backend role",
                        "required_skills": ["python", "django"],
                        "apply_link": "https://example.com/india-role",
                    }
                ], "themuse")
            return ([], "none")

        mock_fetch_jobs.side_effect = fetch_side_effect

        result = refresh_jobs_daily_if_needed(force=True)

        self.assertTrue(result["executed"])
        self.assertEqual(result["status"], "refreshed")
        self.assertEqual(result["added"], 2)
        self.assertTrue(Job.objects.filter(title="Remote Backend Engineer", location="Remote - Canada").exists())
        self.assertTrue(Job.objects.filter(title="India Backend Engineer", location="Pune, Maharashtra").exists())
        self.assertIn("remotive", result["source"])
        self.assertIn("themuse", result["source"])
