# Nexus Research AI website

This is a static website with a shared-account research workspace. It uses Supabase Auth in the browser and the existing authenticated Railway API; it does not need a second backend or expose a Supabase service-role secret.

## Deploy on Cloudflare Pages

1. Select the GitHub repository and `main` branch.
2. Set the project root/build output directory to `website`.
3. Leave the build command blank; the site is static HTML, CSS, and JavaScript.
4. Add `www.brisklightai.com` and `brisklightai.com` as custom domains and configure DNS as Cloudflare Pages requests.
5. Set the canonical domain/redirect behavior so `brisklightai.com` redirects to `www.brisklightai.com`.
6. Add both HTTPS origins to Railway `NEXUS_ALLOWED_ORIGINS` and Supabase Auth's redirect URL allowlist.

## Before going live

- Add monitored privacy and support contact addresses to the policies; update them with the service operator's legal identity and final retention/deletion process.
- Review the draft Terms and Privacy Policy with the service operator.
- In Supabase Authentication, enable Google OAuth and add `https://www.brisklightai.com/` as an allowed redirect URL. The Google provider callback remains `https://mdjgrtkjjcwmhuhpsjsk.supabase.co/auth/v1/callback`.
- Add the exact origins `https://www.brisklightai.com` and `https://brisklightai.com` to Railway's `NEXUS_ALLOWED_ORIGINS`.
- Configure Railway `PAYPAL_RETURN_URL` and `PAYPAL_CANCEL_URL` to return to the website, for example `https://www.brisklightai.com/?checkout=complete` and `https://www.brisklightai.com/?checkout=cancel`.
- Test email confirmation, password sign-in, Google OAuth, token refresh, scans, reports, saved research, and dossier downloads on the deployed domain.
- Apply the Chrome Web Store screenshots and listing steps in [`../extension/STORE_LISTING.md`](../extension/STORE_LISTING.md).

The Chrome extension package can be built with `python extension/build_release.py` from the repository root.
