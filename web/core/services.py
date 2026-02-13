import logging
import math
import re
from typing import Dict, List

import docx
import pdfplumber
import requests
from django.conf import settings


logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, network_error: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.network_error = network_error


SKILLS_DICTIONARY = [
    "python", "sql", "django", "flask", "javascript", "html", "css", "git",
    "numpy", "pandas", "mysql", "postgresql", "postgres", "mongodb", "docker",
    "kubernetes", "aws", "gcp", "azure", "machine learning", "ml", "nlp",
    "data analysis", "data science", "excel", "power bi", "tableau", "linux",
    "rest", "api", "fastapi", "tensorflow", "pytorch", "scikit-learn", "opencv",
    "c", "c++", "java", "c#", "go", "rust", "php", "ruby", "node", "react",
    "vue", "angular", "spark", "hadoop", "etl", "airflow", "bash", "pytest",
    "unit testing", "agile", "scrum"
]

STOPWORDS = {
    "a", "an", "the", "and", "or", "for", "to", "in", "on", "of", "with",
    "by", "is", "are", "was", "were", "be", "as", "at", "from", "that",
    "this", "it", "its", "their", "them", "we", "our", "you", "your"
}


def _normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9+.#\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokenize(text: str) -> List[str]:
    tokens = _normalize_text(text).split()
    return [token for token in tokens if token and token not in STOPWORDS]


def _extract_text(file_path: str, file_type: str) -> str:
    file_type = (file_type or "").lower()
    if file_type == "pdf":
        with pdfplumber.open(file_path) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n".join(pages)
    if file_type == "docx":
        doc = docx.Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)
    raise ValueError("Unsupported file type. Use pdf or docx.")


def _extract_email(text: str) -> str:
    match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return match.group(0) if match else ""


def _extract_phone(text: str) -> str:
    match = re.search(r"(\+?\d[\d\s().-]{7,}\d)", text)
    return match.group(0) if match else ""


def _extract_name(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    for line in lines[:5]:
        if "@" in line or re.search(r"\d", line):
            continue
        if len(line.split()) <= 6:
            return line.split("|")[0].strip()
    return lines[0].split("|")[0].strip()


def _extract_skills(text: str) -> List[str]:
    normalized = _normalize_text(text)
    found = set()
    for skill in SKILLS_DICTIONARY:
        pattern = re.escape(skill.lower())
        if re.search(rf"\b{pattern}\b", normalized):
            found.add(skill.lower())
    return sorted(found)


def _extract_education(text: str) -> List[Dict[str, str]]:
    education = []
    keywords = ["bachelor", "master", "phd", "b.s", "b.sc", "m.s", "mba", "b.tech", "m.tech", "degree"]
    for line in text.splitlines():
        lower = line.lower()
        if any(keyword in lower for keyword in keywords):
            year_match = re.search(r"(19|20)\d{2}", line)
            education.append({
                "degree": line.strip(),
                "institute": "",
                "year": year_match.group(0) if year_match else "",
            })
    return education[:5]


def _extract_experience(text: str) -> List[Dict[str, str]]:
    experience = []
    keywords = ["experience", "engineer", "developer", "intern", "manager", "analyst"]
    for line in text.splitlines():
        lower = line.lower()
        if any(keyword in lower for keyword in keywords):
            year_match = re.search(r"(19|20)\d{2}", line)
            experience.append({
                "title": line.strip(),
                "company": "",
                "years": year_match.group(0) if year_match else "",
                "details": "",
            })
    return experience[:6]


def _extract_projects(text: str) -> List[Dict[str, str]]:
    projects = []
    for line in text.splitlines():
        if "project" in line.lower():
            projects.append({
                "name": line.strip(),
                "details": "",
                "tech": [],
            })
    return projects[:5]


def _compute_similarity(resume_text: str, job_text: str) -> float:
    if not resume_text.strip() or not job_text.strip():
        return 0.0

    docs = [_tokenize(resume_text), _tokenize(job_text)]
    vocab = sorted(set(docs[0]).union(docs[1]))
    if not vocab:
        return 0.0

    def tf(tokens: List[str]) -> Dict[str, float]:
        counts: Dict[str, int] = {}
        total = max(len(tokens), 1)
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        return {token: counts.get(token, 0) / total for token in vocab}

    def idf() -> Dict[str, float]:
        values: Dict[str, float] = {}
        for token in vocab:
            df = sum(1 for doc in docs if token in doc)
            values[token] = math.log((len(docs) + 1) / (df + 1)) + 1
        return values

    idf_values = idf()
    tf1 = tf(docs[0])
    tf2 = tf(docs[1])

    tfidf_1 = [tf1[token] * idf_values[token] for token in vocab]
    tfidf_2 = [tf2[token] * idf_values[token] for token in vocab]

    dot = sum(a * b for a, b in zip(tfidf_1, tfidf_2))
    norm1 = math.sqrt(sum(a * a for a in tfidf_1))
    norm2 = math.sqrt(sum(b * b for b in tfidf_2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return float(dot / (norm1 * norm2))


def _build_match_response(resume_text: str, job: Dict) -> Dict:
    job_required = [skill.lower() for skill in (job.get("required_skills") or [])]
    resume_skills = set(_extract_skills(resume_text))
    job_skills = set(job_required)

    matched = sorted(resume_skills.intersection(job_skills))
    missing = sorted(job_skills.difference(resume_skills))

    job_text = f"{job.get('title', '')} {job.get('description', '')} {' '.join(job_required)}"
    score = int(round(_compute_similarity(resume_text, job_text) * 100))

    summary = f"Match score {score}. {len(matched)} skill(s) matched."
    tips = [f"Consider adding experience with {skill}." for skill in missing[:5]]
    if not tips:
        tips.append("Your resume already covers most required skills.")

    return {
        "score": max(0, min(score, 100)),
        "matched_skills": matched,
        "missing_skills": missing,
        "summary": summary,
        "improvement_tips": tips,
    }


def _build_skill_gap_response(resume_text: str, job: Dict) -> Dict:
    job_required = [skill.lower() for skill in (job.get("required_skills") or [])]
    resume_skills = set(_extract_skills(resume_text))
    job_skills = set(job_required)

    matched = sorted(resume_skills.intersection(job_skills))
    missing = sorted(job_skills.difference(resume_skills))

    suggestions = [f"Build a small project or certification using {skill}." for skill in missing[:5]]
    if not suggestions:
        suggestions.append("Your resume already aligns well with the target role.")

    return {
        "matched_skills": matched,
        "missing_skills": missing,
        "suggestions": suggestions,
    }


def _parse_resume_local(file_path: str, file_type: str) -> dict:
    raw_text = _extract_text(file_path, file_type)
    return {
        "raw_text": raw_text,
        "name": _extract_name(raw_text),
        "email": _extract_email(raw_text),
        "phone": _extract_phone(raw_text),
        "skills": _extract_skills(raw_text),
        "education": _extract_education(raw_text),
        "experience": _extract_experience(raw_text),
        "projects": _extract_projects(raw_text),
    }


def _match_resume_job_local(resume_text: str, job_payload: dict) -> dict:
    return _build_match_response(resume_text, job_payload)


def _recommend_jobs_local(resume_text: str, jobs_payload: list, top_n: int = 10) -> dict:
    recommendations = []
    for job in jobs_payload:
        result = _build_match_response(resume_text, job)
        job_id = job.get("id") or job.get("job_id")
        reason = "Matched skills: " + ", ".join(result["matched_skills"][:5])
        if not result["matched_skills"]:
            reason = "Based on overall text similarity."
        recommendations.append({
            "job_id": job_id,
            "score": result["score"],
            "reason": reason,
        })

    recommendations.sort(key=lambda row: row["score"], reverse=True)
    return {"recommendations": recommendations[:top_n]}


def _skill_gap_local(resume_text: str, job_payload: dict) -> dict:
    return _build_skill_gap_response(resume_text, job_payload)


def _should_use_local_fallback(exc: AIServiceError) -> bool:
    if not getattr(settings, "AI_SERVICE_FALLBACK_LOCAL", True):
        return False
    if exc.network_error:
        return True
    return exc.status_code is not None and exc.status_code >= 500


def _run_with_fallback(operation: str, remote_fn, local_fn):
    try:
        return remote_fn()
    except AIServiceError as exc:
        if not _should_use_local_fallback(exc):
            raise

        logger.warning("AI service unavailable for %s. Falling back to local inference. Error: %s", operation, exc)
        try:
            return local_fn()
        except Exception as local_exc:
            raise AIServiceError(f"Local AI fallback failed for {operation}: {local_exc}") from local_exc


def ai_post(endpoint: str, payload: dict, timeout: int = 10) -> dict:
    base_url = settings.AI_SERVICE_URL.rstrip("/")
    url = f"{base_url}{endpoint}"
    try:
        response = requests.post(url, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        raise AIServiceError(f"AI service request failed: {exc}", network_error=True) from exc

    if response.status_code != 200:
        raise AIServiceError(f"AI service error ({response.status_code}): {response.text}", status_code=response.status_code)

    try:
        return response.json()
    except ValueError as exc:
        raise AIServiceError("AI service returned invalid JSON") from exc


def parse_resume(file_path: str, file_type: str) -> dict:
    return _run_with_fallback(
        "parse_resume",
        lambda: ai_post("/parse_resume", {"file_path": file_path, "file_type": file_type}),
        lambda: _parse_resume_local(file_path, file_type),
    )


def match_resume_job(resume_text: str, job_payload: dict) -> dict:
    return _run_with_fallback(
        "match",
        lambda: ai_post("/match", {"resume_text": resume_text, "job": job_payload}),
        lambda: _match_resume_job_local(resume_text, job_payload),
    )


def recommend_jobs(resume_text: str, jobs_payload: list, top_n: int = 10) -> dict:
    return _run_with_fallback(
        "recommend_jobs",
        lambda: ai_post("/recommend_jobs", {"resume_text": resume_text, "jobs": jobs_payload, "top_n": top_n}),
        lambda: _recommend_jobs_local(resume_text, jobs_payload, top_n),
    )


def skill_gap(resume_text: str, job_payload: dict) -> dict:
    return _run_with_fallback(
        "skill_gap",
        lambda: ai_post("/skill_gap", {"resume_text": resume_text, "job": job_payload}),
        lambda: _skill_gap_local(resume_text, job_payload),
    )


def fetch_remotive_jobs(limit: int = 50) -> list:
    """Fetch real remote jobs from Remotive API."""
    try:
        url = "https://remotive.com/api/remote-jobs"
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()
        jobs_list = data.get("jobs", [])[:limit]

        formatted_jobs = []
        for job in jobs_list:
            # Extract skills from description (basic extraction)
            description = job.get("job_description", "")
            description_lower = description.lower()

            skills = []
            skill_keywords = [
                "python", "javascript", "java", "c#", "golang", "rust", "ruby",
                "react", "vue", "angular", "django", "flask", "fastapi",
                "sql", "postgresql", "mysql", "mongodb", "redis",
                "docker", "kubernetes", "aws", "gcp", "azure",
                "git", "rest", "graphql", "api", "html", "css",
                "nodejs", "typescript", "scala", "php", "laravel"
            ]

            for skill in skill_keywords:
                if skill in description_lower:
                    skills.append(skill)

            formatted_jobs.append({
                "title": job.get("job_title", "Unknown Position"),
                "company": job.get("company_name", "Unknown Company"),
                "location": "Remote",
                "level": "Mid",  # Default level since API doesn't provide it
                "salary_range": "",  # Remotive API doesn't provide salary
                "description": description[:1000],  # Truncate to 1000 chars
                "required_skills": list(set(skills)) if skills else ["remote", "general"],
                "apply_link": job.get("url", ""),
            })

        return formatted_jobs
    except Exception as exc:
        raise AIServiceError(f"Failed to fetch jobs from Remotive: {exc}") from exc


def fetch_jsearch_jobs(query: str = "developer", location: str = "India", limit: int = 50) -> list:
    """Fetch real jobs from Jobs API on RapidAPI."""
    api_key = settings.JSEARCH_API_KEY
    if not api_key:
        raise AIServiceError("JSEARCH_API_KEY not configured in .env file")

    try:
        # Using the working Jobs API endpoint
        url = "https://jobs-api14.p.rapidapi.com/search"
        headers = {
            "x-rapidapi-key": api_key,
            "x-rapidapi-host": "jobs-api14.p.rapidapi.com"
        }

        params = {
            "keywords": query,
            "location": location,
            "page": 1,
            "num_pages": 1,
        }

        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()

        data = response.json()

        # Different APIs have different response structures
        jobs_list = []
        if isinstance(data, dict):
            jobs_list = data.get("data", [])
        elif isinstance(data, list):
            jobs_list = data

        jobs_list = jobs_list[:limit]

        formatted_jobs = []

        skill_keywords = [
            "python", "javascript", "java", "c#", "c++", "golang", "rust", "ruby",
            "react", "vue", "angular", "django", "flask", "fastapi", "spring",
            "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
            "docker", "kubernetes", "aws", "gcp", "azure", "jenkins",
            "git", "rest", "graphql", "api", "html", "css", "typescript",
            "nodejs", "scala", "php", "laravel", "rails", "nestjs",
            "machine learning", "ml", "ai", "tensorflow", "pytorch",
            "devops", "linux", "bash", "shell", "ci/cd",
        ]

        for job in jobs_list:
            # Handle different response formats
            title = job.get("title") or job.get("job_title") or "Unknown Position"
            company = job.get("company") or job.get("employer") or "Unknown Company"
            location_str = job.get("location") or job.get("job_location") or location
            description = job.get("description") or job.get("job_description") or "No description available"
            apply_link = job.get("url") or job.get("job_apply_link") or job.get("apply_link") or ""

            description_lower = description.lower()

            # Extract skills from description
            skills = []
            for skill in skill_keywords:
                if skill in description_lower:
                    skills.append(skill)

            # Determine experience level
            title_lower = title.lower()
            if "senior" in title_lower or "lead" in title_lower or "principal" in title_lower:
                level = "Senior"
            elif "junior" in title_lower or "entry" in title_lower or "intern" in title_lower:
                level = "Junior"
            else:
                level = "Mid"

            # Extract salary if available
            salary_range = ""
            if job.get("salary") or job.get("salary_min"):
                salary_min = job.get("salary_min") or job.get("salary", "")
                salary_max = job.get("salary_max") or ""
                if salary_min and salary_max:
                    salary_range = f"${salary_min:,} - ${salary_max:,}"
                elif salary_min:
                    salary_range = f"${salary_min:,}"

            formatted_jobs.append({
                "title": title,
                "company": company,
                "location": location_str,
                "level": level,
                "salary_range": salary_range,
                "description": description[:2000] if description else "No description available",
                "required_skills": list(set(skills)) if skills else ["general"],
                "apply_link": apply_link,
            })

        return formatted_jobs
    except Exception as exc:
        raise AIServiceError(f"Failed to fetch jobs: {exc}") from exc
