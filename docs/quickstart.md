# Quickstart

## Prerequisites

- Python `3.12+`
- `pip`
- Windows PowerShell commands shown below (adapt for bash if needed)

## 1) Start AI Service (Flask)

```powershell
cd ai
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
flask --app app run --host 127.0.0.1 --port 5000
```

Verify:

```powershell
curl http://127.0.0.1:5000/health
```

Expected response:

```json
{"status":"ok"}
```

## 2) Start Web App (Django)

Open a second terminal:

```powershell
cd web
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 127.0.0.1:8000
```

Open:

- Web app: `http://127.0.0.1:8000`
- AI health: `http://127.0.0.1:5000/health`

## Demo Credentials

- User: `demo` / `demo1234`
- Admin: `admin` / `admin1234`

## First Smoke Test

1. Log in as `demo`.
2. Upload `sample_data/sample_resume.pdf`.
3. Open Jobs and check one match.
4. Open Recommendations and generate top jobs.
