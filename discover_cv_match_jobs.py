#!/usr/bin/env python3
"""Discover jobs and keep only those that match CV 0020_raw (cv_fit).

Used by GitHub Actions scheduled job on martibayoalemany9.

Sources (toggles via env):
  ENABLE_GREENHOUSE=1  ENABLE_LEVER=1  ENABLE_THEIRSTACK=0  ENABLE_APIFY=0

Output:
  applications_cv_match_0020.csv
  cv_match_report.md
  cv_match_report.json
"""
from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

W = Path(__file__).resolve().parent
if str(W) not in sys.path:
    sys.path.insert(0, str(W))

from candidate_profile import CERTS, CV  # noqa: E402
from cv_fit import job_fit_score  # noqa: E402
from discover_sources.common import load_env, log, normalize_job  # noqa: E402
from role_filter import is_preferred_title, title_preference_score  # noqa: E402

OUT_CSV = W / "applications_cv_match_0020.csv"
OUT_MD = W / "cv_match_report.md"
OUT_JSON = W / "cv_match_report.json"
LOG = W / "discover_cv_match.log"

MIN_SCORE = int(os.environ.get("CV_MATCH_MIN_SCORE", "3") or "3")


def _enabled(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).lower() in ("1", "true", "yes")


def collect_raw() -> list[dict]:
    jobs: list[dict] = []
    if _enabled("ENABLE_GREENHOUSE", "1"):
        from discover_sources.greenhouse import discover_greenhouse

        jobs.extend(discover_greenhouse())
    if _enabled("ENABLE_LEVER", "1"):
        from discover_sources.lever import discover_lever

        jobs.extend(discover_lever())
    if _enabled("ENABLE_THEIRSTACK", "0"):
        from discover_sources.theirstack import discover_theirstack

        jobs.extend(discover_theirstack())
    if _enabled("ENABLE_APIFY", "0"):
        from discover_sources.apify_client import discover_apify

        jobs.extend(discover_apify())
    return jobs


def filter_cv_match(jobs: list[dict]) -> list[dict]:
    kept = []
    for j in jobs:
        title = j.get("title") or ""
        company = j.get("company") or ""
        desc = j.get("description") or ""
        url = j.get("url") or ""
        fits, score, reason = job_fit_score(
            title, desc, company, min_score=MIN_SCORE
        )
        if not fits:
            continue
        pref = title_preference_score(title, company)
        j = dict(j)
        j["cv_score"] = score
        j["cv_reason"] = reason
        j["pref_score"] = pref
        j["preferred_title"] = is_preferred_title(title, company)
        # rank key: prefer tech lead/architect then cv score
        j["rank"] = pref * 10 + int(score)
        kept.append(j)
    kept.sort(key=lambda x: (-int(x.get("rank") or 0), -int(x.get("cv_score") or 0)))
    return kept


def write_csv(jobs: list[dict]) -> int:
    fields = [
        "app_id",
        "board",
        "company",
        "title",
        "location",
        "apply_url",
        "employer_url",
        "careers_url",
        "match_score",
        "cv_score",
        "cv_reason",
        "preferred_title",
        "cv_path",
        "certs_path",
        "salary_target",
        "status",
        "resolve",
        "source_note",
        "market",
    ]
    rows = []
    for i, j in enumerate(jobs, 1):
        rows.append(
            {
                "app_id": f"CV20-{i:04d}",
                "board": "cv_match_0020",
                "company": j.get("company") or "",
                "title": j.get("title") or "",
                "location": j.get("location") or "",
                "apply_url": j.get("url") or "",
                "employer_url": j.get("url") or "",
                "careers_url": j.get("url") or "",
                "match_score": j.get("rank") or j.get("score") or 0,
                "cv_score": j.get("cv_score") or 0,
                "cv_reason": j.get("cv_reason") or "",
                "preferred_title": "yes" if j.get("preferred_title") else "no",
                "cv_path": str(Path(CV).resolve()) if Path(CV).exists() else "0020_raw",
                "certs_path": str(Path(CERTS).resolve()) if Path(CERTS).exists() else "",
                "salary_target": "70400-120000 EUR",
                "status": "queued",
                "resolve": "ok",
                "source_note": j.get("source") or "",
                "market": "cv_match_0020",
            }
        )
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def write_reports(jobs: list[dict], raw_n: int) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pref_n = sum(1 for j in jobs if j.get("preferred_title"))
    payload = {
        "generated_utc": now,
        "cv": "0020_raw",
        "min_score": MIN_SCORE,
        "raw_discovered": raw_n,
        "cv_matched": len(jobs),
        "preferred_titles": pref_n,
        "top": [
            {
                "company": j.get("company"),
                "title": j.get("title"),
                "url": j.get("url"),
                "location": j.get("location"),
                "cv_score": j.get("cv_score"),
                "preferred": j.get("preferred_title"),
                "source": j.get("source"),
            }
            for j in jobs[:50]
        ],
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        f"# CV 0020_raw job match report",
        f"",
        f"Generated (UTC): **{now}**",
        f"",
        f"| Metric | Value |",
        f"|--------|------:|",
        f"| CV | 0020_raw |",
        f"| Min fit score | {MIN_SCORE} |",
        f"| Raw discovered | {raw_n} |",
        f"| **CV matched** | **{len(jobs)}** |",
        f"| Preferred titles (Tech Lead / Architect) | {pref_n} |",
        f"",
        f"## Top matches",
        f"",
        f"| Company | Title | Pref | CV score | Source | Link |",
        f"|---------|-------|:----:|---------:|--------|------|",
    ]
    for j in jobs[:40]:
        pref = "✓" if j.get("preferred_title") else ""
        title = (j.get("title") or "").replace("|", "/")
        company = (j.get("company") or "").replace("|", "/")
        url = j.get("url") or ""
        lines.append(
            f"| {company[:30]} | {title[:55]} | {pref} | {j.get('cv_score')} | "
            f"`{j.get('source','')}` | [apply]({url}) |"
        )
    lines += [
        f"",
        f"Queue file: `{OUT_CSV.name}`",
        f"",
        f"Apply locally:",
        f"```bash",
        f"COMPLETE_QUEUE_CSV=applications_cv_match_0020.csv APPLY_ALL=1 COMPLETE_MAX=15 \\",
        f"  python3 -u parallel_apply_instances.py",
        f"```",
        f"",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    load_env(force_file=True)
    log("=== discover_cv_match_jobs (0020_raw) ===", log_path=LOG)
    # Prefer free sources on GHA unless secrets present
    if not os.environ.get("THEIRSTACK_API_KEY"):
        os.environ.setdefault("ENABLE_THEIRSTACK", "0")
    if not os.environ.get("APIFY_TOKEN"):
        os.environ.setdefault("ENABLE_APIFY", "0")

    raw = collect_raw()
    log(f"raw jobs: {len(raw)}", log_path=LOG)
    matched = filter_cv_match(raw)
    log(f"cv matched: {len(matched)} (min_score={MIN_SCORE})", log_path=LOG)
    n = write_csv(matched)
    write_reports(matched, len(raw))
    print(OUT_MD.read_text(encoding="utf-8")[:2000])
    log(f"wrote {n} rows → {OUT_CSV.name}", log_path=LOG)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
