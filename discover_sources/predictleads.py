"""PredictLeads API — hiring / job-openings signals by company.

Env (account A — primary):
  PREDICTLEADS_API_KEY
  PREDICTLEADS_API_TOKEN   (required pair; often key ≠ token)

Env (account B — fallback, optional):
  PREDICTLEADS_API_KEY_2
  PREDICTLEADS_API_TOKEN_2

Shared:
  PREDICTLEADS_BASE        default https://predictleads.com/api/v3
  PREDICTLEADS_DOMAINS     comma-separated domains

Docs: https://docs.predictleads.com/
Auth headers: X-Api-Key + X-Api-Token
Job openings: GET /companies/{domain}/job_openings
Discover:     GET /discover/job_openings
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from discover_sources.common import W, env, log, normalize_job

LOG = W / "discover_sources_run.log"
BASE = env("PREDICTLEADS_BASE", "https://predictleads.com/api/v3")


def _headers(key: str, token: str | None) -> dict[str, str]:
    h = {
        "X-Api-Key": key,
        "Accept": "application/json",
        "User-Agent": "JobDiscover/1.0",
    }
    if token:
        h["X-Api-Token"] = token
    return h


def _get_json(
    url: str, headers: dict[str, str], *, quiet: bool = False
) -> tuple[dict | list | None, int | None]:
    """Return (payload, http_status). status is None on network/parse errors."""
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode()), resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        if not quiet:
            log(f"predictleads HTTP {e.code} {url}: {body}", log_path=LOG)
        return None, e.code
    except Exception as e:
        if not quiet:
            log(f"predictleads {url}: {e}", log_path=LOG)
        return None, None


def _credential_pairs() -> list[tuple[str, str, str]]:
    """Return [(label, key, token), ...] for primary then secondary account."""
    pairs: list[tuple[str, str, str]] = []
    k1, t1 = env("PREDICTLEADS_API_KEY"), env("PREDICTLEADS_API_TOKEN")
    if k1:
        pairs.append(("account_1", k1, t1 or ""))
    k2, t2 = env("PREDICTLEADS_API_KEY_2"), env("PREDICTLEADS_API_TOKEN_2")
    if k2:
        pairs.append(("account_2", k2, t2 or ""))
    return pairs


def _resolve_auth() -> tuple[dict[str, str], str] | None:
    """Try each account against /api_subscription; return (headers, label) or None."""
    pairs = _credential_pairs()
    if not pairs:
        log("predictleads: no PREDICTLEADS_API_KEY / _KEY_2 — skip", log_path=LOG)
        return None

    sub_url = f"{BASE.rstrip('/')}/api_subscription"
    for label, key, token in pairs:
        if not token:
            log(
                f"predictleads {label}: missing token (API needs key+token pair)",
                log_path=LOG,
            )
        headers = _headers(key, token or None)
        data, status = _get_json(sub_url, headers, quiet=True)
        if data is not None:
            log(f"predictleads: authenticated as {label}", log_path=LOG)
            return headers, label
        log(
            f"predictleads {label}: auth failed (HTTP {status}) — trying next account",
            log_path=LOG,
        )

    log(
        "predictleads: all accounts failed auth — paste both KEY+TOKEN pairs "
        "from each PredictLeads dashboard (key and token are usually different)",
        log_path=LOG,
    )
    return None


def _items_from_payload(data: dict | list | None) -> list:
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    items = data.get("data") or data.get("job_openings") or data.get("results") or []
    return items if isinstance(items, list) else []


def _job_rows(items: list, domain: str, account: str) -> list[dict]:
    out: list[dict] = []
    for j in items or []:
        attrs = j.get("attributes") if isinstance(j, dict) and "attributes" in j else j
        if not isinstance(attrs, dict):
            continue
        title = attrs.get("title") or attrs.get("job_title") or ""
        url_j = (
            attrs.get("url")
            or attrs.get("job_url")
            or attrs.get("source_url")
            or attrs.get("first_seen_at_url")
            or ""
        )
        company = attrs.get("company_name") or domain
        loc = attrs.get("location") or attrs.get("city") or ""
        if isinstance(loc, list):
            loc = ", ".join(str(x) for x in loc if x)
        row = normalize_job(
            source=f"predictleads:{account}:{domain}",
            company=str(company),
            title=str(title),
            url=str(url_j),
            location=str(loc),
            description=str(attrs.get("description") or attrs.get("description_text") or "")[:1500],
        )
        if row:
            out.append(row)
    return out


def discover_predictleads(domains: list[str] | None = None) -> list[dict]:
    auth = _resolve_auth()
    if not auth:
        return []
    headers, account = auth

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
    for domain in domains[:25]:
        q = urllib.parse.urlencode({"page": "1"})
        url = f"{BASE.rstrip('/')}/companies/{urllib.parse.quote(domain)}/job_openings?{q}"
        data, _ = _get_json(url, headers)
        out.extend(_job_rows(_items_from_payload(data), domain, account))

    log(
        f"predictleads: {len(out)} jobs from {len(domains)} domains ({account})",
        log_path=LOG,
    )
    return out
