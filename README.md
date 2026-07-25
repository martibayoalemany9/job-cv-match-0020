# job-cv-match-0020

Scheduled **GitHub Actions** job that finds open roles matching CV **0020_raw** (Martí Bayo Alemany).

## What it does

1. Discovers jobs (Greenhouse + Lever public APIs; optional TheirStack / Apify secrets)
2. Scores each role with `cv_fit.py` against `_cv_0020_extracted.txt` (from `0020_raw_…pdf`)
3. Prefers **Technology Lead** / **Software Architect** titles
4. Writes:
   - `reports/applications_cv_match_0020.csv`
   - `reports/cv_match_report.md`
5. Pushes results to branch `cv-match-latest`

## Schedule

### Discover (find matching jobs)
- `0 7 * * *` and `0 17 * * *` UTC  
- **Actions → cv-match-discover-0020 → Run workflow**

### Grok apply cycle (self-hosted, every 10 minutes)
Workflow: **`grok-apply-cycle`** — runs on the **self-hosted** Windows runner.

| Step | Behavior |
|------|----------|
| Detect | If Grok / `complete_apply` is already running → **do not** start another apply |
| Check-in | Merge `applications_cv_match_0020.csv` into the private apply queue |
| Apply | Start **one** Grok application (`COMPLETE_MAX=1`) via `grok_apply_with_report` |
| Explain | Always run **failure analysis** → `reports/failure_analysis.md` |

- Cron: `*/10 * * * *` UTC  
- Manual: **Actions → grok-apply-cycle → Run workflow**  
- Status branch: `apply-status-latest`

#### Optional Variables (Settings → Variables → Actions)

| Variable | Purpose | Default |
|----------|---------|---------|
| `JOB_APPLY_WORKDIR` | Private data dir (ledger, queue, CV) | `%USERPROFILE%\job-application-bot\data\etoro-apply-report` |
| `GROK_APPLY_ROOT` | Path to `grok_apply_with_report` clone | auto-clone under home |
| `CDP_URL` | Playwright Chromium CDP | `http://127.0.0.1:9223` |
| `COMPLETE_MAX` | Apps per cycle | `1` |

Scripts: `scripts/is_grok_running.py`, `scripts/check_in_applications.py`, `scripts/explain_failures.py`, `scripts/run_grok_apply.ps1`.

## Secrets (optional)

| Secret | Purpose |
|--------|---------|
| `THEIRSTACK_API_KEY` | TheirStack job search |
| `APIFY_TOKEN` | Apify Google Jobs scraper |
| `APIFY_ACTOR_ID` | default `orgupdate~google-jobs-scraper` |

Without secrets, Greenhouse + Lever still run.

## Local

```bash
python3 -u discover_cv_match_jobs.py
# → applications_cv_match_0020.csv + cv_match_report.md

# Check-in + failure explain (self-hosted tools)
python -u scripts/check_in_applications.py
python -u scripts/explain_failures.py
python -u scripts/is_grok_running.py  # exit 0 = running, 1 = idle
```
