"""Transactional ledger mutations and derived balances; views only coordinate HTTP."""

import hashlib
import json
from collections import defaultdict

from django.db import transaction
from django.db.models import Count, Sum
from rest_framework.exceptions import NotFound

from ledger.errors import Conflict, FieldError
from ledger.models import (
    Expense,
    ExpenseShare,
    IdempotencyRecord,
    Membership,
    Person,
    Settlement,
)
from ledger.money import format_money, split_equal


def person_data(person, scope_group=None, *, group_count=None):
    """Stable public identity independent of duplicate display names."""
    if group_count is not None:
        count = group_count
    elif hasattr(person, "group_count"):
        count = person.group_count
    elif scope_group:
        count = person.memberships.filter(group=scope_group).count()
    else:
        count = person.memberships.count()
    return {
        "id": person.id,
        "name": person.name,
        "avatar_key": person.avatar_key,
        "created_at": person.created_at.isoformat(),
        "group_count": count,
    }


def group_data(group):
    """Real group totals and a small portrait preview, without fabricated metrics."""
    members = list(group.memberships.select_related("person").order_by("person_id"))
    totals = group.expenses.aggregate(total=Sum("amount_minor"), count=Count("id"))
    amount = totals["total"] or 0
    return {
        "id": group.id,
        "name": group.name,
        "member_count": len(members),
        "expense_count": totals["count"],
        "total_expense_minor": amount,
        "total_expense": format_money(amount),
        "currency": "INR",
        "member_preview": [person_data(m.person, group_count=1) for m in members[:4]],
    }


def expense_data(expense):
    """Saved receipt uses immutable share rows, not current group membership."""
    shares = list(expense.shares.select_related("person").order_by("person_id"))
    return {
        "id": expense.id,
        "group_id": expense.group_id,
        "paid_by": {
            "id": expense.paid_by_id,
            "name": expense.paid_by.name,
            "avatar_key": expense.paid_by.avatar_key,
        },
        "description": expense.description,
        "amount_minor": expense.amount_minor,
        "amount": format_money(expense.amount_minor),
        "currency": "INR",
        "created_at": expense.created_at.isoformat(),
        "participant_count": len(shares),
        "split_type": expense.split_type,
        "has_receipt": bool(expense.receipt),
        "receipt_url": f"/api/v1/expenses/{expense.id}/receipt" if expense.receipt else None,
        "shares": [
            {
                "user_id": s.person_id,
                "name": s.person.name,
                "avatar_key": s.person.avatar_key,
                "amount_minor": s.amount_minor,
                "amount": format_money(s.amount_minor),
            }
            for s in shares
        ],
    }


def settlement_data(settlement, remaining=None):
    """Payment acknowledgement never implies an in-app transfer occurred."""
    data = {
        "id": settlement.id,
        "group_id": settlement.group_id,
        "from_user_id": settlement.from_user_id,
        "to_user_id": settlement.to_user_id,
        "amount_minor": settlement.amount_minor,
        "amount": format_money(settlement.amount_minor),
        "currency": "INR",
        "created_at": settlement.created_at.isoformat(),
    }
    if remaining is not None:
        data["remaining_minor"] = remaining
    return data


def paginate(items, params, serializer=lambda item: item):
    """Every collection uses the same bounded limit/offset envelope."""
    limit, offset = params["limit"], params["offset"]
    total = items.count() if hasattr(items, "all") else len(items)
    return {
        "items": [serializer(item) for item in items[offset : offset + limit]],
        "limit": limit,
        "offset": offset,
        "total": total,
    }


def mutate(access, operation, key, data, action, required=False):
    """Serialize writes and atomically store both record and replay response.

    SQLite BEGIN IMMEDIATE acquires a writer reservation before reading the debt
    or membership snapshot; bounded lock errors are translated by the API layer.
    Scope is part of uniqueness so guest replays cannot reveal private responses.
    """
    if required and not key:
        raise FieldError({"Idempotency-Key": "Supply a unique key and retain it for retries."})
    if key and (len(key) > 128 or any(ord(char) < 32 for char in key)):
        raise FieldError({"Idempotency-Key": "Use 1 to 128 printable characters."})
    digest = hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with transaction.atomic():
        if key:
            saved = IdempotencyRecord.objects.filter(
                workspace=access.workspace, scope=access.scope_key, operation=operation, key=key
            ).first()
            if saved:
                if saved.request_hash != digest:
                    raise Conflict("This Idempotency-Key was already used with different fields.")
                return saved.response, saved.status, True
        result = action()
        if key:
            IdempotencyRecord.objects.create(
                workspace=access.workspace,
                scope=access.scope_key,
                operation=operation,
                key=key,
                request_hash=digest,
                response=result,
                status=201,
            )
        return result, 201, False


def create_person(access, data):
    """Guest-created people remain visible only in their creation group scope."""
    person = Person.objects.create(
        workspace=access.workspace,
        creation_group=access.group,
        name=data["name"],
        avatar_key=data.get("avatar_key", "portrait-01"),
    )
    if "avatar_key" not in data:
        person.avatar_key = f"portrait-{((person.id - 1) % 16) + 1:02}"
        person.save(update_fields=["avatar_key"])
    return person_data(person, scope_group=access.group)


def add_member(access, group, person_id):
    """Never attach a person outside the caller's available people scope."""
    person = access.get_person(person_id)
    if Membership.objects.filter(group=group, person=person).exists():
        raise Conflict("This person is already a member.")
    Membership.objects.create(group=group, person=person)
    return person_data(person, scope_group=access.group)


def create_expense(access, data):
    """Persist payer plus all member shares within the mutation transaction."""
    group = access.get_group(data["group_id"])
    ids = list(group.memberships.order_by("person_id").values_list("person_id", flat=True))
    if not ids:
        raise FieldError({"group_id": "Add members before recording an expense."})
    if data["paid_by"] not in ids:
        raise FieldError({"paid_by": "The payer must be a current group member."})
    if data["split_type"] == "custom":
        submitted = data["splits"]
        submitted_ids = [item["user_id"] for item in submitted]
        if sorted(submitted_ids) != ids:
            raise FieldError({"splits": "Include each current group member exactly once."})
        shares = {item["user_id"]: item["amount"] for item in submitted}
        if sum(shares.values()) != data["amount"]:
            raise FieldError({"splits": "Custom shares must add up exactly to the expense amount."})
    else:
        shares = split_equal(data["amount"], ids)
    expense = Expense.objects.create(
        group=group,
        paid_by_id=data["paid_by"],
        amount_minor=data["amount"],
        description=data["description"],
        split_type=data["split_type"],
    )
    ExpenseShare.objects.bulk_create(
        [
            ExpenseShare(expense=expense, person_id=user_id, amount_minor=minor)
            for user_id, minor in shares.items()
        ]
    )
    return expense_data(expense)


def pair_ledger(group_ids):
    """Return signed direct pair totals, without rerouting debt through strangers.

    A pair (low ID, high ID) is positive when high owes low. Settlements subtract
    in the opposite direction from expense obligations. No floating arithmetic.
    """
    pairs = defaultdict(int)
    paid, allocated = defaultdict(int), defaultdict(int)
    for expense in Expense.objects.filter(group_id__in=group_ids).prefetch_related("shares"):
        paid[expense.paid_by_id] += expense.amount_minor
        for share in expense.shares.all():
            allocated[share.person_id] += share.amount_minor
            if share.person_id != expense.paid_by_id:
                low, high = sorted((share.person_id, expense.paid_by_id))
                pairs[(low, high)] += share.amount_minor * (1 if expense.paid_by_id == low else -1)
    for payment in Settlement.objects.filter(group_id__in=group_ids):
        low, high = sorted((payment.from_user_id, payment.to_user_id))
        pairs[(low, high)] += payment.amount_minor * (-1 if payment.to_user_id == low else 1)
    return pairs, paid, allocated


def balances(access, group=None):
    """Derive full-history balances; paging never changes financial totals."""
    group_ids = [group.id] if group else list(access.groups().values_list("id", flat=True))
    people = (
        Person.objects.filter(memberships__group=group).distinct().order_by("id")
        if group
        else access.people().order_by("id")
    )
    pairs, paid, allocated = pair_ledger(group_ids)
    owes, receivable = defaultdict(int), defaultdict(int)
    debts = []
    for (low, high), signed in sorted(pairs.items()):
        if not signed:
            continue
        debtor, creditor = (high, low) if signed > 0 else (low, high)
        amount = abs(signed)
        owes[debtor] += amount
        receivable[creditor] += amount
        debts.append(
            {
                "from_user_id": debtor,
                "to_user_id": creditor,
                "amount_minor": amount,
                "amount": format_money(amount),
            }
        )
    debts.sort(key=lambda item: (item["from_user_id"], item["to_user_id"]))
    members = []
    for person in people:
        net = receivable[person.id] - owes[person.id]
        members.append(
            {
                "user_id": person.id,
                "name": person.name,
                "avatar_key": person.avatar_key,
                "paid_minor": paid[person.id],
                "allocated_minor": allocated[person.id],
                "owes_minor": owes[person.id],
                "receivable_minor": receivable[person.id],
                "net_minor": net,
                "net": format_money(net),
            }
        )
    return {
        "scope": {
            "type": "group" if group else "workspace",
            **({"group_id": group.id} if group else {}),
        },
        "currency": "INR",
        "debts": debts,
        "members": members,
    }


def explain_pair(access, group, params):
    """Explain even zeroed debts by showing expense and settlement contributions."""
    a, b = params["user_a_id"], params["user_b_id"]
    member_ids = set(group.memberships.values_list("person_id", flat=True))
    if not {a, b}.issubset(member_ids):
        raise NotFound("Group member not found.")
    items = []
    for expense in group.expenses.filter(paid_by_id__in=[a, b]).prefetch_related("shares"):
        counterpart = b if expense.paid_by_id == a else a
        share = next(
            (share for share in expense.shares.all() if share.person_id == counterpart), None
        )
        if share is not None:
            items.append(
                {
                    "type": "expense",
                    "record_id": expense.id,
                    "description": expense.description,
                    "created_at": expense.created_at.isoformat(),
                    "contribution_minor": share.amount_minor
                    * (1 if expense.paid_by_id == a else -1),
                    "split_type": expense.split_type,
                }
            )
    for payment in group.settlements.filter(from_user_id__in=[a, b], to_user_id__in=[a, b]):
        items.append(
            {
                "type": "settlement",
                "record_id": payment.id,
                "description": "Payment recorded outside Splitly",
                "created_at": payment.created_at.isoformat(),
                "contribution_minor": payment.amount_minor * (-1 if payment.to_user_id == a else 1),
            }
        )
    items.sort(key=lambda item: (item["created_at"], item["record_id"]), reverse=True)
    signed = sum(item["contribution_minor"] for item in items)
    debtor, creditor = ((b, a) if signed > 0 else (a, b)) if signed else (None, None)
    return {
        "user_a_id": a,
        "user_b_id": b,
        "currency": "INR",
        "signed_total_minor": signed,
        "amount_minor": abs(signed),
        "amount": format_money(abs(signed)),
        "from_user_id": debtor,
        "to_user_id": creditor,
        **paginate(items, params),
    }


def create_settlement(access, data):
    """Verify debt under the same writer lock as the resulting payment insert."""
    group = access.get_group(data["group_id"])
    member_ids = set(group.memberships.values_list("person_id", flat=True))
    if not {data["from_user_id"], data["to_user_id"]}.issubset(member_ids):
        raise FieldError({"members": "Both people must belong to this group."})
    current = balances(access, group)
    debt = next(
        (
            item["amount_minor"]
            for item in current["debts"]
            if item["from_user_id"] == data["from_user_id"]
            and item["to_user_id"] == data["to_user_id"]
        ),
        0,
    )
    if data["amount"] > debt:
        raise Conflict("Payment exceeds the current direct debt. Refresh balances.")
    settlement = Settlement.objects.create(
        group=group,
        from_user_id=data["from_user_id"],
        to_user_id=data["to_user_id"],
        amount_minor=data["amount"],
    )
    return settlement_data(settlement, debt - data["amount"])
