"""Canonical candidate identity for all job-application scripts.

Last name: Bayo Alemany (single field — do not split).
First name: Martí (preferred) or Marti when forms reject diacritics.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

W = Path(__file__).resolve().parent
PREFS = W / "candidate_prefs.json"
# Default CV: 0020_raw; override with APPLY_CV_FILE=... (e.g. Desktop 021_cc)
CV_FILE = (
    (os.environ.get("APPLY_CV_FILE") or "").strip()
    or "0020_raw_marti__bayo_alemany_curriculum.pdf"
)
CV_FILE_RAW = "0020_raw_marti__bayo_alemany_curriculum.pdf"
CV_FILE_CC = "0021_cc_marti__bayo_alemany_curriculum.pdf"
CERTS_FILE = "Marti__Bayo_Alemany_certificates_2020_compressed.pdf"  # work certificates 2020
# Prefer uncompressed Desktop copy when present in workspace
if (W / "Marti__Bayo_Alemany_certificates_2020.pdf").is_file() and not (
    os.environ.get("APPLY_CERTS_FILE") or ""
).strip():
    # keep compressed as default unless full Desktop PDF preferred via env
    pass
_certs_override = (os.environ.get("APPLY_CERTS_FILE") or "").strip()
if _certs_override:
    CERTS_FILE = _certs_override
ACADEMIC_CERTS_FILE = "etsetb_with_equivalences_and_government_register.pdf"  # academic ETSETB
CV = str((W / CV_FILE).resolve())
CV_RAW = str((W / CV_FILE_RAW).resolve())
CV_CC = str((W / CV_FILE_CC).resolve())
CERTS = str((W / CERTS_FILE).resolve())
ACADEMIC_CERTS = str((W / ACADEMIC_CERTS_FILE).resolve())
# Extra supporting docs uploaded after primary work certs when forms allow more files
EXTRA_CERTS = [ACADEMIC_CERTS] if (W / ACADEMIC_CERTS_FILE).is_file() else []
CV_STEM = Path(CV_FILE).stem[:40]

FIRST = "Martí"
FIRST_ASCII = "Marti"
FIRST_ALT = "Martí"
LAST = "Bayo Alemany"
FULL = f"{FIRST} {LAST}"
FULL_ALT = f"{FIRST_ASCII} {LAST}"

_ES_CA_RE = re.compile(
    r"\.es\b|spain|españa|espana|barcelona|madrid|valencia|sevilla|"
    r"cataluña|catalunya|apellido|nombre|\.cat\b",
    re.I,
)


def _load_prefs() -> dict:
    if PREFS.exists():
        try:
            return json.loads(PREFS.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


_prefs = _load_prefs()
_contact = _prefs.get("contact") or {}
_salary = _prefs.get("salary_target_eur") or {}
_residence = _prefs.get("residence") or {}
_addr = _prefs.get("address") or {}
_edu = _prefs.get("education") or {}

# Prefer prefs; fall back to user-specified identity
PROFILE = {
    "first": FIRST,
    "first_ascii": FIRST_ASCII,
    "first_alt": FIRST_ALT,
    "last": LAST,
    "full": FULL,
    "full_alt": FULL_ALT,
    "email": _contact.get("email")
    or _prefs.get("email")
    or "martibayoalemany@gmail.com",
    "phone": _prefs.get("phone") or _contact.get("phone") or "+4917663325199",
    "title": _prefs.get("professional_title") or "Telecommunications Engineer",
    "level": _prefs.get("education_level") or _edu.get("level") or "Master",
    "city": _residence.get("city") or "Karlsruhe",
    "country": _residence.get("country") or "Germany",
    "residence": _residence.get("city") or "Karlsruhe",
    "residence_country": _residence.get("country") or "Germany",
    "address_street": _addr.get("street") or "Vorholzstrasse 31",
    "address_postal": _addr.get("postal_code") or "76317",
    "address_city": _addr.get("city") or "Karlsruhe",
    "address_country": _addr.get("country") or "Germany",
    "address_full": _addr.get("full")
    or "Vorholzstrasse 31, 76317 Karlsruhe, Germany",
    "school": _prefs.get("university")
    or "Universitat Politècnica de Catalunya",
    "school_aliases": _prefs.get("university_aliases")
    or [
        "BarcelonaTech",
        "Polytechnical University of Catalonia",
        "Universitat Politècnica de Catalunya",
        "Universitat Politecnica de Catalunya",
        "UPC",
        "ETSETB",
    ],
    "school_fallback": "Purdue University",
    "school_fallback_years": "2001 (one year)",
    # University degree notes: year 2003 (user 2026-07-25)
    "degree_year": str(_edu.get("degree_year") or "2003"),
    "degree_year_start": str(_edu.get("degree_year_start") or "2003"),
    "degree_year_end": str(_edu.get("degree_year_end") or "2003"),
    "graduation_year": str(_edu.get("graduation_year") or _edu.get("degree_year") or "2003"),
    # Company certificates: 2020 compressed pack; academic ETSETB separate
    "certificates_year": "2020",
    "certificates_label": "Company certificates 2020 (compressed)",
    "academic_certificates": ACADEMIC_CERTS_FILE,
    "academic_certificates_label": "ETSETB academic certificates + equivalences / government register",
    "gpa": _edu.get("gpa") or "2.6/4.0",
    "gpa_value": "2.6",
    "gpa_scale": "4.0",
    # Salary expectations (user): €70,400–€120,000 annual gross
    "salary_min": int(_salary.get("min") or 70400),
    "salary_max": int(_salary.get("max") or 120000),
    "salary_currency": "EUR",
    "salary": (
        f"{_salary.get('min', 70400)}-{_salary.get('max', 120000)} EUR"
        if _salary
        else "70400-120000 EUR"
    ),
    "salary_display": (
        f"€{int(_salary.get('min') or 70400):,}–€{int(_salary.get('max') or 120000):,}"
        .replace(",", ",")
    ),
    "salary_mid": str(int((_salary.get("min") or 70400) + (_salary.get("max") or 120000)) // 2),
    "cover": (
        "CV (0020_raw), ETSETB academic certificates, and company certificates 2020 attached. "
        "Telecommunications Engineer / Technology Lead / Software Architect (L5) — professional roles only "
        "(not Praktikum / internship / Werkstudent; not facility management). "
        "Open to remote, hybrid, onsite, permanent, and short-term / fixed-term contracts. "
        "Universities: UPC / BarcelonaTech / ETSETB / Polytechnical University of Catalonia "
        "(degree notes year 2003); fallback Purdue University (2001, one year). GPA 2.6/4.0. "
        "Salary expectations: €70,400–€120,000 gross per year. "
        "Gender: Male / Man. "
        "EU work authorization: Yes. "
        "EEO: race/ethnicity White; not a veteran; no disability. "
        "Based in Karlsruhe, Germany."
    ),
    "gender": _prefs.get("gender") or "Male",
    "gender_aliases": _prefs.get("gender_aliases")
    or ["Male", "Man", "Männlich", "Homme", "Masculino"],
    "work_authorization_eu": "Yes",
    "eeo": {
        "race": "White",
        "protected_veteran": "No",
        "disability": "No",
    },
}


def salary_for_field(field_name: str = "") -> str:
    """Pick the best salary string for a form field (min/max/range)."""
    name = (field_name or "").lower()
    smin = str(PROFILE.get("salary_min") or 70400)
    smax = str(PROFILE.get("salary_max") or 120000)
    if any(k in name for k in ("min", "from", "lower", "minimum", "base_min")):
        return smin
    if any(k in name for k in ("max", "to", "upper", "maximum", "ceiling", "top")):
        return smax
    if any(k in name for k in ("mid", "target", "desired", "expect", "wunsch", "expectation")):
        return PROFILE.get("salary") or f"{smin}-{smax} EUR"
    return PROFILE.get("salary") or f"{smin}-{smax} EUR"


# Company-specific “Why do you want to work here?” answers (user-editable in prefs)
_DEFAULT_WHY = {
    "discord": (
        "I want to work at Discord because it sits at the intersection of real-time systems, "
        "community, and high-scale product engineering—areas I care about deeply as a "
        "Telecommunications Engineer and Technology Lead. Discord’s product is mission-critical "
        "for millions of people who collaborate, learn, and build together, which means "
        "reliability, latency, and thoughtful platform design matter every day.\n\n"
        "I am motivated by Discord’s engineering culture around shipping durable services, "
        "improving developer and community experience, and solving hard distributed-systems "
        "problems without losing the human-centered product feel. My background across software "
        "architecture, cloud, DevOps, and large-client delivery (including complex multi-team "
        "environments) aligns with building and evolving platforms that must stay fast and "
        "stable under growth.\n\n"
        "I would be excited to contribute as a senior/lead engineer: raising the quality of "
        "systems and delivery, mentoring through clear technical decisions, and helping Discord "
        "continue to be the best place for communities to connect—while learning from a team "
        "that operates at global scale."
    ),
}


def why_work_at(company: str = "", *, page_url: str = "", title: str = "") -> str:
    """Answer for fields like “Why do you want to work at {Company}?”."""
    blob = f"{company or ''} {page_url or ''} {title or ''}".lower()
    prefs_why = (_prefs.get("motivation") or {}).get("why_company") or {}
    # Prefer explicit prefs keys
    for key, text in prefs_why.items():
        if key and str(key).lower() in blob and text:
            return str(text).strip()
    # Built-in company answers
    for key, text in _DEFAULT_WHY.items():
        if key in blob:
            return text.strip()
    # Infer company name for generic template
    co = (company or "").strip() or "your company"
    if not company:
        for hint in ("discord", "github", "google", "microsoft", "amazon", "meta", "apple"):
            if hint in blob:
                co = hint.title() if hint != "discord" else "Discord"
                if hint in _DEFAULT_WHY:
                    return _DEFAULT_WHY[hint]
                break
    generic = (prefs_why.get("default") or prefs_why.get("*") or "").strip()
    if generic:
        return generic.replace("{company}", co).replace("{Company}", co)
    return (
        f"I want to work at {co} because the role matches my experience as a Telecommunications "
        f"Engineer / Technology Lead in software architecture, cloud, and high-quality delivery. "
        f"I am motivated by {co}'s product impact and engineering standards, and I want to "
        f"contribute senior technical leadership—designing reliable systems, improving delivery, "
        f"and collaborating across teams—while continuing to grow in a strong engineering culture. "
        f"I am based in Karlsruhe, Germany, open to remote/hybrid/onsite arrangements, and ready "
        f"to contribute from day one with professional (non-internship) experience."
    )


def load_employment_snippets() -> dict:
    p = W / "employment_snippets.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def employment_textbox(employer: str) -> str:
    """Single textbox content for Infosys or Accenture consolidated experience."""
    sn = load_employment_snippets()
    key = (employer or "").lower()
    if "infosys" in key:
        return sn.get("infosys_single_textbox") or ""
    if "accenture" in key:
        return sn.get("accenture_single_textbox") or ""
    return ""


def pick_first_name(context: str = "", *, ascii_ok: bool = False) -> str:
    """Use Martí by default; Marti when forms need ASCII."""
    if ascii_ok:
        return FIRST_ASCII
    if context and re.search(r"ascii|without accent|latin1", context, re.I):
        return FIRST_ASCII
    return FIRST


def name_for_field(field_hint: str = "", page_context: str = "") -> str | None:
    """Map a form field hint to the correct name part."""
    h = (field_hint or "").lower()
    if any(k in h for k in ("first", "vorname", "prenom", "given", "nombre", "fname")):
        if "last" in h or "apellido" in h or "surname" in h or "family" in h:
            return None
        return pick_first_name(page_context or h)
    if any(
        k in h
        for k in (
            "last",
            "nachname",
            "surname",
            "family",
            "apellido",
            "lname",
        )
    ):
        if "first" in h or "nombre" in h or "given" in h:
            return None
        return LAST
    return None


def university_search_order() -> list[str]:
    aliases = list(PROFILE.get("school_aliases") or [])
    primary = PROFILE.get("school") or ""
    order = []
    for u in [primary] + aliases + [PROFILE.get("school_fallback") or "Purdue University"]:
        if u and u not in order:
            order.append(u)
    return order
