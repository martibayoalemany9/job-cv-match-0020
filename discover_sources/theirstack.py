"""TheirStack API — company-level “who’s hiring software”.

Env:
  THEIRSTACK_API_KEY

API shape may evolve; this client uses a conservative REST pattern and
fails soft when the key is missing or the endpoint errors.
Docs: https://theirstack.com (check current OpenAPI)
"""
from __future__ import annotations

import json
import urllib.request

from discover_sources.common import W, env, log, normalize_job

LOG = W / "discover_sources_run.log"


def discover_theirstack() -> list[dict]:
    from discover_sources.common import load_env

    load_env(force_file=True)
    key = env("THEIRSTACK_API_KEY")
    if not key:
        log("theirstack: no THEIRSTACK_API_KEY — skip", log_path=LOG)
        return []

    base = env("THEIRSTACK_BASE", "https://api.theirstack.com/v1")
    # Free/"check" tokens: keep queries small (limit≤10, few titles) to avoid 403
    limit = min(40, int(env("THEIRSTACK_LIMIT", "10") or "10"))
    titles = [
        t.strip()
        for t in env(
            "THEIRSTACK_TITLES",
            "Technology Lead,Tech Lead,Software Architect,Solutions Architect,Principal Software Engineer",
        ).split(",")
        if t.strip()
    ]
    query = {
        "page": 0,
        "limit": limit,
        "job_title_or": titles,
        "posted_at_max_age_days": int(env("THEIRSTACK_MAX_AGE_DAYS", "30") or "30"),
    }
    countries = env("THEIRSTACK_COUNTRIES", "")
    if countries:
        query["job_country_code_or"] = [c.strip() for c in countries.split(",") if c.strip()]
    url = f"{base.rstrip('/')}/jobs/search"
    body = json.dumps(query).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        err_body = ""
        if hasattr(e, "read"):
            try:
                err_body = e.read().decode()[:300]
            except Exception:
                pass
        log(f"theirstack error: {e} {err_body}", log_path=LOG)
        # Retry once with minimal free-tier query
        try:
            body2 = json.dumps(
                {
                    "page": 0,
                    "limit": 5,
                    "job_title_or": ["Tech Lead", "Software Architect"],
                    "posted_at_max_age_days": 14,
                }
            ).encode()
            req2 = urllib.request.Request(
                url,
                data=body2,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req2, timeout=45) as resp:
                data = json.loads(resp.read().decode())
            log("theirstack: retry minimal query OK", log_path=LOG)
        except Exception as e2:
            log(f"theirstack retry failed: {e2}", log_path=LOG)
            return []

    items = data if isinstance(data, list) else (
        data.get("data") or data.get("jobs") or data.get("results") or []
    )
    out: list[dict] = []
    for j in items or []:
        if not isinstance(j, dict):
            continue
        title = j.get("job_title") or j.get("title") or ""
        company = (
            j.get("company")
            or (j.get("company_object") or {}).get("name")
            or j.get("company_name")
            or "Unknown"
        )
        if isinstance(company, dict):
            company = (
                company.get("name")
                or company.get("company")
                or company.get("domain")
                or "Unknown"
            )
        url_j = (
            j.get("final_url")
            or j.get("source_url")
            or j.get("url")
            or j.get("job_url")
            or ""
        )
        loc = (
            j.get("long_location")
            or j.get("short_location")
            or j.get("location")
            or j.get("job_location")
            or ""
        )
        if isinstance(loc, dict):
            loc = loc.get("name") or loc.get("city") or ""
        row = normalize_job(
            source="theirstack",
            company=str(company),
            title=str(title),
            url=str(url_j),
            location=str(loc),
            description=str(j.get("description") or j.get("description_text") or "")[:1500],
            extra={"raw_id": j.get("id"), "date_posted": j.get("date_posted")},
        )
        if row:
            out.append(row)
    log(f"theirstack: {len(out)} jobs", log_path=LOG)
    return out
