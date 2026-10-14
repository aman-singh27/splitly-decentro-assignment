# Product enhancement: explain every balance

## Problem

An unexplained number such as “Rahul owes Mohit INR 250” is difficult to trust after multiple expenses, rounding, and partial payments. Users need to trace the debt back to the records that produced it.

## Behavior

“Why this amount?” opens a pair's ledger explanation inside the group. It lists saved expense contributions and recorded payments, and shows the full remaining amount. The explanation is available even when the pair has settled to zero; that history remains useful.

Example: Mohit pays INR 1,200 for Mohit, Rahul, and Ankit. Rahul's saved expense share contributes INR 400 to the Mohit/Rahul pair. A recorded Rahul-to-Mohit payment of INR 150 contributes minus INR 150. The resulting debt is INR 250.

The API exposes `/api/v1/groups/{id}/balances/explanation?user_a_id=...&user_b_id=...`. A positive signed contribution means user B owes user A; a negative contribution points the other way. `signed_total_minor` comes from the full history while `items` is paginated. The ordinary balance endpoint and explanation use the same ledger rules.

## Design choices

Saved participant allocations make the explanation stable after membership changes. Integer paise make rounding inspectable and exact. Display names and portrait keys help identify people, while IDs remain authoritative when names repeat. Partial-payment records explain why the original share differs from the current debt.

We keep direct pair relationships rather than rerouting debts among different people. This preserves an understandable connection between “who paid” and “who owes.” Settlement recording is an additional optional feature; the mandatory enhancement is the explanation itself.

## Tradeoffs

Reading the ledger to build explanations costs more than returning a cached total. Pagination bounds the displayed rows without changing the balance total. The record trail explains arithmetic, but cannot prove that a no-sign-in user reported truthfully or that a payment actually occurred. This application records payments made elsewhere; it has no payment gateway.

Optional custom amount splits and bill-photo attachment complement the required equal split. The explanation always uses saved shares, regardless of split type. Photos are reference material with no OCR or automatic allocation. Future improvements include authenticated attribution, expense correction through reversal records, and exportable group statements.
