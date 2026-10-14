"""Black-box assignment journeys and failure cases through the actual DRF API."""

import pytest
from rest_framework.test import APIClient

from ledger.tests.helpers import BASE, expense, group_key, owner, post

pytestmark = pytest.mark.django_db


def test_workspace_bootstrap_is_idempotent_and_protected():
    client = APIClient()
    assert client.get(BASE + "/workspace").status_code == 401
    assert client.get(BASE + "/groups").status_code == 401
    first = post(client, "/workspace", {})
    assert first.status_code == 201
    assert post(client, "/workspace", {}).json() == first.json()
    assert client.get(BASE + "/workspace").json()["scope"] == "workspace"


def test_required_dinner_and_balance_explanation(dinner):
    client, people, group = dinner
    response = expense(client, people, group)
    assert response.status_code == 201, response.content
    receipt = response.json()
    assert receipt["amount_minor"] == 120000
    assert [share["amount_minor"] for share in receipt["shares"]] == [40000] * 3
    balances = client.get(BASE + f"/groups/{group['id']}/balances").json()
    assert balances["debts"] == [
        {
            "from_user_id": people[1]["id"],
            "to_user_id": people[0]["id"],
            "amount_minor": 40000,
            "amount": "400.00",
        },
        {
            "from_user_id": people[2]["id"],
            "to_user_id": people[0]["id"],
            "amount_minor": 40000,
            "amount": "400.00",
        },
    ]
    assert sum(member["net_minor"] for member in balances["members"]) == 0
    explanation = client.get(
        BASE + f"/groups/{group['id']}/balances/explanation",
        {"user_a_id": people[0]["id"], "user_b_id": people[1]["id"]},
    ).json()
    assert explanation["signed_total_minor"] == 40000
    assert explanation["items"][0]["record_id"] == receipt["id"]
    assert explanation["items"][0]["contribution_minor"] == 40000
    assert client.get(BASE + f"/groups/{group['id']}/expenses").json()["total"] == 1


def test_remainder_and_late_members_do_not_rewrite_history(dinner):
    client, people, group = dinner
    before = expense(client, people, group, 100).json()
    assert [share["amount_minor"] for share in before["shares"]] == [3334, 3333, 3333]
    new = post(client, "/users", {"name": "Late friend"}).json()
    assert post(client, f"/groups/{group['id']}/members", {"user_id": new["id"]}).status_code == 201
    history = client.get(BASE + f"/groups/{group['id']}/expenses").json()["items"]
    assert history[0] == before
    assert expense(client, people, group, "0.01").json()["participant_count"] == 4


def test_idempotency_money_normalization_and_conflict(dinner):
    client, people, group = dinner
    first = expense(client, people, group, 1200, "same-key")
    second = expense(client, people, group, "1200.00", "same-key")
    assert second.status_code == first.status_code == 201
    assert second.json() == first.json()
    assert second["Idempotency-Replayed"] == "true"
    assert expense(client, people, group, "1201", "same-key").status_code == 409
    assert client.get(BASE + f"/groups/{group['id']}/expenses").json()["total"] == 1


@pytest.mark.parametrize(
    "amount", [True, False, "NaN", "Infinity", "0", "-3", "1.001", "10000000.01"]
)
def test_invalid_amounts_never_write(dinner, amount):
    client, people, group = dinner
    assert expense(client, people, group, amount).status_code == 422
    assert client.get(BASE + f"/groups/{group['id']}/expenses").json()["total"] == 0


def test_precise_json_decimals_and_missing_idempotency(dinner):
    client, people, group = dinner
    raw = f'{{"group_id":{group["id"]},"paid_by":{people[0]["id"]},"amount":0.29,"description":"Precision"}}'
    assert client.post(BASE + "/expenses", raw, content_type="application/json").status_code == 422
    response = client.post(
        BASE + "/expenses", raw, content_type="application/json", HTTP_IDEMPOTENCY_KEY="numeric"
    )
    assert response.json()["amount_minor"] == 29


def test_duplicates_empty_group_and_strict_input(dinner):
    client, people, group = dinner
    assert post(client, "/users", {"name": "Mohit"}).status_code == 201
    assert (
        post(client, f"/groups/{group['id']}/members", {"user_id": people[0]["id"]}).status_code
        == 409
    )
    assert post(client, "/groups", {"name": "  "}).status_code == 422
    assert post(client, "/users", {"name": "Okay", "unexpected": 1}).status_code == 422
    assert post(client, "/users", {"name": "x" * 81}).status_code == 422
    empty = post(client, "/groups", {"name": "Empty"}).json()
    assert expense(client, people, empty).status_code == 422
    other = post(client, "/users", {"name": "Outsider"}).json()
    assert expense(client, [other], group).status_code == 422


def test_pairwise_cancellation_and_partial_full_settlement(dinner):
    client, people, group = dinner
    expense(client, people, group)
    expense(client, people, group, "300", payer=1)
    balances = client.get(BASE + f"/groups/{group['id']}/balances").json()
    assert balances["debts"][0]["amount_minor"] == 30000
    payload = {
        "group_id": group["id"],
        "from_user_id": people[1]["id"],
        "to_user_id": people[0]["id"],
        "amount": "100",
    }
    first = post(client, "/settlements", payload, "payment")
    assert first.status_code == 201, first.content
    assert first.json()["remaining_minor"] == 20000
    assert post(client, "/settlements", payload, "payment").json() == first.json()
    assert post(client, "/settlements", {**payload, "amount": "200.01"}).status_code == 409
    assert post(client, "/settlements", {**payload, "amount": "200"}).status_code == 201
    assert post(client, "/settlements", payload).status_code == 409
    assert (
        post(client, "/settlements", {**payload, "from_user_id": people[0]["id"]}).status_code
        == 422
    )
    explanation = client.get(
        BASE + f"/groups/{group['id']}/balances/explanation",
        {"user_a_id": people[0]["id"], "user_b_id": people[1]["id"], "limit": 1},
    ).json()
    assert explanation["signed_total_minor"] == 0
    assert explanation["from_user_id"] is None
    assert explanation["total"] == 4
    assert len(explanation["items"]) == 1


def test_guest_scope_isolation_and_retained_owner(dinner):
    client, people, group = dinner
    other = post(client, "/groups", {"name": "Secret"}).json()
    hidden = post(client, "/users", {"name": "Hidden"}).json()
    guest = APIClient()
    assert (
        post(guest, "/workspace/join", {"access_key": group_key(client, group)}).status_code == 200
    )
    assert guest.get(BASE + "/workspace").json()["scope"] == "group"
    assert guest.get(BASE + "/groups").json()["total"] == 1
    assert guest.get(BASE + f"/groups/{other['id']}").status_code == 404
    assert post(guest, "/groups", {"name": "Forbidden"}).status_code == 403
    assert guest.get(BASE + "/workspace/invite").status_code == 403
    assert (
        post(guest, f"/groups/{group['id']}/members", {"user_id": hidden["id"]}).status_code == 404
    )
    assert guest.get(BASE + "/users").json()["total"] == 3
    created = post(guest, "/users", {"name": "Guest-created"}).json()
    assert guest.get(BASE + "/users").json()["total"] == 4
    assert (
        post(guest, f"/groups/{group['id']}/members", {"user_id": created["id"]}).status_code == 201
    )
    assert post(guest, "/workspace/switch", {"scope": "owner"}).status_code == 403
    assert (
        post(client, "/workspace/join", {"access_key": group_key(client, group)}).status_code == 200
    )
    assert client.get(BASE + "/workspace").json()["can_switch_to_owner"] is True
    assert post(client, "/workspace/switch", {"scope": "owner"}).status_code == 200
    assert client.get(BASE + "/groups").json()["total"] == 2


def test_header_precedence_invalid_caps_and_replay_leak(dinner):
    client, people, group = dinner
    first = expense(client, people, group, key="private-retry")
    guest = APIClient()
    guest.credentials(HTTP_X_GROUP_KEY=group_key(client, group))
    response = expense(guest, people, group, key="private-retry")
    assert response.status_code == 201
    assert response.json()["id"] != first.json()["id"]
    assert guest.get(BASE + "/groups").json()["total"] == 1
    client.credentials(HTTP_X_GROUP_KEY="grp_bad")
    assert client.get(BASE + "/groups").status_code == 401
    assert post(APIClient(), "/workspace/join", {"access_key": "wrong"}).status_code == 401


def test_workspace_balances_keep_group_debts_separate(dinner):
    client, people, group = dinner
    expense(client, people, group)
    other = post(client, "/groups", {"name": "Second"}).json()
    for person in people:
        post(client, f"/groups/{other['id']}/members", {"user_id": person["id"]})
    expense(client, people, other, payer=1)
    balances = client.get(BASE + "/balances").json()
    assert balances["scope"]["type"] == "workspace"
    assert sum(p["net_minor"] for p in balances["members"]) == 0


def test_pagination_validation_unknown_routes_and_explanation_inputs(dinner):
    client, people, group = dinner
    data = client.get(BASE + "/users", {"limit": 2, "offset": 1}).json()
    assert data["total"] == 3 and len(data["items"]) == 2
    for query in [{"limit": 0}, {"limit": "bad"}, {"offset": -1}, {"limit": 101}]:
        assert client.get(BASE + "/users", query).status_code == 422
    url = BASE + f"/groups/{group['id']}/balances/explanation"
    assert client.get(url).status_code == 422
    assert (
        client.get(url, {"user_a_id": people[0]["id"], "user_b_id": people[0]["id"]}).status_code
        == 422
    )
    assert client.get(BASE + "/does-not-exist").status_code == 404


def test_cross_workspace_membership_and_expense_ids_hidden(dinner):
    client, people, group = dinner
    stranger = owner()
    assert stranger.get(BASE + f"/groups/{group['id']}").status_code == 404
    own = post(stranger, "/groups", {"name": "Own"}).json()
    assert (
        post(stranger, f"/groups/{own['id']}/members", {"user_id": people[0]["id"]}).status_code
        == 404
    )
    assert expense(stranger, people, group).status_code == 404


def test_csrf_cookie_origin_and_explicit_capability(dinner):
    strict = APIClient(enforce_csrf_checks=True)
    response = strict.get(BASE + "/workspace")
    token = strict.cookies["csrftoken"].value
    assert response.status_code == 401
    assert strict.post(BASE + "/workspace", {}, format="json").status_code == 403
    assert (
        strict.post(BASE + "/workspace", {}, format="json", HTTP_X_CSRFTOKEN=token).status_code
        == 201
    )
    assert (
        strict.post(
            BASE + "/groups",
            {"name": "Bad"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN="https://evil.example",
        ).status_code
        == 403
    )
    client, people, group = dinner
    capability = APIClient(enforce_csrf_checks=True)
    capability.credentials(HTTP_X_GROUP_KEY=group_key(client, group))
    assert expense(capability, people, group).status_code == 201
    capability.credentials(
        HTTP_X_GROUP_KEY=group_key(client, group), HTTP_ORIGIN="https://evil.example"
    )
    assert expense(capability, people, group).status_code == 403


def test_public_schema_and_downloads_and_health_are_access_free():
    client = APIClient()
    schema = client.get("/api/openapi.json")
    assert schema.status_code == 200
    data = schema.json()
    assert "/api/v1/expenses" in data["paths"]
    assert "requestBody" in data["paths"]["/api/v1/expenses"]["post"]
    assert client.get("/api/postman.json").json()["info"]["schema"].endswith("collection.json")
    assert client.get("/api/environment.json").json()["name"] == "Splitly local"
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200
