import json
from collections import Counter

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
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

from .forms import UserRegistrationForm, ResumeUploadForm, JobForm, ProfileUpdateForm, CustomPasswordChangeForm
from .models import Resume, Job, MatchResult, Recommendation, SavedJob, UserProfile
from .services import (
    parse_resume,
    match_resume_job,
    recommend_jobs,
    skill_gap,
    fetch_jobs_auto,
    AIServiceError,
)


def home(request):
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
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Account created. Please log in.")
            return redirect("login")
    else:
        form = UserRegistrationForm()
    return render(request, "registration/register.html", {"form": form})


@login_required
def profile(request):
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    resumes = Resume.objects.filter(user=request.user).order_by("-uploaded_at")
    saved_count = SavedJob.objects.filter(user=request.user).count()
    
    profile_form = None
    password_form = None
    
    if request.method == "POST":
        if "update_profile" in request.POST:
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
    if not password_form:
        password_form = CustomPasswordChangeForm(request.user)
    
    context = {
        "user_profile": user_profile,
        "profile_form": profile_form,
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
def resume_json_download(request, pk):
    resume = get_object_or_404(Resume, pk=pk, user=request.user)
    response = JsonResponse(resume.extracted_json or {}, json_dumps_params={"indent": 2})
    response["Content-Disposition"] = f"attachment; filename=resume_{resume.pk}_data.json"
    return response


def job_list(request):
    query = request.GET.get("q", "")
    location = request.GET.get("location", "")
    level = request.GET.get("level", "")

    # Show freshly imported jobs first, then stable order for same timestamps.
    jobs = Job.objects.all().order_by("-created_at", "title")

    if query:
        jobs = jobs.filter(Q(title__icontains=query) | Q(company__icontains=query))
    if location:
        # Normalize and handle common city aliases (e.g., Bengaluru/Bangalore)
        loc_normal = location.strip().lower()
        city_aliases = {
            "bengaluru": ["bengaluru", "bangalore"],
            "hyderabad": ["hyderabad"],
            "chennai": ["chennai", "madras"],
            "mumbai": ["mumbai", "bombay"],
            "delhi": ["delhi", "new delhi"],
            "pune": ["pune"],
            "bangalore": ["bangalore", "bengaluru"],
        }

        # If user typed a known alias, expand to all variants; otherwise use raw input
        aliases = None
        for key, vals in city_aliases.items():
            if loc_normal in vals:
                aliases = vals
                break

        if aliases is None:
            # fallback: search by provided substring
            jobs = jobs.filter(location__icontains=location)
        else:
            q_obj = Q()
            for a in aliases:
                q_obj |= Q(location__icontains=a)
            jobs = jobs.filter(q_obj)
    if level:
        jobs = jobs.filter(level__icontains=level)

    return render(request, "jobs_list.html", {
        "jobs": jobs,
        "query": query,
        "location": location,
        "level": level
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
        result = match_resume_job(resume.raw_text, job_payload)
    except AIServiceError as exc:
        return JsonResponse({"error": str(exc)}, status=502)

    match_record = MatchResult.objects.create(
        resume=resume,
        job=job,
        score=result.get("score", 0),
        matched_skills=result.get("matched_skills", []),
        missing_skills=result.get("missing_skills", []),
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
    resumes = Resume.objects.filter(user=request.user).order_by("-uploaded_at")
    resume_id = request.GET.get("resume_id")
    api_query = (request.GET.get("api_query") or "software developer").strip() or "software developer"
    api_location = (request.GET.get("api_location") or "India").strip() or "India"
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

        if include_api:
            try:
                fetched_jobs, api_source = fetch_jobs_auto(
                    query=api_query,
                    location=api_location,
                    limit=api_limit,
                )

                location_key = api_location.lower()
                fetched_jobs = [
                    row for row in fetched_jobs
                    if location_key in (row.get("location", "") or "").lower()
                ]

                refresh_time = timezone.now()
                for job_data in fetched_jobs:
                    if not job_data.get("title") or not job_data.get("company"):
                        continue

                    defaults = {
                        "level": job_data.get("level", "Mid"),
                        "salary_range": job_data.get("salary_range", ""),
                        "description": job_data.get("description", "No description available"),
                        "required_skills": job_data.get("required_skills", []),
                        "apply_link": job_data.get("apply_link", ""),
                        "created_at": refresh_time,
                    }
                    _, created = Job.objects.update_or_create(
                        title=job_data["title"],
                        company=job_data["company"],
                        location=job_data.get("location", api_location),
                        defaults=defaults,
                    )
                    if created:
                        api_jobs_added += 1
                    else:
                        api_jobs_updated += 1

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
            })

        try:
            ai_result = recommend_jobs(selected_resume.raw_text, jobs_payload, top_n=10)
            Recommendation.objects.filter(resume=selected_resume).delete()

            for rec in ai_result.get("recommendations", []):
                job = Job.objects.filter(pk=rec.get("job_id")).first()
                if job:
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
