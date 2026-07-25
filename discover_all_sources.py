#!/usr/bin/env python3
"""Crawl the internet for job offers from multiple public/API sources.

Free (no secrets):
  - Greenhouse Job Board API (boards.json)
  - Lever postings API (boards.json)

Optional (secrets / env):
  - TheirStack, Apify, PredictLeads, Gmail alerts, Stepstone, eFC

Outputs:
  applications_discovered_all.csv
  discovered_all_jobs.json
  DISCOVER_SOURCES_SUMMARY.md
  discover_sources_run.log
  reports/… copies of the above
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

W = Path(__file__).resolve().parent
if str(W) not in sys.path:
    sys.path.insert(0, str(W))

from discover_sources.common import (  # noqa: E402
    load_env,
    log,
    prefer_title_boost,
    write_queue_csv,
)

OUT_CSV = W / "applications_discovered_all.csv"
OUT_JSON = W / "discovered_all_jobs.json"
OUT_MD = W / "DISCOVER_SOURCES_SUMMARY.md"
LOG = W / "discover_sources_run.log"
REPORTS = W / "reports"


def _enabled(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).lower() in ("1", "true", "yes", "on")


def discover_all(
    *,
    prefer_roles: bool | None = None,
) -> list[dict]:
    """Run all enabled sources and return normalized job dicts."""
    load_env(force_file=True)
    if LOG.exists():
        try:
            LOG.write_text("", encoding="utf-8")
        except OSError:
            pass

    prefer = (
        prefer_roles
        if prefer_roles is not None
        else _enabled("PREFER_ROLE_TITLES", "1")
    )

    jobs: list[dict] = []
    counts: dict[str, int] = {}
    errors: list[str] = []

    def _run(name: str, fn, default_on: str = "1") -> None:
        env_key = f"ENABLE_{name.upper()}"
        if not _enabled(env_key, default_on):
            log(f"{name}: disabled ({env_key}=0)", log_path=LOG)
            counts[name] = 0
            return
        try:
            batch = fn() or []
            jobs.extend(batch)
            counts[name] = len(batch)
            log(f"{name}: +{len(batch)} jobs", log_path=LOG)
        except Exception as e:
            msg = f"{name}: ERROR {e}"
            log(msg, log_path=LOG)
            errors.append(msg)
            counts[name] = 0

    # --- free public boards ---
    if _enabled("ENABLE_GREENHOUSE", "1"):
        from discover_sources.greenhouse import discover_greenhouse

        _run("greenhouse", discover_greenhouse, "1")
    else:
        counts["greenhouse"] = 0

    if _enabled("ENABLE_LEVER", "1"):
        from discover_sources.lever import discover_lever

        _run("lever", discover_lever, "1")
    else:
        counts["lever"] = 0

    # --- paid / optional APIs ---
    if _enabled("ENABLE_THEIRSTACK", "0"):
        from discover_sources.theirstack import discover_theirstack

        _run("theirstack", discover_theirstack, "0")
    else:
        counts["theirstack"] = 0

    if _enabled("ENABLE_APIFY", "0"):
        from discover_sources.apify_client import discover_apify

        _run("apify", discover_apify, "0")
    else:
        counts["apify"] = 0

    if _enabled("ENABLE_PREDICTLEADS", "0"):
        from discover_sources.predictleads import discover_predictleads

        _run("predictleads", discover_predictleads, "0")
    else:
        counts["predictleads"] = 0

    if _enabled("ENABLE_GMAIL_ALERTS", "0"):
        from discover_sources.gmail_alerts import discover_gmail_alerts

        _run("gmail_alerts", discover_gmail_alerts, "0")
    else:
        counts["gmail_alerts"] = 0

    # Stepstone HTML crawl (best-effort; often blocked from cloud IPs)
    if _enabled("ENABLE_STEPSTONE", "0") or _enabled("RUN_STEPSTONE", "0"):
        from discover_sources.efc_stepstone import discover_stepstone

        _run("stepstone", discover_stepstone, "0")
    else:
        counts["stepstone"] = 0

    if _enabled("ENABLE_EFC", "0") or _enabled("RUN_EFC", "0"):
        from discover_sources.efc_stepstone import discover_efc

        _run("efc", discover_efc, "0")
    else:
        counts["efc"] = 0

    # Deduplicate by URL
    by_url: dict[str, dict] = {}
    for j in jobs:
        u = (j.get("url") or "").strip()
        if not u:
            continue
        # score for ranking (title preference + any existing score)
        boost = prefer_title_boost(j.get("title") or "") if prefer else 0
        existing = int(j.get("score") or 0)
        j = dict(j)
        j["score"] = max(existing, boost)
        prev = by_url.get(u)
        if not prev or int(j.get("score") or 0) > int(prev.get("score") or 0):
            by_url[u] = j

    unique = list(by_url.values())

    # Optional hard filter: only preferred titles
    if prefer and _enabled("ONLY_PREFERRED_TITLES", "0"):
        try:
            from role_filter import is_preferred_title

            unique = [
                j
                for j in unique
                if is_preferred_title(j.get("title") or "", j.get("company") or "")
            ]
        except Exception as e:
            log(f"role_filter skip: {e}", log_path=LOG)

    unique.sort(
        key=lambda x: (
            -int(x.get("score") or 0),
            (x.get("company") or "").lower(),
            (x.get("title") or "").lower(),
        )
    )

    max_jobs = int(os.environ.get("CRAWL_MAX_JOBS", "0") or "0")
    if max_jobs > 0:
        unique = unique[:max_jobs]

    n = write_queue_csv(
        unique,
        OUT_CSV,
        board="web_crawl",
        market=os.environ.get("CRAWL_MARKET", "multi"),
        prefix="CRAWL",
    )

    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "total_raw": len(jobs),
        "total_unique": len(unique),
        "written_csv": n,
        "by_source": counts,
        "errors": errors,
        "jobs": [
            {
                "company": j.get("company"),
                "title": j.get("title"),
                "url": j.get("url"),
                "location": j.get("location"),
                "source": j.get("source"),
                "score": j.get("score"),
            }
            for j in unique[:500]
        ],
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # Markdown summary
    src_lines = "\n".join(
        f"| {k} | {v} |" for k, v in sorted(counts.items(), key=lambda x: -x[1])
    )
    top = unique[:25]
    top_md = "\n".join(
        f"| {j.get('company','')[:40]} | {(j.get('title') or '')[:55]} | "
        f"{j.get('source','')} | {j.get('score',0)} | [link]({j.get('url','')}) |"
        for j in top
    )
    err_md = "\n".join(f"- {e}" for e in errors) if errors else "_none_"
    md = f"""# Job crawl summary

Generated: `{payload['ts']}`

| Metric | Value |
|--------|------:|
| Raw hits | {payload['total_raw']} |
| Unique URLs | {payload['total_unique']} |
| Written to CSV | {n} |

## By source

| Source | Jobs |
|--------|-----:|
{src_lines or '| — | 0 |'}

## Errors

{err_md}

## Top roles (sample)

| Company | Title | Source | Score | URL |
|---------|-------|--------|------:|-----|
{top_md or '| — | — | — | — | — |'}

## Outputs

- `{OUT_CSV.name}`
- `{OUT_JSON.name}`
- `{LOG.name}`
"""
    OUT_MD.write_text(md, encoding="utf-8")

    # Mirror into reports/
    REPORTS.mkdir(parents=True, exist_ok=True)
    for src, dst_name in (
        (OUT_CSV, "applications_discovered_all.csv"),
        (OUT_JSON, "discovered_all_jobs.json"),
        (OUT_MD, "DISCOVER_SOURCES_SUMMARY.md"),
    ):
        if src.is_file():
            (REPORTS / dst_name).write_bytes(src.read_bytes())

    log(
        f"DONE raw={payload['total_raw']} unique={payload['total_unique']} csv={n}",
        log_path=LOG,
    )
    print(md[:3000])
    return unique


def main() -> int:
    jobs = discover_all()
    # Soft success even if empty (sources may be blocked)
    if not jobs:
        log("WARN: zero jobs discovered", log_path=LOG)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
