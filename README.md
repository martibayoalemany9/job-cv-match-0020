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

- `0 7 * * *` and `0 17 * * *` UTC  
- Also: **Actions → cv-match-discover-0020 → Run workflow**

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
```
