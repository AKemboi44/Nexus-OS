
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

In Supabase **Authentication → URL Configuration**, keep `https://brisklightai.com` as the site URL and add the exact extension redirect URI returned by `chrome.identity.getRedirectURL()` to the redirect allowlist. For the extension ID `cgnachdfccocngempafblhkjckcpjood`, this is normally:

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

When both Supabase environment variables are configured, Railway writes scans,
analytics, entitlements, and payment webhook idempotency records to Supabase.
Without them, local development retains the existing SQLite stores; user-facing
cloud API endpoints still require Supabase authentication and database
configuration.

The authenticated API supports:

- `POST /v1/scan` to run and save a research scan.
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
