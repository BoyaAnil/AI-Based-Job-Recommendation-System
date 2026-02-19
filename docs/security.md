# Security and Privacy

## Secrets Management

- Do not commit real `.env` files or API keys.
- Rotate any accidentally exposed credentials immediately.
- Use deployment platform secret storage for production values.

## Django Hardening Baseline

- Set `DJANGO_DEBUG=false` in production.
- Use a strong random `DJANGO_SECRET_KEY`.
- Restrict `DJANGO_ALLOWED_HOSTS` to actual domains.
- Configure `DJANGO_CSRF_TRUSTED_ORIGINS` for HTTPS origins only in production.
- Enforce HTTPS at proxy/platform layer.

## Resume Data Handling

- Resumes may contain PII (name, email, phone, education, work history).
- Store uploads in controlled storage and limit access.
- Avoid sharing extracted JSON outside required workflows.
- Define retention policy for uploaded files and extracted records.

## Upload Validation

- Only PDF/DOCX accepted (`ResumeUploadForm` validation).
- Maximum size controlled by `RESUME_MAX_FILE_SIZE_MB`.

## External API Considerations

- External job providers may have usage limits and terms.
- Do not log sensitive tokens (`JSEARCH_API_KEY`).
- Handle provider outages with source fallback and monitoring.

## Access Control

- Admin routes are protected with `staff_member_required`.
- User data routes enforce `login_required` and ownership checks for resumes/matches.

## Recommended Next Security Improvements

1. Add security headers (HSTS, X-Frame-Options tuning, CSP at proxy/app level).
2. Add malware scanning for uploaded documents.
3. Encrypt sensitive storage at rest if deployed in shared environments.
4. Add audit logs for admin job changes and sensitive user actions.
