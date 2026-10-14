"""Thin DRF views: capability scope, strict input, transactional services, response."""

from urllib.parse import urlencode

from django.db import transaction
from django.db.models import Count, Q
from django.middleware.csrf import get_token
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from ledger import schema as out
from ledger import serializers as inp
from ledger import services
from ledger.access import (
    Access,
    enforce_request_safety,
    group_capability,
    metadata,
    resolve_key,
    resolve_request,
)
from ledger.models import Group, Person, Workspace

AUTH_PARAMETERS = [
    OpenApiParameter(
        "X-Workspace-Key",
        str,
        OpenApiParameter.HEADER,
        description="Owner capability; takes precedence over cookie session. Never put keys in public docs.",
    ),
    OpenApiParameter(
        "X-Group-Key",
        str,
        OpenApiParameter.HEADER,
        description="Group-only signed capability; takes precedence over owner header/session.",
    ),
]
IDEMPOTENCY = OpenApiParameter(
    "Idempotency-Key",
    str,
    OpenApiParameter.HEADER,
    required=True,
    description="Unique write key, retained for retries. Reusing with different payload returns409.",
)
ERRORS = {
    401: out.ErrorOutput,
    403: out.ErrorOutput,
    404: out.ErrorOutput,
    409: out.ErrorOutput,
    422: out.ErrorOutput,
    503: out.ErrorOutput,
}


def validated(serializer_class, data):
    serializer = serializer_class(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def mutation_response(request, access, operation, data, action, required=False):
    result, status, replay = services.mutate(
        access, operation, request.headers.get("Idempotency-Key"), data, action, required
    )
    return Response(
        result, status=status, headers={"Idempotency-Replayed": "true"} if replay else {}
    )


class SafeAPI(APIView):
    """No login, but unsafe cookie requests still enforce standard Django CSRF."""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        enforce_request_safety(request)


@extend_schema(parameters=AUTH_PARAMETERS)
class WorkspaceView(SafeAPI):
    @extend_schema(
        responses={200: out.WorkspaceOutput, **ERRORS},
        description="Read active scope and establish CSRF cookie; missing access returns401.",
    )
    def get(self, request):
        get_token(request)
        return Response(metadata(request, resolve_request(request)))

    @extend_schema(
        request=inp.EmptyInput,
        responses={201: out.WorkspaceOutput, **ERRORS},
        description="Create a private anonymous owner session or retain the existing active workspace.",
    )
    def post(self, request):
        validated(inp.EmptyInput, request.data)
        if (
            request.session.get("active_key")
            or "X-Workspace-Key" in request.headers
            or "X-Group-Key" in request.headers
        ):
            access = resolve_request(request)
        else:
            workspace = Workspace.objects.create()
            request.session["owner_key"] = workspace.key
            request.session["active_key"] = workspace.key
            request.session.cycle_key()
            access = Access(workspace)
        return Response(metadata(request, access), status=201)


class JoinView(SafeAPI):
    @extend_schema(
        request=inp.JoinInput,
        responses={200: out.WorkspaceOutput, **ERRORS},
        description="Exchange an owner/group capability into a session. Existing owner access is retained.",
    )
    def post(self, request):
        data = validated(inp.JoinInput, request.data)
        access = resolve_key(data["access_key"])
        if not access.group:
            request.session["owner_key"] = access.workspace.key
        else:
            joined = request.session.get("joined_keys", [])
            if data["access_key"] not in joined:
                request.session["joined_keys"] = (joined + [data["access_key"]])[-20:]
        request.session["active_key"] = data["access_key"]
        request.session.cycle_key()
        return Response(metadata(request, access))


class SwitchView(SafeAPI):
    @extend_schema(
        request=inp.SwitchInput,
        responses={200: out.WorkspaceOutput, **ERRORS},
        description="Restore retained owner scope after joining a group.",
    )
    def post(self, request):
        validated(inp.SwitchInput, request.data)
        from rest_framework.exceptions import PermissionDenied

        key = request.session.get("owner_key")
        if not key:
            raise PermissionDenied("This session has no retained owner workspace.")
        access = resolve_key(key)
        request.session["active_key"] = key
        return Response(metadata(request, access))


@extend_schema(parameters=AUTH_PARAMETERS)
class WorkspaceInviteView(SafeAPI):
    @extend_schema(
        responses={200: out.InviteOutput, **ERRORS},
        description="Owner recovery link. Anyone with this key has full owner access; never share it as a group invitation.",
    )
    def get(self, request):
        access = resolve_request(request)
        access.require_owner()
        return Response(
            {"url": "/join#" + urlencode({"key": access.workspace.key}), "scope": "workspace"}
        )


@extend_schema(parameters=AUTH_PARAMETERS)
class UsersView(SafeAPI):
    @extend_schema(
        parameters=[inp.PaginationInput],
        responses={200: out.PeopleOutput, **ERRORS},
        description="List available people. Group guests see members and people created in that group only.",
    )
    def get(self, request):
        access = resolve_request(request)
        params = validated(inp.PaginationInput, request.query_params.dict())
        people = (
            access.people()
            .annotate(
                group_count=Count("memberships", filter=Q(memberships__group=access.group))
                if access.group
                else Count("memberships")
            )
            .order_by("id")
        )
        return Response(services.paginate(people, params, services.person_data))

    @extend_schema(
        request=inp.UserInput,
        responses={201: out.PersonOutput, **ERRORS},
        description="Create a self-declared person, without login; names need not be unique.",
    )
    def post(self, request):
        access = resolve_request(request)
        data = validated(inp.UserInput, request.data)
        return mutation_response(
            request, access, "users:create", data, lambda: services.create_person(access, data)
        )


@extend_schema(parameters=AUTH_PARAMETERS)
class GroupsView(SafeAPI):
    @extend_schema(
        operation_id="groups_list",
        parameters=[inp.PaginationInput],
        responses={200: out.GroupsOutput, **ERRORS},
    )
    def get(self, request):
        access = resolve_request(request)
        params = validated(inp.PaginationInput, request.query_params.dict())
        return Response(services.paginate(access.groups(), params, services.group_data))

    @extend_schema(request=inp.NameInput, responses={201: out.GroupOutput, **ERRORS})
    def post(self, request):
        access = resolve_request(request)
        access.require_owner()
        data = validated(inp.NameInput, request.data)
        return mutation_response(
            request,
            access,
            "groups:create",
            data,
            lambda: services.group_data(Group.objects.create(workspace=access.workspace, **data)),
        )


@extend_schema(parameters=AUTH_PARAMETERS)
class GroupView(SafeAPI):
    @extend_schema(responses={200: out.GroupOutput, **ERRORS})
    def get(self, request, group_id):
        return Response(services.group_data(resolve_request(request).get_group(group_id)))


@extend_schema(parameters=AUTH_PARAMETERS)
class MembersView(SafeAPI):
    @extend_schema(parameters=[inp.PaginationInput], responses={200: out.PeopleOutput, **ERRORS})
    def get(self, request, group_id):
        access = resolve_request(request)
        group = access.get_group(group_id)
        params = validated(inp.PaginationInput, request.query_params.dict())
        people = (
            Person.objects.filter(memberships__group=group)
            .annotate(
                group_count=Count("memberships", filter=Q(memberships__group=group))
                if access.group
                else Count("memberships")
            )
            .order_by("id")
        )
        return Response(services.paginate(people, params, services.person_data))

    @extend_schema(request=inp.MemberInput, responses={201: out.PersonOutput, **ERRORS})
    def post(self, request, group_id):
        access = resolve_request(request)
        group = access.get_group(group_id)
        data = validated(inp.MemberInput, request.data)
        return mutation_response(
            request,
            access,
            f"group:{group_id}:members",
            data,
            lambda: services.add_member(access, group, data["user_id"]),
        )


@extend_schema(parameters=AUTH_PARAMETERS)
class ExpensesView(SafeAPI):
    @extend_schema(
        parameters=[IDEMPOTENCY],
        request=inp.ExpenseInput,
        responses={201: out.ExpenseOutput, **ERRORS},
        description="Record a paid expense atomically. Equal split snapshots every current member; custom shares must name every member exactly once and sum exactly. Deterministic remainder paise go to ascending person IDs.",
    )
    def post(self, request):
        access = resolve_request(request)
        data = validated(inp.ExpenseInput, request.data)
        access.get_group(data["group_id"])
        return mutation_response(
            request,
            access,
            "expenses:create",
            data,
            lambda: services.create_expense(access, data),
            required=True,
        )


@extend_schema(parameters=AUTH_PARAMETERS)
class ExpenseHistoryView(SafeAPI):
    @extend_schema(parameters=[inp.PaginationInput], responses={200: out.ExpensesOutput, **ERRORS})
    def get(self, request, group_id):
        group = resolve_request(request).get_group(group_id)
        params = validated(inp.PaginationInput, request.query_params.dict())
        expenses = group.expenses.select_related("paid_by").prefetch_related("shares__person")
        return Response(services.paginate(expenses, params, services.expense_data))


@extend_schema(parameters=AUTH_PARAMETERS)
class BalancesView(SafeAPI):
    @extend_schema(
        responses={200: out.BalanceOutput, **ERRORS},
        description="Full-history balances within active scope. Opposing direct debts cancel; no self debt and no arbitrary rerouting.",
    )
    def get(self, request, group_id=None):
        access = resolve_request(request)
        group = access.get_group(group_id) if group_id is not None else access.group
        with transaction.atomic():
            return Response(services.balances(access, group))


@extend_schema(parameters=AUTH_PARAMETERS)
class ExplanationView(SafeAPI):
    @extend_schema(
        parameters=[inp.ExplanationInput],
        responses={200: out.ExplanationOutput, **ERRORS},
        description="Mandatory enhancement: explain a direct pair balance, including zeroed balances. Positive signed contribution means B owes A. Total considers full history independently of pagination.",
    )
    def get(self, request, group_id):
        access = resolve_request(request)
        group = access.get_group(group_id)
        params = validated(inp.ExplanationInput, request.query_params.dict())
        with transaction.atomic():
            return Response(services.explain_pair(access, group, params))


@extend_schema(parameters=AUTH_PARAMETERS)
class SettlementsView(SafeAPI):
    @extend_schema(
        parameters=[IDEMPOTENCY],
        request=inp.SettlementInput,
        responses={201: out.SettlementOutput, **ERRORS},
        description="Record a payment made elsewhere. Cannot exceed the current direct group debt; debt check and insert are serialized in one transaction.",
    )
    def post(self, request):
        access = resolve_request(request)
        data = validated(inp.SettlementInput, request.data)
        access.get_group(data["group_id"])
        return mutation_response(
            request,
            access,
            "settlements:create",
            data,
            lambda: services.create_settlement(access, data),
            required=True,
        )


@extend_schema(parameters=AUTH_PARAMETERS)
class SettlementHistoryView(SafeAPI):
    @extend_schema(
        parameters=[inp.PaginationInput], responses={200: out.SettlementsOutput, **ERRORS}
    )
    def get(self, request, group_id):
        group = resolve_request(request).get_group(group_id)
        params = validated(inp.PaginationInput, request.query_params.dict())
        return Response(
            services.paginate(group.settlements.all(), params, services.settlement_data)
        )


@extend_schema(parameters=AUTH_PARAMETERS)
class GroupInviteView(SafeAPI):
    @extend_schema(
        responses={200: out.InviteOutput, **ERRORS},
        description="Group-only invitation. It never grants access to other workspace groups or unrelated people.",
    )
    def get(self, request, group_id):
        group = resolve_request(request).get_group(group_id)
        return Response(
            {
                "url": "/join#" + urlencode({"key": group_capability(group), "group": group.id}),
                "scope": "group",
                "group_id": group.id,
            }
        )
