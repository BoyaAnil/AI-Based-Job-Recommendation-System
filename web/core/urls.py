from django.urls import path
from django.contrib.auth import views as auth_views

from .forms import CustomAuthenticationForm
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("otp-verify/", views.otp_verify, name="otp_verify"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            authentication_form=CustomAuthenticationForm,
        ),
        name="login",
    ),
    path(
        "password-reset/",
        views.CustomPasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "forgot-password/",
        views.CustomPasswordResetView.as_view(),
        name="forgot_password",
    ),
    path(
        "password-reset/done/",
        views.CustomPasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("profile/", views.profile, name="profile"),
    path("interview-simulator/", views.interview_simulator, name="interview_simulator"),
    path("interview-simulator/start/", views.interview_simulator_start_view, name="interview_simulator_start"),
    path("interview-simulator/answer/", views.interview_simulator_answer_view, name="interview_simulator_answer"),
    path("interview-simulator/reset/", views.interview_simulator_reset_view, name="interview_simulator_reset"),
    path("fake-job-detector/", views.fake_job_detector, name="fake_job_detector"),
    path("resumes/upload/", views.resume_upload, name="resume_upload"),
    path("resumes/<int:pk>/", views.resume_detail, name="resume_detail"),
    path("resumes/<int:pk>/delete/", views.resume_delete, name="resume_delete"),
    path("resumes/<int:pk>/ats-check/", views.resume_ats_check, name="resume_ats_check"),
    path("resumes/<int:pk>/download/", views.resume_json_download, name="resume_json_download"),
    path("jobs/", views.job_list, name="job_list"),
    path("jobs/<int:pk>/", views.job_detail, name="job_detail"),
    path("jobs/<int:pk>/fake-check/", views.job_fake_check, name="job_fake_check"),
    path("jobs/<int:pk>/match/", views.match_job, name="match_job"),
    path("jobs/<int:pk>/skill-gap/", views.skill_gap_job, name="skill_gap_job"),
    path("jobs/<int:pk>/save/", views.toggle_saved_job, name="toggle_saved_job"),
    path("matches/<int:pk>/", views.match_result_detail, name="match_result_detail"),
    path("recommendations/", views.recommendations, name="recommendations"),
    path("saved-jobs/", views.saved_jobs, name="saved_jobs"),
    path("admin/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin/jobs/", views.admin_job_list, name="admin_job_list"),
    path("admin/jobs/new/", views.admin_job_create, name="admin_job_create"),
    path("admin/jobs/<int:pk>/edit/", views.admin_job_edit, name="admin_job_edit"),
    path("admin/jobs/<int:pk>/delete/", views.admin_job_delete, name="admin_job_delete"),
]
