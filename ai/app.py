import os
import re
import math
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from flask import Flask, request, jsonify
from dotenv import load_dotenv

import pdfplumber
import docx

load_dotenv()

app = Flask(__name__)

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
    "automated", "engineered", "analyzed", "deployed", "reduced", "increased"
}
DEGREE_KEYWORDS = {
    "bachelor", "master", "phd", "b.s", "b.sc", "m.s", "mba", "b.tech", "m.tech",
    "degree", "engineering", "computer science", "information technology"
}
CERTIFICATION_KEYWORDS = {
    "certification", "certified", "certificate", "aws certified", "google cloud",
    "azure", "pmp", "scrum master", "coursera", "udemy"
}
EXPERIENCE_HINT_WORDS = {
    "experience", "engineer", "developer", "intern", "manager", "analyst",
    "worked", "project", "employment"
}
JOB_KEYWORD_STOPWORDS = {
    "looking", "candidate", "candidates", "required", "requirements", "must",
    "should", "ability", "strong", "excellent", "knowledge", "team", "work",
    "role", "position", "job", "responsible", "responsibilities", "experience",
    "year", "years", "plus", "using", "build", "develop", "maintain", "good"
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


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9+.#\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text: str) -> List[str]:
    tokens = normalize_text(text).split()
    return [token for token in tokens if token and token not in STOPWORDS]


def extract_text(file_path: str, file_type: str) -> str:
    if file_type == "pdf":
        with pdfplumber.open(file_path) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n".join(pages)
    if file_type == "docx":
        doc = docx.Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)
    raise ValueError("Unsupported file type. Use pdf or docx.")


def extract_email(text: str) -> str:
    match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return match.group(0) if match else ""


def extract_phone(text: str) -> str:
    match = re.search(r"(\+?\d[\d\s().-]{7,}\d)", text)
    return match.group(0) if match else ""


def extract_name(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    for line in lines[:5]:
        if "@" in line or re.search(r"\d", line):
            continue
        if len(line.split()) <= 6:
            return line.split("|")[0].strip()
    return lines[0].split("|")[0].strip()


def extract_skills(text: str) -> List[str]:
    normalized = normalize_text(text)
    found = set()
    for skill in SKILLS_DICTIONARY:
        if _contains_exact_phrase(normalized, skill):
            found.add(skill.lower())
    return sorted(found)


def extract_education(text: str) -> List[Dict[str, str]]:
    education = []
    for line in text.splitlines():
        lower = line.lower()
        if any(k in lower for k in DEGREE_KEYWORDS):
            year_match = re.search(r"(19|20)\d{2}", line)
            education.append({
                "degree": line.strip(),
                "institute": "",
                "year": year_match.group(0) if year_match else ""
            })
    return education[:5]


def extract_experience(text: str) -> List[Dict[str, str]]:
    experience = []
    for line in text.splitlines():
        lower = line.lower()
        if any(k in lower for k in EXPERIENCE_HINT_WORDS):
            year_match = re.search(r"(19|20)\d{2}", line)
            experience.append({
                "title": line.strip(),
                "company": "",
                "years": year_match.group(0) if year_match else "",
                "details": ""
            })
    return experience[:6]


def extract_projects(text: str) -> List[Dict[str, str]]:
    projects = []
    for line in text.splitlines():
        if "project" in line.lower():
            projects.append({
                "name": line.strip(),
                "details": "",
                "tech": []
            })
    return projects[:5]


def compute_similarity(resume_text: str, job_text: str) -> float:
    if not resume_text.strip() or not job_text.strip():
        return 0.0
    docs = [tokenize(resume_text), tokenize(job_text)]
    vocab = sorted(set(docs[0]).union(docs[1]))
    if not vocab:
        return 0.0

    def tf(tokens: List[str]) -> Dict[str, float]:
        counts = {}
        total = max(len(tokens), 1)
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        return {token: counts.get(token, 0) / total for token in vocab}

    def idf() -> Dict[str, float]:
        values = {}
        for token in vocab:
            df = sum(1 for doc in docs if token in doc)
            values[token] = math.log((len(docs) + 1) / (df + 1)) + 1
        return values

    tfidf_1 = []
    tfidf_2 = []
    idf_values = idf()
    tf1 = tf(docs[0])
    tf2 = tf(docs[1])
    for token in vocab:
        tfidf_1.append(tf1[token] * idf_values[token])
        tfidf_2.append(tf2[token] * idf_values[token])

    dot = sum(a * b for a, b in zip(tfidf_1, tfidf_2))
    norm1 = math.sqrt(sum(a * a for a in tfidf_1))
    norm2 = math.sqrt(sum(b * b for b in tfidf_2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return float(dot / (norm1 * norm2))


def _contains_exact_phrase(normalized_text: str, phrase: str) -> bool:
    phrase_norm = normalize_text(str(phrase or ""))
    if not phrase_norm:
        return False
    pattern = rf"(?<![{WORD_CHARS_CLASS}]){re.escape(phrase_norm)}(?![{WORD_CHARS_CLASS}])"
    return re.search(pattern, normalized_text) is not None


def _clean_skill_values(raw_skills: List[str]) -> List[str]:
    cleaned = []
    for skill in raw_skills or []:
        value = normalize_text(str(skill or ""))
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


def _extract_job_keywords(job: Dict, normalized_job_text: str, target_skills: Set[str]) -> List[str]:
    title = job.get("title", "")
    description = job.get("description", "")
    title_tokens = {
        token for token in tokenize(title)
        if len(token) >= 3 and token not in JOB_KEYWORD_STOPWORDS
    }
    description_tokens = [
        token for token in tokenize(description)
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


def _score_keywords_match(
    normalized_resume: str,
    job_keywords: List[str],
    missing_skills: List[str],
) -> Tuple[int, Dict, List[str]]:
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


def _score_skills_relevance(
    normalized_resume: str,
    resume_skills: Set[str],
    target_job_skills: Set[str],
) -> Tuple[int, Dict, List[str]]:
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


def _score_experience_match(
    resume_text: str,
    lower_lines: List[str],
    target_terms: Set[str],
) -> Tuple[int, Dict, List[str]]:
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


def _score_education_and_certifications(
    lower_lines: List[str],
    target_terms: Set[str],
) -> Tuple[int, Dict, List[str]]:
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


def _score_resume_format(
    resume_text: str,
    lower_lines: List[str],
    resume_metadata: Optional[Dict],
) -> Tuple[int, Dict, List[str]]:
    metadata = resume_metadata or {}
    file_type = str(metadata.get("file_type", "")).strip().lower().lstrip(".")

    score = 30
    mistakes = []

    if file_type in {"pdf", "docx"}:
        score += 25
    elif file_type:
        mistakes.append("Resume file format should be PDF or DOCX.")
    else:
        # Unknown format in remote match calls; keep neutral scoring.
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
    name = extract_name(resume_text)
    email = extract_email(resume_text)
    phone = extract_phone(resume_text)
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
    achievement_lines = [
        line for line in numeric_lines
        if action_pattern.search(line)
    ]

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
        mistakes.append(
            "Add quantifiable achievements with numbers, for example: improved accuracy by 35%."
        )

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


def build_match_response(resume_text: str, job: Dict, resume_metadata: Optional[Dict] = None) -> Dict:
    normalized_resume = normalize_text(resume_text)
    normalized_job_text = normalize_text(
        f"{job.get('title', '')} {job.get('description', '')} {' '.join(job.get('required_skills') or [])}"
    )

    required_job_skills, target_job_skills = _extract_job_skill_sets(job, normalized_job_text)
    skills_for_output = required_job_skills or target_job_skills

    matched_skills = sorted(skill for skill in skills_for_output if _contains_exact_phrase(normalized_resume, skill))
    missing_skills = sorted(skill for skill in skills_for_output if skill not in matched_skills)

    job_keywords = _extract_job_keywords(job, normalized_job_text, target_job_skills)
    resume_skills = set(extract_skills(resume_text))
    lower_lines = [line.strip().lower() for line in resume_text.splitlines() if line.strip()]
    role_terms = {
        token for token in tokenize(job.get("title", ""))
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


def build_skill_gap_response(resume_text: str, job: Dict) -> Dict:
    normalized_resume = normalize_text(resume_text)
    normalized_job_text = normalize_text(
        f"{job.get('title', '')} {job.get('description', '')} {' '.join(job.get('required_skills') or [])}"
    )

    required_skills, target_skills = _extract_job_skill_sets(job, normalized_job_text)
    skills_for_gap = required_skills or target_skills
    matched = sorted(skill for skill in skills_for_gap if _contains_exact_phrase(normalized_resume, skill))
    missing = sorted(skill for skill in skills_for_gap if skill not in matched)

    suggestions = []
    for skill in missing[:5]:
        suggestions.append(f"Build a small project or certification using {skill}.")
    if not suggestions:
        suggestions.append("Your resume already aligns well with the target role.")

    return {
        "matched_skills": matched,
        "missing_skills": missing,
        "suggestions": suggestions
    }


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/parse_resume", methods=["POST"])
def parse_resume():
    payload = request.get_json(silent=True) or {}
    file_path = payload.get("file_path")
    file_type = payload.get("file_type")

    if not file_path or not file_type:
        return jsonify({"error": "file_path and file_type are required"}), 400

    try:
        raw_text = extract_text(file_path, file_type.lower())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({
        "raw_text": raw_text,
        "name": extract_name(raw_text),
        "email": extract_email(raw_text),
        "phone": extract_phone(raw_text),
        "skills": extract_skills(raw_text),
        "education": extract_education(raw_text),
        "experience": extract_experience(raw_text),
        "projects": extract_projects(raw_text)
    })


@app.route("/match", methods=["POST"])
def match():
    payload = request.get_json(silent=True) or {}
    resume_text = payload.get("resume_text", "")
    job = payload.get("job") or {}
    resume_metadata = payload.get("resume_metadata") or {}

    if not resume_text or not job:
        return jsonify({"error": "resume_text and job are required"}), 400

    result = build_match_response(resume_text, job, resume_metadata=resume_metadata)
    return jsonify(result)


@app.route("/recommend_jobs", methods=["POST"])
def recommend_jobs():
    payload = request.get_json(silent=True) or {}
    resume_text = payload.get("resume_text", "")
    jobs = payload.get("jobs") or []
    top_n = int(payload.get("top_n", 10))

    if not resume_text or not jobs:
        return jsonify({"error": "resume_text and jobs are required"}), 400

    recommendations = []
    for job in jobs:
        result = build_match_response(resume_text, job)
        if not result["matched_skills"]:
            continue

        job_id = job.get("id") or job.get("job_id")
        reason = "Matched skills: " + ", ".join(result["matched_skills"][:5])
        recommendations.append({
            "job_id": job_id,
            "score": result["score"],
            "reason": reason
        })

    recommendations.sort(key=lambda x: x["score"], reverse=True)
    return jsonify({"recommendations": recommendations[:top_n]})


@app.route("/skill_gap", methods=["POST"])
def skill_gap():
    payload = request.get_json(silent=True) or {}
    resume_text = payload.get("resume_text", "")
    job = payload.get("job") or {}

    if not resume_text or not job:
        return jsonify({"error": "resume_text and job are required"}), 400

    result = build_skill_gap_response(resume_text, job)
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
