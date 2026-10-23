# Security

Please report security issues privately through the repository's GitHub security advisory feature when available. Do not include credentials, personal records, or exploit details in a public issue.

## Local configuration

Copy the relevant `.env.example` to `.env` and supply your own credentials locally. Example values are placeholders. Environment files, service accounts, private keys, session cookies, local databases and uploads must remain untracked. Browser variables prefixed `VITE_`, `NEXT_PUBLIC_` or `REACT_APP_` are visible to visitors and must never contain a server secret.

## Before contributing

Run `python .github/scripts/privacy_check.py` after staging your changes. Continuous integration repeats that check and scans the current source with Gitleaks. A scan is a safeguard, not a guarantee that every sensitive value has been found.

If a credential is exposed, revoke or rotate it with its provider. Removing the current file does not remove older commits, cached copies or forks. Coordinate any history rewrite with collaborators.
