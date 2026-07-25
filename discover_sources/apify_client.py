"""Apify / Crawlee cloud actors for job-board scraping.

Requires APIFY_TOKEN. Without it, returns [] and logs a skip.

Common patterns:
  - Run actor synchronously via API
  - Pull dataset items

Env:
  APIFY_TOKEN
  APIFY_ACTOR_ID   (optional default actor, e.g. your custom job scraper)
  APIFY_INPUT_JSON (optional path or inline JSON for actor input)
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from discover_sources.common import W, env, log, normalize_job

LOG = W / "discover_sources_run.log"
API = "https://api.apify.com/v2"


def _auth_headers() -> dict[str, str] | None:
    token = env("APIFY_TOKEN")
    if not token:
        return None
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def run_actor(actor_id: str, run_input: dict, *, timeout_sec: int = 180) -> list[dict]:
    """Start actor, wait, return dataset items (best-effort)."""
    headers = _auth_headers()
    if not headers:
        log("apify: no APIFY_TOKEN — skip", log_path=LOG)
        return []
    actor_id = actor_id.strip().replace("/", "~")
    start_url = f"{API}/acts/{actor_id}/runs?waitForFinish={min(timeout_sec, 300)}"
    body = json.dumps(run_input).encode("utf-8")
    req = urllib.request.Request(start_url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec + 30) as resp:
            run = json.loads(resp.read().decode())
    except Exception as e:
        log(f"apify run failed: {e}", log_path=LOG)
        return []
    data = run.get("data") or run
    dataset_id = data.get("defaultDatasetId")
    status = data.get("status")
    log(f"apify actor={actor_id} status={status} dataset={dataset_id}", log_path=LOG)
    if not dataset_id:
        return []
    # fetch items
    items_url = f"{API}/datasets/{dataset_id}/items?format=json&clean=1"
    req2 = urllib.request.Request(items_url, headers=headers)
    try:
        with urllib.request.urlopen(req2, timeout=60) as resp:
            items = json.loads(resp.read().decode())
    except Exception as e:
        log(f"apify dataset fetch failed: {e}", log_path=LOG)
        return []
    if not isinstance(items, list):
        return []
    return items


def items_to_jobs(items: list[dict], *, source: str = "apify") -> list[dict]:
    out: list[dict] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        title = (
            it.get("title")
            or it.get("jobTitle")
            or it.get("name")
            or it.get("position")
            or ""
        )
        url = (
            it.get("url")
            or it.get("applyUrl")
            or it.get("jobUrl")
            or it.get("link")
            or ""
        )
        company = it.get("company") or it.get("companyName") or it.get("employer") or "Unknown"
        location = it.get("location") or it.get("city") or ""
        desc = it.get("description") or it.get("text") or ""
        row = normalize_job(
            source=source,
            company=str(company),
            title=str(title),
            url=str(url),
            location=str(location),
            description=str(desc)[:1500],
            extra={"apify": True},
        )
        if row:
            out.append(row)
    return out


def discover_apify() -> list[dict]:
    """Run configured Apify actor(s) if token present."""
    if not env("APIFY_TOKEN"):
        log("apify: APIFY_TOKEN not set — skip (add to discover_sources.env)", log_path=LOG)
        return []
    # Default: Google Jobs scraper (works with APIFY_TOKEN alone)
    actor = env("APIFY_ACTOR_ID", "orgupdate~google-jobs-scraper")
    if not actor:
        log("apify: empty APIFY_ACTOR_ID", log_path=LOG)
        return []
    # Input shape for orgupdate/google-jobs-scraper (verified working)
    run_input: dict = {
        "queries": [
            "technology lead Germany",
            "software architect Germany",
            "tech lead software Europe",
            "principal software engineer Germany",
            "software architect Netherlands",
        ],
        "maxItems": int(env("APIFY_MAX_ITEMS", "40") or "40"),
        "country": env("APIFY_COUNTRY", "DE"),
    }
    inp_path = env("APIFY_INPUT_JSON")
    if inp_path:
        p = Path(inp_path)
        if p.exists():
            run_input = json.loads(p.read_text(encoding="utf-8"))
        else:
            try:
                run_input = json.loads(inp_path)
            except Exception:
                pass
    items = run_actor(actor, run_input, timeout_sec=int(env("APIFY_TIMEOUT_SEC", "180") or "180"))
    # Map Google Jobs actor field names
    mapped = []
    for it in items:
        if not isinstance(it, dict):
            continue
        mapped.append(
            {
                "title": it.get("job_title") or it.get("title") or "",
                "company": it.get("company_name") or it.get("company") or "",
                "url": it.get("URL") or it.get("url") or it.get("applyUrl") or "",
                "location": it.get("location") or "",
                "description": it.get("description") or "",
            }
        )
    jobs = items_to_jobs(mapped if mapped else items, source=f"apify:{actor}")
    log(f"apify: {len(jobs)} jobs from actor {actor}", log_path=LOG)
    return jobs


# Crawlee local note: use a separate Node project (crawlee_jobs/) for long scrapes;
# push results to applications_apify.csv via write_queue_csv from a small bridge script.
