"""Greenhouse public Job Board API.

Docs pattern:
  https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs
  https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{id}

Many companies expose boards.greenhouse.io/{token} or job-boards.eu.greenhouse.io/{token}.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from discover_sources.common import (
    W,
    http_get_json,
    load_board_tokens,
    log,
    normalize_job,
)
from discover_sources.proxies import active_proxy_url

LOG = W / "discover_sources_run.log"
API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


def fetch_board(token: str, *, company: str = "", proxy: str | None = None) -> list[dict]:
    token = (token or "").strip()
    if not token:
        return []
    url = API.format(token=token)
    try:
        data = http_get_json(url, proxy_url=proxy)
    except Exception as e:
        log(f"greenhouse {token}: {e}", log_path=LOG)
        return []
    jobs_raw = data.get("jobs") if isinstance(data, dict) else data
    out: list[dict] = []
    for j in jobs_raw or []:
        if not isinstance(j, dict):
            continue
        title = j.get("title") or ""
        abs_url = j.get("absolute_url") or j.get("url") or ""
        loc = ""
        if isinstance(j.get("location"), dict):
            loc = j["location"].get("name") or ""
        elif isinstance(j.get("location"), str):
            loc = j["location"]
        co = company or token
        # departments sometimes hold company context
        deps = j.get("departments") or []
        if deps and isinstance(deps[0], dict):
            pass
        row = normalize_job(
            source=f"greenhouse:{token}",
            company=co,
            title=title,
            url=abs_url,
            location=loc,
            description=(j.get("content") or "")[:1500]
            if isinstance(j.get("content"), str)
            else "",
            extra={"id": j.get("id"), "updated_at": j.get("updated_at")},
        )
        if row:
            out.append(row)
    log(f"greenhouse {token}: {len(out)} kept", log_path=LOG)
    return out


def discover_greenhouse(boards: list[dict] | None = None) -> list[dict]:
    proxy = active_proxy_url()
    boards = boards or [
        b for b in load_board_tokens() if (b.get("type") or "").lower() == "greenhouse"
    ]
    # built-in seeds if empty
    if not boards:
        boards = [
            {"type": "greenhouse", "token": "stripe", "company": "Stripe"},
            {"type": "greenhouse", "token": "airbnb", "company": "Airbnb"},
            {"type": "greenhouse", "token": "cloudflare", "company": "Cloudflare"},
            {"type": "greenhouse", "token": "datadog", "company": "Datadog"},
            {"type": "greenhouse", "token": "hashicorp", "company": "HashiCorp"},
            {"type": "greenhouse", "token": "figma", "company": "Figma"},
            {"type": "greenhouse", "token": "notion", "company": "Notion"},
            {"type": "greenhouse", "token": "discord", "company": "Discord"},
            {"type": "greenhouse", "token": "gitlab", "company": "GitLab"},
            {"type": "greenhouse", "token": "elastic", "company": "Elastic"},
            {"type": "greenhouse", "token": "twilio", "company": "Twilio"},
            {"type": "greenhouse", "token": "dropbox", "company": "Dropbox"},
            {"type": "greenhouse", "token": "asana", "company": "Asana"},
            {"type": "greenhouse", "token": "pinterest", "company": "Pinterest"},
            {"type": "greenhouse", "token": "reddit", "company": "Reddit"},
            {"type": "greenhouse", "token": "airtable", "company": "Airtable"},
            {"type": "greenhouse", "token": "brex", "company": "Brex"},
            {"type": "greenhouse", "token": "coinbase", "company": "Coinbase"},
            {"type": "greenhouse", "token": "robinhood", "company": "Robinhood"},
            {"type": "greenhouse", "token": "doordash", "company": "DoorDash"},
        ]
    all_jobs: list[dict] = []
    for b in boards:
        token = b.get("token") or b.get("board") or ""
        company = b.get("company") or token
        all_jobs.extend(fetch_board(token, company=company, proxy=proxy))
    return all_jobs


if __name__ == "__main__":
    jobs = discover_greenhouse()
    print("jobs", len(jobs))
    for j in jobs[:5]:
        print(j.get("score"), j.get("company"), j.get("title")[:50], j.get("url")[:70])
