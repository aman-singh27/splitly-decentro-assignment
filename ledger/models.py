"""Durable ledger records and constraints; no editable cached balances."""

import secrets

from django.db import models
from django.db.models import F, Q


def workspace_key():
    return "ws_" + secrets.token_urlsafe(32)


def share_nonce():
    return secrets.token_urlsafe(32)


class Workspace(models.Model):
    """Private owner capability; contains people and groups without login."""

    key = models.CharField(max_length=64, unique=True, default=workspace_key)
    created_at = models.DateTimeField(auto_now_add=True)


class Group(models.Model):
    """Sharing unit. A signed capability grants this group only."""

    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT, related_name="groups")
    name = models.CharField(max_length=80)
    share_nonce = models.CharField(max_length=64, default=share_nonce)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]


class Person(models.Model):
    """Self-declared person, not an authenticated account; duplicate names allowed."""

    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT, related_name="people")
    creation_group = models.ForeignKey(
        Group, null=True, blank=True, on_delete=models.PROTECT, related_name="created_people"
    )
    name = models.CharField(max_length=80)
    avatar_key = models.CharField(max_length=24)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]


class Membership(models.Model):
    """Current membership; immutable expense shares snapshot historical membership."""

    group = models.ForeignKey(Group, on_delete=models.PROTECT, related_name="memberships")
    person = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="memberships")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["person_id"]
        constraints = [
            models.UniqueConstraint(fields=["group", "person"], name="unique_group_member")
        ]


class Expense(models.Model):
    """Immutable paid expense; amount and full participant allocation saved atomically."""

    group = models.ForeignKey(Group, on_delete=models.PROTECT, related_name="expenses")
    paid_by = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="paid_expenses")
    amount_minor = models.PositiveBigIntegerField()
    description = models.CharField(max_length=200)
    split_type = models.CharField(
        max_length=8, default="equal", choices=[("equal", "Equal"), ("custom", "Custom")]
    )
    receipt = models.ImageField(upload_to="receipts/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount_minor__gt=0, amount_minor__lte=1_000_000_000),
                name="expense_amount_bounds",
            )
        ]
        indexes = [models.Index(fields=["group", "-id"], name="expense_group_recent")]


class ExpenseShare(models.Model):
    """One historical participant allocation, including the payer's own share."""

    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name="shares")
    person = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="expense_shares")
    amount_minor = models.PositiveBigIntegerField()

    class Meta:
        ordering = ["person_id"]
        constraints = [
            models.UniqueConstraint(fields=["expense", "person"], name="unique_expense_share")
        ]


class Settlement(models.Model):
    """Recorded payment outside Splitly, reducing an existing direct debt only."""

    group = models.ForeignKey(Group, on_delete=models.PROTECT, related_name="settlements")
    from_user = models.ForeignKey(
        Person, on_delete=models.PROTECT, related_name="outgoing_settlements"
    )
    to_user = models.ForeignKey(
        Person, on_delete=models.PROTECT, related_name="incoming_settlements"
    )
    amount_minor = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount_minor__gt=0, amount_minor__lte=1_000_000_000),
                name="settlement_amount_bounds",
            ),
            models.CheckConstraint(condition=~Q(from_user=F("to_user")), name="settlement_no_self"),
        ]
        indexes = [models.Index(fields=["group", "-id"], name="settlement_group_recent")]


class IdempotencyRecord(models.Model):
    """Saved successful mutation result, scoped to access context and operation."""

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    scope = models.CharField(max_length=48)
    operation = models.CharField(max_length=120)
    key = models.CharField(max_length=128)
    request_hash = models.CharField(max_length=64)
    response = models.JSONField()
    status = models.PositiveSmallIntegerField(default=201)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "scope", "operation", "key"], name="unique_mutation_retry"
            )
        ]
