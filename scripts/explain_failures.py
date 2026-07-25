#!/usr/bin/env python3
"""Explain why recent job applications failed / did not complete.

Reads the apply workdir ledger + complete_apply results and writes:
  - reports/failure_analysis.md  (also under workdir)
  - reports/failure_analysis.json
  - GitHub step summary

Failure statuses covered: failed, exception, open_only, login_required,
stuck_on_board, partial_form_filled, cv_uploaded_only, failed_no_submit, etc.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Statuses that mean "not a successful closed application"
FAIL_LIKE = frozenset(
    {
        "failed",
        "exception",
        "open_only",
        "login_required",
        "stuck_on_board",
        "partial_form_filled",
        "cv_uploaded_only",
        "failed_no_submit",
        "ats_opened",
        "ats_opened_incomplete",
        "no_url",
        "job_closed",
    }
)

CLOSED_OK = frozenset(
    {
        "submitted_or_confirmed",
        "likely_submitted",
        "submitted",
        "succeeded",
        "done",
        "applied",
    }
)

REASON_GUIDE = {
    "open_only": (
        "Browser opened the job page but never uploaded a CV or confirmed submit. "
        "Often: anti-bot wall, multi-step redirect, or form not detected."
    ),
    "exception": (
        "The apply script crashed (timeout, tab crash, selector error, network). "
        "Check detail + logs; usually safe to retry."
    ),
    "login_required": (
        "ATS requires SSO/login; guest apply is unavailable. "
        "Needs saved session cookies or a manual login once."
    ),
    "stuck_on_board": (
        "Stayed on a job-board page and never reached the employer ATS form."
    ),
    "partial_form_filled": (
        "Some fields were filled but final submit was not confirmed "
        "(validation errors, captcha, missing required field)."
    ),
    "cv_uploaded_only": (
        "CV reached the form but submit/thank-you was not confirmed."
    ),
    "failed": "Generic failure without a closed application — see detail.",
    "failed_no_submit": "Form was reached but the submit click did not stick.",
    "ats_opened": "ATS opened but the form was not completed.",
    "ats_opened_incomplete": "ATS form left incomplete.",
    "no_url": "Queue row had no apply URL.",
    "job_closed": "Role was already closed when opened.",
}


def _workdir() -> Path:
    env = (os.environ.get("JOB_APPLY_WORKDIR") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    fallback = Path.home() / "job-application-bot" / "data" / "etoro-apply-report"
    return fallback.resolve()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def _load_json_list(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _classify_detail(detail: str, status: str) -> str:
    d = (detail or "").lower()
    if "captcha" in d or "recaptcha" in d:
        return "Blocked by CAPTCHA / bot protection"
    if "timeout" in d or "timed out" in d:
        return "Timed out waiting for page or form"
    if "login" in d or "sso" in d or "sign in" in d:
        return "Authentication / login wall"
    if "closed" in d or "no longer" in d:
        return "Job posting closed"
    if "required" in d and "field" in d:
        return "Missing required form field"
    if "selector" in d or "locator" in d:
        return "UI selector mismatch (ATS layout changed)"
    if "network" in d or "net::" in d:
        return "Network / connectivity error"
    if "cdp" in d or "connect" in d:
        return "Browser CDP connection problem"
    if "workday" in d:
        return "Workday ATS friction (often multi-step / login)"
    return REASON_GUIDE.get(status, f"Unclassified failure (status={status})")


def collect_records(workdir: Path) -> list[dict]:
    out: list[dict] = []
    for r in _load_jsonl(workdir / "applications_ledger.jsonl"):
        out.append({**r, "_source": "ledger"})
    for r in _load_json_list(workdir / "complete_apply_results.json"):
        out.append(
            {
                "ts": r.get("submitted_at") or r.get("ts") or "",
                "company": r.get("company", ""),
                "title": r.get("title", ""),
                "url": r.get("final_url") or r.get("ats_url") or r.get("url") or "",
                "status": r.get("status", ""),
                "detail": r.get("detail", ""),
                "app_id": r.get("app_id", ""),
                "uploaded_cv": r.get("uploaded_cv"),
                "submitted_click": r.get("submitted_click"),
                "_source": "complete_apply_results",
            }
        )
    # newest first
    out.sort(key=lambda r: (r.get("ts") or ""), reverse=True)
    return out


def analyze(workdir: Path, limit: int = 50) -> dict:
    records = collect_records(workdir)
    failed = []
    ok = []
    for r in records:
        st = (r.get("status") or "").strip()
        if st in CLOSED_OK:
            ok.append(r)
        elif st in FAIL_LIKE or st.startswith("failed") or st.startswith("error"):
            reason = _classify_detail(r.get("detail") or "", st)
            failed.append({**r, "explained_reason": reason})

    by_status = Counter((r.get("status") or "unknown") for r in failed)
    by_reason = Counter((r.get("explained_reason") or "unknown") for r in failed)
    by_company = Counter((r.get("company") or "?") for r in failed)

    # recent failures only for narrative table
    recent = failed[:limit]

    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "workdir": str(workdir),
        "total_records": len(records),
        "success_count": len(ok),
        "failure_count": len(failed),
        "by_status": dict(by_status.most_common()),
        "by_reason": dict(by_reason.most_common()),
        "top_companies": dict(by_company.most_common(15)),
        "recent_failures": [
            {
                "ts": (r.get("ts") or "")[:19],
                "company": r.get("company") or "",
                "title": (r.get("title") or "")[:80],
                "status": r.get("status") or "",
                "detail": (r.get("detail") or "")[:200],
                "explained_reason": r.get("explained_reason") or "",
                "url": r.get("url") or "",
                "app_id": r.get("app_id") or "",
            }
            for r in recent
        ],
    }


def render_md(report: dict) -> str:
    lines = [
        "# Application failure analysis\n",
        f"\nGenerated: `{report['ts']}`\n",
        f"\nWorkdir: `{report['workdir']}`\n",
        f"\n| Metric | Count |\n|--------|------:|\n",
        f"| Total ledger/result rows | {report['total_records']} |\n",
        f"| Successful / closed | {report['success_count']} |\n",
        f"| Failed / incomplete | {report['failure_count']} |\n",
        "\n## Why applications failed (grouped)\n\n",
    ]
    if report["by_reason"]:
        lines.append("| Count | Reason |\n|------:|--------|\n")
        for reason, n in report["by_reason"].items():
            lines.append(f"| {n} | {reason} |\n")
    else:
        lines.append("_No failures found in ledger/results._\n")

    lines.append("\n## By status code\n\n")
    if report["by_status"]:
        lines.append("| Count | Status |\n|------:|--------|\n")
        for st, n in report["by_status"].items():
            guide = REASON_GUIDE.get(st, "")
            extra = f" — {guide}" if guide else ""
            lines.append(f"| {n} | `{st}`{extra} |\n")

    lines.append("\n## Recent failures (detail)\n\n")
    if report["recent_failures"]:
        lines.append(
            "| When | Company | Status | Why | Detail |\n"
            "|------|---------|--------|-----|--------|\n"
        )
        for r in report["recent_failures"][:40]:
            company = (r.get("company") or "").replace("|", "/")
            status = (r.get("status") or "").replace("|", "/")
            why = (r.get("explained_reason") or "").replace("|", "/")[:90]
            detail = (r.get("detail") or "").replace("|", "/")[:80]
            lines.append(
                f"| {r.get('ts','')} | {company} | `{status}` | {why} | {detail} |\n"
            )
    else:
        lines.append("_No recent failures to list._\n")

    lines.append(
        "\n## Recommended next actions\n\n"
        "1. **login_required** — open CDP browser once, log into those ATS, re-run.\n"
        "2. **open_only / stuck_on_board** — verify apply URLs resolve to real ATS forms.\n"
        "3. **exception / timeout** — increase dwell, ensure Chromium CDP `:9223` is up.\n"
        "4. **partial_form_filled / cv_uploaded_only** — inspect required fields / captcha.\n"
        "5. Re-queue only non-closed rows (check-in already skips closed companies).\n"
    )
    return "".join(lines)


def main() -> int:
    workdir = _workdir()
    repo = _repo_root()
    limit = int(os.environ.get("FAILURE_ANALYSIS_LIMIT", "50"))
    report = analyze(workdir, limit=limit)

    reports_dir = repo / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    workdir.mkdir(parents=True, exist_ok=True)

    md = render_md(report)
    (reports_dir / "failure_analysis.md").write_text(md, encoding="utf-8")
    (reports_dir / "failure_analysis.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (workdir / "failure_analysis.md").write_text(md, encoding="utf-8")
    (workdir / "failure_analysis.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(md[:4000])
    print(
        f"\n[explain] failures={report['failure_count']} "
        f"success={report['success_count']} wrote reports/failure_analysis.md"
    )

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"failure_count={report['failure_count']}\n")
            f.write(f"success_count={report['success_count']}\n")
            f.write(f"has_failures={'true' if report['failure_count'] else 'false'}\n")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(md)

    # Non-zero only if we want CI red on failures — keep green by default
    fail_ci = (os.environ.get("FAIL_CI_ON_APPLY_FAILURES") or "").lower() in (
        "1",
        "true",
        "yes",
    )
    if fail_ci and report["failure_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
