## API keys (the api-keys module)

Features that call a paid service use the signed-in person's own key, saved on
`/profile.html` (checked with the service when saved, stored encrypted, never shown
again). An administrator without their own key falls back to the server's key
(`ANTHROPIC_API_KEY` in the shared secrets file); everyone else without one simply
doesn't have the feature. In a route: `key = apikeys.require(db, user, "anthropic")`
(a 400 telling them to add one on Profile), or `apikeys.resolve(...)` for `None`.
Add a service in `app/apikeys.py` (`PROVIDERS` plus a `_verify_...` function).
Production needs `KEY_ENCRYPTION_SECRET` in `/etc/personal-apps/shared.env` - never
change it once keys are saved (see `DEPLOYMENT.md`).

