"""Public response contracts used by the generated OpenAPI and Swagger explorer."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from ledger.serializers import MoneyField, ShareMoneyField

extend_schema_field(
    {
        "oneOf": [
            {"type": "string", "pattern": r"^\d+(\.\d{1,2})?$"},
            {"type": "number", "minimum": 0.01, "maximum": 10000000},
        ]
    }
)(MoneyField)
extend_schema_field(
    {
        "oneOf": [
            {"type": "string", "pattern": r"^\d+(\.\d{1,2})?$"},
            {"type": "number", "minimum": 0, "maximum": 10000000},
        ]
    }
)(ShareMoneyField)


class WorkspaceOutput(serializers.Serializer):
    id = serializers.IntegerField()
    scope = serializers.ChoiceField(choices=["workspace", "group"])
    group_id = serializers.IntegerField(allow_null=True)
    can_switch_to_owner = serializers.BooleanField()


class PersonOutput(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    avatar_key = serializers.CharField()
    created_at = serializers.DateTimeField()
    group_count = serializers.IntegerField()


class GroupOutput(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    member_count = serializers.IntegerField()
    expense_count = serializers.IntegerField()
    total_expense_minor = serializers.IntegerField()
    total_expense = serializers.CharField()
    currency = serializers.CharField()
    member_preview = PersonOutput(many=True)


class ShareOutput(serializers.Serializer):
    user_id = serializers.IntegerField()
    name = serializers.CharField()
    avatar_key = serializers.CharField()
    amount_minor = serializers.IntegerField()
    amount = serializers.CharField()


class PayerOutput(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    avatar_key = serializers.CharField()


class ExpenseOutput(serializers.Serializer):
    id = serializers.IntegerField()
    group_id = serializers.IntegerField()
    paid_by = PayerOutput()
    description = serializers.CharField()
    amount_minor = serializers.IntegerField()
    amount = serializers.CharField()
    currency = serializers.CharField()
    created_at = serializers.DateTimeField()
    participant_count = serializers.IntegerField()
    shares = ShareOutput(many=True)
    split_type = serializers.ChoiceField(choices=["equal", "custom"])
    has_receipt = serializers.BooleanField()
    receipt_url = serializers.CharField(allow_null=True)


class SettlementOutput(serializers.Serializer):
    id = serializers.IntegerField()
    group_id = serializers.IntegerField()
    from_user_id = serializers.IntegerField()
    to_user_id = serializers.IntegerField()
    amount_minor = serializers.IntegerField()
    amount = serializers.CharField()
    currency = serializers.CharField()
    created_at = serializers.DateTimeField()
    remaining_minor = serializers.IntegerField(required=False)


class ErrorOutput(serializers.Serializer):
    detail = serializers.CharField()
    errors = serializers.JSONField(required=False)


class InviteOutput(serializers.Serializer):
    url = serializers.CharField()
    scope = serializers.CharField()
    group_id = serializers.IntegerField(required=False)


class DebtOutput(serializers.Serializer):
    from_user_id = serializers.IntegerField()
    to_user_id = serializers.IntegerField()
    amount_minor = serializers.IntegerField()
    amount = serializers.CharField()


class BalanceMemberOutput(serializers.Serializer):
    user_id = serializers.IntegerField()
    name = serializers.CharField()
    avatar_key = serializers.CharField()
    paid_minor = serializers.IntegerField()
    allocated_minor = serializers.IntegerField()
    owes_minor = serializers.IntegerField()
    receivable_minor = serializers.IntegerField()
    net_minor = serializers.IntegerField()
    net = serializers.CharField()


class ScopeOutput(serializers.Serializer):
    type = serializers.ChoiceField(choices=["workspace", "group"])
    group_id = serializers.IntegerField(required=False)


class BalanceOutput(serializers.Serializer):
    scope = ScopeOutput()
    currency = serializers.CharField()
    debts = DebtOutput(many=True)
    members = BalanceMemberOutput(many=True)


class ExplanationItem(serializers.Serializer):
    type = serializers.ChoiceField(choices=["expense", "settlement"])
    record_id = serializers.IntegerField()
    description = serializers.CharField()
    created_at = serializers.DateTimeField()
    contribution_minor = serializers.IntegerField()
    split_type = serializers.CharField(required=False)


class ExplanationOutput(serializers.Serializer):
    user_a_id = serializers.IntegerField()
    user_b_id = serializers.IntegerField()
    currency = serializers.CharField()
    signed_total_minor = serializers.IntegerField()
    amount_minor = serializers.IntegerField()
    amount = serializers.CharField()
    from_user_id = serializers.IntegerField(allow_null=True)
    to_user_id = serializers.IntegerField(allow_null=True)
    items = ExplanationItem(many=True)
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    total = serializers.IntegerField()


def envelope(name, item_serializer):
    """Create named collection schemas matching the common runtime envelope."""
    return type(
        name,
        (serializers.Serializer,),
        {
            "items": item_serializer(many=True),
            "limit": serializers.IntegerField(),
            "offset": serializers.IntegerField(),
            "total": serializers.IntegerField(),
        },
    )


PeopleOutput = envelope("PeopleOutput", PersonOutput)
GroupsOutput = envelope("GroupsOutput", GroupOutput)
ExpensesOutput = envelope("ExpensesOutput", ExpenseOutput)
SettlementsOutput = envelope("SettlementsOutput", SettlementOutput)


def normalize_paths(endpoints):
    """Optional trailing slash routes are documented once using the UI convention."""
    return [
        (path.rstrip("/"), path_regex, method, callback)
        for path, path_regex, method, callback in endpoints
    ]


def normalize_ids(result, generator, request, public):
    """Named regex ID routes are integers even though Django regexes are strings."""
    for operations in result["paths"].values():
        for operation in operations.values():
            if not isinstance(operation, dict):
                continue
            for parameter in operation.get("parameters", []):
                if parameter.get("in") == "path" and parameter.get("name", "").endswith("_id"):
                    parameter["schema"] = {"type": "integer", "minimum": 1}
    return result
