# Testing Guide

## Automated Tests

### AI service tests

From `ai/`:

```powershell
pytest
```

Coverage focus:

- Flask endpoint behavior
- Core parsing/matching helper behavior

### Django tests

From `web/`:

```powershell
python manage.py test
```

Coverage focus:

- Web app views and integrations where tests are defined

## Useful Local Validation Scripts

Inside `web/`:

- `python test_api_endpoints.py`
- `python test_jsearch.py`
- `python verify_jobs.py`
- `python check_jobs.py`

## Manual Smoke Checklist

1. Start Flask and Django services.
2. Register/login user.
3. Upload a valid PDF/DOCX resume.
4. Confirm parsed data appears in resume detail.
5. Open a job and run match.
6. Run skill-gap analysis.
7. Save and unsave a job.
8. Generate recommendations for a resume.
9. Login as admin and verify dashboard + job CRUD.

## CI Recommendation

- Run both test suites on pull requests:
  - `pytest` in `ai/`
  - `python manage.py test` in `web/`
- Add linting (`ruff`/`flake8`) and formatting checks if not already configured.
