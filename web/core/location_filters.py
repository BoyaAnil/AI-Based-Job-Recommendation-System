import re

from django.db.models import Q


REMOTE_SEARCH_VALUES = {
    "remote",
    "work from home",
    "work-from-home",
    "wfh",
    "home based",
    "home-based",
    "anywhere",
    "worldwide",
    "global",
    "global remote",
    "remote worldwide",
    "remote global",
}

REMOTE_LOCATION_TERMS = (
    "remote",
    "work from home",
    "work-from-home",
    "wfh",
    "home based",
    "home-based",
    "anywhere",
    "worldwide",
    "global",
    "distributed",
    "telecommute",
    "telecommuting",
)

INDIA_SEARCH_VALUES = {
    "india",
    "indian",
    "all india",
    "india states",
    "all india states",
}

INDIA_REGION_VARIANTS = {
    "andhra pradesh": ("andhra pradesh", "amaravati", "visakhapatnam", "vizag", "vijayawada", "tirupati"),
    "arunachal pradesh": ("arunachal pradesh", "itanagar"),
    "assam": ("assam", "guwahati", "dispur", "jorhat", "silchar"),
    "bihar": ("bihar", "patna", "gaya", "muzaffarpur"),
    "chandigarh": ("chandigarh",),
    "chhattisgarh": ("chhattisgarh", "raipur", "bilaspur", "bhilai"),
    "dadra and nagar haveli and daman and diu": (
        "dadra and nagar haveli and daman and diu",
        "daman",
        "diu",
        "silvassa",
    ),
    "delhi": ("delhi", "new delhi"),
    "delhi ncr": ("delhi ncr", "new delhi", "delhi", "gurugram", "gurgaon", "noida", "ghaziabad", "faridabad"),
    "goa": ("goa", "panaji", "margao", "vasco da gama"),
    "gujarat": ("gujarat", "gandhinagar", "ahmedabad", "surat", "vadodara", "rajkot"),
    "haryana": ("haryana", "gurugram", "gurgaon", "faridabad", "panipat"),
    "himachal pradesh": ("himachal pradesh", "shimla", "dharamshala", "solan"),
    "jammu and kashmir": ("jammu and kashmir", "jammu", "srinagar"),
    "jharkhand": ("jharkhand", "ranchi", "jamshedpur", "dhanbad"),
    "karnataka": ("karnataka", "bengaluru", "bangalore", "mysuru", "mangalore", "hubli"),
    "kerala": ("kerala", "thiruvananthapuram", "trivandrum", "kochi", "cochin", "kozhikode"),
    "ladakh": ("ladakh", "leh", "kargil"),
    "lakshadweep": ("lakshadweep", "kavaratti"),
    "madhya pradesh": ("madhya pradesh", "bhopal", "indore", "gwalior", "jabalpur"),
    "maharashtra": ("maharashtra", "mumbai", "bombay", "pune", "nagpur", "nashik"),
    "manipur": ("manipur", "imphal"),
    "meghalaya": ("meghalaya", "shillong"),
    "mizoram": ("mizoram", "aizawl"),
    "nagaland": ("nagaland", "kohima", "dimapur"),
    "odisha": ("odisha", "orissa", "bhubaneswar", "cuttack", "rourkela"),
    "puducherry": ("puducherry", "pondicherry"),
    "punjab": ("punjab", "amritsar", "ludhiana", "mohali", "jalandhar"),
    "rajasthan": ("rajasthan", "jaipur", "jodhpur", "udaipur", "kota"),
    "sikkim": ("sikkim", "gangtok"),
    "tamil nadu": ("tamil nadu", "chennai", "madras", "coimbatore", "madurai", "salem"),
    "telangana": ("telangana", "hyderabad", "warangal"),
    "tripura": ("tripura", "agartala"),
    "uttar pradesh": ("uttar pradesh", "lucknow", "noida", "kanpur", "agra", "ghaziabad"),
    "uttarakhand": ("uttarakhand", "dehradun", "haridwar"),
    "west bengal": ("west bengal", "kolkata", "calcutta", "siliguri", "durgapur"),
}

INDIA_REGION_ALIASES = {
    "bangalore": INDIA_REGION_VARIANTS["karnataka"],
    "bengaluru": INDIA_REGION_VARIANTS["karnataka"],
    "bombay": INDIA_REGION_VARIANTS["maharashtra"],
    "mumbai": INDIA_REGION_VARIANTS["maharashtra"],
    "pune": INDIA_REGION_VARIANTS["maharashtra"],
    "hyderabad": INDIA_REGION_VARIANTS["telangana"],
    "madras": INDIA_REGION_VARIANTS["tamil nadu"],
    "chennai": INDIA_REGION_VARIANTS["tamil nadu"],
    "new delhi": INDIA_REGION_VARIANTS["delhi ncr"],
    "gurgaon": INDIA_REGION_VARIANTS["delhi ncr"],
    "gurugram": INDIA_REGION_VARIANTS["delhi ncr"],
    "noida": INDIA_REGION_VARIANTS["delhi ncr"],
    "trivandrum": INDIA_REGION_VARIANTS["kerala"],
    "kochi": INDIA_REGION_VARIANTS["kerala"],
    "cochin": INDIA_REGION_VARIANTS["kerala"],
    "calcutta": INDIA_REGION_VARIANTS["west bengal"],
    "kolkata": INDIA_REGION_VARIANTS["west bengal"],
    "orissa": INDIA_REGION_VARIANTS["odisha"],
}

INDIA_WIDE_TERMS = tuple(sorted({
    "india",
    *(term for terms in INDIA_REGION_VARIANTS.values() for term in terms),
    *(term for terms in INDIA_REGION_ALIASES.values() for term in terms),
}))

LOCATION_SUGGESTIONS = [
    "Remote",
    "Work from home",
    "Remote | India",
    "Worldwide",
    "India",
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chandigarh",
    "Chhattisgarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi",
    "Delhi NCR",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jammu and Kashmir",
    "Karnataka",
    "Kerala",
    "Ladakh",
    "Lakshadweep",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Puducherry",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
    "Pune",
    "Bengaluru",
    "Hyderabad",
    "Chennai",
    "Mumbai",
]

QUICK_LOCATION_FILTERS = [
    "Remote",
    "Remote | India",
    "India",
    "Delhi NCR",
    "Karnataka",
    "Maharashtra",
    "Tamil Nadu",
    "Telangana",
]


def normalize_location_text(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9\s|-]", " ", str(value or "").lower())
    return re.sub(r"\s+", " ", normalized).strip()


def split_location_targets(value: str) -> list[str]:
    raw_value = str(value or "").strip()
    if not raw_value:
        return []
    return [part.strip() for part in re.split(r"[|\n;]+", raw_value) if part.strip()]


def expand_location_terms(target: str) -> tuple[str, ...]:
    normalized_target = normalize_location_text(target)
    if not normalized_target:
        return tuple()
    if normalized_target in REMOTE_SEARCH_VALUES:
        return REMOTE_LOCATION_TERMS
    if normalized_target in INDIA_SEARCH_VALUES:
        return INDIA_WIDE_TERMS
    if normalized_target in INDIA_REGION_VARIANTS:
        return INDIA_REGION_VARIANTS[normalized_target]
    if normalized_target in INDIA_REGION_ALIASES:
        return INDIA_REGION_ALIASES[normalized_target]
    return (str(target).strip(),)


def build_location_query(raw_location: str) -> Q:
    targets = split_location_targets(raw_location)
    if not targets:
        return Q()

    location_query = Q()
    for target in targets:
        single_target_query = Q()
        for term in expand_location_terms(target):
            single_target_query |= Q(location__icontains=term)
        location_query |= single_target_query
    return location_query


def location_matches_target(job_location: str, target: str) -> bool:
    normalized_location = normalize_location_text(job_location)
    normalized_target = normalize_location_text(target)
    if not normalized_target:
        return True
    if not normalized_location and normalized_target in REMOTE_SEARCH_VALUES:
        return True
    return any(normalize_location_text(term) in normalized_location for term in expand_location_terms(target))


def filter_jobs_by_location_targets(jobs: list[dict], raw_location: str) -> list[dict]:
    targets = split_location_targets(raw_location)
    if not targets:
        return list(jobs)
    return [
        job for job in jobs
        if any(location_matches_target(job.get("location", ""), target) for target in targets)
    ]


def deduplicate_jobs(jobs: list[dict]) -> list[dict]:
    deduplicated = {}
    for job in jobs:
        key = (
            str(job.get("title") or "").strip().lower(),
            str(job.get("company") or "").strip().lower(),
            str(job.get("location") or "").strip().lower(),
            str(job.get("apply_link") or "").strip().lower(),
        )
        deduplicated[key] = job
    return list(deduplicated.values())
