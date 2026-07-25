"""eFC + Stepstone discovery wrappers for scheduled/cloud runs.

- eFC: reuses efc_job_search.py (rings from Karlsruhe, EU/SG/US expansion)
- Stepstone: lightweight public search HTML/JSON scrape (best-effort; use proxy if blocked)

Env:
  RUN_EFC=1
  RUN_STEPSTONE=1
  STEPSTONE_QUERY  (default: technology lead OR software architect)
  STEPSTONE_LOCATIONS  comma list
  DISCOVER_PROXY_URL / Bright Data / Oxylabs via proxies.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from discover_sources.common import W, env, http_get_text, log, normalize_job
from discover_sources.proxies import active_proxy_url

LOG = W / "discover_sources_run.log"


def discover_efc() -> list[dict]:
    """Run efc_job_search.py and harvest its output CSV/JSON if produced."""
    if env("RUN_EFC", "1") not in ("1", "true", "yes"):
        log("efc: RUN_EFC=0 skip", log_path=LOG)
        return []
    script = W / "efc_job_search.py"
    if not script.exists():
        log("efc: efc_job_search.py missing", log_path=LOG)
        return []
    py = sys.executable
    # Prefer limited rings for CI; full rings when EFC_FULL=1
    env_run = dict(**{k: v for k, v in __import__("os").environ.items()})
    env_run.setdefault("EFC_MAX_RINGS", env("EFC_MAX_RINGS", "4"))
    log("efc: running efc_job_search.py …", log_path=LOG)
    try:
        subprocess.run(
            [py, "-u", str(script)],
            cwd=str(W),
            env=env_run,
            timeout=int(env("EFC_TIMEOUT_SEC", "600") or "600"),
            check=False,
        )
    except Exception as e:
        log(f"efc run err: {e}", log_path=LOG)

    jobs: list[dict] = []
    # Collect from known eFC outputs
    for path in [
        W / "applications_software_rings_cvfit.csv",
        W / "efc_software_rings_jobs.json",
        W / "efc_real_jobs_senior.json",
    ]:
        if not path.exists():
            continue
        if path.suffix == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                items = data if isinstance(data, list) else data.get("jobs") or data.get("results") or []
                for j in items:
                    if not isinstance(j, dict):
                        continue
                    row = normalize_job(
                        source="efc",
                        company=j.get("company") or j.get("employer") or "",
                        title=j.get("title") or j.get("job_title") or "",
                        url=j.get("url") or j.get("apply_url") or j.get("job_url") or "",
                        location=j.get("location") or "",
                        description=str(j.get("description") or "")[:1000],
                    )
                    if row:
                        jobs.append(row)
            except Exception as e:
                log(f"efc parse {path.name}: {e}", log_path=LOG)
        else:
            import csv

            try:
                with path.open(encoding="utf-8") as f:
                    for r in csv.DictReader(f):
                        row = normalize_job(
                            source="efc_csv",
                            company=r.get("company") or "",
                            title=r.get("title") or "",
                            url=r.get("apply_url") or r.get("employer_url") or r.get("url") or "",
                            location=r.get("location") or "",
                        )
                        if row:
                            jobs.append(row)
            except Exception as e:
                log(f"efc csv {path.name}: {e}", log_path=LOG)
    log(f"efc: {len(jobs)} jobs collected", log_path=LOG)
    return jobs


def discover_stepstone() -> list[dict]:
    """Best-effort Stepstone DE search pages for preferred titles."""
    if env("RUN_STEPSTONE", "1") not in ("1", "true", "yes"):
        log("stepstone: RUN_STEPSTONE=0 skip", log_path=LOG)
        return []
    proxy = active_proxy_url()
    query = env("STEPSTONE_QUERY", "Technology Lead OR Software Architect")
    locations = [
        x.strip()
        for x in env(
            "STEPSTONE_LOCATIONS",
            "Karlsruhe,Stuttgart,München,Frankfurt,Berlin,Remote",
        ).split(",")
        if x.strip()
    ]
    jobs: list[dict] = []
    for loc in locations[:6]:
        # Public search URL (HTML). May require proxy if blocked.
        from urllib.parse import quote_plus

        url = (
            "https://www.stepstone.de/jobs/"
            f"{quote_plus(query)}/in-{quote_plus(loc)}"
        )
        try:
            html = http_get_text(url, proxy_url=proxy, timeout=40)
        except Exception as e:
            log(f"stepstone {loc}: {e}", log_path=LOG)
            continue
        # Extract job links + titles
        for m in re.finditer(
            r'href="(https://www\.stepstone\.de/job-suche/[^"]+|/stellenangebote--[^"]+)"[^>]*>([^<]{8,120})<',
            html,
            re.I,
        ):
            href, title = m.group(1), re.sub(r"\s+", " ", m.group(2)).strip()
            if href.startswith("/"):
                href = "https://www.stepstone.de" + href
            row = normalize_job(
                source="stepstone",
                company="Stepstone listing",
                title=title,
                url=href,
                location=loc,
            )
            if row:
                jobs.append(row)
        # JSON-LD JobPosting
        for m in re.finditer(
            r'<script type="application/ld\+json">(.*?)</script>',
            html,
            re.I | re.S,
        ):
            try:
                blob = json.loads(m.group(1))
            except Exception:
                continue
            items = blob if isinstance(blob, list) else [blob]
            for it in items:
                if not isinstance(it, dict):
                    continue
                if it.get("@type") not in ("JobPosting", ["JobPosting"]):
                    if it.get("@type") != "JobPosting":
                        continue
                title = it.get("title") or ""
                url_j = it.get("url") or ""
                company = ""
                org = it.get("hiringOrganization") or {}
                if isinstance(org, dict):
                    company = org.get("name") or ""
                loc_name = ""
                jl = it.get("jobLocation") or {}
                if isinstance(jl, dict):
                    addr = jl.get("address") or {}
                    if isinstance(addr, dict):
                        loc_name = addr.get("addressLocality") or ""
                row = normalize_job(
                    source="stepstone_ld",
                    company=company or "Unknown",
                    title=title,
                    url=url_j,
                    location=loc_name or loc,
                )
                if row:
                    jobs.append(row)
    log(f"stepstone: {len(jobs)} jobs", log_path=LOG)
    return jobs


def discover_efc_stepstone() -> list[dict]:
    return discover_efc() + discover_stepstone()
