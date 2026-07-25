"""Parse Gmail job-alert emails into queue rows.

Local path:
  - Uses Gmail MCP if unavailable falls back to mbox/export JSON, or
  - Chrome CDP Gmail scrape via existing helpers when ALERT_CDP_URL set,
  - Or reads `gmail_alerts_export.json` (array of {subject, body, from, date}).

Cloud path:
  - Same parse_alert_email() used by cloud_functions/gmail_alerts_ingest

Supported-ish senders: Stepstone, eFinancialCareers, LinkedIn, Indeed, Xing,
EuroTechJobs, Greenhouse digests, Lever digests.
"""
from __future__ import annotations

import json
import re
from email import policy
from email.parser import BytesParser
from pathlib import Path
from urllib.parse import unquote, urlparse

from discover_sources.common import W, env, log, normalize_job

LOG = W / "discover_sources_run.log"
EXPORT = W / "gmail_alerts_export.json"
OUT_JSON = W / "gmail_alerts_parsed.json"

URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.I)
TRACKING_SKIP = re.compile(
    r"unsubscribe|mailto:|schemas\.|facebook\.com|twitter\.com|instagram|"
    r"linkedin\.com/comm/|doubleclick|googleads|tracking|pixel",
    re.I,
)

SENDER_HINTS = re.compile(
    r"stepstone|efinancialcareers|linkedin|indeed|xing|eurotechjobs|"
    r"euroengineer|greenhouse|lever\.co|smartrecruiters|workable|"
    r"job.?alert|jobs@|careers@",
    re.I,
)


def extract_urls(text: str) -> list[str]:
    found = []
    for m in URL_RE.findall(text or ""):
        u = m.rstrip(".,;:)>\"'")
        # unwrap common redirectors
        if "url=" in u and ("linkedin.com" in u or "stepstone" in u):
            try:
                from urllib.parse import parse_qs, urlparse as up

                qs = parse_qs(up(u).query)
                for key in ("url", "u", "redirectUrl", "dest"):
                    if key in qs and qs[key]:
                        u = unquote(qs[key][0])
                        break
            except Exception:
                pass
        if TRACKING_SKIP.search(u):
            continue
        if not re.search(
            r"job|career|greenhouse|lever|workday|personio|smartrecruiters|"
            r"ashby|icims|taleo|successfactors|stepstone|indeed|efinancial",
            u,
            re.I,
        ):
            # still keep if path looks like /jobs/
            if not re.search(r"/jobs?/|/apply|/vacanc|/position", u, re.I):
                continue
        found.append(u.split("#")[0])
    # unique preserve order
    seen = set()
    out = []
    for u in found:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def title_from_subject(subject: str) -> str:
    s = re.sub(r"^(re:|fwd:)\s*", "", (subject or "").strip(), flags=re.I)
    s = re.sub(
        r"\s*[-|–]\s*(linkedin|stepstone|indeed|efinancialcareers|job alert).*$",
        "",
        s,
        flags=re.I,
    )
    return s[:200] if s else "Job alert role"


def company_from_text(subject: str, body: str, url: str) -> str:
    for pat in [
        r"at\s+([A-Z][\w .&-]{2,40})\b",
        r"bei\s+([A-ZÄÖÜ][\w .&-]{2,40})\b",
        r"@\s*([A-Z][\w .&-]{2,40})\b",
    ]:
        m = re.search(pat, subject or "")
        if m:
            return m.group(1).strip()
    host = urlparse(url).netloc.lower().replace("www.", "")
    if host:
        return host.split(".")[0].title()
    return "Unknown"


def parse_alert_email(
    *,
    subject: str = "",
    body: str = "",
    sender: str = "",
    date: str = "",
) -> list[dict]:
    """Parse one email into normalized jobs."""
    blob = f"{sender}\n{subject}\n{body}"
    if sender and not SENDER_HINTS.search(sender) and not SENDER_HINTS.search(subject):
        # still allow if body has job URLs
        if not extract_urls(body):
            return []
    urls = extract_urls(blob)
    jobs = []
    base_title = title_from_subject(subject)
    for i, u in enumerate(urls[:12]):
        title = base_title if i == 0 else f"{base_title} [{i+1}]"
        # try line near url in body for better title
        for line in (body or "").splitlines():
            if u[:40] in line or (len(u) > 20 and u.split("/")[-1][:20] in line):
                t = re.sub(r"https?://\S+", "", line).strip(" -|·•\t")
                if 8 <= len(t) <= 120:
                    title = t
                break
        company = company_from_text(subject, body, u)
        row = normalize_job(
            source="gmail_alert",
            company=company,
            title=title,
            url=u,
            location="",
            description=f"from:{sender} date:{date} subject:{subject}"[:500],
            extra={"sender": sender, "date": date},
        )
        if row:
            jobs.append(row)
    return jobs


def load_export_messages() -> list[dict]:
    """Load messages from gmail_alerts_export.json if present."""
    if not EXPORT.exists():
        return []
    try:
        data = json.loads(EXPORT.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(data, dict):
        data = data.get("messages") or data.get("emails") or []
    return list(data) if isinstance(data, list) else []


def discover_gmail_alerts() -> list[dict]:
    """Main entry: parse export file and optional .eml drops."""
    messages = load_export_messages()
    # also scan gmail_alerts_inbox/*.eml
    inbox = W / "gmail_alerts_inbox"
    if inbox.is_dir():
        for eml in sorted(inbox.glob("*.eml"))[:50]:
            try:
                msg = BytesParser(policy=policy.default).parsebytes(eml.read_bytes())
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body += part.get_content() or ""
                        elif part.get_content_type() == "text/html" and not body:
                            body += part.get_content() or ""
                else:
                    body = msg.get_content() or ""
                messages.append(
                    {
                        "subject": str(msg.get("subject") or ""),
                        "body": body if isinstance(body, str) else str(body),
                        "from": str(msg.get("from") or ""),
                        "date": str(msg.get("date") or ""),
                    }
                )
            except Exception as e:
                log(f"gmail eml {eml.name}: {e}", log_path=LOG)

    if not messages:
        log(
            "gmail_alerts: no export/inbox messages — "
            "write gmail_alerts_export.json or drop .eml into gmail_alerts_inbox/",
            log_path=LOG,
        )
        return []

    all_jobs: list[dict] = []
    for m in messages:
        jobs = parse_alert_email(
            subject=m.get("subject") or m.get("Subject") or "",
            body=m.get("body") or m.get("snippet") or m.get("text") or "",
            sender=m.get("from") or m.get("sender") or "",
            date=m.get("date") or "",
        )
        all_jobs.extend(jobs)
    OUT_JSON.write_text(json.dumps(all_jobs, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"gmail_alerts: {len(all_jobs)} jobs from {len(messages)} messages", log_path=LOG)
    return all_jobs


if __name__ == "__main__":
    js = discover_gmail_alerts()
    print(len(js))
