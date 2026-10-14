"""Public API artifacts generated from the runtime OpenAPI, never live account data."""

import json

from django.http import JsonResponse
from drf_spectacular.generators import SchemaGenerator


def openapi_document():
    return SchemaGenerator().get_schema(request=None, public=True)


def schema_download(request):
    """The exact same annotated operations power Swagger and the downloadable schema."""
    return JsonResponse(openapi_document())


EXAMPLES = {
    "WorkspaceView": {},
    "JoinView": {"access_key": "{{group_key}}"},
    "SwitchView": {"scope": "owner"},
    "UsersView": {"name": "Mohit", "avatar_key": "portrait-01"},
    "GroupsView": {"name": "Dinner"},
    "MembersView": {"user_id": "{{user_a_id}}"},
    "ExpensesView": {
        "group_id": "{{group_id}}",
        "paid_by": "{{user_a_id}}",
        "amount": "1200.00",
        "description": "Dinner bill",
    },
    "SettlementsView": {
        "group_id": "{{group_id}}",
        "from_user_id": "{{user_b_id}}",
        "to_user_id": "{{user_a_id}}",
        "amount": "100.00",
    },
}


def request_body(path):
    """Endpoint examples; numeric ID variables stay unquoted after manual setup."""
    bodies = {
        "/api/v1/workspace": {},
        "/api/v1/workspace/join": EXAMPLES["JoinView"],
        "/api/v1/workspace/switch": EXAMPLES["SwitchView"],
        "/api/v1/users": EXAMPLES["UsersView"],
        "/api/v1/groups": EXAMPLES["GroupsView"],
        "/api/v1/groups/{group_id}/members": EXAMPLES["MembersView"],
        "/api/v1/expenses": EXAMPLES["ExpensesView"],
        "/api/v1/settlements": EXAMPLES["SettlementsView"],
    }
    text = json.dumps(bodies.get(path, {}), indent=2)
    for variable in ["group_id", "user_a_id", "user_b_id"]:
        text = text.replace('"{{' + variable + '}}"', "{{" + variable + "}}")
    return text


def postman_checks(path, method):
    """Portable Postman checks for real ledger invariants, beyond HTTP success."""
    lines = [
        "pm.test('Successful API response', () => pm.expect(pm.response.code).to.be.within(200, 299));"
    ]
    if path.endswith("/receipt") and method == "get":
        return lines + [
            "pm.test('Verified image response', () => pm.expect(pm.response.headers.get('Content-Type')).to.match(/^image\\/(jpeg|png|webp)$/));"
        ]
    if path == "/api/v1/expenses" and method == "post":
        lines += [
            "const expense = pm.response.json();",
            "pm.test('Exact shares conserve expense total', () => pm.expect(expense.shares.reduce((sum, share) => sum + share.amount_minor, 0)).to.equal(expense.amount_minor));",
            "pm.test('Receipt includes every saved participant', () => pm.expect(expense.shares.length).to.equal(expense.participant_count));",
        ]
    if path.endswith("/balances") or path == "/api/v1/balances":
        lines += [
            "const balances = pm.response.json();",
            "pm.test('Member net balances sum to zero', () => pm.expect(balances.members.reduce((sum, member) => sum + member.net_minor, 0)).to.equal(0));",
            "pm.test('No self or non-positive debt', () => balances.debts.forEach(debt => { pm.expect(debt.from_user_id).not.to.equal(debt.to_user_id); pm.expect(debt.amount_minor).to.be.above(0); }));",
        ]
    if path.endswith("/explanation"):
        lines += [
            "const explanation = pm.response.json();",
            "pm.test('Explained amount matches signed total', () => pm.expect(explanation.amount_minor).to.equal(Math.abs(explanation.signed_total_minor)));",
            "if (explanation.items.length === explanation.total) pm.test('Full explanation conserves signed total', () => pm.expect(explanation.items.reduce((sum, item) => sum + item.contribution_minor, 0)).to.equal(explanation.signed_total_minor));",
        ]
    return lines


def postman_collection():
    """Build one item per live OpenAPI operation; safe environment has no real keys."""
    schema = openapi_document()
    items = []
    for path, operations in schema["paths"].items():
        path = path.rstrip("/")
        if not path.startswith("/api/v1/"):
            continue
        for method, operation in operations.items():
            if method not in {"get", "post"}:
                continue
            target = "{{base_url}}" + path.replace("{group_id}", "{{group_id}}").replace(
                "{expense_id}", "{{expense_id}}"
            )
            if path.endswith("/explanation"):
                target += "?user_a_id={{user_a_id}}&user_b_id={{user_b_id}}"
            headers = [
                {
                    "key": "X-Workspace-Key",
                    "value": "{{workspace_key}}",
                    "disabled": path
                    in ["/api/v1/workspace", "/api/v1/workspace/join", "/api/v1/workspace/switch"],
                },
                {"key": "X-Group-Key", "value": "{{group_key}}", "disabled": True},
            ]
            request = {
                "method": method.upper(),
                "header": headers,
                "url": target,
                "description": operation.get("description", "")
                + "\nCookie writes require CSRF. Workspace/bootstrap in a browser first, then set workspace_key from GET workspace/invite. Disable owner header and enable group header for guest scope.",
            }
            if method == "post":
                headers.append({"key": "Idempotency-Key", "value": "{{$guid}}"})
                if path.endswith("/receipt"):
                    request["body"] = {
                        "mode": "formdata",
                        "formdata": [{"key": "photo", "type": "file", "src": []}],
                    }
                else:
                    headers.append({"key": "Content-Type", "value": "application/json"})
                    request["body"] = {
                        "mode": "raw",
                        "raw": request_body(path),
                        "options": {"raw": {"language": "json"}},
                    }
            items.append(
                {
                    "name": operation.get("operationId", method + " " + path),
                    "request": request,
                    "event": [
                        {
                            "listen": "test",
                            "script": {
                                "type": "text/javascript",
                                "exec": postman_checks(path, method),
                            },
                        }
                    ],
                }
            )
    return {
        "info": {
            "name": "Splitly Expense Sharing API",
            "description": "Endpoint catalog generated from the runtime OpenAPI, with example requests and ledger invariant checks. This is not a sequential seeded demo: set private capability and actual IDs, then send the relevant requests. Read docs/public/api.md for setup and complete dinner walkthrough. Keep the same Idempotency-Key for retries; {{$guid}} is intended for a new write only.",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "variable": [
            {"key": "base_url", "value": "http://localhost:8000"},
            {"key": "workspace_key", "value": ""},
            {"key": "group_key", "value": ""},
            {"key": "group_id", "value": "1"},
            {"key": "expense_id", "value": "1"},
            {"key": "user_a_id", "value": "1"},
            {"key": "user_b_id", "value": "2"},
        ],
        "item": items,
    }


def postman_download(request):
    response = JsonResponse(postman_collection())
    response["Content-Disposition"] = 'attachment; filename="splitly.postman_collection.json"'
    return response


def environment_download(request):
    data = {
        "name": "Splitly local",
        "values": [
            {
                "key": variable["key"],
                "value": variable["value"],
                "type": "secret" if "key" in variable["key"] else "default",
                "enabled": True,
            }
            for variable in postman_collection()["variable"]
        ],
        "_postman_variable_scope": "environment",
    }
    response = JsonResponse(data)
    response["Content-Disposition"] = 'attachment; filename="splitly.postman_environment.json"'
    return response
