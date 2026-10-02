
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

## Hosting

The Chrome extension and API is hosted at uses Supabase. 

## Supabase application database

Before enabling database-backed persistence in Railway, create and apply database scripts
to the Supabase project using the SQL Editor or Supabase CLI. It creates user-owned
research history, saved dossiers and sources, server-only analytics and entitlement
tables, and the analytics-summary function. Row-level security limits direct
research and saved-item access to each authenticated owner. The Railway API uses
the service-role key and also filters every user-facing query by the authenticated
Supabase user ID.

The research dossier tables creates the private `research-dossiers` Storage bucket and an atomic
per-user download counter. New Excel dossiers are stored privately in Supabase
Storage rather than on the API server's filesystem. Free accounts can download
three dossiers; active paid entitlements and the verified `admin account`
account have unlimited downloads. Each successful free download consumes one
allowance, including repeat downloads of the same dossier.

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
