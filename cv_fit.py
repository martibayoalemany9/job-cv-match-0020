"""Score job titles/descriptions against the 0020_raw CV text.

Used before applying: skip roles that do not fit Technology Lead / software profile.

Well-paid override (user 2026-07-25): low CV-fit scores may still apply when
compensation is clearly high enough (default ≥ €70,400 gross / year).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

W = Path(__file__).resolve().parent
CV_TEXT_PATH = W / "_cv_0020_extracted.txt"
CV_PDF = W / "0020_raw_marti__bayo_alemany_curriculum.pdf"

# Apply even with low fit when estimated pay ≥ geo floor (EUR gross annual)
# Default / DE-NL-CH-Nordics floor; Spain (Barcelona/Madrid) lower — user is from Spain
WELL_PAID_MIN_EUR = int(os.environ.get("WELL_PAID_MIN_EUR", "70400") or "70400")
SPAIN_MIN_EUR = int(os.environ.get("SPAIN_MIN_EUR", "55000") or "55000")
EU_OTHER_MIN_EUR = int(os.environ.get("EU_OTHER_MIN_EUR", "60000") or "60000")
ALLOW_LOW_FIT_IF_WELL_PAID = os.environ.get("ALLOW_LOW_FIT_IF_WELL_PAID", "1").lower() in (
    "1",
    "true",
    "yes",
)

# Country → minimum EUR for "well paid enough" / low-fit override
_GEO_SALARY_FLOOR: list[tuple[re.Pattern[str], int, str]] = [
    # Spain — Barcelona / Madrid / general ES (user origin → lower floor)
    (
        re.compile(
            r"\bspain\b|\bespaña\b|\bespana\b|\bes\b|barcelona|madrid|valencia|"
            r"sevilla|bilbao|málaga|malaga|zaragoza|\.es/|/es/|catalunya|cataluña",
            re.I,
        ),
        SPAIN_MIN_EUR,
        "ES",
    ),
    (
        re.compile(
            r"\bgermany\b|\bdeutschland\b|berlin|munich|münchen|muenchen|hamburg|"
            r"frankfurt|stuttgart|karlsruhe|cologne|köln|koeln|düsseldorf|"
            r"\bde\b|\.de/|/de/",
            re.I,
        ),
        WELL_PAID_MIN_EUR,
        "DE",
    ),
    (
        re.compile(
            r"\bnetherlands\b|\bholland\b|amsterdam|rotterdam|utrecht|eindhoven|"
            r"den haag|the hague|\bnl\b|\.nl/|/nl/",
            re.I,
        ),
        WELL_PAID_MIN_EUR,
        "NL",
    ),
    (
        re.compile(
            r"\bswitzerland\b|\bschweiz\b|zurich|zürich|geneva|basel|\bch\b",
            re.I,
        ),
        max(WELL_PAID_MIN_EUR, 85000),
        "CH",
    ),
    (
        re.compile(
            r"\baustria\b|\bösterreich\b|oesterreich|vienna|wien|\bat\b",
            re.I,
        ),
        WELL_PAID_MIN_EUR,
        "AT",
    ),
    (
        re.compile(
            r"\bbelgium\b|\bbelgië\b|belgique|brussels|bruxelles|antwerp|\bbe\b",
            re.I,
        ),
        WELL_PAID_MIN_EUR,
        "BE",
    ),
    (
        re.compile(
            r"\bfrance\b|\bparis\b|lyon|toulouse|marseille|\bfr\b|\.fr/",
            re.I,
        ),
        WELL_PAID_MIN_EUR,
        "FR",
    ),
    (
        re.compile(
            r"\bitaly\b|\bitalia\b|milan|milano|rome|roma|\bit\b",
            re.I,
        ),
        EU_OTHER_MIN_EUR,
        "IT",
    ),
    (
        re.compile(
            r"\bsweden\b|stockholm|\bnorway\b|oslo|\bfinland\b|helsinki|"
            r"\bdenmark\b|copenhagen|\bse\b|\bno\b|\bfi\b|\bdk\b",
            re.I,
        ),
        WELL_PAID_MIN_EUR,
        "NORDIC",
    ),
    (
        re.compile(
            r"\bportugal\b|lisbon|lisboa|porto|\bpt\b|"
            r"\bpoland\b|warsaw|warszawa|\bpl\b|"
            r"\bczech\b|prague|praha|\bcz\b|"
            r"\bireland\b|dublin|\bie\b|"
            r"\bluxembourg\b|\blu\b|"
            r"\bremote\s*eu\b|\beurope\b",
            re.I,
        ),
        EU_OTHER_MIN_EUR,
        "EU_OTHER",
    ),
]


def detect_geo_code(*texts: str) -> str:
    """Best-effort country/region code from job location text."""
    blob = " ".join(t for t in texts if t) or ""
    if not blob.strip():
        return "UNKNOWN"
    for rx, _floor, code in _GEO_SALARY_FLOOR:
        if rx.search(blob):
            return code
    return "UNKNOWN"


def salary_floor_eur(*texts: str) -> tuple[int, str]:
    """Return (min_eur_floor, geo_code) for this job's location."""
    blob = " ".join(t for t in texts if t) or ""
    for rx, floor, code in _GEO_SALARY_FLOOR:
        if rx.search(blob):
            return int(floor), code
    return WELL_PAID_MIN_EUR, "DEFAULT"

# Skills / domains evidenced on 0020 raw CV (and close synonyms)
CV_SKILL_GROUPS: dict[str, list[str]] = {
    "software": [r"\bsoftware\b", r"software\s*development", r"software\s*engineer"],
    "java": [r"\bjava\b", r"spring\s*boot", r"jvm"],
    "python": [r"\bpython\b"],
    "cpp": [r"\bc\+\+\b", r"\bcpp\b"],
    "javascript": [r"\bjavascript\b", r"\btypescript\b", r"\bnode\.?js\b", r"\breact\b"],
    "devops": [r"\bdevops\b", r"\bci/?cd\b", r"github\s*actions", r"gitlab", r"jenkins"],
    "cloud": [r"\bcloud\b", r"\bazure\b", r"\bgcp\b", r"google\s*cloud", r"\baws\b", r"btp"],
    "sap": [r"\bsap\b", r"\babap\b", r"sap\s*btp"],
    "architecture": [r"\barchitect", r"architecture", r"technology\s*lead", r"tech\s*lead"],
    "ai": [r"\bai\b", r"\bllm\b", r"machine\s*learning", r"generative\s*ai", r"hugging\s*face"],
    "terraform": [r"\bterraform\b", r"infrastructure\s*as\s*code", r"\biac\b"],
    "containers": [r"\bdocker\b", r"\bkubernetes\b", r"\bpodman\b", r"\bk8s\b", r"\bkyma\b"],
    "security": [r"\bsecurity\b", r"\bdevops\b", r"secure\s*sdlc", r"do-?178", r"do-?254"],
    "agile": [r"\bagile\b", r"\bscrum\b"],
    "integration": [r"integration", r"enterprise", r"microservices"],
    "lead": [
        r"technology\s*lead",
        r"tech(?:nical)?\s*lead",
        r"\blead\b",
        r"\bstaff\b",
        r"\bprincipal\b",
        r"\bsenior\b",
        r"engineering\s*manager",
    ],
    "architect": [
        r"software\s*architect",
        r"solution[s]?\s*architect",
        r"\barchitect\b",
        r"systems?\s*architect",
        r"enterprise\s*architect",
    ],
}

# Prefer "software"; also accept clear SWE titles (java/devops/backend engineer, etc.)
REQUIRE_SOFTWARE = re.compile(r"\bsoftware\b", re.I)
REQUIRE_SW_RELATED = re.compile(
    r"\bsoftware\b|"
    r"(java|kotlin|rust|python|devops|backend|fullstack|full[- ]stack|platform|cloud)\s*"
    r"(engineer|developer|architect)|"
    r"(engineer|developer|architect).{0,24}(java|kotlin|rust|python|devops|backend)|"
    r"technology\s*lead|tech(?:nical)?\s*lead|software\s*engineer|"
    r"software\s*architect|solution[s]?\s*architect|systems?\s*architect|"
    r"enterprise\s*architect|application\s*architect|cloud\s*architect|"
    r"platform\s*architect|technical\s*architect|"
    r"engineering\s*manager|head\s*of\s*(?:engineering|software|technology)|"
    r"staff\s*(?:software\s*)?engineer|principal\s*(?:software\s*)?(?:engineer|architect)|"
    r"platform\s*reliability|infrastructure\s*engineering|development\s*infrastructure",
    re.I,
)

# Hard reject even if some skills match (PhD / doctoral roles are NOT rejected)
REJECT = re.compile(
    r"werkstudent|working\s*student|(?<!phd )(?<!ph\.d )(?<!ph.d )\bstudent\b|"
    r"praktikum|internship|\bintern\b|"
    r"duales?\s*studium|junior|\bjr\.?\b|entry[- ]level|ausbildung|apprentice|"
    r"facility|hausmeister|graduate\s+(programme|program|scheme)|"
    r"sales\s+only|account\s+executive|recruiter",
    re.I,
)

_cv_cache: str | None = None
_cv_skills: set[str] | None = None


def load_cv_text() -> str:
    global _cv_cache
    if _cv_cache is not None:
        return _cv_cache
    if CV_TEXT_PATH.exists():
        _cv_cache = CV_TEXT_PATH.read_text(encoding="utf-8", errors="replace")
        return _cv_cache
    # try extract once
    try:
        import pypdf

        if CV_PDF.exists():
            r = pypdf.PdfReader(str(CV_PDF))
            text = ""
            for p in r.pages:
                text += p.extract_text() or ""
            CV_TEXT_PATH.write_text(text, encoding="utf-8")
            _cv_cache = text
            return text
    except Exception:
        pass
    _cv_cache = ""
    return ""


def cv_skill_hits() -> set[str]:
    global _cv_skills
    if _cv_skills is not None:
        return _cv_skills
    text = load_cv_text().lower()
    hits = set()
    for name, pats in CV_SKILL_GROUPS.items():
        for pat in pats:
            if re.search(pat, text, re.I):
                hits.add(name)
                break
    _cv_skills = hits
    return hits


def parse_salary_eur(*texts: str) -> int | None:
    """Best-effort annual EUR estimate from free text / CSV salary fields.

    Returns the highest plausible annual figure found, or None.
    """
    blob = " ".join(t for t in texts if t) or ""
    if not blob.strip():
        return None
    low = blob.lower().replace("\u00a0", " ").replace(",", "")
    amounts: list[int] = []

    # Explicit EUR / € figures (k / k€ / 000)
    for m in re.finditer(
        r"(?:€|eur|euro[s]?)\s*([0-9]{2,3}(?:\.[0-9]+)?)\s*[kK]\b|"
        r"([0-9]{2,3}(?:\.[0-9]+)?)\s*[kK]\s*(?:€|eur|euro[s]?)?|"
        r"(?:€|eur)\s*([0-9]{4,7})\b|"
        r"\b([0-9]{4,7})\s*(?:€|eur|euro[s]?|/year|/yr|per year|p\.?a\.?|gross)\b|"
        r"\b([0-9]{2,3})\s*[-–]\s*([0-9]{2,3})\s*[kK]\b|"
        r"\b([5-9][0-9]|1[0-4][0-9])\s*k\b",  # 50k+ including Spain €55k
        low,
        re.I,
    ):
        groups = [g for g in m.groups() if g]
        for g in groups:
            try:
                v = float(g)
            except ValueError:
                continue
            if v < 200:  # treat as thousands
                amounts.append(int(v * 1000))
            elif 20000 <= v <= 400000:
                amounts.append(int(v))

    # USD often listed for US roles — rough EUR ≈ USD * 0.92 for threshold compare
    for m in re.finditer(
        r"(?:\$|usd)\s*([0-9]{2,3})\s*[kK]\b|"
        r"([0-9]{2,3})\s*[kK]\s*(?:\$|usd)|"
        r"(?:\$|usd)\s*([0-9]{5,7})\b",
        low,
        re.I,
    ):
        for g in m.groups():
            if not g:
                continue
            try:
                v = float(g)
            except ValueError:
                continue
            if v < 200:
                amounts.append(int(v * 1000 * 0.92))
            elif 20000 <= v <= 400000:
                amounts.append(int(v * 0.92))

    # CSV style "70400-90000 EUR" / "65000-90000"
    for m in re.finditer(
        r"\b([5-9][0-9]{4}|1[0-4][0-9]{4})\s*[-–/]\s*([5-9][0-9]{4}|1[0-4][0-9]{4})\b",
        low,
    ):
        try:
            amounts.append(max(int(m.group(1)), int(m.group(2))))
        except ValueError:
            pass
    for m in re.finditer(r"\b([5-9][0-9]{4}|1[0-2][0-9]{4})\b", low):
        try:
            v = int(m.group(1))
            if 50000 <= v <= 250000:
                amounts.append(v)
        except ValueError:
            pass

    if not amounts:
        return None
    return max(amounts)


def is_well_paid(
    *texts: str,
    min_eur: int | None = None,
) -> tuple[bool, int | None, int, str]:
    """True when pay ≥ geo-specific floor.

    Returns (ok, pay_or_none, floor_used, geo_code).
    Spain (Barcelona/Madrid) floor defaults to SPAIN_MIN_EUR (55000).
    DE/NL/FR/… use WELL_PAID_MIN_EUR (70400) unless overridden.
    """
    floor_geo, code = salary_floor_eur(*texts)
    floor = int(min_eur if min_eur is not None else floor_geo)
    pay = parse_salary_eur(*texts)
    if pay is None:
        return False, None, floor, code
    return pay >= floor, pay, floor, code


def job_fit_score(
    title: str = "",
    description: str = "",
    company: str = "",
    *,
    min_score: int = 3,
    salary_hint: str = "",
    allow_well_paid_low_fit: bool | None = None,
) -> tuple[bool, int, str]:
    """Return (fits, score, reason). Requires 'software' and CV skill overlap.

    Technical PhD / doctoral positions get a dedicated pass with lower software gate.
    Low fit + well-paid roles may still pass (user: apply if well paid).
    """
    blob = f"{title or ''} {description or ''} {company or ''}"
    if not blob.strip():
        return False, 0, "empty_job"

    allow_wp = (
        ALLOW_LOW_FIT_IF_WELL_PAID
        if allow_well_paid_low_fit is None
        else bool(allow_well_paid_low_fit)
    )
    pay_ok, pay, pay_floor, geo_code = is_well_paid(
        salary_hint, blob, description or "", title or "", company or ""
    )

    # PhD track: allow technical doctoral roles even without literal "software"
    try:
        from role_filter import is_phd_role, PHD_TECH_FIELD

        if is_phd_role(title, "", company, description):
            score = 4
            matched = ["phd"]
            if PHD_TECH_FIELD.search(blob):
                score += 2
                matched.append("tech_field")
            for name, pats in CV_SKILL_GROUPS.items():
                for pat in pats:
                    if re.search(pat, blob, re.I):
                        matched.append(name)
                        score += 1
                        break
            fits = score >= min(min_score, 3)
            return fits, score, f"phd_track score={score} skills={','.join(sorted(set(matched)))}"
    except Exception:
        pass

    if REJECT.search(blob):
        return False, 0, "rejected_student_junior_or_non_eng"
    if not REQUIRE_SW_RELATED.search(blob):
        # Well-paid professional eng titles without "software" keyword still allowed
        if (
            allow_wp
            and pay_ok
            and re.search(
                r"engineer|architect|developer|sre|devops|platform|infrastructure|"
                r"engineering\s*manager|technology|"
                r"(?:ai|cloud|data|it|sap|security|solutions?)\s*consultant|"
                r"technical\s*consultant|solution[s]?\s*consultant",
                title or "",
                re.I,
            )
            and not is_weak_seniority(title)
        ):
            return (
                True,
                1,
                f"well_paid_no_software_kw_override pay≈{pay}€ "
                f"floor={pay_floor}€ geo={geo_code}",
            )
        return False, 0, "missing_keyword_software"
    if is_weak_seniority(title):
        # still allow if software engineer senior-ish in title
        pass

    cv_hits = cv_skill_hits()
    matched = []
    score = 0
    for name, pats in CV_SKILL_GROUPS.items():
        if name not in cv_hits and name not in ("software", "lead"):
            # only score skills present on CV
            if name not in cv_hits:
                continue
        for pat in pats:
            if re.search(pat, blob, re.I):
                matched.append(name)
                score += 2 if name in ("software", "java", "python", "cloud", "devops", "architecture", "lead") else 1
                break
    # title seniority bonus — prefer tech lead / architect over plain senior
    if re.search(
        r"technology\s*lead|tech(?:nical)?\s*lead|software\s*architect|"
        r"solution[s]?\s*architect|systems?\s*architect",
        title or "",
        re.I,
    ):
        score += 6
        if "lead" not in matched:
            matched.append("lead")
        if re.search(r"architect", title or "", re.I) and "architect" not in matched:
            matched.append("architect")
    elif re.search(r"staff|principal|\blead\b|engineering\s*manager", title or "", re.I):
        score += 3
    elif re.search(r"\bsenior\b", title or "", re.I):
        score += 1  # plain senior — weaker than lead/architect
    # java/devops engineer titles count as software-related even without the word software
    if re.search(r"java|kotlin|rust|devops|backend|platform", title or "", re.I):
        score += 2
        if "software" not in matched:
            matched.append("software_related")
    # location-agnostic fit
    fits = score >= min_score and bool(REQUIRE_SW_RELATED.search(blob))
    if fits:
        return True, score, f"score={score} skills={','.join(sorted(set(matched))) or 'none'}"

    # Low fit but well paid for that geo → still apply
    # Spain floor €55k (Barcelona/Madrid); DE/NL/… €70.4k; other EU €60k
    if allow_wp and pay_ok and not REJECT.search(blob) and not is_weak_seniority(title):
        return (
            True,
            score,
            f"low_fit_well_paid_override score={score} pay≈{pay}€ "
            f"floor={pay_floor}€ geo={geo_code} "
            f"skills={','.join(sorted(set(matched))) or 'none'}",
        )

    # Spain home market: good-enough titles with unknown pay still get a soft pass
    # only when score is close (score >= min_score-1) — not for zero-fit junk
    if (
        allow_wp
        and geo_code == "ES"
        and pay is None
        and score >= max(1, min_score - 1)
        and not REJECT.search(blob)
        and not is_weak_seniority(title)
        and REQUIRE_SW_RELATED.search(blob)
    ):
        return (
            True,
            score,
            f"spain_home_market_soft_pass score={score} pay=unknown "
            f"floor={pay_floor}€ skills={','.join(sorted(set(matched))) or 'none'}",
        )

    reason = (
        f"low_fit score={score} skills={','.join(sorted(set(matched))) or 'none'} "
        f"min={min_score} geo={geo_code} floor={pay_floor}€"
        + (f" pay≈{pay}€" if pay else " pay=unknown")
    )
    return False, score, reason


def is_weak_seniority(title: str) -> bool:
    t = title or ""
    if re.search(r"junior|intern|student|praktikum|werkstudent|duales", t, re.I):
        return True
    return False


def fits_cv(title: str = "", description: str = "", company: str = "", *, min_score: int = 3) -> bool:
    ok, _, _ = job_fit_score(title, description, company, min_score=min_score)
    return ok
