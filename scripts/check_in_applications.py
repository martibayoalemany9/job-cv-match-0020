#!/usr/bin/env python3
"""Check in newly discovered applications into the Grok apply workdir queue.

Merges repo discovery CSV (applications_cv_match_0020.csv) into the private
workdir so complete_apply / grok_apply_with_report can consume them.

Outputs:
  - $JOB_APPLY_WORKDIR/applications_resolved_ats.csv  (queue for complete_apply)
  - $JOB_APPLY_WORKDIR/applications_cv_match_0020.csv (mirror of discovery)
  - $JOB_APPLY_WORKDIR/check_in_report.json
  - github step summary + GITHUB_OUTPUT counts
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

CLOSED = frozenset(
    {
        "submitted_or_confirmed",
        "likely_submitted",
        "submitted",
        "succeeded",
        "done",
        "applied",
        "skipped_already_done",
        "job_closed",
    }
)


def _workdir() -> Path:
    env = (os.environ.get("JOB_APPLY_WORKDIR") or "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p
    fallback = Path.home() / "job-application-bot" / "data" / "etoro-apply-report"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback.resolve()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _norm_url(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    return u.split("?")[0].rstrip("/").lower()


def _norm_company(c: str) -> str:
    return re.sub(r"\s+", " ", (c or "").strip().lower())


def _row_key(row: dict) -> str:
    app_id = (row.get("app_id") or "").strip()
    if app_id:
        return f"id:{app_id}"
    u = _norm_url(row.get("apply_url") or row.get("employer_url") or row.get("url") or "")
    if u:
        return f"url:{u}"
    c = _norm_company(row.get("company") or "")
    t = (row.get("title") or "").strip().lower()
    return f"co:{c}|t:{t}"


def _read_csv(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _load_ledger_keys(workdir: Path) -> set[str]:
    """Keys already closed/succeeded so we don't re-queue them as fresh."""
    keys: set[str] = set()
    ledger = workdir / "applications_ledger.jsonl"
    if not ledger.is_file():
        return keys
    for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        st = (r.get("status") or "").strip()
        if st not in CLOSED and not (r.get("uploaded_cv") and r.get("submitted_click")):
            continue
        if r.get("app_id"):
            keys.add(f"id:{r['app_id']}")
        u = _norm_url(r.get("url") or r.get("apply_url") or r.get("final_url") or "")
        if u:
            keys.add(f"url:{u}")
        c = _norm_company(r.get("company") or "")
        if c:
            keys.add(f"co:{c}")
    return keys


def _source_csvs(repo: Path, workdir: Path) -> list[Path]:
    paths = []
    # Prefer freshly checked-out discovery results
    for p in (
        repo / "applications_cv_match_0020.csv",
        repo / "reports" / "applications_cv_match_0020.csv",
        workdir / "applications_cv_match_0020.csv",
    ):
        if p.is_file() and p not in paths:
            paths.append(p)
    extra = (os.environ.get("CHECK_IN_EXTRA_CSV") or "").strip()
    if extra:
        ep = Path(extra).expanduser()
        if ep.is_file():
            paths.append(ep)
    return paths


def check_in() -> dict:
    repo = _repo_root()
    workdir = _workdir()
    sources = _source_csvs(repo, workdir)
    if not sources:
        report = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "workdir": str(workdir),
            "error": "no discovery CSV found",
            "added": 0,
            "queued_total": 0,
        }
        (workdir / "check_in_report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print("ERROR: no applications_cv_match_0020.csv found", file=sys.stderr)
        return report

    existing_queue = workdir / "applications_resolved_ats.csv"
    by_key: dict[str, dict] = {}
    for row in _read_csv(existing_queue):
        by_key[_row_key(row)] = row

    before = len(by_key)
    closed = _load_ledger_keys(workdir)
    added = 0
    skipped_closed = 0
    skipped_no_url = 0

    for src in sources:
        for row in _read_csv(src):
            url = (
                (row.get("apply_url") or "").strip()
                or (row.get("employer_url") or "").strip()
                or (row.get("url") or "").strip()
            )
            if not url:
                skipped_no_url += 1
                continue
            # Normalize fields expected by complete_apply
            out = dict(row)
            out.setdefault("apply_url", url)
            out.setdefault("employer_url", row.get("employer_url") or url)
            out.setdefault("status", row.get("status") or "queued")
            out.setdefault("board", row.get("board") or "cv_match_0020")
            out.setdefault(
                "source_note",
                row.get("source_note") or f"check_in:{src.name}",
            )

            key = _row_key(out)
            # skip if company/url already closed in ledger
            if f"id:{out.get('app_id','')}" in closed or f"url:{_norm_url(url)}" in closed:
                skipped_closed += 1
                continue
            ckey = f"co:{_norm_company(out.get('company') or '')}"
            if ckey in closed and ckey != "co:":
                skipped_closed += 1
                continue

            if key not in by_key:
                added += 1
            by_key[key] = out

    # Prefer higher cv_score first when writing queue
    rows = list(by_key.values())

    def _score(r: dict) -> float:
        try:
            return float(r.get("cv_score") or r.get("match_score") or 0)
        except Exception:
            return 0.0

    rows.sort(key=_score, reverse=True)

    fieldnames: list[str] = []
    for r in rows:
        for k in r.keys():
            if k not in fieldnames:
                fieldnames.append(k)
    preferred = [
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
        "status",
        "source_note",
    ]
    ordered = [f for f in preferred if f in fieldnames] + [
        f for f in fieldnames if f not in preferred
    ]

    with existing_queue.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ordered, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # Mirror latest discovery source into workdir
    primary = sources[0]
    mirror = workdir / "applications_cv_match_0020.csv"
    try:
        mirror.write_bytes(primary.read_bytes())
    except Exception:
        pass

    # Point complete_apply at this queue via a small marker file
    (workdir / "COMPLETE_QUEUE_CSV.path").write_text(
        str(existing_queue), encoding="utf-8"
    )

    report = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "workdir": str(workdir),
        "sources": [str(s) for s in sources],
        "queue_csv": str(existing_queue),
        "before": before,
        "added": added,
        "queued_total": len(rows),
        "skipped_closed": skipped_closed,
        "skipped_no_url": skipped_no_url,
    }
    (workdir / "check_in_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"added={added}\n")
            f.write(f"queued_total={len(rows)}\n")
            f.write(f"workdir={workdir}\n")
            f.write(f"queue_csv={existing_queue}\n")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("## Check-in applications\n\n")
            f.write(f"- Workdir: `{workdir}`\n")
            f.write(f"- Added new: **{added}**\n")
            f.write(f"- Queue total: **{len(rows)}**\n")
            f.write(f"- Skipped (already closed): {skipped_closed}\n")
            f.write(f"- Queue file: `{existing_queue.name}`\n")
    return report


if __name__ == "__main__":
    rep = check_in()
    if rep.get("error"):
        raise SystemExit(2)
    raise SystemExit(0)
