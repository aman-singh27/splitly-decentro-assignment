# API quickstart

The API runs under `/api/v1`. Open `/developers` for the bundled interactive explorer, or download `/api/openapi.json`, `/api/postman.json`, and `/api/environment.json` from the same server. The OpenAPI schema is generated from the running Django API; the Postman collection is generated from that schema.

## Access without sign-in

Splitly uses access capabilities rather than accounts. The browser silently creates a private workspace and stores access in its Django session. Group sharing grants access to one group. A display name identifies a ledger person; it does not authenticate the person operating the browser. Anyone possessing a group's link can add members, expenses, and recorded payments in that group. Use this model for trusted groups and the assignment demonstration.

Cookie-authenticated writes require Django's `csrftoken` cookie and the matching `X-CSRFToken` header. The frontend handles this automatically. A fresh `GET /api/v1/workspace` returns `401` and establishes the CSRF cookie; `POST /api/v1/workspace` creates the workspace. Export an owner return link with `GET /api/v1/workspace/invite`. Its `key` fragment supplies a private owner capability for API tools. Keep that link private.

For curl/Postman, pass `X-Workspace-Key: ws_...`, or use a group's `X-Group-Key: grp_...`. Explicit capability headers take precedence over the cookie session and do not need cookie CSRF. An invalid capability returns `401`. IDs outside the active scope return `404`. A group capability cannot list other groups or unrelated workspace people, or create unrelated groups. Do not include both capability headers.

To share, use `GET /api/v1/groups/{id}/invite`. In a browser, `/join#key=grp_...&group=ID` exchanges the fragment through `POST /api/v1/workspace/join`; the fragment is not sent as part of the HTTP request URL. Joining does not discard any retained owner access; `POST /api/v1/workspace/switch` with `{"scope":"owner"}` restores it when present.

## Dinner example

The following examples assume the workspace has been created and `SPLITLY_KEY` contains its owner key. The base URL is a shell variable; use your platform's equivalent if needed.

```bash
SPLITLY_URL=http://127.0.0.1:8000
curl "$SPLITLY_URL/api/v1/groups" \
  -H "X-Workspace-Key: $SPLITLY_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Dinner with friends"}'

curl "$SPLITLY_URL/api/v1/users" \
  -H "X-Workspace-Key: $SPLITLY_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Mohit"}'
```

Create Rahul and Ankit through the same users endpoint. Substitute the returned IDs below; example IDs are placeholders, not guaranteed database values.

```bash
curl "$SPLITLY_URL/api/v1/groups/1/members" \
  -H "X-Workspace-Key: $SPLITLY_KEY" \
  -H 'Content-Type: application/json' -d '{"user_id":1}'
```

Add all three users, then create the expense:

```bash
curl "$SPLITLY_URL/api/v1/expenses" \
  -H "X-Workspace-Key: $SPLITLY_KEY" \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: dinner-2026-10-14-1' \
  -d '{"group_id":1,"paid_by":1,"amount":"1200.00","description":"Dinner at the cafe"}'

curl "$SPLITLY_URL/api/v1/groups/1/balances" \
  -H "X-Workspace-Key: $SPLITLY_KEY"
```

The expense response includes three persisted shares of `40000` paise. Rahul owes Mohit `40000` paise; Ankit owes Mohit `40000` paise. The payer's own share is included in allocation and produces no self-debt.

```bash
curl "$SPLITLY_URL/api/v1/groups/1/balances/explanation?user_a_id=1&user_b_id=2" \
  -H "X-Workspace-Key: $SPLITLY_KEY"

curl "$SPLITLY_URL/api/v1/settlements" \
  -H "X-Workspace-Key: $SPLITLY_KEY" \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: rahul-payment-1' \
  -d '{"group_id":1,"from_user_id":2,"to_user_id":1,"amount":"150.00"}'
```

This records a payment made elsewhere; it does not transfer money. Rahul's remaining direct debt is `25000` paise. Explainability includes both the expense contribution and the recorded payment.

## Money, retries, and pagination

- INR only. Amounts accept decimal JSON numbers or strings, at most two fractional digits, strictly positive and at most `10000000.00` INR. Responses include `amount_minor` integer paise plus a decimal string. JSON booleans and nonfinite values are invalid.
- Equal allocation includes every member at expense creation time. Integer division assigns remaining paise deterministically in ascending user-ID order; shares sum exactly to the paid amount. Later membership changes affect new expenses only.
- Custom allocation is optional: add `"split_type":"custom"` and `"splits":[{"user_id":1,"amount":"500.00"},{"user_id":2,"amount":"300.00"},{"user_id":3,"amount":"200.00"}]` to an INR 1,000 expense. Every current member must appear exactly once, amounts may be zero, and the total must match the expense exactly. Omitting both `split_type` and `splits` defaults to the required equal split; supplying `splits` without `split_type` infers custom allocation.
- Expense and settlement creation require an `Idempotency-Key` header. Reuse the same key and payload after an uncertain network result. A successful replay returns the original response/status and `Idempotency-Replayed: true`. Reusing the key with a different payload returns `409`. Numerically equivalent monetary representations are treated alike. Keys are scoped to the workspace, access scope, and operation.
- List responses use `{items, limit, offset, total}`. `limit` defaults to 50 and cannot exceed 100. Balances and explanation totals use the full ledger; paging explanation rows never changes its total.
- Opposite debts cancel within each pair. Cross-group debts are not silently paid off by a payment in another group. Settlements must reduce an existing direct group debt and cannot exceed it.

## Errors

Errors use `{detail, errors?}`. `422` means invalid fields, `401` invalid/missing access, `403` an unavailable action in the active scope, `404` an absent or inaccessible ID, `409` duplicate membership/idempotency conflict, and `503` a transient database lock. Unknown fields are rejected. Keep the idempotency key when retrying a write after a network failure or `503`.

## Postman

Import the collection and environment downloads. Set `base_url` to your server. Obtain the private workspace return link through `GET /api/v1/workspace/invite` in your existing browser session and set `workspace_key` from its `key` fragment. For group-scoped requests, set `group_key` from a group invite and enable that header instead of the workspace header. Set `group_id`, `user_a_id`, `user_b_id`, and `expense_id` to actual returned IDs. The collection is an endpoint catalog with manual setup, rather than a sequential demo runner. Its generated assertions check saved-share totals, participant counts, zero-sum net positions, absence of self-debt, explanation totals, and receipt image content types where applicable.

Generated write examples use Postman's `{{$guid}}` for a fresh idempotency key. For a retry after an uncertain response, replace this dynamic value with the same fixed key used for the first request; generating a new key would create a new operation. The frontend retains its original key automatically. Monetary correctness is additionally verified by automated API and browser tests.

## Optional bill photos

Create the expense first, then `POST /api/v1/expenses/{id}/receipt` with multipart field `photo` and an `Idempotency-Key` header. Supported decoded formats are still JPEG, PNG, and WebP, up to 5 MB and 20 megapixels. The server re-encodes images to remove metadata and ignores the uploaded filename. A protected `GET` to the same route returns the photo to authorized scope holders with private, no-store caching. Expense responses expose `receipt_url` or `null`. Photos are optional and do not affect amounts or shares. There is no OCR.

When a photo upload fails after expense creation, retry the upload against the saved expense ID. Do not create the expense again. The frontend retains that ID and offers “Retry photo upload.” Receipt media needs durable storage alongside the database in deployed environments.
