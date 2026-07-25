# Application failure analysis

Generated: `2026-07-25T19:54:55.660084+00:00`

Workdir: `C:\Users\martibayoalemany4\job-application-bot\data\etoro-apply-report`

| Metric | Count |
|--------|------:|
| Total ledger/result rows | 36 |
| Successful / closed | 1 |
| Failed / incomplete | 13 |

## Why applications failed (grouped)

| Count | Reason |
|------:|--------|
| 5 | Authentication / login wall |
| 4 | Some fields were filled but final submit was not confirmed (validation errors, captcha, missing required field). |
| 2 | Job posting closed |
| 1 | ATS form left incomplete. |
| 1 | Missing required form field |

## By status code

| Count | Status |
|------:|--------|
| 5 | `partial_form_filled` — Some fields were filled but final submit was not confirmed (validation errors, captcha, missing required field). |
| 4 | `login_required` — ATS requires SSO/login; guest apply is unavailable. Needs saved session cookies or a manual login once. |
| 2 | `exception` — The apply script crashed (timeout, tab crash, selector error, network). Check detail + logs; usually safe to retry. |
| 2 | `ats_opened_incomplete` — ATS form left incomplete. |

## Recent failures (detail)

| When | Company | Status | Why | Detail |
|------|---------|--------|-----|--------|
| 2026-07-25T19:34:48 | Vesterling AG | `exception` | Job posting closed | Page.goto: Target page, context or browser has been closed |
| 2026-07-25T19:34:46 | SkillTank GmbH & Co. KG | `exception` | Job posting closed | Page.goto: Target page, context or browser has been closed |
| 2026-07-25T19:34:02 | NTT DATA Europe & Latam | `ats_opened_incomplete` | ATS form left incomplete. | Opened listing but could not fill form. final_url=https://de.linkedin.com/jobs/v |
| 2026-07-25T18:54:35 | Meta (Facebook) | `partial_form_filled` | Some fields were filled but final submit was not confirmed (validation errors, captcha, mi | Still missing: gender |
| 2026-07-25T18:51:48 | Meta (Facebook) | `partial_form_filled` | Some fields were filled but final submit was not confirmed (validation errors, captcha, mi | Submit attempted; verify screenshots for confirmation |
| 2026-07-25T18:49:54 | Meta (Facebook) | `login_required` | Authentication / login wall | Post-submit Meta account login required |
| 2026-07-25T18:45:46 | Meta (Facebook) | `login_required` | Authentication / login wall | Submit led to Meta account login/SSO wall |
| 2026-07-25T18:41:13 | Meta (Facebook) | `login_required` | Authentication / login wall | Meta Careers requires account login/password (or Facebook SSO). Email prefilled  |
| 2026-07-25T18:32:36 | Ashby | `partial_form_filled` | Missing required form field | Clicked submit; may need required fields (uploads=2). Check screenshot. |
| 2026-07-25T18:17:20 | SAP | `partial_form_filled` | Some fields were filled but final submit was not confirmed (validation errors, captcha, mi | Reached SAP apply flow; filled what was possible (uploads=0). Manual finish may  |
| 2026-07-25T18:13:43 | SAP | `partial_form_filled` | Some fields were filled but final submit was not confirmed (validation errors, captcha, mi | In SAP ATS but stuck on multi-step form. uploads=0. url=https://career5.successf |
| 2026-07-25T18:11:50 | SAP | `login_required` | Authentication / login wall | ATS requires candidate account login/password. Email prefilled; complete sign-in |
| 2026-07-25T18:07:49 | SAP | `ats_opened_incomplete` | Authentication / login wall | Opened job posting but could not fill form automatically (likely login wall or c |

## Recommended next actions

1. **login_required** — open CDP browser once, log into those ATS, re-run.
2. **open_only / stuck_on_board** — verify apply URLs resolve to real ATS forms.
3. **exception / timeout** — increase dwell, ensure Chromium CDP `:9223` is up.
4. **partial_form_filled / cv_uploaded_only** — inspect required fields / captcha.
5. Re-queue only non-closed rows (check-in already skips closed companies).
