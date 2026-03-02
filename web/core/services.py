import logging
import math
import re
from typing import Dict, List, Optional, Set, Tuple
from collections import Counter
from datetime import datetime

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


def fetch_jobs_auto(query: str = "developer", location: str = "India", limit: int = 50) -> tuple[list, str]:
    """
    Fetch jobs with source fallback order:
    JSearch -> The Muse -> Remotive

    Returns:
        (jobs, source_name)
    """
    try:
        return fetch_jsearch_jobs(query=query, location=location, limit=limit), "jsearch"
    except AIServiceError as jsearch_exc:
        logger.warning("JSearch unavailable (%s). Falling back to The Muse.", jsearch_exc)
        try:
            return fetch_muse_jobs(query=query, location=location, limit=limit), "themuse"
        except AIServiceError as muse_exc:
            logger.warning("The Muse unavailable (%s). Falling back to Remotive.", muse_exc)
            return fetch_remotive_jobs(limit=limit), "remotive"
