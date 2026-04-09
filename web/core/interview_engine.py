import re
from collections import Counter

INTERVIEW_SIMULATOR_SESSION_KEY = "interview_simulator_state"
INTERVIEW_MIN_QUESTION_COUNT = 50
INTERVIEW_MAX_QUESTION_COUNT = 100
INTERVIEW_DIFFICULTY_LABELS = {1: "Warm-up", 2: "Baseline", 3: "Pressure", 4: "Stress Test", 5: "Panel Heat"}
INTERVIEW_INPUT_KIND_LABELS = {"text": "Typing", "radio": "Radio", "checkbox": "Checkbox"}
INTERVIEW_HEDGES = {"maybe", "probably", "i think", "i guess", "kind of", "sort of", "i am not sure", "perhaps"}
INTERVIEW_FILLERS = {"um", "uh", "like", "you know", "actually", "basically", "literally"}
INTERVIEW_STRUCTURE_TERMS = {"first", "second", "third", "then", "finally", "because", "so that", "result", "impact"}
INTERVIEW_DEPTH_TERMS = {
    "tradeoff", "constraint", "latency", "scale", "rollback", "root cause", "metric", "customer",
    "experiment", "ownership", "stakeholder", "failure", "incident", "decision", "priority",
}
ACTION_VERBS = {
    "developed", "built", "implemented", "designed", "optimized", "improved", "delivered", "created",
    "led", "managed", "architected", "launched", "automated", "engineered", "analyzed", "deployed",
    "reduced", "increased",
}
INTERVIEW_SKILL_HINTS = [
    "python", "sql", "django", "flask", "javascript", "html", "css", "react", "node", "api", "docker",
    "kubernetes", "aws", "azure", "gcp", "postgres", "mongodb", "pandas", "machine learning", "analytics",
]
INTERVIEW_ROLE_PROFILES = {
    "general": {
        "domain_label": "product engineering",
        "artifact_terms": ["delivery plan", "customer issue", "feature release", "handoff", "project plan", "support escalation"],
        "constraint_terms": ["timeline pressure", "unclear requirements", "scope churn", "quality risk", "cross-team dependency", "conflicting priorities"],
        "metric_terms": ["delivery time", "quality", "customer impact", "reliability", "adoption", "execution confidence"],
        "stakeholder_terms": ["manager", "product lead", "QA lead", "teammate", "customer support", "cross-functional partner"],
        "decision_terms": ["scope cut", "rollback plan", "ownership split", "communication plan", "priority call", "validation plan"],
        "tool_terms": ["checklist", "written update", "dashboard", "debugging notes", "decision log", "runbook"],
        "quality_terms": ["speed", "quality", "reliability", "clarity", "scope", "maintainability"],
        "skill_terms": ["delivery", "communication", "ownership", "execution", "problem solving", "collaboration"],
    },
    "backend": {
        "domain_label": "backend systems",
        "artifact_terms": ["API layer", "database migration", "queue worker", "authentication service", "caching layer", "background job"],
        "constraint_terms": ["latency spike", "error budget", "schema risk", "traffic burst", "backward compatibility", "on-call pressure"],
        "metric_terms": ["latency", "error rate", "throughput", "availability", "p95 response time", "rollback safety"],
        "stakeholder_terms": ["SRE", "platform lead", "product manager", "support engineer", "on-call teammate", "engineering manager"],
        "decision_terms": ["rollback", "query tuning", "rate limiting", "retry policy", "instrumentation", "caching strategy"],
        "tool_terms": ["logs", "dashboards", "runbook", "query plan", "alerts", "trace data"],
        "quality_terms": ["latency", "reliability", "maintainability", "throughput", "resilience", "correctness"],
        "skill_terms": ["python", "django", "sql", "api", "database", "caching"],
    },
    "frontend": {
        "domain_label": "frontend systems",
        "artifact_terms": ["checkout flow", "dashboard page", "design system component", "mobile layout", "client-side state", "bundle pipeline"],
        "constraint_terms": ["load time", "accessibility gap", "browser regression", "launch deadline", "design churn", "render bottleneck"],
        "metric_terms": ["Core Web Vitals", "conversion", "engagement", "error rate", "render time", "task completion rate"],
        "stakeholder_terms": ["designer", "product manager", "QA lead", "frontend lead", "mobile user", "support teammate"],
        "decision_terms": ["progressive enhancement", "code splitting", "feature flag", "fallback UI", "instrumentation", "scope cut"],
        "tool_terms": ["session replay", "performance profile", "component tests", "feature flags", "analytics", "error tracker"],
        "quality_terms": ["usability", "performance", "accessibility", "consistency", "delivery speed", "stability"],
        "skill_terms": ["javascript", "react", "css", "html", "accessibility", "performance"],
    },
    "data": {
        "domain_label": "data and ML systems",
        "artifact_terms": ["model pipeline", "forecasting workflow", "training job", "dashboard metric", "ETL pipeline", "feature store"],
        "constraint_terms": ["data drift", "low data quality", "stakeholder pressure", "model latency", "explainability", "deadline pressure"],
        "metric_terms": ["precision", "recall", "lift", "latency", "coverage", "forecast accuracy"],
        "stakeholder_terms": ["analyst", "data science lead", "business stakeholder", "ML engineer", "product manager", "operations partner"],
        "decision_terms": ["threshold tuning", "feature engineering", "backfill", "retraining", "guardrail metric", "validation plan"],
        "tool_terms": ["experiment tracker", "notebook", "validation report", "dataset audit", "monitoring alerts", "feature dashboard"],
        "quality_terms": ["accuracy", "explainability", "speed", "coverage", "trust", "robustness"],
        "skill_terms": ["python", "sql", "pandas", "machine learning", "analytics", "experimentation"],
    },
    "behavioral": {
        "domain_label": "team execution",
        "artifact_terms": ["team project", "cross-functional plan", "incident review", "delivery commitment", "stakeholder update", "roadmap change"],
        "constraint_terms": ["conflict", "missed deadline", "unclear ownership", "priority change", "public criticism", "resource gap"],
        "metric_terms": ["trust", "alignment", "delivery confidence", "team velocity", "customer impact", "stakeholder confidence"],
        "stakeholder_terms": ["manager", "peer", "stakeholder", "director", "client", "partner team"],
        "decision_terms": ["escalation", "reset", "clarification", "feedback loop", "ownership plan", "tradeoff"],
        "tool_terms": ["agenda", "written update", "retro notes", "decision log", "action plan", "follow-up document"],
        "quality_terms": ["trust", "clarity", "speed", "alignment", "ownership", "follow-through"],
        "skill_terms": ["communication", "leadership", "ownership", "feedback", "stakeholder management", "prioritization"],
    },
}
INTERVIEW_STRESS_SCENARIOS = {
    "general": [
        "Ten minutes before a deadline, your manager asks you to cut scope by half. What do you do first?",
        "A teammate says your plan is too risky and the room turns against you. Defend or revise it.",
        "Your project is going over budget and timeline. Walk me through your next steps.",
        "A critical stakeholder is unhappy with your decision. How do you handle the feedback?",
        "You discover a major assumption in your plan was wrong. What do you do?",
    ],
    "backend": [
        "Your service error rate spikes right after deployment and leadership wants an answer in five minutes. Walk me through your first moves.",
        "A critical API is timing out during peak traffic. What do you inspect first, and what do you communicate?",
        "A database migration failed and you cannot easily rollback. How do you recover?",
        "Your caching strategy is causing more problems than it solves. What's your decision?",
        "Load testing reveals your architecture will not scale to next quarter's targets. What now?",
    ],
    "frontend": [
        "A major release breaks on mobile devices one hour before launch. How do you triage and communicate?",
        "Design says do not cut scope, engineering says the page is too slow. What call do you make?",
        "Users are complaining about a feature you shipped last week. What's your response?",
        "Browser compatibility issues surface during QA. You cannot fix all of them by launch. What do you do?",
        "A performance optimization you made actually broke user workflows. How do you handle this?",
    ],
    "data": [
        "Your model accuracy drops in production and stakeholders want a root cause before the end of the day. What do you do?",
        "Leadership wants you to present a metric trend that you do not fully trust. How do you handle that pressure?",
        "Your training data is biased but fixing it will delay the project. What's your approach?",
        "An experiment you ran shows results that contradict your hypothesis. How do you proceed?",
        "Stakeholders want to use your model for high-stakes decisions but you have concerns. What do you say?",
    ],
    "behavioral": [
        "A senior interviewer cuts you off and says your answer is too vague. Recover in 30 seconds.",
        "A stakeholder blames your team publicly for a missed target. How do you respond in the moment?",
        "You disagree strongly with your manager on a key decision. How do you handle it?",
        "A peer takes credit for work you did. How do you address this professionally?",
        "Two senior leaders have conflicting opinions on your project direction. What do you do?",
    ],
}
INTERVIEW_TEXT_SPECS = [
    {"mode": "opening", "difficulty": 2, "instructions": "Type a short answer with context, action, tradeoff, and result.", "prompt": "You are interviewing for {role}{company_suffix}. Start with {anchor}. What problem were you solving, what did you own, and what changed because of your work?"},
    {"mode": "constraint", "difficulty": 2, "instructions": "Explain the constraint first, then the action you took.", "prompt": "In {artifact}, what was the hardest constraint around {constraint}, and how did you adjust your plan?"},
    {"mode": "metrics", "difficulty": 2, "instructions": "Anchor your answer on the metric that proved the work mattered.", "prompt": "When you worked on {artifact}, which {metric} told you whether the work was succeeding, and how did you improve it?"},
    {"mode": "tradeoff", "difficulty": 3, "instructions": "Explain what you optimized for and what you were willing to give up.", "prompt": "Describe a tradeoff you made between {quality} and {metric} while working on {artifact}. What did you choose and why?"},
    {"mode": "stakeholder", "difficulty": 3, "instructions": "Show how you handled pressure from another person, not just the technical work.", "prompt": "Tell me about a time a {stakeholder} pushed you toward a decision you did not agree with. How did you respond?"},
    {"mode": "prioritization", "difficulty": 3, "instructions": "Describe the framework you used to make the priority call.", "prompt": "You had limited time, a {constraint}, and open work in {artifact}. How did you prioritize what happened first?"},
    {"mode": "redesign", "difficulty": 4, "instructions": "Be explicit about what you would redesign and why your new decision is stronger.", "prompt": "If you could revisit {artifact} today, what would you redesign, and what {decision} would you make differently?"},
    {"mode": "recovery", "difficulty": 4, "instructions": "Show how you recovered after a miss and what changed afterward.", "prompt": "Tell me about a failure, miss, or near miss connected to {artifact}. How did you recover and what changed afterward?"},
    {"mode": "learning", "difficulty": 2, "instructions": "Describe what you learned from a specific project or experience.", "prompt": "What was the most important thing you learned from working on {artifact}, and how has it changed your approach?"},
    {"mode": "technical_depth", "difficulty": 3, "instructions": "Dive deep into the technical aspects of your work.", "prompt": "Walk me through the {skill} choices you made in {artifact}. What alternatives did you consider?"},
    {"mode": "collaboration", "difficulty": 3, "instructions": "Show how you worked with others to achieve the goal.", "prompt": "In {artifact}, how did you coordinate with {stakeholder} to deliver on {metric}?"},
    {"mode": "impact", "difficulty": 3, "instructions": "Quantify and explain the business or user impact.", "prompt": "What measurable impact did {artifact} have on {metric}? Talk about the before and after."},
    {"mode": "challenges", "difficulty": 4, "instructions": "Be honest about obstacles and how you overcame them.", "prompt": "What was the biggest technical challenge in {artifact}, and what did you do to solve it?"},
    {"mode": "iteration", "difficulty": 4, "instructions": "Explain how you improved based on feedback and results.", "prompt": "After launching {artifact}, what feedback did you receive, and what iterations did you make based on it?"},
    {"mode": "scaling", "difficulty": 4, "instructions": "Describe how you handled growth or increased demands.", "prompt": "As {artifact} grew or demands increased, what scaling challenges did you face, and how did you address {metric}?"},
]
INTERVIEW_RADIO_SPECS = [
    {"mode": "triage", "difficulty": 2, "instructions": "Pick the strongest first move under pressure.", "prompt": "The {artifact} shows a sudden {constraint}. What is the best first response?", "options": [{"label": "Stabilize impact, inspect {tool}, and communicate what is confirmed so far.", "score": 92, "feedback": "Strong triage. You reduced risk before guessing."}, {"label": "State a root cause immediately so stakeholders stop asking questions.", "score": 36, "feedback": "Confidence without evidence creates more risk."}, {"label": "Wait for the next scheduled check-in before investigating.", "score": 18, "feedback": "This delays containment and communication."}, {"label": "Push several changes at once so something probably works.", "score": 10, "feedback": "Changing multiple variables makes recovery harder."}]},
    {"mode": "deadline", "difficulty": 2, "instructions": "Pick the response that protects delivery without hiding risk.", "prompt": "A {stakeholder} wants you to skip validation so {artifact} ships faster. What do you do?", "options": [{"label": "Explain the specific risk, propose the smallest safe scope, and keep the validation that protects {metric}.", "score": 90, "feedback": "Good balance of delivery speed and control."}, {"label": "Agree immediately because speed matters more than validation.", "score": 20, "feedback": "This optimizes for speed while exposing preventable risk."}, {"label": "Refuse without offering an alternative path.", "score": 42, "feedback": "You protected quality, but you did not help solve the delivery problem."}, {"label": "Delay the conversation and hope the deadline moves.", "score": 12, "feedback": "Avoiding the decision usually makes the deadline worse."}]},
    {"mode": "ambiguity", "difficulty": 3, "instructions": "Choose the response that creates signal before a big decision.", "prompt": "You have conflicting signals on {artifact}, and nobody agrees which decision is right. What is your next move?", "options": [{"label": "Define the decision, collect the smallest evidence set, and time-box a follow-up with the {stakeholder}.", "score": 88, "feedback": "Good. You reduced ambiguity before committing."}, {"label": "Let the loudest person decide so the team can move on.", "score": 18, "feedback": "Speed without evidence weakens the decision."}, {"label": "Keep debating until everyone feels comfortable.", "score": 26, "feedback": "Endless debate burns time without improving signal."}, {"label": "Pick an option randomly and fix it later.", "score": 8, "feedback": "This removes discipline from the decision process."}]},
    {"mode": "quality", "difficulty": 3, "instructions": "Pick the response that protects quality while staying pragmatic.", "prompt": "A regression appears in {artifact}, but the deadline is fixed. Which action is strongest?", "options": [{"label": "Contain the regression, reduce scope if needed, and explain the impact on {metric} before shipping.", "score": 91, "feedback": "Strong. You protected users and made the tradeoff explicit."}, {"label": "Ship anyway and wait to see whether users complain.", "score": 14, "feedback": "This treats production as the testing environment."}, {"label": "Blame another team and ask them to decide.", "score": 9, "feedback": "That avoids ownership."}, {"label": "Cancel the entire release without evaluating blast radius.", "score": 44, "feedback": "You reacted to risk, but without proportional judgment."}]},
    {"mode": "communication", "difficulty": 3, "instructions": "Choose the answer that keeps stakeholders aligned without overpromising.", "prompt": "Leadership wants an update on {artifact}, but you still do not know the root cause. What is the best response?", "options": [{"label": "Share what is known, what is unknown, what is being tested next, and when the next update will arrive.", "score": 93, "feedback": "Good pressure communication: factual, bounded, and accountable."}, {"label": "Say everything is under control even though the evidence is incomplete.", "score": 18, "feedback": "Overconfidence destroys trust when facts change."}, {"label": "Stay silent until you have a perfect answer.", "score": 16, "feedback": "Silence increases pressure and uncertainty."}, {"label": "Give every technical detail without a recommendation.", "score": 46, "feedback": "Too much detail without a clear message weakens clarity."}]},
    {"mode": "prioritization", "difficulty": 4, "instructions": "Pick the option that shows disciplined prioritization.", "prompt": "Two urgent requests hit at once: one threatens {metric}, the other comes from a senior {stakeholder}. What should you do first?", "options": [{"label": "Evaluate user impact, risk, and reversibility, then explain the priority call with evidence.", "score": 90, "feedback": "Strong prioritization. You used impact and risk, not job title, to decide."}, {"label": "Always do what the most senior person asks first.", "score": 22, "feedback": "Seniority is not a substitute for impact-based prioritization."}, {"label": "Split your attention evenly between both, even if neither moves.", "score": 28, "feedback": "Context switching can leave both issues unresolved."}, {"label": "Ignore the metric issue because it looks technical.", "score": 10, "feedback": "That can leave the real business risk unaddressed."}]},
    {"mode": "ownership", "difficulty": 4, "instructions": "Choose the answer that shows ownership with a controlled recovery path.", "prompt": "A release tied to {artifact} goes wrong because your initial assumption was incomplete. What is the strongest response?", "options": [{"label": "Own the miss, contain the impact, explain the wrong assumption, and define the correction plan.", "score": 92, "feedback": "Strong recovery. You combined accountability with action."}, {"label": "Hide the assumption error until you have already fixed it.", "score": 16, "feedback": "That protects ego, not the team or users."}, {"label": "Blame unclear requirements and move on.", "score": 14, "feedback": "That avoids learning and weakens trust."}, {"label": "Restart the work from scratch without communicating the recovery path.", "score": 34, "feedback": "Action without communication leaves others blind."}]},
    {"mode": "decision", "difficulty": 4, "instructions": "Pick the answer that shows judgment, not just activity.", "prompt": "You must choose between a quick fix and a deeper {decision} change in {artifact}. Which approach is strongest?", "options": [{"label": "Choose the path that best balances current risk, reversibility, and impact on {metric}, and explain the tradeoff clearly.", "score": 89, "feedback": "Good judgment. You framed the decision with tradeoffs and reversibility."}, {"label": "Always choose the quick fix because deadlines are more important than long-term health.", "score": 24, "feedback": "This ignores the cost of repeated rework."}, {"label": "Always choose the rewrite because long-term work is more impressive.", "score": 30, "feedback": "Big changes without proportional need can be irresponsible."}, {"label": "Ask someone else to decide so you are not blamed.", "score": 8, "feedback": "That avoids ownership instead of exercising judgment."}]},
    {"mode": "risk_assessment", "difficulty": 3, "instructions": "Pick the best approach to assess and communicate risk.", "prompt": "You spot a potential risk in {artifact} that might affect {metric}. What is your best move?", "options": [{"label": "Assess the severity quickly, define what needs to be tested, and communicate the risk with a timeline.", "score": 88, "feedback": "Smart risk management: you quantified before alarming."}, {"label": "Sound the alarm immediately to make sure everyone knows.", "score": 32, "feedback": "Early warning is good, but unquantified risk causes panic."}, {"label": "Assume it will probably resolve itself and monitor quietly.", "score": 18, "feedback": "Passive risk management can let small issues become big ones."}, {"label": "Investigate exhaustively before telling anyone.", "score": 45, "feedback": "Hidden investigation delays your team from preparing."}]},
    {"mode": "feedback_response", "difficulty": 3, "instructions": "Choose how you respond to critical feedback on your {artifact}.", "prompt": "A {stakeholder} gives you tough feedback on your approach to {artifact}. What do you do?", "options": [{"label": "Listen for specifics, ask questions to understand their concern, and separate the feedback from blame.", "score": 90, "feedback": "Mature feedback response: you stayed curious instead of defensive."}, {"label": "Explain why your approach was right and they did not understand.", "score": 22, "feedback": "Defending yourself shuts down the feedback loop."}, {"label": "Get defensive and argue that they did not give you enough information.", "score": 15, "feedback": "Blame-shifting damages trust and stalls learning."}, {"label": "Accept all feedback as gospel and second-guess every decision.", "score": 48, "feedback": "Over-correction based on single feedback weakens your judgment."}]},
    {"mode": "team_conflict", "difficulty": 4, "instructions": "Pick the approach that builds alignment without causing resentment.", "prompt": "Two team members disagree on how to approach {artifact}. How do you resolve it?", "options": [{"label": "Understand both perspectives, decide based on impact and tradeoff, then explain the choice and next steps.", "score": 91, "feedback": "Strong leadership: you valued their input while making a clear call."}, {"label": "Side with whoever has more seniority to avoid conflict.", "score": 20, "feedback": "Rank-based decisions ignore merit and demotivate junior people."}, {"label": "Try to make both happy by doing both approaches.", "score": 32, "feedback": "Half-measures often fail and waste effort."}, {"label": "Let them argue until they decide themselves.", "score": 18, "feedback": "Absent leadership leaves the team misaligned."}]},
]
INTERVIEW_CHECKBOX_SPECS = [
    {"mode": "change_plan", "difficulty": 2, "instructions": "Select the actions that belong in a strong plan.", "prompt": "Select the actions that belong in a strong plan before changing {artifact}.", "options": [{"label": "Define rollback criteria before release.", "correct": True}, {"label": "Add instrumentation for {metric}.", "correct": True}, {"label": "Update the {stakeholder} if risk changes.", "correct": True}, {"label": "Skip baselines because the likely outcome is obvious.", "correct": False}, {"label": "Bundle unrelated changes together to save time.", "correct": False}]},
    {"mode": "debugging", "difficulty": 2, "instructions": "Pick the steps that make the investigation more reliable.", "prompt": "You need to debug a problem in {artifact}. Which steps improve the investigation?", "options": [{"label": "Reproduce the issue with a narrow scope.", "correct": True}, {"label": "Check {tool} for timing and sequence clues.", "correct": True}, {"label": "Change several variables at once so you move faster.", "correct": False}, {"label": "Write down the likely hypotheses before testing them.", "correct": True}, {"label": "Assume the most recent change must be the cause without validation.", "correct": False}]},
    {"mode": "launch", "difficulty": 3, "instructions": "Select the steps that protect the launch without drifting into ceremony.", "prompt": "The team is preparing to launch {artifact}. Which steps strengthen the launch plan?", "options": [{"label": "Define the success and failure signals for {metric}.", "correct": True}, {"label": "Clarify who approves a rollback if risk rises.", "correct": True}, {"label": "Disable all feedback channels so the release looks cleaner.", "correct": False}, {"label": "Prewrite the update you will send if launch risk increases.", "correct": True}, {"label": "Skip QA because the team already feels confident.", "correct": False}]},
    {"mode": "communication", "difficulty": 3, "instructions": "Select the behaviors that keep communication credible during pressure.", "prompt": "A risk tied to {artifact} is active. Which communication behaviors are strong?", "options": [{"label": "Separate facts, assumptions, and next steps.", "correct": True}, {"label": "Set the next update time even if the root cause is not final.", "correct": True}, {"label": "Overstate confidence so the room stays calm.", "correct": False}, {"label": "Explain the user impact in plain language.", "correct": True}, {"label": "Hold the update until every technical detail is confirmed.", "correct": False}]},
    {"mode": "postmortem", "difficulty": 3, "instructions": "Select the actions that turn a miss into a learning loop.", "prompt": "After a miss involving {artifact}, which actions belong in a strong retrospective?", "options": [{"label": "Name the wrong assumption or missing signal.", "correct": True}, {"label": "Define one or two follow-up actions with owners.", "correct": True}, {"label": "Frame the problem only as another team's fault.", "correct": False}, {"label": "Capture the trigger that should be watched next time.", "correct": True}, {"label": "Avoid specifics so the meeting stays comfortable.", "correct": False}]},
    {"mode": "prioritization", "difficulty": 4, "instructions": "Select the factors that should drive the priority call.", "prompt": "You have more work than time. Which inputs should shape the priority order for {artifact}?", "options": [{"label": "User impact on {metric}.", "correct": True}, {"label": "Reversibility if the decision is wrong.", "correct": True}, {"label": "Who shouted the loudest in the last meeting.", "correct": False}, {"label": "Dependencies that could block other teams.", "correct": True}, {"label": "Whether the task sounds impressive on paper.", "correct": False}]},
    {"mode": "validation", "difficulty": 4, "instructions": "Select the steps that make the decision more defensible.", "prompt": "You need to validate a major decision for {artifact}. Which actions improve decision quality?", "options": [{"label": "Define the decision criteria before collecting more data.", "correct": True}, {"label": "Check whether the signal changes a real tradeoff.", "correct": True}, {"label": "Gather endless data even if the decision window closes.", "correct": False}, {"label": "Test the highest-risk assumption first.", "correct": True}, {"label": "Ignore contradictory evidence because it slows momentum.", "correct": False}]},
    {"mode": "recovery", "difficulty": 4, "instructions": "Select the recovery behaviors that rebuild trust.", "prompt": "A decision on {artifact} went the wrong way. Which actions help you recover strongly?", "options": [{"label": "Acknowledge the miss directly.", "correct": True}, {"label": "Contain impact before debating blame.", "correct": True}, {"label": "Write down what signal was missing.", "correct": True}, {"label": "Hide the mistake until the team forgets it.", "correct": False}, {"label": "Rewrite the history so the decision looks reasonable.", "correct": False}]},
    {"mode": "testing_strategy", "difficulty": 3, "instructions": "Select the testing elements that make {artifact} more reliable.", "prompt": "Which testing strategies would strengthen the quality of {artifact}?", "options": [{"label": "Test the happy path thoroughly before edge cases.", "correct": False}, {"label": "Automate tests for regression prevention.", "correct": True}, {"label": "Write test scenarios that cover highest-risk {metric} moves.", "correct": True}, {"label": "Skip testing if the code is obviously correct.", "correct": False}, {"label": "Get user feedback early on critical workflows.", "correct": True}]},
    {"mode": "team_collaboration", "difficulty": 3, "instructions": "Select practices that improve team alignment on {artifact}.", "prompt": "Which practices would improve collaboration on {artifact}?", "options": [{"label": "Document design decisions and tradeoffs.", "correct": True}, {"label": "Hold regular syncs to surface blockers early.", "correct": True}, {"label": "Work in isolation until the feature is complete.", "correct": False}, {"label": "Clarify ownership and decision authority upfront.", "correct": True}, {"label": "Assume everyone knows the context of the work.", "correct": False}]},
]
def _normalize_text(text):
    text = str(text or "").lower()
    text = re.sub(r"[^a-z0-9+.#\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokenize(text):
    return [token for token in _normalize_text(text).split() if token]


def _extract_skill_hints(text):
    normalized = _normalize_text(text)
    return [skill for skill in INTERVIEW_SKILL_HINTS if f" {skill} " in f" {normalized} "]


def _focus_key(value):
    value = _normalize_text(value)
    return value if value in INTERVIEW_ROLE_PROFILES else "general"


def _focus_from_role(role):
    normalized = _normalize_text(role)
    focus_map = {
        "backend": {"backend", "api", "python", "django", "flask", "database", "server", "platform"},
        "frontend": {"frontend", "ui", "ux", "react", "angular", "vue", "javascript", "web"},
        "data": {"data", "ml", "machine learning", "analytics", "analyst", "scientist", "ai"},
        "behavioral": {"manager", "lead", "leadership", "people", "program"},
    }
    for focus, tokens in focus_map.items():
        if any(token in normalized for token in tokens):
            return focus
    return "general"


def _role_profile(role, focus):
    focus_key = _focus_key(focus)
    if focus_key == "general":
        focus_key = _focus_from_role(role)
    return focus_key, INTERVIEW_ROLE_PROFILES[focus_key]


def _resume_context(resume_payload, role=""):
    extracted = resume_payload or {}
    raw_text = str(extracted.get("raw_text") or "")
    skills = extracted.get("skills") or _extract_skill_hints(raw_text)
    skills = [str(skill).strip().lower() for skill in skills if str(skill).strip()][:8]
    projects = []
    for project in extracted.get("projects") or []:
        if isinstance(project, dict):
            name = str(project.get("name") or "").strip()
        else:
            name = str(project or "").strip()
        if name:
            projects.append(name)
    experience_titles = []
    for item in extracted.get("experience") or []:
        if isinstance(item, dict):
            title = str(item.get("title") or item.get("company") or "").strip()
        else:
            title = str(item or "").strip()
        if title:
            experience_titles.append(title)
    return {
        "name": str(extracted.get("name") or "Candidate").strip() or "Candidate",
        "skills": skills[:8],
        "projects": projects[:6],
        "experience_titles": experience_titles[:6],
        "role_terms": [token for token in _tokenize(role) if len(token) >= 3][:6],
    }


def _primary_anchor(resume_context):
    if resume_context.get("projects"):
        return resume_context["projects"][0]
    if resume_context.get("experience_titles"):
        return resume_context["experience_titles"][0]
    if resume_context.get("skills"):
        return ", ".join(resume_context["skills"][:2])
    return "your most relevant recent work"


def _unique_items(*groups):
    values = []
    seen = set()
    for group in groups:
        for raw in group or []:
            value = str(raw or "").strip()
            if not value:
                continue
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            values.append(value)
    return values


def _term_pools(role, company, focus, profile, resume_context):
    anchor = _primary_anchor(resume_context)
    return {
        "role": role,
        "company": company,
        "company_suffix": f" at {company}" if company else "",
        "anchor": anchor,
        "artifacts": _unique_items([anchor], resume_context.get("projects"), resume_context.get("experience_titles"), profile.get("artifact_terms")) or [anchor],
        "constraints": _unique_items(profile.get("constraint_terms")) or ["time pressure"],
        "metrics": _unique_items(profile.get("metric_terms")) or ["impact"],
        "stakeholders": _unique_items([f"{company} hiring panel"] if company else [], profile.get("stakeholder_terms")) or ["hiring manager"],
        "decisions": _unique_items(profile.get("decision_terms")) or ["decision"],
        "tools": _unique_items(profile.get("tool_terms")) or ["evidence"],
        "qualities": _unique_items(profile.get("quality_terms")) or ["quality"],
        "skills": _unique_items(resume_context.get("skills"), resume_context.get("role_terms"), profile.get("skill_terms"), [role]) or [role],
        "domain_label": profile.get("domain_label") or focus,
    }


def _question_values(pools, spec_index, variant):
    return {
        "role": pools["role"],
        "company": pools["company"],
        "company_suffix": pools["company_suffix"],
        "anchor": pools["anchor"],
        "artifact": pools["artifacts"][(spec_index + variant) % len(pools["artifacts"])],
        "constraint": pools["constraints"][(spec_index + 2 * variant) % len(pools["constraints"])],
        "metric": pools["metrics"][(spec_index + variant) % len(pools["metrics"])],
        "stakeholder": pools["stakeholders"][(spec_index + variant) % len(pools["stakeholders"])],
        "decision": pools["decisions"][(spec_index + 2 * variant) % len(pools["decisions"])],
        "tool": pools["tools"][(spec_index + variant) % len(pools["tools"])],
        "quality": pools["qualities"][(spec_index + variant) % len(pools["qualities"])],
        "skill": pools["skills"][(spec_index + variant) % len(pools["skills"])],
        "domain_label": pools["domain_label"],
    }


def _question_difficulty(base, variant):
    return max(1, min(5, int(base or 2) + variant - 1))


def _make_question(question_id, kind, mode, difficulty, prompt, instructions, expected_keywords=None, options=None):
    return {
        "id": question_id,
        "kind": kind,
        "kind_label": INTERVIEW_INPUT_KIND_LABELS.get(kind, kind.title()),
        "mode": mode,
        "difficulty": _question_difficulty(difficulty, 1),
        "prompt": prompt,
        "instructions": instructions,
        "expected_keywords": [value for value in (expected_keywords or []) if value],
        "options": options or [],
    }


def _question_bank(role, company, focus, resume_context):
    focus_key, profile = _role_profile(role, focus)
    pools = _term_pools(role, company, focus_key, profile, resume_context)
    questions = []
    for variant in range(5):
        for spec_index, spec in enumerate(INTERVIEW_TEXT_SPECS, start=1):
            values = _question_values(pools, spec_index, variant)
            questions.append({
                "id": f"text-{variant + 1}-{spec_index}",
                "kind": "text",
                "kind_label": INTERVIEW_INPUT_KIND_LABELS["text"],
                "mode": spec["mode"],
                "difficulty": _question_difficulty(spec["difficulty"], variant),
                "prompt": spec["prompt"].format(**values),
                "instructions": spec["instructions"],
                "expected_keywords": [values["artifact"], values["constraint"], values["metric"], values["decision"], values["skill"]],
                "options": [],
            })
        for spec_index, spec in enumerate(INTERVIEW_RADIO_SPECS, start=1):
            values = _question_values(pools, spec_index, variant)
            options = []
            qid = f"radio-{variant + 1}-{spec_index}"
            for option_index, option in enumerate(spec["options"], start=1):
                options.append({
                    "id": f"{qid}-opt-{option_index}",
                    "label": option["label"].format(**values),
                    "score": int(option["score"]),
                    "feedback": option["feedback"],
                })
            questions.append({
                "id": qid,
                "kind": "radio",
                "kind_label": INTERVIEW_INPUT_KIND_LABELS["radio"],
                "mode": spec["mode"],
                "difficulty": _question_difficulty(spec["difficulty"], variant),
                "prompt": spec["prompt"].format(**values),
                "instructions": spec["instructions"],
                "expected_keywords": [values["artifact"], values["constraint"], values["metric"], values["decision"]],
                "options": options,
            })
        for spec_index, spec in enumerate(INTERVIEW_CHECKBOX_SPECS, start=1):
            values = _question_values(pools, spec_index, variant)
            options = []
            qid = f"checkbox-{variant + 1}-{spec_index}"
            for option_index, option in enumerate(spec["options"], start=1):
                options.append({
                    "id": f"{qid}-opt-{option_index}",
                    "label": option["label"].format(**values),
                    "correct": bool(option["correct"]),
                })
            questions.append({
                "id": qid,
                "kind": "checkbox",
                "kind_label": INTERVIEW_INPUT_KIND_LABELS["checkbox"],
                "mode": spec["mode"],
                "difficulty": _question_difficulty(spec["difficulty"], variant),
                "prompt": spec["prompt"].format(**values),
                "instructions": spec["instructions"],
                "expected_keywords": [values["artifact"], values["metric"], values["stakeholder"]],
                "options": options,
            })
    return questions
def _question_mix(turns):
    counts = Counter((turn.get("question_kind") or "text") for turn in turns or [])
    return {"text": counts.get("text", 0), "radio": counts.get("radio", 0), "checkbox": counts.get("checkbox", 0)}


def _score_summary(score_history):
    if not score_history:
        return {"confidence": 0, "clarity": 0, "depth": 0, "overall": 0}
    confidence = round(sum(item.get("confidence", 0) for item in score_history) / len(score_history))
    clarity = round(sum(item.get("clarity", 0) for item in score_history) / len(score_history))
    depth = round(sum(item.get("depth", 0) for item in score_history) / len(score_history))
    return {"confidence": confidence, "clarity": clarity, "depth": depth, "overall": round((confidence + clarity + depth) / 3)}


def _public_question(question):
    if not question:
        return None
    payload = {
        "id": question.get("id"),
        "kind": question.get("kind", "text"),
        "kind_label": question.get("kind_label", "Typing"),
        "mode": question.get("mode", "standard"),
        "prompt": question.get("prompt", ""),
        "instructions": question.get("instructions", ""),
        "options": [],
    }
    if question.get("kind") == "radio":
        payload["min_choices"] = 1
        payload["max_choices"] = 1
    elif question.get("kind") == "checkbox":
        payload["min_choices"] = 1
        payload["max_choices"] = len(question.get("options") or [])
    else:
        payload["placeholder"] = "Type your answer with context, action, tradeoff, and result."
    for option in question.get("options") or []:
        payload["options"].append({"id": option.get("id"), "label": option.get("label", "")})
    return payload


def _desired_kind(turn_number):
    pattern = ["text", "radio", "checkbox", "text", "radio", "checkbox"]
    return pattern[(max(1, int(turn_number or 1)) - 1) % len(pattern)]


def _pick_next_question(state):
    bank = state.get("question_bank") or []
    asked_ids = set(state.get("asked_question_ids") or [])
    remaining = [question for question in bank if question.get("id") not in asked_ids]
    if not remaining:
        return None
    if not state.get("turns"):
        opening = next((question for question in remaining if question.get("mode") == "opening" and question.get("kind") == "text"), None)
        if opening:
            return opening
    wanted_kind = _desired_kind(len(state.get("turns") or []) + 1)
    target_difficulty = int(state.get("difficulty") or 2)
    ranked = sorted(remaining, key=lambda q: (0 if q.get("kind") == wanted_kind else 1, abs(int(q.get("difficulty") or 2) - target_difficulty), q.get("id", "")))
    return ranked[0]


def _find_option(question, option_id):
    for option in question.get("options") or []:
        if option.get("id") == option_id:
            return option
    return None


def _normalize_selected_options(selected_options):
    if selected_options is None:
        return []
    if isinstance(selected_options, str):
        value = selected_options.strip()
        return [value] if value else []
    values = []
    for item in selected_options if isinstance(selected_options, list) else []:
        value = str(item or "").strip()
        if value:
            values.append(value)
    return values


def _skill_terms(state):
    resume_context = state.get("resume_context") or {}
    role = str(state.get("role") or "")
    terms = set(resume_context.get("skills") or [])
    terms.update(resume_context.get("role_terms") or [])
    terms.update(token for token in _tokenize(role) if len(token) >= 3)
    terms.update(_normalize_text(value) for value in (state.get("current_question") or {}).get("expected_keywords") or [])
    return {term for term in terms if term}


def _evaluate_text(state, question, answer):
    text = str(answer or "").strip()
    if not text:
        raise ValueError("Type your answer before submitting.")
    words = re.findall(r"[A-Za-z0-9+#.%'-]+", text)
    lower_text = text.lower()
    word_count = len(words)
    sentences = [part.strip() for part in re.split(r"[.!?\n]+", text) if part.strip()]
    sentence_count = len(sentences)
    avg_sentence_len = (word_count / sentence_count) if sentence_count else word_count
    filler_count = sum(lower_text.count(term) for term in INTERVIEW_FILLERS)
    hedge_count = sum(lower_text.count(term) for term in INTERVIEW_HEDGES)
    metric_hits = len(re.findall(r"\b\d+(?:\.\d+)?%?\b", text))
    action_hits = sum(1 for verb in ACTION_VERBS if verb in lower_text)
    structure_hits = sum(1 for term in INTERVIEW_STRUCTURE_TERMS if term in lower_text)
    depth_hits = sum(1 for term in INTERVIEW_DEPTH_TERMS if term in lower_text)
    skill_hits = sum(1 for term in _skill_terms(state) if term and term in lower_text)
    pronoun_hits = lower_text.count(" i ") + lower_text.count(" i'") + (1 if lower_text.startswith("i ") else 0)
    confidence = 42 + min(word_count, 160) / 160 * 16 + min(action_hits, 5) * 4 + min(metric_hits, 3) * 4 + min(pronoun_hits, 4) * 2 - min(hedge_count, 5) * 6 - min(filler_count, 5) * 4
    if word_count < 30:
        confidence -= 12
    confidence = max(0, min(100, round(confidence)))
    clarity = 35 + (18 if 2 <= sentence_count <= 7 else 6 if sentence_count == 1 else 0)
    if 8 <= avg_sentence_len <= 26:
        clarity += 18
    elif avg_sentence_len < 6 or avg_sentence_len > 34:
        clarity -= 8
    clarity += min(structure_hits, 4) * 5 - min(filler_count, 5) * 3
    if word_count < 25:
        clarity -= 12
    clarity = max(0, min(100, round(clarity)))
    depth = 28 + min(metric_hits, 4) * 8 + min(skill_hits, 6) * 4 + min(depth_hits, 4) * 6
    depth += 10 if word_count >= 90 else -12 if word_count < 40 else 0
    depth = max(0, min(100, round(depth)))
    strengths, improvements = [], []
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
    return {"confidence": confidence, "clarity": clarity, "depth": depth, "overall": overall, "word_count": word_count, "sentence_count": sentence_count, "strengths": strengths[:3], "improvements": improvements[:3], "coaching_note": "Use crisp, specific answers with ownership and measurable impact." if overall < 70 else "Maintain this structure under pressure and keep anchoring on impact."}


def _evaluate_radio(question, selected_options):
    if not selected_options:
        raise ValueError("Select one option before submitting.")
    option = _find_option(question, selected_options[0])
    if option is None:
        raise ValueError("Selected option is invalid.")
    base = int(option.get("score", 0))
    confidence = max(0, min(100, round(base * 0.95 + 5)))
    clarity = max(0, min(100, round(base)))
    depth = max(0, min(100, round(base * 0.9 + 6)))
    overall = round((confidence + clarity + depth) / 3)
    strengths, improvements = [], []
    if overall >= 78:
        strengths.extend(["You picked the most defensible response under pressure.", "Your choice prioritized signal, risk control, and communication."])
    elif overall >= 55:
        strengths.append("You identified part of the right response.")
        improvements.append("Push your choice further toward evidence, containment, and explicit tradeoffs.")
    else:
        improvements.extend(["Choose the option that reduces risk first instead of reacting with certainty or delay.", "Look for the answer that adds evidence, containment, or a safer scope boundary."])
    return {"confidence": confidence, "clarity": clarity, "depth": depth, "overall": overall, "word_count": 0, "sentence_count": 0, "strengths": strengths[:3], "improvements": improvements[:3], "coaching_note": option.get("feedback") or "Pick the answer that protects users, evidence quality, and reversibility."}


def _evaluate_checkbox(question, selected_options):
    selected = set(selected_options)
    if not selected:
        raise ValueError("Select at least one option before submitting.")
    correct_ids = {option.get("id") for option in question.get("options") or [] if option.get("correct")}
    hits = len(selected & correct_ids)
    misses = len(correct_ids - selected)
    wrong = len(selected - correct_ids)
    precision = hits / len(selected) if selected else 0.0
    recall = hits / len(correct_ids) if correct_ids else 0.0
    overall = round(((0.55 * precision) + (0.45 * recall)) * 100)
    confidence = max(0, min(100, round(overall + (6 if wrong == 0 else -6 * wrong))))
    clarity = max(0, min(100, round(overall + (4 if misses == 0 else -5 * misses))))
    depth = max(0, min(100, round(recall * 100 - wrong * 10)))
    missed_labels = [option.get("label", "") for option in question.get("options") or [] if option.get("id") in correct_ids - selected]
    wrong_labels = [option.get("label", "") for option in question.get("options") or [] if option.get("id") in selected - correct_ids]
    strengths = ["You selected actions that improve decision quality under pressure."] if hits else []
    if precision >= 0.8 and recall >= 0.8:
        strengths.append("Your checklist covered both control and communication steps.")
    improvements = []
    if missed_labels:
        improvements.append("You missed some important controls: " + ", ".join(missed_labels[:2]) + ".")
    if wrong_labels:
        improvements.append("Avoid weak actions such as: " + ", ".join(wrong_labels[:2]) + ".")
    if not improvements and overall >= 80:
        improvements.append("Maintain the same discipline when the room gets noisy or the deadline tightens.")
    return {"confidence": confidence, "clarity": clarity, "depth": depth, "overall": round((confidence + clarity + depth) / 3), "word_count": 0, "sentence_count": 0, "strengths": strengths[:3], "improvements": improvements[:3], "coaching_note": "Choose the checklist items that protect evidence, reversibility, and communication quality."}


def _evaluate_submission(state, question, answer, selected_options):
    kind = question.get("kind", "text")
    if kind == "radio":
        return _evaluate_radio(question, selected_options)
    if kind == "checkbox":
        return _evaluate_checkbox(question, selected_options)
    return _evaluate_text(state, question, answer)
def _pressure_event(state, evaluation, question):
    kind = question.get("kind", "text")
    if kind == "text":
        if evaluation["word_count"] > 190 or evaluation["clarity"] < 55:
            return {"type": "interruption", "label": "Interruption", "message": "I am stopping you there. Tighten the next answer and lead with the impact first."}
        if evaluation["depth"] < 58:
            return {"type": "follow_up", "label": "Follow-Up", "message": "That is still high-level. In the next answer, name the constraint, your decision, and the metric that moved."}
    elif evaluation["overall"] < 55:
        return {"type": "follow_up", "label": "Pressure Note", "message": "That choice left risk exposed. Expect the next question to test how you reduce uncertainty under pressure."}
    if state.get("difficulty", 2) >= 4 or evaluation["overall"] >= 85:
        scenarios = INTERVIEW_STRESS_SCENARIOS.get(_focus_key(state.get("focus"))) or INTERVIEW_STRESS_SCENARIOS["general"]
        index = len(state.get("pressure_events") or []) % len(scenarios)
        return {"type": "stress", "label": "Stress Scenario", "message": scenarios[index]}
    return None


def _adjust_difficulty(current_difficulty, evaluation):
    difficulty = int(current_difficulty or 2)
    if evaluation["overall"] >= 75 and evaluation["confidence"] >= 68 and evaluation["depth"] >= 68:
        difficulty += 1
    elif evaluation["overall"] <= 48 or evaluation["clarity"] <= 45:
        difficulty -= 1
    return max(1, min(5, difficulty))


def _submission_summary(question, answer, selected_options):
    if question.get("kind") == "text":
        return str(answer or "").strip()
    chosen = [option.get("label", "") for option in question.get("options") or [] if option.get("id") in set(selected_options)]
    return "; ".join(chosen)


def _final_summary(state):
    score_summary = _score_summary(state.get("score_history") or [])
    dimensions = {"confidence": score_summary["confidence"], "clarity": score_summary["clarity"], "depth": score_summary["depth"]}
    strongest = max(dimensions, key=dimensions.get)
    weakest = min(dimensions, key=dimensions.get)
    mix = _question_mix(state.get("turns") or [])
    recommendations = []
    if score_summary["confidence"] < 70:
        recommendations.append("Lead with a decision, not a disclaimer. Cut hedging and filler words.")
    if score_summary["clarity"] < 70:
        recommendations.append("Use a repeatable structure: context, action, tradeoff, result.")
    if score_summary["depth"] < 70:
        recommendations.append("Add metrics, constraints, tradeoffs, and what you personally owned.")
    if len(state.get("pressure_events") or []) >= 4:
        recommendations.append("Practice shorter pressure answers so interruptions do not break your flow.")
    if mix["radio"] + mix["checkbox"] >= 20 and score_summary["overall"] < 70:
        recommendations.append("Strengthen decision quality by explicitly choosing for evidence, reversibility, and user impact.")
    if not recommendations:
        recommendations.append("You handled pressure well. Push further by sharpening your numbers and tradeoff language.")
    verdict = "Strong pressure handling" if score_summary["overall"] >= 78 else "Needs more pressure reps" if score_summary["overall"] < 60 else "Solid baseline with room to tighten delivery"
    return {"overall": score_summary["overall"], "confidence": score_summary["confidence"], "clarity": score_summary["clarity"], "depth": score_summary["depth"], "strongest_dimension": strongest, "weakest_dimension": weakest, "pressure_events_triggered": len(state.get("pressure_events") or []), "verdict": verdict, "recommendations": recommendations[:5], "question_mix": mix, "questions_answered": len(state.get("turns") or [])}


def _response_payload(state, extra=None):
    current_question = state.get("current_question") or {}
    total_questions = int(state.get("total_questions") or 0)
    answered = len(state.get("turns") or [])
    current_progress = total_questions if state.get("status") == "completed" and total_questions else min(answered + 1, total_questions) if total_questions else 0
    payload = {
        "status": state.get("status", "idle"),
        "question": current_question.get("prompt", ""),
        "question_mode": current_question.get("mode", "standard"),
        "question_type": current_question.get("kind", "text"),
        "question_details": _public_question(current_question),
        "difficulty": state.get("difficulty", 2),
        "difficulty_label": INTERVIEW_DIFFICULTY_LABELS.get(state.get("difficulty", 2), "Baseline"),
        "progress": {"current": current_progress, "total": total_questions},
        "score_summary": _score_summary(state.get("score_history") or []),
        "transcript": state.get("turns", []),
        "resume_context": state.get("resume_context", {}),
        "question_mix": _question_mix(state.get("turns") or []),
        "question_bank_size": len(state.get("question_bank") or []),
    }
    if extra:
        payload.update(extra)
    if state.get("status") == "completed":
        payload["final_summary"] = _final_summary(state)
    return payload


def start_interview_simulator(resume_payload, role, company="", focus="general", total_questions=INTERVIEW_MIN_QUESTION_COUNT, total_rounds=None):
    clean_role = str(role or "").strip() or "Software Engineer"
    clean_company = str(company or "").strip()
    requested = total_rounds if total_rounds is not None else total_questions
    requested = int(requested or INTERVIEW_MIN_QUESTION_COUNT)
    resume_context = _resume_context(resume_payload or {}, clean_role)
    focus_key, _ = _role_profile(clean_role, focus)
    question_bank = _question_bank(clean_role, clean_company, focus_key, resume_context)
    total = max(INTERVIEW_MIN_QUESTION_COUNT, min(requested, min(len(question_bank), INTERVIEW_MAX_QUESTION_COUNT)))
    state = {
        "status": "active",
        "role": clean_role,
        "company": clean_company,
        "focus": focus_key,
        "difficulty": 2,
        "current_round": 1,
        "total_questions": total,
        "resume_context": resume_context,
        "question_bank": question_bank,
        "asked_question_ids": [],
        "current_question": {},
        "score_history": [],
        "turns": [],
        "pressure_events": [],
    }
    state["current_question"] = _pick_next_question(state) or {}
    return state, _response_payload(state)


def advance_interview_simulator(state, answer="", selected_options=None):
    if not state or state.get("status") != "active":
        raise ValueError("Interview session is not active.")
    question = state.get("current_question") or {}
    if not question:
        raise ValueError("Current interview question is missing.")
    chosen_options = _normalize_selected_options(selected_options)
    evaluation = _evaluate_submission(state, question, answer, chosen_options)
    state.setdefault("score_history", []).append({key: evaluation[key] for key in ("confidence", "clarity", "depth", "overall")})
    before = state.get("difficulty", 2)
    after = _adjust_difficulty(before, evaluation)
    event = _pressure_event({**state, "difficulty": after}, evaluation, question)
    if event:
        state.setdefault("pressure_events", []).append(event)
    state.setdefault("turns", []).append({
        "round": len(state.get("turns") or []) + 1,
        "question": question.get("prompt", ""),
        "question_mode": question.get("mode", "standard"),
        "question_kind": question.get("kind", "text"),
        "question_kind_label": question.get("kind_label", "Typing"),
        "answer": _submission_summary(question, answer, chosen_options),
        "scores": {key: evaluation[key] for key in ("confidence", "clarity", "depth", "overall")},
        "strengths": evaluation.get("strengths", []),
        "improvements": evaluation.get("improvements", []),
    })
    state.setdefault("asked_question_ids", []).append(question.get("id"))
    state["difficulty"] = after
    if len(state.get("turns") or []) >= int(state.get("total_questions") or INTERVIEW_MIN_QUESTION_COUNT):
        state["status"] = "completed"
        state["current_round"] = int(state.get("total_questions") or len(state.get("turns") or []))
        state["current_question"] = {}
        return state, _response_payload(state, {"evaluation": {**evaluation, "difficulty_before": before, "difficulty_after": after}, "pressure_event": event})
    state["current_round"] = len(state.get("turns") or []) + 1
    state["current_question"] = _pick_next_question(state) or {}
    return state, _response_payload(state, {"evaluation": {**evaluation, "difficulty_before": before, "difficulty_after": after}, "pressure_event": event})
