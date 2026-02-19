# Troubleshooting

## Service Does Not Start

### Port already in use

- Symptoms: `Address already in use` for `8000` or `5000`
- Fix: stop existing process or run on different port

```powershell
python manage.py runserver 127.0.0.1:8001
flask --app app run --host 127.0.0.1 --port 5001
```

### Missing dependencies

- Symptoms: import/module errors
- Fix: recreate venv and reinstall requirements

```powershell
Remove-Item -Recurse -Force .venv
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## AI Errors from Django (`502` or warning messages)

### AI service not reachable

- Verify Flask is running:

```powershell
curl http://127.0.0.1:5000/health
```

- Ensure `AI_SERVICE_URL` in `web/.env` matches running Flask URL.

### Fallback behavior

- If `AI_SERVICE_FALLBACK_LOCAL=true`, Django should continue with local inference when remote AI is down or returns 5xx.
- If disabled, requests fail fast and user sees AI service errors.

## Resume Upload Rejected

Possible causes:

- File extension is not `.pdf` or `.docx`
- File size exceeds `RESUME_MAX_FILE_SIZE_MB`

Fix:

- Upload a supported format
- Increase `RESUME_MAX_FILE_SIZE_MB` if needed

## Job Import Issues

### JSearch returns 403

- Usually API key/subscription issue
- Verify `JSEARCH_API_KEY` and RapidAPI plan permissions
- Use `--source themuse` or `--source remotive` temporarily

### No jobs after import

- Query/location too strict
- `--require-location-match` filtered all rows
- Try broader query or location

## Database and Migration Issues

- Run:

```powershell
python manage.py migrate
```

- Confirm `DATABASE_URL` points to expected DB.

## Email/Password Reset Not Working

- In development, prefer file/console backend.
- For SMTP, verify host/port/user/password/TLS flags.
- Check `web/sent_emails/` when file backend is active.
