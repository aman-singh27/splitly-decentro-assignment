# Verification

Observed on 14 October 2026 with Python 3.13.3, Node 22.17.0 and npm 10.9.2. These results describe executed checks, not a guarantee that every possible defect is absent.

| Check | Observed result |
| --- | --- |
| Backend unit/API/database/runtime tests | 98 passed, including Render hostname/TLS/CSRF and startup regressions |
| Backend statement / branch coverage | 95.97% / 85.51%; combined 94.18% |
| Frontend unit/component tests | 46 passed |
| Frontend line / branch coverage | 96.99% / 88.29% |
| Browser journeys | 30 passed across desktop Chromium and Pixel 7 emulation; no skips |
| Built single-origin runtime | Same 30 browser checks passed against Waitress with DEBUG=false, without Vite |
| TypeScript and production frontend build | Passed |
| Django system and migration consistency checks | Passed |
| Python Ruff and installed dependency compatibility | Passed |
| npm dependency audit, including development dependencies | Zero reported vulnerabilities |
| OpenAPI validation and exported API artifact consistency | Passed; 22 operations and 22 Postman scripts checked |
| Clean setup from public source in a new directory | Real pip install, npm ci, build, migrations and HTTP checks passed |

Backend coverage includes `ledger` and `config`; test code and generated migrations are excluded. Frontend coverage includes the application, API explorer and entrypoint. All configured coverage gates require at least 80%.

Browser checks cover the assignment's ₹1,200/₹400 case; paise rounding; historical membership; settlements and explanations; scoped group sharing; guests adding their own expense; custom ₹500/₹300/₹200 allocation; optional photos and attachment-only retry; committed writes losing a network response or receiving truncated 201 JSON; mobile overflow; keyboard focus; and the React and standalone Django API explorers.

Regression work followed red/green tests for arithmetic, API access, receipts, concurrency/runtime behavior and frontend recovery issues. Some initial custom-split integration tests were added after the feature implementation; those are regression coverage rather than an observed red/green cycle.

The [verification workflow](../../.github/workflows/verify.yml) repeats the checks on Linux and builds/runs the Docker image, including readiness and frontend HTTP smoke tests. Local Compose configuration validates, but the local Docker daemon was unavailable: actual image execution is assigned to CI. See the repository's Actions run for its observed outcome.

Known product limits remain documented in README: anonymous self-declared identity, bearer invitation access, INR only, addition-only ledger records, one SQLite application instance, no OCR and no actual payment transfer. The Postman export is a configured endpoint catalog, not an automatic seeded end-to-end demo.
