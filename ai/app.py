import os
import re
from typing import List, Dict

from flask import Flask, request, jsonify
from dotenv import load_dotenv

import math

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

STOPWORDS = set([
    "a", "an", "the", "and", "or", "for", "to", "in", "on", "of", "with",
    "by", "is", "are", "was", "were", "be", "as", "at", "from", "that",
    "this", "it", "its", "their", "them", "we", "our", "you", "your"
])


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
        pattern = re.escape(skill.lower())
        if re.search(rf"\b{pattern}\b", normalized):
            found.add(skill.lower())
    return sorted(found)


def extract_education(text: str) -> List[Dict[str, str]]:
    education = []
    keywords = ["bachelor", "master", "phd", "b.s", "b.sc", "m.s", "mba", "b.tech", "m.tech", "degree"]
    for line in text.splitlines():
        lower = line.lower()
        if any(k in lower for k in keywords):
            year_match = re.search(r"(19|20)\d{2}", line)
            education.append({
                "degree": line.strip(),
                "institute": "",
                "year": year_match.group(0) if year_match else ""
            })
    return education[:5]


def extract_experience(text: str) -> List[Dict[str, str]]:
    experience = []
    keywords = ["experience", "engineer", "developer", "intern", "manager", "analyst"]
    for line in text.splitlines():
        lower = line.lower()
        if any(k in lower for k in keywords):
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


def build_match_response(resume_text: str, job: Dict) -> Dict:
    job_required = [s.lower() for s in job.get("required_skills", [])]
    resume_skills = set(extract_skills(resume_text))
    job_skills = set(job_required)

    matched = sorted(resume_skills.intersection(job_skills))
    missing = sorted(job_skills.difference(resume_skills))

    job_text = f"{job.get('title', '')} {job.get('description', '')} {' '.join(job_required)}"
    score = int(round(compute_similarity(resume_text, job_text) * 100))

    summary = f"Match score {score}. {len(matched)} skill(s) matched."
    tips = []
    for skill in missing[:5]:
        tips.append(f"Consider adding experience with {skill}.")
    if not tips:
        tips.append("Your resume already covers most required skills.")

    return {
        "score": max(0, min(score, 100)),
        "matched_skills": matched,
        "missing_skills": missing,
        "summary": summary,
        "improvement_tips": tips
    }


def build_skill_gap_response(resume_text: str, job: Dict) -> Dict:
    job_required = [s.lower() for s in job.get("required_skills", [])]
    resume_skills = set(extract_skills(resume_text))
    job_skills = set(job_required)

    matched = sorted(resume_skills.intersection(job_skills))
    missing = sorted(job_skills.difference(resume_skills))

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

    if not resume_text or not job:
        return jsonify({"error": "resume_text and job are required"}), 400

    result = build_match_response(resume_text, job)
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
