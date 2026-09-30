
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

Set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in Railway. The service-role key is server-only and must never be added to the extension. Set `NEXUS_ALLOWED_ORIGINS` (or `CORS_origins`) to a comma-separated list containing `https://brisklightai.com` and `chrome-extension://cgnachdfccocngempafblhkjckcpjood`. User-facing Railway API routes validate the Supabase bearer token against Supabase Auth.
