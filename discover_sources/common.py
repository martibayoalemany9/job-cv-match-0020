"""Shared helpers for multi-source job discovery."""
from __future__ import annotations

import csv
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

W = Path(__file__).resolve().parent.parent
ENV_FILE = W / "discover_sources.env"
CREDS = W / "credentials_local.env"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 "
    "JobDiscover/1.0"
)


def load_env(*, force_file: bool = True) -> dict[str, str]:
    """Load key=value from discover_sources.env + credentials_local.env into os.environ.

    force_file=True (default): file values win over a possibly broken shell `source`
    (JWT tokens break when unquoted in bash).
    """
    out: dict[str, str] = {}
    for path in (CREDS, ENV_FILE):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if not k:
                continue
            if force_file or k not in os.environ or not os.environ.get(k):
                if v:
                    os.environ[k] = v
            out[k] = os.environ.get(k, v)
    return out


def env(key: str, default: str = "") -> str:
    load_env()
    return (os.environ.get(key) or default).strip()


def log(msg: str = "", *, log_path: Path | None = None) -> None:
    line = f"{datetime.now().isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def http_get_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 45,
    proxy_url: str | None = None,
) -> Any:
    """GET JSON (optionally via HTTP(S)_PROXY-style proxy URL)."""
    h = {"User-Agent": UA, "Accept": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    handlers = []
    if proxy_url:
        handlers.append(
            urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        )
    opener = urllib.request.build_opener(*handlers) if handlers else urllib.request.build_opener()
    with opener.open(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8", errors="replace"))


def http_get_text(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 45,
    proxy_url: str | None = None,
) -> str:
    h = {"User-Agent": UA, "Accept": "text/html,application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    handlers = []
    if proxy_url:
        handlers.append(
            urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        )
    opener = urllib.request.build_opener(*handlers) if handlers else urllib.request.build_opener()
    with opener.open(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def prefer_title_boost(title: str) -> int:
    try:
        from role_filter import title_preference_score

        return int(title_preference_score(title))
    except Exception:
        t = (title or "").lower()
        if re.search(r"technology lead|tech lead|software architect|solution", t):
            return 100
        if re.search(r"principal|staff|architect", t):
            return 50
        if re.search(r"senior software", t):
            return 15
        return 0


def normalize_job(
    *,
    source: str,
    company: str,
    title: str,
    url: str,
    location: str = "",
    description: str = "",
    extra: dict | None = None,
) -> dict | None:
    """Return a queue-ready job dict or None if filtered out."""
    title = re.sub(r"\s+", " ", (title or "").strip())
    url = (url or "").strip()
    company = (company or "").strip() or "Unknown"
    if not url.startswith("http") or len(title) < 3:
        return None
    try:
        from role_filter import (
            is_never_apply,
            is_junior_or_student_track,
            is_phd_role,
            is_target_role,
        )

        if is_never_apply(title, company, url) and not is_phd_role(title, url, company):
            return None
        if is_junior_or_student_track(title, url, company) and not is_phd_role(
            title, url, company
        ):
            return None
        # Keep if target role OR preferred keywords OR phd
        if not (
            is_target_role(title, company, url)
            or is_phd_role(title, url, company, description)
            or re.search(
                r"technology lead|tech lead|software architect|solution[s]? architect|"
                r"principal|staff software|software engineer|engineering manager",
                title,
                re.I,
            )
        ):
            return None
    except Exception:
        pass

    score = 5 + prefer_title_boost(title)
    try:
        from cv_fit import job_fit_score

        fits, sc, _ = job_fit_score(title, description, company, min_score=2)
        if fits:
            score = max(score, int(sc) + prefer_title_boost(title) // 10)
        elif sc:
            score = max(score, int(sc))
    except Exception:
        pass

    row = {
        "source": source,
        "company": company,
        "title": title[:220],
        "url": url.split("#")[0],
        "location": (location or "")[:120],
        "description": (description or "")[:2000],
        "score": score,
        "host": urlparse(url).netloc.lower(),
    }
    if extra:
        row["extra"] = extra
    return row


def write_queue_csv(
    jobs: Iterable[dict],
    out_path: Path,
    *,
    board: str,
    market: str = "multi",
    prefix: str = "SRC",
) -> int:
    from candidate_profile import CERTS, CV

    by_url: dict[str, dict] = {}
    for j in jobs:
        u = j.get("url") or ""
        if not u:
            continue
        prev = by_url.get(u)
        if not prev or int(j.get("score") or 0) > int(prev.get("score") or 0):
            by_url[u] = j
    jobs_sorted = sorted(
        by_url.values(),
        key=lambda x: (-int(x.get("score") or 0), x.get("company") or ""),
    )
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
        "cv_path",
        "certs_path",
        "salary_target",
        "status",
        "resolve",
        "source_note",
        "market",
    ]
    rows = []
    for i, j in enumerate(jobs_sorted, 1):
        rows.append(
            {
                "app_id": f"{prefix}-{i:04d}",
                "board": board,
                "company": j.get("company") or "",
                "title": j.get("title") or "",
                "location": j.get("location") or "",
                "apply_url": j.get("url") or "",
                "employer_url": j.get("url") or "",
                "careers_url": j.get("url") or "",
                "match_score": j.get("score") or 0,
                "cv_path": str(Path(CV).resolve()),
                "certs_path": str(Path(CERTS).resolve()),
                "salary_target": "70400-120000 EUR",
                "status": "queued",
                "resolve": "ok",
                "source_note": j.get("source") or board,
                "market": market,
            }
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def merge_jsonl(path: Path, jobs: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for j in jobs:
            f.write(json.dumps(j, ensure_ascii=False) + "\n")


def load_board_tokens(path: Path | None = None) -> list[dict]:
    """Load greenhouse/lever board tokens from JSON list."""
    p = path or (W / "discover_sources" / "boards.json")
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return list(data) if isinstance(data, list) else list(data.get("boards") or [])
    except Exception:
        return []
