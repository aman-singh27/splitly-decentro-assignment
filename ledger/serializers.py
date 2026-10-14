"""Strict request contracts and exact JSON decimal parsing for money inputs."""

import json
from decimal import Decimal

from rest_framework import serializers
from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser

from ledger.money import parse_money


class ExactJSONParser(JSONParser):
    """Preserve JSON fractions as Decimal instead of binary floating point."""

    def parse(self, stream, media_type=None, parser_context=None):
        try:
            return json.loads(
                stream.read().decode("utf-8"),
                parse_float=Decimal,
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
            )
        except (ValueError, UnicodeDecodeError) as exc:
            raise ParseError("Malformed JSON or non-finite numeric value.") from exc


class StrictSerializer(serializers.Serializer):
    """Fail unknown keys so a client cannot silently submit unsupported behavior."""

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError({"body": "Expected a JSON object."})
        extra = set(data) - set(self.fields)
        if extra:
            raise serializers.ValidationError({key: "Unknown field." for key in sorted(extra)})
        return super().to_internal_value(data)


class EmptyInput(StrictSerializer):
    pass


class NameInput(StrictSerializer):
    name = serializers.CharField(max_length=80, trim_whitespace=True)


class UserInput(NameInput):
    avatar_key = serializers.RegexField(r"^portrait-(0[1-9]|1[0-6])$", required=False)


class JoinInput(StrictSerializer):
    access_key = serializers.CharField(max_length=512)


class SwitchInput(StrictSerializer):
    scope = serializers.ChoiceField(choices=["owner"])


class MemberInput(StrictSerializer):
    user_id = serializers.IntegerField(min_value=1)


class MoneyField(serializers.Field):
    """Deserialize exact positive rupee values into canonical integer paise."""

    def to_internal_value(self, value):
        try:
            return parse_money(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def to_representation(self, value):
        from ledger.money import format_money

        return format_money(value)


class ShareMoneyField(MoneyField):
    """Custom allocation permits a zero share, while total expense stays positive."""

    def to_internal_value(self, value):
        try:
            return parse_money(value, allow_zero=True)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc


class SplitInput(StrictSerializer):
    user_id = serializers.IntegerField(min_value=1)
    amount = ShareMoneyField()


class ExpenseInput(StrictSerializer):
    group_id = serializers.IntegerField(min_value=1)
    paid_by = serializers.IntegerField(min_value=1)
    amount = MoneyField()
    description = serializers.CharField(max_length=200, trim_whitespace=True)
    split_type = serializers.ChoiceField(choices=["equal", "custom"], required=False)
    splits = SplitInput(many=True, required=False, allow_empty=False)

    def validate(self, attrs):
        attrs["split_type"] = attrs.get("split_type", "custom" if "splits" in attrs else "equal")
        if attrs["split_type"] == "equal" and "splits" in attrs:
            raise serializers.ValidationError(
                {"splits": "Equal splitting cannot include custom shares."}
            )
        if attrs["split_type"] == "custom" and "splits" not in attrs:
            raise serializers.ValidationError({"splits": "Supply every member's custom share."})
        if "splits" in attrs:
            attrs["splits"] = sorted(attrs["splits"], key=lambda item: item["user_id"])
        return attrs


class SettlementInput(StrictSerializer):
    group_id = serializers.IntegerField(min_value=1)
    from_user_id = serializers.IntegerField(min_value=1)
    to_user_id = serializers.IntegerField(min_value=1)
    amount = MoneyField()

    def validate(self, attrs):
        if attrs["from_user_id"] == attrs["to_user_id"]:
            raise serializers.ValidationError({"to_user_id": "Choose a different person."})
        return attrs


class PaginationInput(StrictSerializer):
    limit = serializers.IntegerField(min_value=1, max_value=100, default=50)
    offset = serializers.IntegerField(min_value=0, default=0)


class ExplanationInput(PaginationInput):
    user_a_id = serializers.IntegerField(min_value=1)
    user_b_id = serializers.IntegerField(min_value=1)

    def validate(self, attrs):
        if attrs["user_a_id"] == attrs["user_b_id"]:
            raise serializers.ValidationError({"user_b_id": "Choose a different person."})
        return attrs


class PhotoInput(serializers.Serializer):
    photo = serializers.FileField()
