"""PredictLeads API — hiring / job-openings signals by company.

Env:
  PREDICTLEADS_API_KEY
  PREDICTLEADS_API_TOKEN  (some accounts use key+token pair)

Docs: https://predictleads.com/api
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

from discover_sources.common import W, env, log, normalize_job

LOG = W / "discover_sources_run.log"
BASE = env("PREDICTLEADS_BASE", "https://predictleads.com/api/v2")


def discover_predictleads(domains: list[str] | None = None) -> list[dict]:
    key = env("PREDICTLEADS_API_KEY")
    token = env("PREDICTLEADS_API_TOKEN")
    if not key:
        log("predictleads: no PREDICTLEADS_API_KEY — skip", log_path=LOG)
        return []

    domains = domains or [
        d.strip()
        for d in env(
            "PREDICTLEADS_DOMAINS",
            "sap.com,siemens.com,bosch.com,infineon.com,ericsson.com,nokia.com,"
            "airbus.com,zalando.de,deliveryhero.com,n26.com,klarna.com",
        ).split(",")
        if d.strip()
    ]

    out: list[dict] = []
    headers = {
        "X-Api-Key": key,
        "Accept": "application/json",
        "User-Agent": "JobDiscover/1.0",
    }
    if token:
        headers["X-Api-Token"] = token

    for domain in domains[:25]:
        # Job openings endpoint pattern (soft-fail if 404)
        q = urllib.parse.urlencode({"limit": "20"})
        url = f"{BASE.rstrip('/')}/companies/domain/{urllib.parse.quote(domain)}/job_openings?{q}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            log(f"predictleads {domain}: {e}", log_path=LOG)
            continue
        items = data if isinstance(data, list) else (
            data.get("data") or data.get("job_openings") or data.get("results") or []
        )
        # JSON:API style
        if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
            items = data["data"]
        for j in items or []:
            attrs = j.get("attributes") if isinstance(j, dict) and "attributes" in j else j
            if not isinstance(attrs, dict):
                continue
            title = attrs.get("title") or attrs.get("job_title") or ""
            url_j = attrs.get("url") or attrs.get("job_url") or attrs.get("source_url") or ""
            company = attrs.get("company_name") or domain
            loc = attrs.get("location") or attrs.get("city") or ""
            row = normalize_job(
                source=f"predictleads:{domain}",
                company=str(company),
                title=str(title),
                url=str(url_j),
                location=str(loc),
                description=str(attrs.get("description") or "")[:1500],
            )
            if row:
                out.append(row)
    log(f"predictleads: {len(out)} jobs from {len(domains)} domains", log_path=LOG)
    return out
