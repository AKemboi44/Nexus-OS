
This contains a complete Nexus Research AI Discovery MVP with OpenAlex normalization and evals


Every Nexus Research AI module must have:

1. Unit Tests
2. Benchmark Data
3. Evaluation Script

No module moves to production
without all three.

**This is the flow:**
Research Query
        ↓
OpenAlex
        ↓
Raw JSON
        ↓
Normalization
        ↓
Source
        ↓
DiscoveryResult
        ↓
Eval

## Supabase authentication

The Chrome extension uses Supabase Auth with email/password and Google OAuth. Configure Google under Supabase **Authentication → Providers** and set its authorized callback URL to:

`https://mdjgrtkjjcwmhuhpsjsk.supabase.co/auth/v1/callback`

In Supabase **Authentication → URL Configuration**, use `https://www.brisklightai.com` as the canonical site URL, allow both `https://www.brisklightai.com/` and `https://brisklightai.com/`, and add the exact extension redirect URI returned by `chrome.identity.getRedirectURL()` to the redirect allowlist. For the extension ID `cgnachdfccocngempafblhkjckcpjood`, this is normally:

`https://cgnachdfccocngempafblhkjckcpjood.chromiumapp.org/`

The API is hosted at `https://nexus-os-production-2e14.up.railway.app`. Set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in Railway. The service-role key is server-only and must never be added to the extension. Set `NEXUS_ALLOWED_ORIGINS` (or `CORS_origins`) to a comma-separated list containing `https://brisklightai.com`, `https://www.brisklightai.com`, and `chrome-extension://cgnachdfccocngempafblhkjckcpjood`. User-facing Railway API routes validate the Supabase bearer token against Supabase Auth.

## Supabase application database

Before enabling database-backed persistence in Railway, apply
[`supabase/migrations/202610010001_initial_app_data.sql`](supabase/migrations/202610010001_initial_app_data.sql)
to the Supabase project using the SQL Editor or Supabase CLI. It creates user-owned
research history, saved dossiers and sources, server-only analytics and entitlement
tables, and the analytics-summary function. Row-level security limits direct
research and saved-item access to each authenticated owner. The Railway API uses
the service-role key and also filters every user-facing query by the authenticated
Supabase user ID.

Apply
[`supabase/migrations/202610010002_research_dossier_downloads.sql`](supabase/migrations/202610010002_research_dossier_downloads.sql)
as well. It creates the private `research-dossiers` Storage bucket and an atomic
per-user download counter. New Excel dossiers are stored privately in Supabase
Storage rather than on the API server's filesystem. Free accounts can download
three dossiers; active paid entitlements and the verified `akiptoo20@gmail.com`
account have unlimited downloads. Each successful free download consumes one
allowance, including repeat downloads of the same dossier.

Apply
[`supabase/migrations/202610010003_backfill_saved_research_dossiers.sql`](supabase/migrations/202610010003_backfill_saved_research_dossiers.sql)
to backfill saved-dossier index records for existing research runs. New scans
also create a saved-dossier record linked to the full result in `research_runs`;
the index stores counts and filename rather than duplicating all source data.

When both Supabase environment variables are configured, Railway writes scans,
analytics, entitlements, and payment webhook idempotency records to Supabase.
Without them, local development retains the existing SQLite stores; user-facing
cloud API endpoints still require Supabase authentication and database
configuration.

The authenticated API supports:

- `POST /v1/scan` to run and save a research scan.
- `GET /v1/research/{run_id}/dossier` to download that run's Excel dossier.
- `POST /v1/reports` to generate and download a Word report.
- `GET /v1/research` and `GET /v1/research/{run_id}` for the current user's saved scans.
- `GET`, `POST`, and `DELETE /v1/dossiers` for saved dossiers.
- `GET`, `POST`, and `DELETE /v1/sources` for saved sources.

All these routes require a Supabase access token. Never expose the service-role key
in extension or website code; browser clients should use the publishable key and
Supabase Auth.

## Chrome extension distribution

The extension sends research scans and report-generation requests to the
authenticated Railway API. It no longer requires a locally installed Native
Messaging host, Python environment, or machine-specific filesystem paths. Scans
are persisted to the signed-in user's Supabase research history, and generated
Word reports are returned to the browser for download. The same API is intended
to serve the website client.

To build the Chrome Web Store ZIP, run `python extension/build_release.py` from
the repository root. The generated package is saved under `extension/dist/`.
Listing copy and final submission requirements are in
[`extension/STORE_LISTING.md`](extension/STORE_LISTING.md).

## Website

The static web workspace is in [`website/`](website/), built to deploy on
Cloudflare Pages with `website` as the project root and no build command. It
uses the existing Supabase Auth project and Railway API. Review the deployment
and launch checklist in [`website/README.md`](website/README.md); in particular,
verify the privacy/support contact, set the website origins in Railway and
Supabase Auth, and configure DNS before launch.
