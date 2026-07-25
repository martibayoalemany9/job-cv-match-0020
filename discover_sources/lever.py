"""Lever public postings API.

  https://api.lever.co/v0/postings/{company}?mode=json
  https://api.lever.co/v0/postings/{company}/{id}
"""
from __future__ import annotations

from discover_sources.common import W, http_get_json, load_board_tokens, log, normalize_job
from discover_sources.proxies import active_proxy_url

LOG = W / "discover_sources_run.log"
API = "https://api.lever.co/v0/postings/{company}?mode=json"


def fetch_company(slug: str, *, company: str = "", proxy: str | None = None) -> list[dict]:
    slug = (slug or "").strip()
    if not slug:
        return []
    url = API.format(company=slug)
    try:
        data = http_get_json(url, proxy_url=proxy)
    except Exception as e:
        log(f"lever {slug}: {e}", log_path=LOG)
        return []
    if not isinstance(data, list):
        data = data.get("data") or data.get("postings") or []
    out: list[dict] = []
    for j in data or []:
        if not isinstance(j, dict):
            continue
        title = j.get("text") or j.get("title") or ""
        abs_url = j.get("hostedUrl") or j.get("applyUrl") or j.get("url") or ""
        cats = j.get("categories") or {}
        loc = ""
        if isinstance(cats, dict):
            loc = cats.get("location") or cats.get("team") or ""
        desc = ""
        if isinstance(j.get("descriptionPlain"), str):
            desc = j["descriptionPlain"][:1500]
        elif isinstance(j.get("description"), str):
            desc = j["description"][:1500]
        row = normalize_job(
            source=f"lever:{slug}",
            company=company or slug,
            title=title,
            url=abs_url,
            location=str(loc),
            description=desc,
            extra={"id": j.get("id"), "createdAt": j.get("createdAt")},
        )
        if row:
            out.append(row)
    log(f"lever {slug}: {len(out)} kept", log_path=LOG)
    return out


def discover_lever(boards: list[dict] | None = None) -> list[dict]:
    proxy = active_proxy_url()
    boards = boards or [
        b for b in load_board_tokens() if (b.get("type") or "").lower() == "lever"
    ]
    if not boards:
        boards = [
            {"type": "lever", "token": "netflix", "company": "Netflix"},
            {"type": "lever", "token": "spotify", "company": "Spotify"},
            {"type": "lever", "token": "palantir", "company": "Palantir"},
            {"type": "lever", "token": "shopify", "company": "Shopify"},
            {"type": "lever", "token": "twitch", "company": "Twitch"},
            {"type": "lever", "token": "wealthsimple", "company": "Wealthsimple"},
            {"type": "lever", "token": "revolut", "company": "Revolut"},
            {"type": "lever", "token": "n26", "company": "N26"},
            {"type": "lever", "token": "mistral", "company": "Mistral AI"},
            {"type": "lever", "token": "anthropic", "company": "Anthropic"},
            {"type": "lever", "token": "openai", "company": "OpenAI"},
        ]
    all_jobs: list[dict] = []
    for b in boards:
        slug = b.get("token") or b.get("board") or b.get("slug") or ""
        company = b.get("company") or slug
        all_jobs.extend(fetch_company(slug, company=company, proxy=proxy))
    return all_jobs


if __name__ == "__main__":
    jobs = discover_lever()
    print("jobs", len(jobs))
    for j in jobs[:5]:
        print(j.get("score"), j.get("company"), j.get("title")[:50])
