# Phase 3A: automated NFL statistics refresh

This package automates the **existing** `export.py` and updates the existing `public.nfl_stat_exports` row. It does **not** yet create pregame predictions, grade them, sync injury reports, or alter the HTML application.

1. Copy `export.py`, `requirements-phase3.txt`, `scripts/upload_stats.py`, and `.github/workflows/nfl-stats-refresh.yml` into the **same paths** in the `NFL_Parlays_Test` repository on its default `main` branch. GitHub scheduled workflows only run from the default branch. For testing a feature branch, commit there, then merge to `main` when ready; `workflow_dispatch` availability may require workflow to be present on default branch.
2. In repository Settings → Secrets and variables → Actions, create `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` repository secrets. Get the secret key from your Supabase project's API keys settings. **Never put the service-role key in HTML, source control, logs, or chat.** For safer isolation, use a separate Supabase test project; this package targets whichever project URL is configured.
3. In Actions, select **NFL stats refresh (Phase 3A)** → **Run workflow**. Inspect logs for `Uploaded ... rows ... successfully`.
4. In Supabase SQL Editor verify:
   ```sql
   SELECT season, generated_at, record_count, length(csv_text) AS csv_characters
   FROM public.nfl_stat_exports ORDER BY generated_at DESC;
   ```
5. Confirm that the app can read the updated cloud stats on both devices.

Schedule is 12:35 UTC daily September–February; GitHub schedules can run late or be disabled after inactivity. Failures leave the existing database row unchanged. The script rejects unexpectedly small or malformed exports. No historical pregame predictions are fabricated.

**Important:** GitHub Actions on the test repository using the same Supabase credentials will update the shared database used by production. Prefer a separate Supabase test project if you need full isolation.
