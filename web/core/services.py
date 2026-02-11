import requests
from django.conf import settings


class AIServiceError(Exception):
    pass


def ai_post(endpoint: str, payload: dict, timeout: int = 10) -> dict:
    base_url = settings.AI_SERVICE_URL.rstrip("/")
    url = f"{base_url}{endpoint}"
    try:
        response = requests.post(url, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        raise AIServiceError(f"AI service request failed: {exc}") from exc

    if response.status_code != 200:
        raise AIServiceError(f"AI service error ({response.status_code}): {response.text}")

    try:
        return response.json()
    except ValueError as exc:
        raise AIServiceError("AI service returned invalid JSON") from exc


def parse_resume(file_path: str, file_type: str) -> dict:
    return ai_post("/parse_resume", {"file_path": file_path, "file_type": file_type})


def match_resume_job(resume_text: str, job_payload: dict) -> dict:
    return ai_post("/match", {"resume_text": resume_text, "job": job_payload})


def recommend_jobs(resume_text: str, jobs_payload: list, top_n: int = 10) -> dict:
    return ai_post("/recommend_jobs", {"resume_text": resume_text, "jobs": jobs_payload, "top_n": top_n})


def skill_gap(resume_text: str, job_payload: dict) -> dict:
    return ai_post("/skill_gap", {"resume_text": resume_text, "job": job_payload})


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
    from django.conf import settings
    
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
