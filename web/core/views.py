import json
import logging
import random
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.core.mail import send_mail
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import PasswordResetDoneView, PasswordResetView
from django.db.models import Avg, Q
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.decorators.http import require_POST

from .forms import (
    UserRegistrationForm,
    ResumeUploadForm,
    JobForm,
    FakeJobDetectionForm,
    ProfileUpdateForm,
    ProfilePhotoForm,
    CustomPasswordChangeForm,
)
from .location_filters import LOCATION_SUGGESTIONS, QUICK_LOCATION_FILTERS, build_location_query
from .models import Resume, Job, MatchResult, Recommendation, SavedJob, UserProfile
from .services import (
    parse_resume,
    match_resume_job,
    recommend_jobs,
    skill_gap,
    detect_fake_job_posting,
    start_interview_simulator,
    advance_interview_simulator,
    INTERVIEW_SIMULATOR_SESSION_KEY,
    AIServiceError,
)
from .job_refresh import fetch_jobs_for_location_targets, merge_jobs_into_database, refresh_jobs_daily_if_needed

GENERIC_SKILL_TAGS = {"general", "remote"}
logger = logging.getLogger(__name__)


def _request_payload(request):
    if request.content_type == "application/json":
        try:
            return json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return None
    return request.POST


def _normalized_skill_set(skills):
    normalized = set()
    for skill in skills or []:
        if not isinstance(skill, str):
            continue
        value = skill.strip().lower()
        if value and value not in GENERIC_SKILL_TAGS:
            normalized.add(value)
    return normalized


def _is_resume_job_match(resume_skills, job_skills):
    if not resume_skills or not job_skills:
        return False
    overlap_count = len(resume_skills.intersection(job_skills))
    if len(job_skills) == 1:
        return overlap_count == 1
    return overlap_count >= 2


def _merge_jobs_into_database(fetched_jobs, default_location):
    return merge_jobs_into_database(fetched_jobs, default_location)


def _refresh_jobs_daily_if_needed():
    try:
        refresh_jobs_daily_if_needed()
    except AIServiceError as exc:
        logger.warning("Daily jobs refresh failed: %s", exc)
    except Exception as exc:
        logger.exception("Unexpected error during daily jobs refresh: %s", exc)


@login_required
def home(request):
    _refresh_jobs_daily_if_needed()
    return render(request, "home.html")


class CustomPasswordResetView(PasswordResetView):
    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.html"
    subject_template_name = "registration/password_reset_subject.txt"

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.session.pop("debug_password_reset_link", None)
        self.request.session.pop("debug_password_reset_user_found", None)
        self.request.session.pop("debug_password_reset_email", None)
        if settings.DEBUG:
            submitted_email = (form.cleaned_data.get("email") or "").strip()
            users = list(form.get_users(submitted_email))
            self.request.session["debug_password_reset_email"] = submitted_email
            self.request.session["debug_password_reset_user_found"] = bool(users)
            if users:
                user = users[0]
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                link = self.request.build_absolute_uri(
                    reverse("password_reset_confirm", kwargs={"uidb64": uid, "token": token})
                )
                self.request.session["debug_password_reset_link"] = link
        return response


class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = "registration/password_reset_done.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if settings.DEBUG:
            context["debug_reset_link"] = self.request.session.get("debug_password_reset_link")
            context["debug_email_backend"] = settings.EMAIL_BACKEND
            context["debug_email_file_path"] = (
                settings.EMAIL_FILE_PATH
                if settings.EMAIL_BACKEND == "django.core.mail.backends.filebased.EmailBackend"
                else ""
            )
            context["debug_requested_email"] = self.request.session.get("debug_password_reset_email", "")
            context["debug_user_found"] = self.request.session.get("debug_password_reset_user_found")
        return context


def register(request):
    if request.GET.get('reset') == '1':
        request.session.pop('registration_data', None)
        request.session.pop('otp', None)
        return redirect('register')

    session_data = request.session.get('registration_data')
    otp_sent = bool(session_data)
    registration_email = session_data.get('email') if session_data else ""
    registration_username = session_data.get('username') if session_data else ""

    if request.method == "POST":
        if "otp" in request.POST and otp_sent:
            entered_otp = request.POST.get('otp', '').strip()
            if entered_otp == request.session.get('otp'):
                data = request.session.get('registration_data')
                if data:
                    User = get_user_model()
                    user = User.objects.create_user(
                        username=data['username'],
                        email=data['email'],
                        password=data['password1']
                    )
                    login(request, user)
                    request.session.pop('otp', None)
                    request.session.pop('registration_data', None)
                    messages.success(request, "Account created and logged in.")
                    return redirect('home')
            messages.error(request, "Invalid OTP. Please try again.")
            form = UserRegistrationForm(initial=session_data)
        else:
            form = UserRegistrationForm(request.POST)
            if form.is_valid():
                email = form.cleaned_data['email']
                User = get_user_model()
                if User.objects.filter(email__iexact=email).exists():
                    messages.info(request, "This email is already registered. Please log in.")
                    return redirect('login')

                otp = str(random.randint(100000, 999999))
                print("Sending OTP to", email, "OTP:", otp)  # Debug print
                send_mail(
                    'Your OTP for registration',
                    f'Your OTP is {otp}',
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
                request.session['otp'] = otp
                request.session['registration_data'] = form.cleaned_data
                otp_sent = True
                registration_email = form.cleaned_data['email']
                registration_username = form.cleaned_data['username']
                messages.success(request, "OTP sent to your email. Enter it to complete registration.")
                form = UserRegistrationForm(initial={
                    'username': form.cleaned_data['username'],
                    'email': form.cleaned_data['email'],
                })
    else:
        form = UserRegistrationForm(initial=session_data) if session_data else UserRegistrationForm()

    return render(
        request,
        "registration/register.html",
        {
            "form": form,
            "otp_sent": otp_sent,
            "registration_email": registration_email,
            "registration_username": registration_username,
        },
    )


def otp_verify(request):
    if not request.session.get('registration_data'):
        messages.info(request, "Start registration first to receive an OTP.")
        return redirect('register')

    if request.method == "POST":
        entered_otp = request.POST.get('otp')
        if entered_otp == request.session.get('otp'):
            data = request.session.get('registration_data')
            if data:
                User = get_user_model()
                user = User.objects.create_user(
                    username=data['username'],
                    email=data['email'],
                    password=data['password1']
                )
                login(request, user)
                request.session.pop('otp', None)
                request.session.pop('registration_data', None)
                messages.success(request, "Account created and logged in.")
                return redirect('home')
        messages.error(request, "Invalid OTP. Please try again.")
    return render(request, 'registration/otp_verify.html')


@login_required
def profile(request):
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    resumes = Resume.objects.filter(user=request.user).order_by("-uploaded_at")
    saved_count = SavedJob.objects.filter(user=request.user).count()
    
    profile_form = None
    photo_form = None
    password_form = None
    
    if request.method == "POST":
        if "update_photo" in request.POST:
            photo_form = ProfilePhotoForm(request.POST, request.FILES, instance=user_profile)
            if photo_form.is_valid():
                photo_form.save()
                messages.success(request, "Profile photo updated successfully.")
                return redirect("profile")
        elif "update_profile" in request.POST:
            profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=user_profile)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Profile updated successfully.")
                return redirect("profile")
        elif "change_password" in request.POST:
            password_form = CustomPasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                password_form.save()
                messages.success(request, "Password changed successfully.")
                return redirect("profile")
    
    if not profile_form:
        profile_form = ProfileUpdateForm(instance=user_profile)
    if not photo_form:
        photo_form = ProfilePhotoForm(instance=user_profile)
    if not password_form:
        password_form = CustomPasswordChangeForm(request.user)
    
    context = {
        "user_profile": user_profile,
        "profile_form": profile_form,
        "photo_form": photo_form,
        "password_form": password_form,
        "resumes": resumes,
        "saved_count": saved_count,
    }
    return render(request, "profile.html", context)


@login_required
def resume_upload(request):
    if request.method == "POST":
        form = ResumeUploadForm(request.POST, request.FILES)
        if form.is_valid():
            resume = form.save(commit=False)
            resume.user = request.user
            resume.original_filename = Path(request.FILES["original_file"].name).name
            resume.save()

            file_path = resume.original_file.path
            file_type = resume.original_file.name.split(".")[-1].lower()

            try:
                parsed = parse_resume(file_path, file_type)
                resume.raw_text = parsed.get("raw_text", "")
                resume.extracted_json = parsed
                resume.save()
                messages.success(request, "Resume uploaded and parsed successfully.")
            except AIServiceError as exc:
                messages.error(request, f"AI service error: {exc}")
            return redirect("resume_detail", pk=resume.pk)
    else:
        form = ResumeUploadForm()

    return render(request, "resume_upload.html", {"form": form})


@login_required
@require_POST
def resume_delete(request, pk):
    resume = get_object_or_404(Resume, pk=pk, user=request.user)
    file_name = resume.display_name

    session_state = request.session.get(INTERVIEW_SIMULATOR_SESSION_KEY)
    if session_state and session_state.get("resume_id") == resume.id:
        request.session.pop(INTERVIEW_SIMULATOR_SESSION_KEY, None)

    if resume.original_file:
        resume.original_file.delete(save=False)
    resume.delete()
    request.session.modified = True
    messages.success(request, f"Deleted resume: {file_name}")
    return redirect("profile")


@login_required
def resume_detail(request, pk):
    resume = get_object_or_404(Resume, pk=pk, user=request.user)
    extracted = resume.extracted_json or {}
    raw_text = resume.raw_text or ""
    word_count = len([word for word in raw_text.split() if word.strip()])
    return render(request, "resume_detail.html", {
        "resume": resume,
        "extracted": extracted,
        "skills": extracted.get("skills", []),
        "education": extracted.get("education", []),
        "experience": extracted.get("experience", []),
        "projects": extracted.get("projects", []),
        "word_count": word_count,
        "skill_count": len(extracted.get("skills", [])),
    })


@login_required
@require_POST
def resume_ats_check(request, pk):
    resume = get_object_or_404(Resume, pk=pk, user=request.user)

    if request.content_type == "application/json":
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid JSON")
    else:
        payload = request.POST

    job_description = (payload.get("job_description") or "").strip()
    if not job_description:
        return HttpResponseBadRequest("job_description is required")

    job_title = (payload.get("job_title") or "Target Role").strip() or "Target Role"
    required_skills_raw = payload.get("required_skills") or []

    if isinstance(required_skills_raw, str):
        required_skills = [
            skill.strip().lower()
            for skill in required_skills_raw.replace("\n", ",").split(",")
            if skill.strip()
        ]
    elif isinstance(required_skills_raw, list):
        required_skills = [
            str(skill).strip().lower()
            for skill in required_skills_raw
            if str(skill).strip()
        ]
    else:
        required_skills = []

    if not (resume.raw_text or "").strip():
        try:
            file_path = resume.original_file.path
            file_type = resume.original_file.name.split(".")[-1].lower()
            parsed = parse_resume(file_path, file_type)
            resume.raw_text = parsed.get("raw_text", "")
            resume.extracted_json = parsed
            resume.save()
        except AIServiceError as exc:
            return JsonResponse({"error": str(exc)}, status=502)

    job_payload = {
        "title": job_title,
        "description": job_description,
        "required_skills": required_skills,
    }

    try:
        resume_file_type = Path(resume.original_file.name).suffix.lower().lstrip(".")
        result = match_resume_job(
            resume.raw_text,
            job_payload,
            resume_metadata={"file_type": resume_file_type},
        )
    except AIServiceError as exc:
        return JsonResponse({"error": str(exc)}, status=502)

    return JsonResponse(result)


@login_required
def resume_json_download(request, pk):
    resume = get_object_or_404(Resume, pk=pk, user=request.user)
    response = JsonResponse(resume.extracted_json or {}, json_dumps_params={"indent": 2})
    response["Content-Disposition"] = f"attachment; filename=resume_{resume.pk}_data.json"
    return response


def job_list(request):
    _refresh_jobs_daily_if_needed()
    query = request.GET.get("q", "")
    location = request.GET.get("location", "")
    level = request.GET.get("level", "")
    resume_id = request.GET.get("resume_id")
    show_all = request.GET.get("show_all") == "1"

    # Show freshly imported jobs first, then stable order for same timestamps.
    jobs = Job.objects.all().order_by("-created_at", "title")
    selected_resume = None
    match_filter_active = False

    if query:
        jobs = jobs.filter(Q(title__icontains=query) | Q(company__icontains=query))
    if location:
        jobs = jobs.filter(build_location_query(location))
    if level:
        jobs = jobs.filter(level__icontains=level)

    if request.user.is_authenticated:
        user_resumes = Resume.objects.filter(user=request.user).order_by("-uploaded_at")
        if resume_id:
            selected_resume = get_object_or_404(user_resumes, pk=resume_id)
        else:
            selected_resume = user_resumes.first()

    if selected_resume and not show_all:
        resume_skills = _normalized_skill_set((selected_resume.extracted_json or {}).get("skills", []))
        if resume_skills:
            jobs = [
                job for job in jobs
                if _is_resume_job_match(resume_skills, _normalized_skill_set(job.required_skills))
            ]
        else:
            jobs = []
        match_filter_active = True

    return render(request, "jobs_list.html", {
        "jobs": jobs,
        "query": query,
        "location": location,
        "level": level,
        "selected_resume": selected_resume,
        "match_filter_active": match_filter_active,
        "show_all": show_all,
        "matching_jobs_count": len(jobs) if match_filter_active else None,
        "location_suggestions": LOCATION_SUGGESTIONS,
        "quick_location_filters": QUICK_LOCATION_FILTERS,
    })


def job_detail(request, pk):
    job = get_object_or_404(Job, pk=pk)
    resumes = Resume.objects.filter(user=request.user) if request.user.is_authenticated else []
    is_saved = False
    if request.user.is_authenticated:
        is_saved = SavedJob.objects.filter(user=request.user, job=job).exists()
    return render(request, "job_detail.html", {
        "job": job,
        "resumes": resumes,
        "is_saved": is_saved
    })


def fake_job_detector(request):
    analysis = None
    if request.method == "POST":
        form = FakeJobDetectionForm(request.POST)
        if form.is_valid():
            analysis = detect_fake_job_posting(form.cleaned_data)
    else:
        form = FakeJobDetectionForm()

    return render(request, "fake_job_detector.html", {
        "form": form,
        "analysis": analysis,
    })


@login_required
def interview_simulator(request):
    resumes = Resume.objects.filter(user=request.user).order_by("-uploaded_at")
    return render(request, "interview_simulator.html", {
        "resumes": resumes,
        "selected_resume": resumes.first(),
    })


@login_required
@require_POST
def interview_simulator_start_view(request):
    payload = _request_payload(request)
    if payload is None:
        return HttpResponseBadRequest("Invalid JSON")

    resume_id = payload.get("resume_id")
    if not resume_id:
        return HttpResponseBadRequest("resume_id is required")

    resume = get_object_or_404(Resume, pk=resume_id, user=request.user)
    if not (resume.extracted_json or {}).get("skills") and not (resume.raw_text or "").strip() and resume.original_file:
        try:
            file_path = resume.original_file.path
            file_type = resume.original_file.name.split(".")[-1].lower()
            parsed = parse_resume(file_path, file_type)
            resume.raw_text = parsed.get("raw_text", "")
            resume.extracted_json = parsed
            resume.save()
        except AIServiceError as exc:
            return JsonResponse({"error": str(exc)}, status=502)

    role = (payload.get("role") or "Software Engineer").strip() or "Software Engineer"
    company = (payload.get("company") or "").strip()
    focus = (payload.get("focus") or "general").strip() or "general"
    try:
        question_count = int(payload.get("question_count") or payload.get("rounds") or 50)
    except (TypeError, ValueError):
        question_count = 50

    session_state, response_payload = start_interview_simulator(
        resume.extracted_json or {"raw_text": resume.raw_text},
        role=role,
        company=company,
        focus=focus,
        total_questions=question_count,
    )
    session_state["resume_id"] = resume.id
    request.session[INTERVIEW_SIMULATOR_SESSION_KEY] = session_state
    request.session.modified = True
    return JsonResponse(response_payload)


@login_required
@require_POST
def interview_simulator_answer_view(request):
    payload = _request_payload(request)
    if payload is None:
        return HttpResponseBadRequest("Invalid JSON")

    state = request.session.get(INTERVIEW_SIMULATOR_SESSION_KEY)
    if not state:
        return JsonResponse({"error": "Interview session not started."}, status=400)

    try:
        new_state, response_payload = advance_interview_simulator(
            state,
            payload.get("answer", ""),
            payload.get("selected_options"),
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    request.session[INTERVIEW_SIMULATOR_SESSION_KEY] = new_state
    request.session.modified = True
    return JsonResponse(response_payload)


@login_required
@require_POST
def interview_simulator_reset_view(request):
    request.session.pop(INTERVIEW_SIMULATOR_SESSION_KEY, None)
    request.session.modified = True
    return JsonResponse({"reset": True})


@require_POST
def job_fake_check(request, pk):
    job = get_object_or_404(Job, pk=pk)
    result = detect_fake_job_posting({
        "job_title": job.title,
        "company": job.company,
        "location": job.location,
        "salary_range": job.salary_range,
        "description": job.description,
        "apply_link": job.apply_link,
    })
    return JsonResponse(result)


@login_required
@require_POST
def match_job(request, pk):
    job = get_object_or_404(Job, pk=pk)

    if request.content_type == "application/json":
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid JSON")
    else:
        payload = request.POST

    resume_id = payload.get("resume_id")
    if not resume_id:
        return HttpResponseBadRequest("resume_id is required")

    resume = get_object_or_404(Resume, pk=resume_id, user=request.user)

    job_payload = {
        "title": job.title,
        "description": job.description,
        "required_skills": job.required_skills,
    }
    # If resume hasn't been parsed (no raw_text), try to parse it first
    if not (resume.raw_text or "").strip():
        try:
            file_path = resume.original_file.path
            file_type = resume.original_file.name.split(".")[-1].lower()
            parsed = parse_resume(file_path, file_type)
            resume.raw_text = parsed.get("raw_text", "")
            resume.extracted_json = parsed
            resume.save()
        except AIServiceError as exc:
            return JsonResponse({"error": str(exc)}, status=502)

    try:
        resume_file_type = Path(resume.original_file.name).suffix.lower().lstrip(".")
        result = match_resume_job(
            resume.raw_text,
            job_payload,
            resume_metadata={"file_type": resume_file_type},
        )
    except AIServiceError as exc:
        return JsonResponse({"error": str(exc)}, status=502)

    match_record = MatchResult.objects.create(
        resume=resume,
        job=job,
        score=result.get("score", 0),
        matched_skills=result.get("matched_skills", []),
        missing_skills=result.get("missing_skills", []),
        analysis_details={
            "ats_score": result.get("ats_score", result.get("score", 0)),
            "score_breakdown": result.get("score_breakdown", []),
            "mistakes": result.get("mistakes", []),
            "matched_keywords": result.get("matched_keywords", []),
            "missing_keywords": result.get("missing_keywords", []),
            "summary": result.get("summary", ""),
            "improvement_tips": result.get("improvement_tips", []),
            "section_details": result.get("section_details", {}),
        },
    )

    return JsonResponse({
        "match_id": match_record.id,
        "match_url": reverse("match_result_detail", args=[match_record.id]),
        **result
    })


@login_required
@require_POST
def skill_gap_job(request, pk):
    job = get_object_or_404(Job, pk=pk)

    if request.content_type == "application/json":
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid JSON")
    else:
        payload = request.POST

    resume_id = payload.get("resume_id")
    if not resume_id:
        return HttpResponseBadRequest("resume_id is required")

    resume = get_object_or_404(Resume, pk=resume_id, user=request.user)

    job_payload = {
        "title": job.title,
        "description": job.description,
        "required_skills": job.required_skills,
    }
    # If resume hasn't been parsed (no raw_text), try to parse it first
    if not (resume.raw_text or "").strip():
        try:
            file_path = resume.original_file.path
            file_type = resume.original_file.name.split(".")[-1].lower()
            parsed = parse_resume(file_path, file_type)
            resume.raw_text = parsed.get("raw_text", "")
            resume.extracted_json = parsed
            resume.save()
        except AIServiceError as exc:
            return JsonResponse({"error": str(exc)}, status=502)

    try:
        result = skill_gap(resume.raw_text, job_payload)
    except AIServiceError as exc:
        return JsonResponse({"error": str(exc)}, status=502)

    return JsonResponse(result)


@login_required
def match_result_detail(request, pk):
    match = get_object_or_404(MatchResult, pk=pk, resume__user=request.user)
    return render(request, "match_results.html", {"match": match})


@login_required
def recommendations(request):
    _refresh_jobs_daily_if_needed()
    resumes = Resume.objects.filter(user=request.user).order_by("-uploaded_at")
    resume_id = request.GET.get("resume_id")
    api_query = (request.GET.get("api_query") or "software developer").strip() or "software developer"
    api_location = (request.GET.get("api_location") or "Remote | India").strip() or "Remote | India"
    include_api = (request.GET.get("include_api") or "1") == "1"
    try:
        api_limit = int(request.GET.get("api_limit", 50))
    except ValueError:
        api_limit = 50
    api_limit = max(5, min(api_limit, 150))

    selected_resume = None
    results = []
    api_source = ""
    api_jobs_added = 0
    api_jobs_updated = 0
    db_jobs_before_api = Job.objects.count()
    recommendation_pool_size = 0

    if resume_id:
        selected_resume = get_object_or_404(Resume, pk=resume_id, user=request.user)
        resume_skills = _normalized_skill_set((selected_resume.extracted_json or {}).get("skills", []))

        if include_api:
            try:
                fetched_jobs, api_source = fetch_jobs_for_location_targets(
                    query=api_query,
                    location=api_location,
                    limit=api_limit,
                    require_location_match=True,
                )

                api_jobs_added, api_jobs_updated = _merge_jobs_into_database(fetched_jobs, api_location)

                if api_source:
                    messages.info(
                        request,
                        (
                            f"Recommendation pool merged from Database + API ({api_source}). "
                            f"API new: {api_jobs_added}, updated: {api_jobs_updated}."
                        ),
                    )
            except AIServiceError as exc:
                messages.warning(request, f"Could not fetch API jobs ({exc}). Using database jobs only.")

        jobs_payload = list(
            Job.objects.order_by("-created_at", "title")
            .values("id", "title", "description", "required_skills")[:500]
        )
        recommendation_pool_size = len(jobs_payload)
        if not jobs_payload:
            messages.warning(request, "No jobs available for recommendations yet.")
            return render(request, "recommendations.html", {
                "resumes": resumes,
                "selected_resume": selected_resume,
                "results": results,
                "api_query": api_query,
                "api_location": api_location,
                "api_limit": api_limit,
                "include_api": include_api,
                "api_source": api_source,
                "api_jobs_added": api_jobs_added,
                "api_jobs_updated": api_jobs_updated,
                "db_jobs_before_api": db_jobs_before_api,
                "recommendation_pool_size": recommendation_pool_size,
                "location_suggestions": LOCATION_SUGGESTIONS,
            })

        try:
            ai_result = recommend_jobs(selected_resume.raw_text, jobs_payload, top_n=10)
            Recommendation.objects.filter(resume=selected_resume).delete()

            jobs_by_id = Job.objects.in_bulk(
                [rec.get("job_id") for rec in ai_result.get("recommendations", []) if rec.get("job_id")]
            )

            for rec in ai_result.get("recommendations", []):
                job = jobs_by_id.get(rec.get("job_id"))
                if not job:
                    continue

                job_skills = _normalized_skill_set(job.required_skills)
                if not _is_resume_job_match(resume_skills, job_skills):
                    continue

                Recommendation.objects.create(
                    resume=selected_resume,
                    job=job,
                    score=rec.get("score", 0),
                    reason=rec.get("reason", "")
                )
        except AIServiceError as exc:
            messages.error(request, f"AI service error: {exc}")

        results = Recommendation.objects.filter(resume=selected_resume).select_related("job").order_by("-score")

    return render(request, "recommendations.html", {
        "resumes": resumes,
        "selected_resume": selected_resume,
        "results": results,
        "api_query": api_query,
        "api_location": api_location,
        "api_limit": api_limit,
        "include_api": include_api,
        "api_source": api_source,
        "api_jobs_added": api_jobs_added,
        "api_jobs_updated": api_jobs_updated,
        "db_jobs_before_api": db_jobs_before_api,
        "recommendation_pool_size": recommendation_pool_size,
        "location_suggestions": LOCATION_SUGGESTIONS,
    })


@login_required
def saved_jobs(request):
    saved = SavedJob.objects.filter(user=request.user).select_related("job").order_by("-created_at")
    return render(request, "saved_jobs.html", {"saved_jobs": saved})


@login_required
@require_POST
def toggle_saved_job(request, pk):
    job = get_object_or_404(Job, pk=pk)
    saved, created = SavedJob.objects.get_or_create(user=request.user, job=job)
    if not created:
        saved.delete()
        return JsonResponse({"saved": False})
    return JsonResponse({"saved": True})


@staff_member_required
def admin_dashboard(request):
    total_resumes = Resume.objects.count()
    saved_jobs_count = SavedJob.objects.count()
    avg_score = MatchResult.objects.aggregate(avg=Avg("score"))["avg"] or 0

    skills_counter = Counter()
    for resume in Resume.objects.exclude(extracted_json={}):
        for skill in resume.extracted_json.get("skills", []):
            skills_counter[skill.lower()] += 1
    top_skills = skills_counter.most_common(10)

    job_counter = Counter()
    for rec in Recommendation.objects.select_related("job"):
        if rec.job:
            job_counter[rec.job] += 1
    top_jobs = [{"job": job, "count": count} for job, count in job_counter.most_common(10)]

    return render(request, "admin/admin_dashboard.html", {
        "total_resumes": total_resumes,
        "saved_jobs_count": saved_jobs_count,
        "avg_score": round(avg_score, 2),
        "top_skills": top_skills,
        "top_jobs": top_jobs
    })


@staff_member_required
def admin_job_list(request):
    jobs = Job.objects.all().order_by("title")
    return render(request, "admin/admin_job_list.html", {"jobs": jobs})


@staff_member_required
def admin_job_create(request):
    if request.method == "POST":
        form = JobForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Job created.")
            return redirect("admin_job_list")
    else:
        form = JobForm()
    return render(request, "admin/admin_job_form.html", {"form": form, "mode": "Create"})


@staff_member_required
def admin_job_edit(request, pk):
    job = get_object_or_404(Job, pk=pk)
    if request.method == "POST":
        form = JobForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            messages.success(request, "Job updated.")
            return redirect("admin_job_list")
    else:
        form = JobForm(instance=job)
    return render(request, "admin/admin_job_form.html", {"form": form, "mode": "Edit"})


@staff_member_required
@require_POST
def admin_job_delete(request, pk):
    job = get_object_or_404(Job, pk=pk)
    job.delete()
    messages.success(request, "Job deleted.")
    return redirect("admin_job_list")


