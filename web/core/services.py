import html as html_lib
import ipaddress
import logging
import math
import re
from typing import Dict, List, Optional, Set, Tuple
from collections import Counter
from datetime import datetime
from urllib.parse import urlparse

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

GENERIC_SKILL_TAGS = {"general", "remote"}
ACTION_VERBS = {
    "developed", "built", "implemented", "designed", "optimized", "improved",
    "delivered", "created", "led", "managed", "architected", "launched",
    "automated", "engineered", "analyzed", "deployed", "reduced", "increased",
}
DEGREE_KEYWORDS = {
    "bachelor", "master", "phd", "b.s", "b.sc", "m.s", "mba", "b.tech", "m.tech",
    "degree", "engineering", "computer science", "information technology",
}
CERTIFICATION_KEYWORDS = {
    "certification", "certified", "certificate", "aws certified", "google cloud",
    "azure", "pmp", "scrum master", "coursera", "udemy",
}
EXPERIENCE_HINT_WORDS = {
    "experience", "engineer", "developer", "intern", "manager", "analyst",
    "worked", "project", "employment",
}
JOB_KEYWORD_STOPWORDS = {
    "looking", "candidate", "candidates", "required", "requirements", "must",
    "should", "ability", "strong", "excellent", "knowledge", "team", "work",
    "role", "position", "job", "responsible", "responsibilities", "experience",
    "year", "years", "plus", "using", "build", "develop", "maintain", "good",
}
STANDARD_HEADINGS = ("skills", "experience", "education")
WORD_CHARS_CLASS = r"a-z0-9+.#"

SECTION_WEIGHTS = (
    ("keywords_match", "Keywords Match", 35),
    ("skills_relevance", "Skills Relevance", 20),
    ("experience_match", "Experience Match", 15),
    ("education_certifications", "Education & Certifications", 10),
    ("resume_format", "Resume Format", 10),
    ("contact_information", "Contact Information", 5),
    ("quantifiable_achievements", "Quantifiable Achievements", 5),
)

PERSONAL_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "live.com",
    "aol.com", "icloud.com", "protonmail.com", "proton.me",
}
URL_SHORTENER_HOSTS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "cutt.ly", "rb.gy", "shorturl.at", "buff.ly",
}
SUSPICIOUS_TLDS = {"xyz", "top", "buzz", "click", "work", "shop", "live", "support"}
TRUSTED_JOB_HOSTS = {
    "linkedin.com", "indeed.com", "glassdoor.com", "naukri.com", "internshala.com",
    "wellfound.com", "angel.co", "foundit.in", "foundit.com", "cutshort.io", "timesjobs.com",
}
TRUSTED_ATS_HOST_TOKENS = (
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "jobvite.com",
    "icims.com",
    "myworkdayjobs.com",
    "workdayjobs.com",
    "smartrecruiters.com",
    "bamboohr.com",
    "teamtailor.com",
)
GENERIC_COMPANY_VALUES = {"", "confidential", "unknown", "unknown company", "n/a", "na", "hiring", "urgent hiring"}
FAKE_JOB_SIGNAL_RULES = (
    {
        "label": "Upfront payment requested",
        "terms": ["registration fee", "security deposit", "processing fee", "training fee", "payment required", "refundable deposit", "pay fee"],
        "points": 35,
        "category": "financial",
        "detail": "Legitimate employers should not charge candidates any fee to apply, interview, or start work.",
    },
    {
        "label": "Off-platform chat request",
        "terms": ["whatsapp", "telegram", "signal app", "dm us", "direct message"],
        "points": 25,
        "category": "communication",
        "detail": "Scam recruiters often move candidates to chat apps to avoid traceable company channels.",
    },
    {
        "label": "Too-good-to-be-true earnings claim",
        "terms": ["earn money", "quick money", "guaranteed income", "guaranteed job", "daily payout", "weekly payout", "earn from home"],
        "points": 25,
        "category": "promises",
        "detail": "Job posts promising effortless or guaranteed income are high-risk.",
    },
    {
        "label": "Minimal screening claim",
        "terms": ["no interview", "no experience required", "no resume", "no cv", "instant joining", "immediate joining"],
        "points": 15,
        "category": "process",
        "detail": "Real employers usually define a screening process and role expectations.",
    },
    {
        "label": "Task or investment scam language",
        "terms": ["crypto", "usdt", "investment", "recharge", "review task", "like and subscribe", "captcha", "data entry"],
        "points": 18,
        "category": "content",
        "detail": "Low-effort tasks mixed with payment or investment language are common scam patterns.",
    },
    {
        "label": "Sensitive identity or banking data request",
        "terms": ["aadhaar", "pan card", "bank account", "upi id", "otp", "passport copy"],
        "points": 30,
        "category": "data_request",
        "detail": "Do not share identity documents, OTPs, or bank details before verifying the employer.",
    },
    {
        "label": "Artificial urgency",
        "terms": ["limited slots", "apply immediately", "only today", "urgent requirement", "selected immediately", "hiring all candidates"],
        "points": 10,
        "category": "pressure",
        "detail": "Pressure tactics are used to rush candidates past basic verification.",
    },
)


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
        if _contains_exact_phrase(normalized, skill):
            found.add(skill.lower())
    return sorted(found)


def _extract_education(text: str) -> List[Dict[str, str]]:
    education = []
    for line in text.splitlines():
        lower = line.lower()
        if any(keyword in lower for keyword in DEGREE_KEYWORDS):
            year_match = re.search(r"(19|20)\d{2}", line)
            education.append({
                "degree": line.strip(),
                "institute": "",
                "year": year_match.group(0) if year_match else "",
            })
    return education[:5]


def _extract_experience(text: str) -> List[Dict[str, str]]:
    experience = []
    for line in text.splitlines():
        lower = line.lower()
        if any(keyword in lower for keyword in EXPERIENCE_HINT_WORDS):
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


def _contains_exact_phrase(normalized_text: str, phrase: str) -> bool:
    phrase_norm = _normalize_text(str(phrase or ""))
    if not phrase_norm:
        return False
    pattern = rf"(?<![{WORD_CHARS_CLASS}]){re.escape(phrase_norm)}(?![{WORD_CHARS_CLASS}])"
    return re.search(pattern, normalized_text) is not None


def _clean_skill_values(raw_skills: List[str]) -> List[str]:
    cleaned = []
    for skill in raw_skills or []:
        value = _normalize_text(str(skill or ""))
        if value and value not in GENERIC_SKILL_TAGS:
            cleaned.append(value)
    return sorted(set(cleaned))


def _extract_job_skill_sets(job: Dict, normalized_job_text: str) -> Tuple[Set[str], Set[str]]:
    required_skills = set(_clean_skill_values(job.get("required_skills") or []))
    detected = set()
    for skill in SKILLS_DICTIONARY:
        if _contains_exact_phrase(normalized_job_text, skill):
            detected.add(skill.lower())
    target_skills = required_skills.union(detected)
    return required_skills, target_skills


def _extract_job_keywords(job: Dict, target_skills: Set[str]) -> List[str]:
    title = job.get("title", "")
    description = job.get("description", "")
    title_tokens = {
        token for token in _tokenize(title)
        if len(token) >= 3 and token not in JOB_KEYWORD_STOPWORDS
    }
    description_tokens = [
        token for token in _tokenize(description)
        if len(token) >= 4 and token not in JOB_KEYWORD_STOPWORDS
    ]
    description_freq = Counter(description_tokens)
    repeated_terms = {token for token, count in description_freq.items() if count >= 2}
    keywords = set(target_skills).union(title_tokens).union(repeated_terms)
    keywords = {keyword for keyword in keywords if keyword and keyword not in JOB_KEYWORD_STOPWORDS}
    return sorted(keywords)


def _extract_years_signal(text: str) -> float:
    lower = text.lower()
    max_years = 0.0

    for raw in re.findall(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", lower):
        try:
            max_years = max(max_years, float(raw))
        except ValueError:
            continue

    current_year = datetime.now().year
    range_pattern = re.compile(r"\b((?:19|20)\d{2})\b\s*(?:-|to|–|—)\s*\b((?:19|20)\d{2}|present|current)\b")
    for start_raw, end_raw in range_pattern.findall(lower):
        try:
            start_year = int(start_raw)
        except ValueError:
            continue
        if end_raw in {"present", "current"}:
            end_year = current_year
        else:
            try:
                end_year = int(end_raw)
            except ValueError:
                continue
        if end_year >= start_year:
            max_years = max(max_years, float(end_year - start_year))

    return min(max_years, 40.0)


def _score_keywords_match(normalized_resume: str, job_keywords: List[str], missing_skills: List[str]) -> Tuple[int, Dict, List[str]]:
    matched_keywords = [kw for kw in job_keywords if _contains_exact_phrase(normalized_resume, kw)]
    missing_keywords = [kw for kw in job_keywords if kw not in matched_keywords]
    total_keywords = len(job_keywords)
    ratio = (len(matched_keywords) / total_keywords) if total_keywords else 0.0
    score = int(round(ratio * 100))

    mistakes = []
    if total_keywords == 0:
        mistakes.append("Job description has limited extractable keywords; add clearer role keywords for better ATS matching.")
    elif ratio < 0.6:
        mistakes.append("Low keyword match. Add exact terms from the job post in skills and experience sections.")
    if missing_keywords:
        mistakes.append("Missing important job keywords: " + ", ".join(missing_keywords[:6]) + ".")
    if missing_skills:
        mistakes.append("Add missing role skills: " + ", ".join(missing_skills[:5]) + ".")

    details = {
        "matched_keywords": matched_keywords,
        "missing_keywords": missing_keywords,
        "keyword_coverage": round(ratio * 100, 1),
    }
    return score, details, mistakes


def _score_skills_relevance(normalized_resume: str, resume_skills: Set[str], target_job_skills: Set[str]) -> Tuple[int, Dict, List[str]]:
    matched_role_skills = sorted(skill for skill in target_job_skills if _contains_exact_phrase(normalized_resume, skill))
    recall = (len(matched_role_skills) / len(target_job_skills)) if target_job_skills else 0.0
    precision = (len(set(matched_role_skills).intersection(resume_skills)) / len(resume_skills)) if resume_skills else 0.0
    score = int(round((0.8 * recall + 0.2 * precision) * 100))

    mistakes = []
    if target_job_skills and recall < 0.6:
        mistakes.append("Technical skills are not closely aligned with the job requirements.")
    if resume_skills and precision < 0.4:
        mistakes.append("Resume includes many skills not relevant to this role.")
    if not resume_skills:
        mistakes.append("No clear technical skills detected in the resume.")

    details = {
        "matched_role_skills": matched_role_skills,
        "skill_recall": round(recall * 100, 1),
        "skill_precision": round(precision * 100, 1),
    }
    return score, details, mistakes


def _score_experience_match(resume_text: str, lower_lines: List[str], target_terms: Set[str]) -> Tuple[int, Dict, List[str]]:
    years_signal = _extract_years_signal(resume_text)
    action_pattern = re.compile(r"\b(" + "|".join(sorted(ACTION_VERBS)) + r")\b")
    action_hits = len(action_pattern.findall(resume_text.lower()))

    experience_lines = []
    for line in lower_lines:
        has_experience_word = any(word in line for word in EXPERIENCE_HINT_WORDS)
        has_year_signal = bool(re.search(r"\d+\s*(?:\+)?\s*(?:years?|yrs?)", line))
        has_range = bool(re.search(r"\b(?:19|20)\d{2}\b\s*(?:-|to|–|—)\s*\b(?:(?:19|20)\d{2}|present|current)\b", line))
        has_action = bool(action_pattern.search(line))
        if has_experience_word or has_year_signal or has_range or has_action:
            experience_lines.append(line)

    relevant_lines = 0
    if experience_lines and target_terms:
        for line in experience_lines:
            if any(term in line for term in target_terms):
                relevant_lines += 1
    relevance_ratio = (relevant_lines / len(experience_lines)) if experience_lines else 0.0

    years_component = min(years_signal / 5.0, 1.0) * 40.0
    action_component = min(action_hits / 6.0, 1.0) * 30.0
    relevance_component = relevance_ratio * 30.0
    score = int(round(years_component + action_component + relevance_component))

    mistakes = []
    if years_signal <= 0:
        mistakes.append("Mention total years of experience (for example: 3+ years).")
    if action_hits < 2:
        mistakes.append("Use more action verbs like Developed, Built, and Implemented in experience bullets.")
    if relevance_ratio < 0.4:
        mistakes.append("Experience section should mention role-relevant technologies and responsibilities.")

    details = {
        "years_signal": round(years_signal, 2),
        "action_word_hits": action_hits,
        "experience_relevance": round(relevance_ratio * 100, 1),
    }
    return score, details, mistakes


def _score_education_and_certifications(lower_lines: List[str], target_terms: Set[str]) -> Tuple[int, Dict, List[str]]:
    education_lines = [line for line in lower_lines if any(keyword in line for keyword in DEGREE_KEYWORDS)]
    certification_lines = [line for line in lower_lines if any(keyword in line for keyword in CERTIFICATION_KEYWORDS)]

    relevance_terms = set(target_terms).union({"computer", "software", "information", "data", "engineering", "science", "ai"})
    relevant_education = False
    for line in education_lines:
        if any(term in line for term in relevance_terms if len(term) >= 2):
            relevant_education = True
            break

    score = 0
    if education_lines:
        score += 70
    if education_lines and relevant_education:
        score += 15
    if certification_lines:
        score += 15
    score = min(score, 100)

    mistakes = []
    if not education_lines:
        mistakes.append("Education details are missing or unclear. Add degree and specialization.")
    elif not relevant_education:
        mistakes.append("Clarify education specialization relevant to this role.")
    if not certification_lines:
        mistakes.append("Add role-relevant certifications to improve ATS performance.")

    details = {
        "education_found": bool(education_lines),
        "certifications_found": bool(certification_lines),
        "education_relevance": relevant_education,
    }
    return score, details, mistakes


def _score_resume_format(resume_text: str, lower_lines: List[str], resume_metadata: Optional[Dict]) -> Tuple[int, Dict, List[str]]:
    metadata = resume_metadata or {}
    file_type = str(metadata.get("file_type", "")).strip().lower().lstrip(".")
    score = 30
    mistakes = []

    if file_type in {"pdf", "docx"}:
        score += 25
    elif file_type:
        mistakes.append("Resume file format should be PDF or DOCX.")
    else:
        score += 15

    found_headings = []
    for heading in STANDARD_HEADINGS:
        has_heading = bool(re.search(rf"(?im)^\s*{re.escape(heading)}\s*:?", resume_text))
        if not has_heading:
            has_heading = any(heading in line for line in lower_lines)
        if has_heading:
            found_headings.append(heading)

    score += len(found_headings) * 15
    missing_headings = [heading.title() for heading in STANDARD_HEADINGS if heading not in found_headings]
    if missing_headings:
        mistakes.append("Use standard headings: " + ", ".join(missing_headings) + ".")

    table_like_lines = sum(1 for line in resume_text.splitlines() if line.count("|") >= 2 or line.count("\t") >= 2)
    if table_like_lines > 0:
        score -= 20
        mistakes.append("Avoid tables in resume content for better ATS parsing.")

    has_image_reference = bool(re.search(r"\.(png|jpg|jpeg|gif|svg)\b", resume_text.lower()))
    if has_image_reference:
        score -= 15
        mistakes.append("Avoid image-only content; use plain text sections.")

    score = max(0, min(score, 100))
    details = {
        "file_type": file_type or "unknown",
        "headings_found": [heading.title() for heading in found_headings],
        "table_like_content": table_like_lines > 0,
        "image_reference_found": has_image_reference,
    }
    return score, details, mistakes


def _find_linkedin_url(text: str) -> str:
    match = re.search(r"(https?://)?(www\.)?linkedin\.com/in/[A-Za-z0-9_-]+/?", text, flags=re.IGNORECASE)
    return match.group(0) if match else ""


def _score_contact_information(resume_text: str) -> Tuple[int, Dict, List[str], List[str]]:
    name = _extract_name(resume_text)
    email = _extract_email(resume_text)
    phone = _extract_phone(resume_text)
    linkedin = _find_linkedin_url(resume_text)

    score = 0
    mistakes = []
    optional_tips = []

    if name:
        score += 15
    else:
        mistakes.append("Add your full name at the top of the resume.")
    if email:
        score += 40
    else:
        mistakes.append("Professional email address is missing.")
    if phone:
        score += 35
    else:
        mistakes.append("Phone number is missing.")
    if linkedin:
        score += 10
    else:
        optional_tips.append("Add your LinkedIn profile URL (optional but recommended).")

    details = {
        "name_found": bool(name),
        "email_found": bool(email),
        "phone_found": bool(phone),
        "linkedin_found": bool(linkedin),
    }
    return score, details, mistakes, optional_tips


def _score_quantifiable_achievements(lower_lines: List[str]) -> Tuple[int, Dict, List[str]]:
    action_pattern = re.compile(r"\b(" + "|".join(sorted(ACTION_VERBS)) + r")\b")
    number_pattern = re.compile(r"\b\d+(?:\.\d+)?%?\b")

    numeric_lines = [line for line in lower_lines if number_pattern.search(line)]
    achievement_lines = [line for line in numeric_lines if action_pattern.search(line)]

    if len(achievement_lines) >= 3:
        score = 100
    elif len(achievement_lines) == 2:
        score = 75
    elif len(achievement_lines) == 1:
        score = 55
    elif len(numeric_lines) >= 2:
        score = 35
    elif len(numeric_lines) == 1:
        score = 20
    else:
        score = 0

    mistakes = []
    if not achievement_lines:
        mistakes.append("Add quantifiable achievements with numbers, for example: improved accuracy by 35%.")

    details = {
        "numeric_line_count": len(numeric_lines),
        "achievement_line_count": len(achievement_lines),
    }
    return score, details, mistakes


def _deduplicate_messages(messages: List[str]) -> List[str]:
    seen = set()
    unique = []
    for message in messages:
        clean = (message or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        unique.append(clean)
    return unique


def _build_match_response(resume_text: str, job: Dict, resume_metadata: Optional[Dict] = None) -> Dict:
    normalized_resume = _normalize_text(resume_text)
    normalized_job_text = _normalize_text(
        f"{job.get('title', '')} {job.get('description', '')} {' '.join(job.get('required_skills') or [])}"
    )

    required_job_skills, target_job_skills = _extract_job_skill_sets(job, normalized_job_text)
    skills_for_output = required_job_skills or target_job_skills

    matched_skills = sorted(skill for skill in skills_for_output if _contains_exact_phrase(normalized_resume, skill))
    missing_skills = sorted(skill for skill in skills_for_output if skill not in matched_skills)

    job_keywords = _extract_job_keywords(job, target_job_skills)
    resume_skills = set(_extract_skills(resume_text))
    lower_lines = [line.strip().lower() for line in resume_text.splitlines() if line.strip()]
    role_terms = {
        token for token in _tokenize(job.get("title", ""))
        if len(token) >= 3 and token not in JOB_KEYWORD_STOPWORDS
    }.union({skill for skill in target_job_skills if len(skill) >= 3})

    keyword_score, keyword_details, keyword_mistakes = _score_keywords_match(
        normalized_resume,
        job_keywords,
        missing_skills,
    )
    skill_score, skill_details, skill_mistakes = _score_skills_relevance(
        normalized_resume,
        resume_skills,
        target_job_skills,
    )
    experience_score, experience_details, experience_mistakes = _score_experience_match(
        resume_text,
        lower_lines,
        role_terms,
    )
    education_score, education_details, education_mistakes = _score_education_and_certifications(
        lower_lines,
        role_terms,
    )
    format_score, format_details, format_mistakes = _score_resume_format(
        resume_text,
        lower_lines,
        resume_metadata,
    )
    contact_score, contact_details, contact_mistakes, optional_contact_tips = _score_contact_information(resume_text)
    achievements_score, achievement_details, achievement_mistakes = _score_quantifiable_achievements(lower_lines)

    section_scores = {
        "keywords_match": keyword_score,
        "skills_relevance": skill_score,
        "experience_match": experience_score,
        "education_certifications": education_score,
        "resume_format": format_score,
        "contact_information": contact_score,
        "quantifiable_achievements": achievements_score,
    }

    weighted_total = 0.0
    score_breakdown = []
    for key, label, weight in SECTION_WEIGHTS:
        section_score = max(0, min(section_scores.get(key, 0), 100))
        weighted_score = round((section_score / 100.0) * weight, 2)
        weighted_total += weighted_score
        score_breakdown.append({
            "key": key,
            "label": label,
            "weight": weight,
            "score": section_score,
            "weighted_score": weighted_score,
        })

    ats_score = int(round(max(0.0, min(weighted_total, 100.0))))
    mistakes = _deduplicate_messages(
        keyword_mistakes
        + skill_mistakes
        + experience_mistakes
        + education_mistakes
        + format_mistakes
        + contact_mistakes
        + achievement_mistakes
    )
    improvement_tips = mistakes[:6]
    if optional_contact_tips:
        improvement_tips.extend(optional_contact_tips[:1])
    if not improvement_tips:
        improvement_tips.append("Resume is strongly aligned with ATS expectations for this job.")

    skills_total = len(skills_for_output)
    summary = (
        f"ATS score {ats_score}/100. "
        f"Matched {len(keyword_details['matched_keywords'])}/{len(job_keywords)} job keywords and "
        f"{len(matched_skills)}/{skills_total} key skills."
    )

    return {
        "score": ats_score,
        "ats_score": ats_score,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "matched_keywords": keyword_details["matched_keywords"],
        "missing_keywords": keyword_details["missing_keywords"],
        "score_breakdown": score_breakdown,
        "section_details": {
            "keywords_match": keyword_details,
            "skills_relevance": skill_details,
            "experience_match": experience_details,
            "education_certifications": education_details,
            "resume_format": format_details,
            "contact_information": contact_details,
            "quantifiable_achievements": achievement_details,
        },
        "mistakes": mistakes,
        "summary": summary,
        "improvement_tips": improvement_tips,
    }


def _build_skill_gap_response(resume_text: str, job: Dict) -> Dict:
    normalized_resume = _normalize_text(resume_text)
    normalized_job_text = _normalize_text(
        f"{job.get('title', '')} {job.get('description', '')} {' '.join(job.get('required_skills') or [])}"
    )

    required_skills, target_skills = _extract_job_skill_sets(job, normalized_job_text)
    skills_for_gap = required_skills or target_skills
    matched = sorted(skill for skill in skills_for_gap if _contains_exact_phrase(normalized_resume, skill))
    missing = sorted(skill for skill in skills_for_gap if skill not in matched)

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


def _match_resume_job_local(resume_text: str, job_payload: dict, resume_metadata: Optional[dict] = None) -> dict:
    return _build_match_response(resume_text, job_payload, resume_metadata=resume_metadata)


def _recommend_jobs_local(resume_text: str, jobs_payload: list, top_n: int = 10) -> dict:
    recommendations = []
    for job in jobs_payload:
        result = _build_match_response(resume_text, job)
        if not result["matched_skills"]:
            continue

        job_id = job.get("id") or job.get("job_id")
        reason = "Matched skills: " + ", ".join(result["matched_skills"][:5])
        recommendations.append({
            "job_id": job_id,
            "score": result["score"],
            "reason": reason,
        })

    recommendations.sort(key=lambda row: row["score"], reverse=True)
    return {"recommendations": recommendations[:top_n]}


def _skill_gap_local(resume_text: str, job_payload: dict) -> dict:
    return _build_skill_gap_response(resume_text, job_payload)


def _ai_service_uses_loopback_url() -> bool:
    raw_url = str(getattr(settings, "AI_SERVICE_URL", "") or "").strip()
    if not raw_url:
        return False

    parsed = urlparse(raw_url if "//" in raw_url else f"http://{raw_url}")
    hostname = (parsed.hostname or "").strip().lower()
    return hostname in {"localhost", "127.0.0.1", "::1"}


def _should_use_local_fallback(exc: AIServiceError) -> bool:
    if not getattr(settings, "AI_SERVICE_FALLBACK_LOCAL", True):
        return False
    if exc.network_error:
        return True
    if exc.status_code in {404, 405} and _ai_service_uses_loopback_url():
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


def match_resume_job(resume_text: str, job_payload: dict, resume_metadata: Optional[dict] = None) -> dict:
    return _run_with_fallback(
        "match",
        lambda: ai_post("/match", {"resume_text": resume_text, "job": job_payload, "resume_metadata": resume_metadata or {}}),
        lambda: _match_resume_job_local(resume_text, job_payload, resume_metadata),
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




def _build_fake_job_flag(label: str, detail: str, points: int, category: str = "general") -> dict:
    return {"label": label, "detail": detail, "points": points, "category": category}


def _host_matches(hostname: str, domain: str) -> bool:
    return hostname == domain or hostname.endswith(f".{domain}")


def _host_matches_any(hostname: str, domains: set[str]) -> bool:
    return any(_host_matches(hostname, domain) for domain in domains)


def _host_uses_trusted_ats(hostname: str) -> bool:
    return any(_host_matches(hostname, domain) for domain in TRUSTED_ATS_HOST_TOKENS)


def _is_ip_hostname(hostname: str) -> bool:
    if not hostname:
        return False
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        return False


def _extract_primary_company_token(company: str) -> str:
    ignored = {"private", "limited", "ltd", "inc", "llc", "company", "technologies", "technology", "solutions", "services", "group"}
    tokens = [token for token in _tokenize(company) if len(token) >= 3 and token not in ignored]
    return tokens[0] if tokens else ""


def _strip_html_to_text(raw_html: str) -> tuple[str, str]:
    html_text = str(raw_html or "")
    title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html_text)
    page_title = html_lib.unescape(re.sub(r"\s+", " ", title_match.group(1))).strip() if title_match else ""
    cleaned = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html_text)
    cleaned = re.sub(r"(?is)<!--.*?-->", " ", cleaned)
    cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
    cleaned = html_lib.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return page_title, cleaned


def _fetch_job_link_insights(apply_link: str) -> dict:
    if not apply_link:
        return {
            "submitted_url": "",
            "final_url": "",
            "domain": "",
            "page_title": "",
            "content_excerpt": "",
            "reachable": False,
            "status_code": None,
            "fetch_note": "",
        }

    parsed = urlparse(apply_link)
    hostname = (parsed.hostname or "").strip().lower()
    result = {
        "submitted_url": apply_link,
        "final_url": "",
        "domain": hostname,
        "page_title": "",
        "content_excerpt": "",
        "reachable": False,
        "status_code": None,
        "fetch_note": "",
    }

    try:
        response = requests.get(
            apply_link,
            timeout=8,
            allow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; AIResumeAnalyzer/1.0; FakeJobCheck)",
            },
        )
        result["final_url"] = response.url
        result["status_code"] = response.status_code
        result["reachable"] = bool(getattr(response, "ok", False))
        if response.url:
            final_hostname = (urlparse(response.url).hostname or "").strip().lower()
            if final_hostname:
                result["domain"] = final_hostname

        if result["reachable"]:
            page_title, page_text = _strip_html_to_text(getattr(response, "text", ""))
            result["page_title"] = page_title
            result["content_excerpt"] = page_text[:1800]
            if not page_text:
                result["fetch_note"] = "The link loaded, but the page content was not readable as text."
        else:
            result["fetch_note"] = f"The link responded with HTTP {response.status_code}."
    except requests.RequestException as exc:
        result["fetch_note"] = f"Could not fetch the link live: {exc}"

    return result


def _score_fake_job_posting(job_payload: dict) -> dict:
    job_title = str(job_payload.get("job_title") or job_payload.get("title") or "").strip()
    company = str(job_payload.get("company") or "").strip()
    location = str(job_payload.get("location") or "").strip()
    salary_range = str(job_payload.get("salary_range") or "").strip()
    description = str(job_payload.get("description") or "").strip()
    apply_link = str(job_payload.get("apply_link") or "").strip()

    link_analysis = _fetch_job_link_insights(apply_link)
    evidence_parts = [
        job_title,
        company,
        location,
        salary_range,
        description,
        link_analysis.get("page_title", ""),
        link_analysis.get("content_excerpt", ""),
    ]
    combined_text = " ".join(part for part in evidence_parts if part).strip()
    normalized_text = _normalize_text(combined_text)

    flags = []
    positive_signals = []
    recommendations = []
    risk_points = 0
    trust_bonus = 0

    company_normalized = _normalize_text(company)
    if company_normalized in GENERIC_COMPANY_VALUES:
        flags.append(_build_fake_job_flag(
            "Missing or generic company name",
            "The posting does not clearly identify the employer.",
            12,
            "company",
        ))
        risk_points += 12
    else:
        positive_signals.append("The posting includes a named company.")
        trust_bonus += 5

    if len(description) >= 250 or len(link_analysis.get("content_excerpt", "")) >= 250:
        positive_signals.append("The listing contains a reasonably detailed job description.")
        trust_bonus += 5
    elif not description and not link_analysis.get("content_excerpt"):
        flags.append(_build_fake_job_flag(
            "Not enough job detail to verify",
            "There is not enough readable content to validate the job beyond the raw link.",
            10,
            "content",
        ))
        risk_points += 10
    else:
        flags.append(_build_fake_job_flag(
            "Thin job description",
            "Short job descriptions make it harder to verify a real employer and role.",
            8,
            "content",
        ))
        risk_points += 8

    for rule in FAKE_JOB_SIGNAL_RULES:
        hits = [term for term in rule["terms"] if term in normalized_text]
        if not hits:
            continue
        sample_hits = ", ".join(sorted(set(hits))[:3])
        flags.append(_build_fake_job_flag(
            rule["label"],
            f"{rule['detail']} Triggered by: {sample_hits}.",
            int(rule["points"]),
            rule.get("category", "general"),
        ))
        risk_points += int(rule["points"])

    if apply_link:
        parsed = urlparse(apply_link)
        hostname = (link_analysis.get("domain") or parsed.hostname or "").strip().lower()
        scheme = (parsed.scheme or "").strip().lower()

        if scheme != "https":
            flags.append(_build_fake_job_flag(
                "Application link is not HTTPS",
                "Use extra caution with job links that do not use encrypted HTTPS.",
                8,
                "security",
            ))
            risk_points += 8
        else:
            positive_signals.append("The application link uses HTTPS.")
            trust_bonus += 5

        if hostname:
            if _host_matches_any(hostname, URL_SHORTENER_HOSTS):
                flags.append(_build_fake_job_flag(
                    "Shortened application URL",
                    "Short links hide the real destination and are common in scam posts.",
                    28,
                    "security",
                ))
                risk_points += 28

            if _is_ip_hostname(hostname):
                flags.append(_build_fake_job_flag(
                    "Application link uses a raw IP address",
                    "Legitimate employers almost never use a bare IP address for recruiting pages.",
                    25,
                    "security",
                ))
                risk_points += 25

            if "xn--" in hostname:
                flags.append(_build_fake_job_flag(
                    "Punycode or lookalike domain",
                    "Lookalike domains can be used to impersonate real companies.",
                    22,
                    "security",
                ))
                risk_points += 22

            tld = hostname.rsplit(".", 1)[-1] if "." in hostname else hostname
            if tld in SUSPICIOUS_TLDS:
                flags.append(_build_fake_job_flag(
                    "Low-trust top-level domain",
                    f"The link uses the .{tld} domain, which deserves additional verification for job applications.",
                    12,
                    "security",
                ))
                risk_points += 12

            trusted_host = _host_matches_any(hostname, TRUSTED_JOB_HOSTS) or _host_uses_trusted_ats(hostname)
            if trusted_host:
                positive_signals.append(f"The application link points to a known job board or ATS domain ({hostname}).")
                trust_bonus += 15

            company_token = _extract_primary_company_token(company)
            if company_token and not trusted_host and company_token not in hostname:
                flags.append(_build_fake_job_flag(
                    "Company and domain do not match cleanly",
                    f"The employer name '{company}' does not clearly match the application domain '{hostname}'.",
                    10,
                    "company",
                ))
                risk_points += 10

        if link_analysis.get("fetch_note"):
            recommendations.append("Open the job link independently and confirm the company careers page before applying.")
        elif link_analysis.get("reachable"):
            positive_signals.append("The job link was reachable during analysis.")
            trust_bonus += 5

    all_caps_ratio = 0.0
    alpha_chars = [ch for ch in combined_text if ch.isalpha()]
    if alpha_chars:
        all_caps_ratio = sum(1 for ch in alpha_chars if ch.isupper()) / len(alpha_chars)
    if all_caps_ratio > 0.35 and len(alpha_chars) > 40:
        flags.append(_build_fake_job_flag(
            "Excessive all-caps formatting",
            "Overly aggressive formatting is common in spam-like recruiting messages.",
            8,
            "content",
        ))
        risk_points += 8

    if "!!!" in combined_text or combined_text.count("$$") >= 1:
        flags.append(_build_fake_job_flag(
            "Spam-style punctuation",
            "Heavy use of exclamation marks or money symbols is a caution signal.",
            6,
            "content",
        ))
        risk_points += 6

    emails = re.findall(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})", combined_text)
    personal_domains = sorted({domain.lower() for domain in emails if domain.lower() in PERSONAL_EMAIL_DOMAINS})
    if personal_domains:
        flags.append(_build_fake_job_flag(
            "Recruiter uses a personal email domain",
            "Use caution when a recruiter communicates only through public email providers instead of a company domain.",
            14,
            "communication",
        ))
        risk_points += 14
        recommendations.append("Ask for confirmation from an official company email address before sharing documents.")

    if not job_title.strip():
        flags.append(_build_fake_job_flag(
            "Missing job title",
            "A legitimate posting should clearly state the role being advertised.",
            6,
            "content",
        ))
        risk_points += 6

    trust_bonus = min(trust_bonus, 30)
    risk_score = max(0, min(100, risk_points - trust_bonus))

    if risk_score >= 60:
        risk_level = "high"
        verdict = "This posting shows several common scam signals. Verify the employer before taking any next step."
    elif risk_score >= 30:
        risk_level = "medium"
        verdict = "This posting needs manual verification before you trust it."
    else:
        risk_level = "low"
        verdict = "No major scam indicators were found in the submitted data, but basic verification is still recommended."

    if risk_level == "high":
        recommendations.insert(0, "Do not pay any registration, onboarding, or security fee for this job.")
        recommendations.append("Search the company and job title on the employer's official website instead of relying only on the shared link.")
    elif risk_level == "medium":
        recommendations.append("Verify the recruiter on LinkedIn or the company's careers page before applying.")
    else:
        recommendations.append("Still confirm the employer's careers page and recruiter identity before sharing sensitive documents.")

    if any(flag["label"] == "Sensitive identity or banking data request" for flag in flags):
        recommendations.append("Never share Aadhaar, PAN, OTP, or bank information before a verified offer stage.")

    if not apply_link:
        recommendations.append("Ask for the official careers link or company domain before proceeding.")

    recommendations = _deduplicate_messages(recommendations)[:5]
    positive_signals = _deduplicate_messages(positive_signals)[:5]

    summary = (
        f"Risk score {risk_score}/100 based on {len(flags)} risk signal(s)"
        f" and {len(positive_signals)} positive verification signal(s)."
    )

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_label": f"{risk_level.title()} Risk",
        "verdict": verdict,
        "summary": summary,
        "flags": flags,
        "positive_signals": positive_signals,
        "recommendations": recommendations,
        "link_analysis": link_analysis,
        "analyzed_input": {
            "job_title": job_title,
            "company": company,
            "location": location,
            "salary_range": salary_range,
            "description": description,
            "apply_link": apply_link,
        },
    }


def detect_fake_job_posting(job_payload: dict) -> dict:
    return _score_fake_job_posting(job_payload or {})

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
            # Remotive returns HTML in `description`; normalize to plain text for search/display.
            raw_description = job.get("description") or job.get("job_description") or ""
            description = re.sub(r"<[^>]+>", " ", raw_description)
            description = re.sub(r"\s+", " ", description).strip()
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

            title = job.get("title") or job.get("job_title") or "Unknown Position"
            title_lower = title.lower()
            if "senior" in title_lower or "lead" in title_lower or "principal" in title_lower:
                level = "Senior"
            elif "junior" in title_lower or "entry" in title_lower or "intern" in title_lower:
                level = "Junior"
            else:
                level = "Mid"

            formatted_jobs.append({
                "title": title,
                "company": job.get("company_name", "Unknown Company"),
                "location": job.get("candidate_required_location") or "Remote",
                "level": level,
                "salary_range": job.get("salary", "") or "",
                "description": description[:1000],  # Truncate to 1000 chars
                "required_skills": list(set(skills)) if skills else ["remote", "general"],
                "apply_link": job.get("url") or "",
            })

        return formatted_jobs
    except Exception as exc:
        raise AIServiceError(f"Failed to fetch jobs from Remotive: {exc}") from exc


def fetch_muse_jobs(query: str = "developer", location: str = "India", limit: int = 50) -> list:
    """Fetch real jobs from The Muse public API (no API key required)."""
    try:
        page = 1
        max_pages = 30
        collected = []
        query_l = (query or "").strip().lower()
        query_terms = [term for term in re.split(r"\s+", query_l) if len(term) >= 3]

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

        while len(collected) < limit and page <= max_pages:
            response = requests.get(
                "https://www.themuse.com/api/public/jobs",
                params={"location": location, "page": page},
                timeout=15,
            )
            if response.status_code == 400:
                # The Muse can return 400 when page exceeds available range for a location.
                break
            response.raise_for_status()
            payload = response.json()

            rows = payload.get("results", [])
            if not rows:
                break

            for row in rows:
                if len(collected) >= limit:
                    break

                title = row.get("name") or "Unknown Position"
                company = (row.get("company") or {}).get("name") or "Unknown Company"

                locations = [loc.get("name", "").strip() for loc in (row.get("locations") or []) if loc.get("name")]
                location_str = ", ".join(locations) if locations else (location or "Remote")

                raw_description = row.get("contents") or "No description available"
                description = re.sub(r"<[^>]+>", " ", raw_description)
                description = re.sub(r"\s+", " ", description).strip()
                description_lower = description.lower()

                if query_l:
                    haystack = f"{title} {description_lower}".lower()
                    if query_l not in haystack and not any(term in haystack for term in query_terms):
                        continue

                levels = [lvl.get("name", "") for lvl in (row.get("levels") or [])]
                level_text = " ".join(levels).lower()
                if "senior" in level_text or "lead" in level_text or "principal" in level_text:
                    level = "Senior"
                elif "junior" in level_text or "entry" in level_text or "intern" in level_text:
                    level = "Junior"
                else:
                    level = "Mid"

                skills = [skill for skill in skill_keywords if skill in description_lower]
                apply_link = (row.get("refs") or {}).get("landing_page") or ""

                collected.append({
                    "title": title,
                    "company": company,
                    "location": location_str,
                    "level": level,
                    "salary_range": "",
                    "description": description[:2000],
                    "required_skills": sorted(set(skills)) if skills else ["general"],
                    "apply_link": apply_link,
                })

            page_count = int(payload.get("page_count") or page)
            if page >= page_count:
                break
            page += 1

        return collected[:limit]
    except Exception as exc:
        raise AIServiceError(f"Failed to fetch jobs from The Muse: {exc}") from exc


def fetch_jsearch_jobs(query: str = "developer", location: str = "India", limit: int = 50) -> list:
    """Fetch real jobs from RapidAPI job endpoints (tries multiple compatible hosts)."""
    api_key = settings.JSEARCH_API_KEY
    if not api_key:
        raise AIServiceError("JSEARCH_API_KEY not configured in .env file")

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

    endpoints = [
        {
            "name": "jobs-api14",
            "url": "https://jobs-api14.p.rapidapi.com/search",
            "host": "jobs-api14.p.rapidapi.com",
            "params": {
                "keywords": query,
                "location": location,
                "page": 1,
                "num_pages": 1,
            },
        },
        {
            "name": "jsearch",
            "url": "https://jsearch.p.rapidapi.com/search",
            "host": "jsearch.p.rapidapi.com",
            "params": {
                "query": f"{query} in {location}" if location else query,
                "page": "1",
                "num_pages": "1",
            },
        },
    ]

    errors = []
    for endpoint in endpoints:
        try:
            headers = {
                "x-rapidapi-key": api_key,
                "x-rapidapi-host": endpoint["host"],
            }
            response = requests.get(endpoint["url"], headers=headers, params=endpoint["params"], timeout=15)

            # Keep provider-specific message when the key isn't subscribed.
            if response.status_code == 403:
                message = ""
                try:
                    message = (response.json() or {}).get("message", "")
                except Exception:
                    message = response.text
                errors.append(f"{endpoint['name']}: {message or '403 Forbidden'}")
                continue

            response.raise_for_status()
            data = response.json()

            jobs_list = []
            if isinstance(data, dict):
                jobs_list = data.get("data", []) or data.get("results", [])
            elif isinstance(data, list):
                jobs_list = data

            jobs_list = jobs_list[:limit]
            formatted_jobs = []

            for job in jobs_list:
                title = job.get("title") or job.get("job_title") or "Unknown Position"
                company = (
                    job.get("company")
                    or job.get("employer")
                    or job.get("employer_name")
                    or "Unknown Company"
                )

                job_city = job.get("job_city") or ""
                job_country = job.get("job_country") or ""
                location_str = (
                    job.get("location")
                    or job.get("job_location")
                    or ", ".join([value for value in [job_city, job_country] if value])
                    or location
                )

                description = job.get("description") or job.get("job_description") or "No description available"
                apply_link = (
                    job.get("url")
                    or job.get("job_apply_link")
                    or job.get("apply_link")
                    or ""
                )
                description_lower = description.lower()
                skills = [skill for skill in skill_keywords if skill in description_lower]

                title_lower = title.lower()
                if "senior" in title_lower or "lead" in title_lower or "principal" in title_lower:
                    level = "Senior"
                elif "junior" in title_lower or "entry" in title_lower or "intern" in title_lower:
                    level = "Junior"
                else:
                    level = "Mid"

                salary_range = ""
                salary_min = job.get("salary_min") or job.get("job_min_salary") or ""
                salary_max = job.get("salary_max") or job.get("job_max_salary") or ""
                if salary_min and salary_max:
                    salary_range = f"${salary_min} - ${salary_max}"
                elif salary_min:
                    salary_range = f"${salary_min}"
                elif job.get("salary"):
                    salary_range = str(job.get("salary"))

                formatted_jobs.append({
                    "title": title,
                    "company": company,
                    "location": location_str,
                    "level": level,
                    "salary_range": salary_range,
                    "description": description[:2000] if description else "No description available",
                    "required_skills": sorted(set(skills)) if skills else ["general"],
                    "apply_link": apply_link,
                })

            if formatted_jobs:
                return formatted_jobs

            errors.append(f"{endpoint['name']}: no jobs returned")
        except Exception as exc:
            errors.append(f"{endpoint['name']}: {exc}")

    raise AIServiceError("Failed to fetch jobs: " + " | ".join(errors))


def fetch_gemini_jobs(query: str = "developer", location: str = "India", limit: int = 50) -> list:
    """Generate realistic job listings using Google Gemini AI."""
    try:
        import google.generativeai as genai
        
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise AIServiceError("GEMINI_API_KEY not configured in .env file")
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        prompt = f"""Generate {limit} realistic job listings for {location} in JSON format.
        
        Focus on: {query}
        
        Each job should have:
        - title (string: job title)
        - company (string: company name)
        - location (string: within {location})
        - level (string: 'Junior', 'Mid', or 'Senior')
        - salary_range (string: e.g., "$30,000 - $50,000" or "₹30,00,000 - ₹50,00,000")
        - description (string: 2-3 sentence job description)
        - required_skills (array: relevant technical skills)
        - apply_link (string: "https://example.com/apply" - use realistic company domains)
        
        Return ONLY valid JSON array, no markdown, no explanation.
        Example:
        [
            {{
                "title": "Senior Python Developer",
                "company": "TechCorp India",
                "location": "Bangalore, India",
                "level": "Senior",
                "salary_range": "₹80,00,000 - ₹1,20,00,000",
                "description": "Building scalable microservices for AI applications...",
                "required_skills": ["python", "django", "postgresql", "docker"],
                "apply_link": "https://techcorp.com/careers"
            }}
        ]"""
        
        response = model.generate_content(prompt)
        response_text = response.text
        
        # Clean up response (remove markdown code blocks if present)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        import json
        jobs_data = json.loads(response_text)
        
        if not isinstance(jobs_data, list):
            jobs_data = [jobs_data] if isinstance(jobs_data, dict) else []
        
        return jobs_data[:limit]
    except Exception as exc:
        raise AIServiceError(f"Failed to fetch jobs from Gemini: {exc}") from exc


def fetch_jobs_auto(query: str = "developer", location: str = "India", limit: int = 50) -> tuple[list, str]:
    """
    Fetch jobs with source fallback order:
    JSearch -> The Muse -> Remotive -> Gemini AI
    Falls through if a source returns 0 jobs.

    Returns:
        (jobs, source_name)
    """
    sources = [
        ("jsearch", lambda: fetch_jsearch_jobs(query=query, location=location, limit=limit)),
        ("themuse", lambda: fetch_muse_jobs(query=query, location=location, limit=limit)),
        ("remotive", lambda: fetch_remotive_jobs(limit=limit)),
        ("gemini", lambda: fetch_gemini_jobs(query=query, location=location, limit=limit)),
    ]
    
    for source_name, fetch_func in sources:
        try:
            jobs = fetch_func()
            if jobs:  # Only accept if jobs were returned
                logger.info(f"Successfully fetched {len(jobs)} jobs from {source_name}")
                return jobs, source_name
            else:
                logger.warning(f"{source_name} returned 0 jobs, trying next source...")
        except AIServiceError as exc:
            logger.warning(f"{source_name} unavailable ({exc}). Trying next source...")
        except Exception as exc:
            logger.warning(f"{source_name} error: {exc}. Trying next source...")
    
    # If all sources fail or return empty
    raise AIServiceError("All job sources exhausted: JSearch (no subscription) -> The Muse (no jobs) -> Remotive (no jobs) -> Gemini (failed)")
INTERVIEW_SIMULATOR_SESSION_KEY = "interview_simulator_state"
INTERVIEW_DIFFICULTY_LABELS = {
    1: "Warm-up",
    2: "Baseline",
    3: "Pressure",
    4: "Stress Test",
    5: "Panel Heat",
}
INTERVIEW_HEDGES = {
    "maybe", "probably", "i think", "i guess", "kind of", "sort of", "i am not sure", "perhaps",
}
INTERVIEW_FILLERS = {
    "um", "uh", "like", "you know", "actually", "basically", "literally",
}
INTERVIEW_STRUCTURE_TERMS = {
    "first", "second", "third", "then", "finally", "because", "so that", "result", "impact",
}
INTERVIEW_DEPTH_TERMS = {
    "tradeoff", "constraint", "latency", "scale", "rollback", "root cause", "metric", "customer",
    "experiment", "ownership", "stakeholder", "failure", "incident", "decision", "priority",
}
INTERVIEW_FOCUS_PROMPTS = {
    "general": [
        "Tell me about a project from your resume that best represents how you work under pressure.",
        "Describe a time you had to make a decision with incomplete information.",
        "What is the hardest tradeoff you have made in a real project?",
    ],
    "backend": [
        "Walk me through a backend project where you owned an API, database, or reliability problem.",
        "Tell me about a production issue you had to debug quickly.",
        "Describe a scaling or performance tradeoff you had to make.",
    ],
    "frontend": [
        "Walk me through a frontend feature where you balanced UX, performance, and delivery speed.",
        "Tell me about a bug that affected users and how you handled it.",
        "Describe a tradeoff you made between polish and shipping.",
    ],
    "data": [
        "Walk me through a project where you improved a metric, model, or data pipeline.",
        "Tell me about a time your analysis was challenged by stakeholders.",
        "Describe a tradeoff you made between speed, accuracy, and explainability.",
    ],
    "behavioral": [
        "Tell me about a conflict you had with a teammate or manager and how you handled it.",
        "Describe a time you had to recover after a poor decision.",
        "Tell me about a time you had to influence without authority.",
    ],
}
INTERVIEW_STRESS_SCENARIOS = {
    "general": [
        "Ten minutes before a deadline, your manager asks you to cut scope by half. What do you do first?",
        "A teammate says your plan is too risky and the room turns against you. Defend or revise it.",
    ],
    "backend": [
        "Your service error rate spikes right after deployment and leadership wants an answer in five minutes. Walk me through your first moves.",
        "A critical API is timing out during peak traffic. What do you inspect first, and what do you communicate?",
    ],
    "frontend": [
        "A major release breaks on mobile devices one hour before launch. How do you triage and communicate?",
        "Design says do not cut scope, engineering says the page is too slow. What call do you make?",
    ],
    "data": [
        "Your model accuracy drops in production and stakeholders want a root cause before the end of the day. What do you do?",
        "Leadership wants you to present a metric trend that you do not fully trust. How do you handle that pressure?",
    ],
    "behavioral": [
        "A senior interviewer cuts you off and says your answer is too vague. Recover in 30 seconds.",
        "A stakeholder blames your team publicly for a missed target. How do you respond in the moment?",
    ],
}


def _interview_focus_key(value: str) -> str:
    normalized = _normalize_text(value or "")
    if normalized in INTERVIEW_FOCUS_PROMPTS:
        return normalized
    return "general"


def _interview_resume_context(resume_payload: dict, role: str = "") -> dict:
    extracted = resume_payload or {}
    raw_text = str(extracted.get("raw_text") or "")
    skills = extracted.get("skills") or _extract_skills(raw_text)
    skills = [str(skill).strip().lower() for skill in skills if str(skill).strip()][:8]

    projects = []
    for project in extracted.get("projects") or []:
        if isinstance(project, dict):
            name = str(project.get("name") or "").strip()
            if name:
                projects.append(name)
        elif str(project).strip():
            projects.append(str(project).strip())
    projects = projects[:4]

    experience_titles = []
    for item in extracted.get("experience") or []:
        if isinstance(item, dict):
            title = str(item.get("title") or item.get("company") or "").strip()
            if title:
                experience_titles.append(title)
        elif str(item).strip():
            experience_titles.append(str(item).strip())
    experience_titles = experience_titles[:4]

    role_terms = [token for token in _tokenize(role) if len(token) >= 3][:4]
    return {
        "name": str(extracted.get("name") or "Candidate").strip() or "Candidate",
        "skills": skills,
        "projects": projects,
        "experience_titles": experience_titles,
        "role_terms": role_terms,
    }


def _interview_primary_anchor(resume_context: dict) -> str:
    if resume_context.get("projects"):
        return resume_context["projects"][0]
    if resume_context.get("experience_titles"):
        return resume_context["experience_titles"][0]
    if resume_context.get("skills"):
        return ", ".join(resume_context["skills"][:2])
    return "your most relevant recent work"


def _interview_skill_terms(state: dict) -> set[str]:
    resume_context = state.get("resume_context") or {}
    role = str(state.get("role") or "")
    terms = set(resume_context.get("skills") or [])
    terms.update(resume_context.get("role_terms") or [])
    terms.update(token for token in _tokenize(role) if len(token) >= 3)
    return {term for term in terms if term}


def _interview_score_summary(score_history: list[dict]) -> dict:
    if not score_history:
        return {"confidence": 0, "clarity": 0, "depth": 0, "overall": 0}
    confidence = round(sum(item.get("confidence", 0) for item in score_history) / len(score_history))
    clarity = round(sum(item.get("clarity", 0) for item in score_history) / len(score_history))
    depth = round(sum(item.get("depth", 0) for item in score_history) / len(score_history))
    overall = round((confidence + clarity + depth) / 3)
    return {
        "confidence": confidence,
        "clarity": clarity,
        "depth": depth,
        "overall": overall,
    }


def _interview_pressure_event(state: dict, evaluation: dict) -> dict | None:
    if evaluation["word_count"] > 170 or evaluation["clarity"] < 55:
        return {
            "type": "interruption",
            "label": "Interruption",
            "message": "I am going to stop you there. Give me the 30-second version and lead with the impact.",
        }
    if evaluation["depth"] < 58:
        return {
            "type": "follow_up",
            "label": "Follow-Up",
            "message": "That is still high-level. What exactly did you own, what was the constraint, and what metric moved?",
        }
    if state.get("difficulty", 2) >= 4 or evaluation["overall"] >= 82:
        focus = _interview_focus_key(state.get("focus"))
        scenarios = INTERVIEW_STRESS_SCENARIOS.get(focus) or INTERVIEW_STRESS_SCENARIOS["general"]
        index = len(state.get("pressure_events") or []) % len(scenarios)
        return {
            "type": "stress",
            "label": "Stress Scenario",
            "message": scenarios[index],
        }
    return None


def _interview_adjust_difficulty(current_difficulty: int, evaluation: dict) -> int:
    difficulty = int(current_difficulty or 2)
    if evaluation["overall"] >= 75 and evaluation["confidence"] >= 68 and evaluation["depth"] >= 68:
        difficulty += 1
    elif evaluation["overall"] <= 48 or evaluation["clarity"] <= 45:
        difficulty -= 1
    return max(1, min(5, difficulty))


def _interview_evaluate_answer(state: dict, answer: str) -> dict:
    text = str(answer or "").strip()
    words = re.findall(r"[A-Za-z0-9+#.%'-]+", text)
    word_count = len(words)
    lower_text = text.lower()
    sentences = [part.strip() for part in re.split(r"[.!?\n]+", text) if part.strip()]
    sentence_count = len(sentences)
    avg_sentence_len = (word_count / sentence_count) if sentence_count else word_count
    filler_count = sum(lower_text.count(term) for term in INTERVIEW_FILLERS)
    hedge_count = sum(lower_text.count(term) for term in INTERVIEW_HEDGES)
    metric_hits = len(re.findall(r"\b\d+(?:\.\d+)?%?\b", text))
    action_hits = sum(1 for verb in ACTION_VERBS if verb in lower_text)
    structure_hits = sum(1 for term in INTERVIEW_STRUCTURE_TERMS if term in lower_text)
    depth_hits = sum(1 for term in INTERVIEW_DEPTH_TERMS if term in lower_text)
    skill_hits = sum(1 for term in _interview_skill_terms(state) if term and term in lower_text)
    pronoun_hits = lower_text.count(" i ") + lower_text.count(" i'") + (1 if lower_text.startswith("i ") else 0)

    confidence = 42
    confidence += min(word_count, 140) / 140 * 16
    confidence += min(action_hits, 5) * 4
    confidence += min(metric_hits, 3) * 4
    confidence += min(pronoun_hits, 4) * 2
    confidence -= min(hedge_count, 5) * 6
    confidence -= min(filler_count, 5) * 4
    if word_count < 30:
        confidence -= 12
    confidence = max(0, min(100, round(confidence)))

    clarity = 35
    if 2 <= sentence_count <= 6:
        clarity += 18
    elif sentence_count == 1:
        clarity += 6
    if 8 <= avg_sentence_len <= 26:
        clarity += 18
    elif avg_sentence_len < 6 or avg_sentence_len > 34:
        clarity -= 8
    clarity += min(structure_hits, 4) * 5
    clarity -= min(filler_count, 5) * 3
    if word_count < 25:
        clarity -= 12
    clarity = max(0, min(100, round(clarity)))

    depth = 28
    depth += min(metric_hits, 4) * 8
    depth += min(skill_hits, 5) * 5
    depth += min(depth_hits, 4) * 6
    if word_count >= 90:
        depth += 10
    elif word_count < 40:
        depth -= 12
    depth = max(0, min(100, round(depth)))

    strengths = []
    improvements = []
    if confidence >= 75:
        strengths.append("You sounded decisive and took ownership of your actions.")
    else:
        improvements.append("Lead with what you decided and cut hedging phrases.")
    if clarity >= 75:
        strengths.append("Your answer had a clear structure and was easy to follow.")
    else:
        improvements.append("Use a tighter structure such as situation, action, result.")
    if depth >= 75:
        strengths.append("You backed your answer with specifics, constraints, or measurable impact.")
    else:
        improvements.append("Add metrics, constraints, tradeoffs, and the outcome you drove.")

    overall = round((confidence + clarity + depth) / 3)
    return {
        "confidence": confidence,
        "clarity": clarity,
        "depth": depth,
        "overall": overall,
        "word_count": word_count,
        "sentence_count": sentence_count,
        "strengths": strengths[:3],
        "improvements": improvements[:3],
        "coaching_note": "Use crisp, specific answers with ownership and measurable impact." if overall < 70 else "Maintain this structure under pressure and keep anchoring on impact.",
    }

def _interview_standard_prompt(state: dict) -> str:
    focus = _interview_focus_key(state.get("focus"))
    prompts = INTERVIEW_FOCUS_PROMPTS.get(focus) or INTERVIEW_FOCUS_PROMPTS["general"]
    round_number = int(state.get("current_round") or 1)
    role = str(state.get("role") or "the role").strip() or "the role"
    company = str(state.get("company") or "").strip()
    anchor = _interview_primary_anchor(state.get("resume_context") or {})

    if round_number == 1:
        if company:
            return f"You are interviewing for {role} at {company}. Start with {anchor}. What problem were you solving, what did you own, and what changed because of your work?"
        return f"Start with {anchor}. What problem were you solving, what did you personally own, and what changed because of your work?"

    if round_number == 2:
        return prompts[1 % len(prompts)]
    if round_number == 3:
        return prompts[2 % len(prompts)]
    if round_number == 4:
        return "Tell me about a time your first approach was wrong. How did you realize it, and how did you recover?"
    if round_number == 5:
        return "You have two conflicting priorities, incomplete data, and a hard deadline. What framework do you use to make the call?"
    return "Final question. What would a strong interviewer still doubt about your fit for this role, and how would you address it directly?"


def _interview_next_prompt(state: dict, evaluation: dict, pressure_event: dict | None) -> tuple[str, str]:
    if pressure_event:
        if pressure_event["type"] == "interruption":
            return pressure_event["message"], "interruption"
        if pressure_event["type"] == "follow_up":
            return pressure_event["message"], "follow_up"
        return pressure_event["message"], "stress"

    return _interview_standard_prompt(state), "standard"


def _interview_final_summary(state: dict) -> dict:
    score_summary = _interview_score_summary(state.get("score_history") or [])
    dimensions = {
        "confidence": score_summary["confidence"],
        "clarity": score_summary["clarity"],
        "depth": score_summary["depth"],
    }
    strongest = max(dimensions, key=dimensions.get)
    weakest = min(dimensions, key=dimensions.get)

    recommendations = []
    if score_summary["confidence"] < 70:
        recommendations.append("Lead with a decision, not a disclaimer. Cut hedging and filler words.")
    if score_summary["clarity"] < 70:
        recommendations.append("Use a repeatable structure: context, action, tradeoff, result.")
    if score_summary["depth"] < 70:
        recommendations.append("Add metrics, constraints, tradeoffs, and what you personally owned.")
    if len(state.get("pressure_events") or []) >= 2:
        recommendations.append("Practice answering the same story in both a short and long version so interruptions do not break your flow.")
    if not recommendations:
        recommendations.append("You handled pressure well. Push further by sharpening your numbers and tradeoff language.")

    verdict = "Strong pressure handling" if score_summary["overall"] >= 78 else "Needs more pressure reps" if score_summary["overall"] < 60 else "Solid baseline with room to tighten delivery"
    return {
        "overall": score_summary["overall"],
        "confidence": score_summary["confidence"],
        "clarity": score_summary["clarity"],
        "depth": score_summary["depth"],
        "strongest_dimension": strongest,
        "weakest_dimension": weakest,
        "pressure_events_triggered": len(state.get("pressure_events") or []),
        "verdict": verdict,
        "recommendations": recommendations[:5],
    }


def _interview_response_payload(state: dict, extra: dict | None = None) -> dict:
    payload = {
        "status": state.get("status", "idle"),
        "question": state.get("current_question", ""),
        "question_mode": state.get("current_question_mode", "standard"),
        "difficulty": state.get("difficulty", 2),
        "difficulty_label": INTERVIEW_DIFFICULTY_LABELS.get(state.get("difficulty", 2), "Baseline"),
        "progress": {
            "current": state.get("current_round", 0),
            "total": state.get("total_rounds", 0),
        },
        "score_summary": _interview_score_summary(state.get("score_history") or []),
        "transcript": state.get("turns", []),
        "resume_context": state.get("resume_context", {}),
    }
    if extra:
        payload.update(extra)
    if state.get("status") == "completed":
        payload["final_summary"] = _interview_final_summary(state)
    return payload


def start_interview_simulator(resume_payload: dict, role: str, company: str = "", focus: str = "general", total_rounds: int = 6) -> tuple[dict, dict]:
    clean_role = str(role or "").strip() or "Software Engineer"
    clean_company = str(company or "").strip()
    rounds = max(4, min(int(total_rounds or 6), 8))
    state = {
        "status": "active",
        "role": clean_role,
        "company": clean_company,
        "focus": _interview_focus_key(focus),
        "difficulty": 2,
        "current_round": 1,
        "total_rounds": rounds,
        "resume_context": _interview_resume_context(resume_payload or {}, clean_role),
        "current_question": "",
        "current_question_mode": "opening",
        "score_history": [],
        "turns": [],
        "pressure_events": [],
    }
    state["current_question"] = _interview_standard_prompt(state)
    return state, _interview_response_payload(state)


def advance_interview_simulator(state: dict, answer: str) -> tuple[dict, dict]:
    if not state or state.get("status") != "active":
        raise ValueError("Interview session is not active.")

    clean_answer = str(answer or "").strip()
    if not clean_answer:
        raise ValueError("answer is required")

    evaluation = _interview_evaluate_answer(state, clean_answer)
    state.setdefault("score_history", []).append({
        "confidence": evaluation["confidence"],
        "clarity": evaluation["clarity"],
        "depth": evaluation["depth"],
        "overall": evaluation["overall"],
    })

    prior_difficulty = state.get("difficulty", 2)
    next_difficulty = _interview_adjust_difficulty(prior_difficulty, evaluation)
    pressure_event = _interview_pressure_event({**state, "difficulty": next_difficulty}, evaluation)
    if pressure_event:
        state.setdefault("pressure_events", []).append(pressure_event)

    state.setdefault("turns", []).append({
        "round": state.get("current_round", 1),
        "question": state.get("current_question", ""),
        "question_mode": state.get("current_question_mode", "standard"),
        "answer": clean_answer,
        "scores": {
            "confidence": evaluation["confidence"],
            "clarity": evaluation["clarity"],
            "depth": evaluation["depth"],
            "overall": evaluation["overall"],
        },
        "strengths": evaluation["strengths"],
        "improvements": evaluation["improvements"],
    })

    state["difficulty"] = next_difficulty

    if state.get("current_round", 1) >= state.get("total_rounds", 6):
        state["status"] = "completed"
        state["current_question"] = ""
        state["current_question_mode"] = "complete"
        return state, _interview_response_payload(
            state,
            {
                "evaluation": evaluation,
                "pressure_event": pressure_event,
            },
        )

    state["current_round"] = int(state.get("current_round", 1)) + 1
    next_question, next_mode = _interview_next_prompt(state, evaluation, pressure_event)
    state["current_question"] = next_question
    state["current_question_mode"] = next_mode

    return state, _interview_response_payload(
        state,
        {
            "evaluation": {
                **evaluation,
                "difficulty_before": prior_difficulty,
                "difficulty_after": next_difficulty,
            },
            "pressure_event": pressure_event,
        },
    )
from .interview_engine import (
    INTERVIEW_SIMULATOR_SESSION_KEY,
    INTERVIEW_MIN_QUESTION_COUNT,
    INTERVIEW_MAX_QUESTION_COUNT,
    INTERVIEW_DIFFICULTY_LABELS,
    start_interview_simulator,
    advance_interview_simulator,
)
