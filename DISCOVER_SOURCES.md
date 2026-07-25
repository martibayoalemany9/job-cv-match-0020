# Multi-source job discovery

Implements the discovery stack:

| Option | Module | Needs |
|--------|--------|--------|
| **Greenhouse Job Board API** | `discover_sources/greenhouse.py` | Free public API + `boards.json` tokens |
| **Lever postings API** | `discover_sources/lever.py` | Free public API + company slugs |
| **Apify / Crawlee** | `discover_sources/apify_client.py` | `APIFY_TOKEN` + actor id |
| **Bright Data / Oxylabs** | `discover_sources/proxies.py` | Proxy credentials |
| **TheirStack** | `discover_sources/theirstack.py` | `THEIRSTACK_API_KEY` |
| **PredictLeads** | `discover_sources/predictleads.py` | `PREDICTLEADS_API_KEY` |
| **Gmail → queue** | `discover_sources/gmail_alerts.py` + `cloud_functions/gmail_alerts_ingest` | Export JSON / `.eml` / Cloud Function |
| **eFC / Stepstone** | `discover_sources/efc_stepstone.py` | Network; proxy if blocked |

## Quick start

```bash
cd ~/deepline/data/karlsruhe-public-co-job-apps
cp discover_sources.env.example discover_sources.env
# edit keys as available

# Official boards only (no paid keys) — works offline-ish with network
ENABLE_APIFY=0 ENABLE_THEIRSTACK=0 ENABLE_PREDICTLEADS=0 ENABLE_EFC=0 \
  python3 -u discover_all_sources.py

# Full stack when keys are set
python3 -u discover_all_sources.py

# Apply the unified queue
COMPLETE_QUEUE_CSV=applications_discovered_all.csv APPLY_ALL=1 \
  COMPLETE_MAX=15 python3 -u complete_apply.py
```

Outputs:

- `applications_discovered_all.csv` — apply queue  
- `discovered_all_jobs.json` — counts  
- `DISCOVER_SOURCES_SUMMARY.md` — last run table  
- `discover_sources_run.log` — detail log  

## Board tokens

Edit `discover_sources/boards.json`:

```json
{"type": "greenhouse", "token": "stripe", "company": "Stripe"}
{"type": "lever", "token": "netflix", "company": "Netflix"}
```

Token = path segment in `boards.greenhouse.io/{token}` or Lever `jobs.lever.co/{token}`.

## Gmail alerts

**Local**

1. Export recent job-alert emails to `gmail_alerts_export.json`:

```json
[
  {
    "from": "jobalert@stepstone.de",
    "subject": "Technology Lead at Example GmbH",
    "body": "Apply: https://www.stepstone.de/stellenangebote--....html",
    "date": "2026-07-25"
  }
]
```

2. Or drop `.eml` files into `gmail_alerts_inbox/`  
3. Run `discover_all_sources.py` (ENABLE_GMAIL_ALERTS=1)

**Cloud Function**

See `cloud_functions/gmail_alerts_ingest/main.py` — HTTP or Pub/Sub entry points that parse alert payloads and optionally POST to `QUEUE_WEBHOOK_URL`.

## Proxies

When Stepstone/eFC block datacenter IPs:

```bash
# Bright Data
BRIGHTDATA_CUSTOMER=... BRIGHTDATA_ZONE=... BRIGHTDATA_PASSWORD=...

# or Oxylabs
OXYLABS_USERNAME=... OXYLABS_PASSWORD=...

# or full URL
DISCOVER_PROXY_URL=http://user:pass@host:port
```

## CI schedule

`ci/pipeline.sh discover` calls airline/PhD discoverers; also:

```bash
# in Jenkins / launchd
ENABLE_EFC=0 python3 -u discover_all_sources.py
```

Title preference (Technology Lead / Software Architect) is applied in `normalize_job` via `role_filter.title_preference_score`.

## Crawlee (local OSS)

Apify cloud is the managed path. For pure OSS Crawlee, scaffold a Node project separately and write JSON that `apify_client.items_to_jobs` can ingest, or CSV matching the applications_* schema.
