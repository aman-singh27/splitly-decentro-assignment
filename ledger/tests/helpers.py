"""Shared black-box request builders; no direct database fixture shortcuts."""

from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from rest_framework.test import APIClient

BASE = "/api/v1"


def post(client, route, data, key=None):
    return client.post(BASE + route, data, format="json", HTTP_IDEMPOTENCY_KEY=key or str(uuid4()))


def owner():
    client = APIClient()
    response = post(client, "/workspace", {})
    assert response.status_code == 201, response.content
    return client


def expense(client, people, group, amount="1200.00", key=None, payer=0):
    return post(
        client,
        "/expenses",
        {
            "group_id": group["id"],
            "paid_by": people[payer]["id"],
            "amount": amount,
            "description": "Dinner bill",
        },
        key,
    )


def group_key(client, group):
    response = client.get(BASE + f"/groups/{group['id']}/invite")
    assert response.status_code == 200
    return parse_qs(urlparse(response.json()["url"]).fragment)["key"][0]
