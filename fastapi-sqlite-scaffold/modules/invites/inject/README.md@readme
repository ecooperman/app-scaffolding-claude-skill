## Invites (the invites module)

Anyone can ask for a person with no account to be let in (`/invites.html`); the
administrator approves or declines each request there. Approving adds the email to the
Cloudflare Access group (`CF_API_TOKEN`, `CF_ACCOUNT_ID`, `CF_INVITEES_GROUP_ID` in the
shared secrets file) and gives the person an account; they get an email saying how
to sign in (SMTP settings, also shared). Each person may ask for `INVITES_PER_USER`
people (default 5); the administrator is unlimited and approved immediately. The rules
are in `app/invites.py`, the routes in `app/routers/invites.py`. Note the Cloudflare group
is shared by every app on the shared-apps Access application: being let in here lets the
person through the gate for all of them. See `DEPLOYMENT.md`.

