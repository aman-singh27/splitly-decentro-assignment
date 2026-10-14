"""Operational contracts: real concurrent writes, readiness, SPA boundaries, demo."""

import importlib
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from threading import Barrier
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.db import (
    IntegrityError,
    OperationalError,
    close_old_connections,
    connections,
    transaction,
)
from rest_framework.test import APIClient

from ledger.models import Expense, ExpenseShare, Membership, Settlement, Workspace
from ledger.tests.helpers import BASE, expense, group_key, owner, post

pytestmark = pytest.mark.django_db


@pytest.mark.django_db(transaction=True)
def test_two_simultaneous_full_payments_cannot_oversettle():
    client = owner()
    people = [post(client, "/users", {"name": name}).json() for name in ["Payer", "Debtor"]]
    group = post(client, "/groups", {"name": "Concurrent"}).json()
    for person in people:
        post(client, f"/groups/{group['id']}/members", {"user_id": person["id"]})
    expense(client, people, group, "1.00")
    key = group_key(client, group)
    barrier = Barrier(2)

    def pay(index):
        close_old_connections()
        thread_client = APIClient()
        thread_client.credentials(HTTP_X_GROUP_KEY=key)
        barrier.wait(timeout=5)
        try:
            return post(
                thread_client,
                "/settlements",
                {
                    "group_id": group["id"],
                    "from_user_id": people[1]["id"],
                    "to_user_id": people[0]["id"],
                    "amount": "0.50",
                },
                f"concurrent-{index}",
            ).status_code
        finally:
            # Django intentionally keeps shared in-memory SQLite connections
            # alive on close(); test worker threads may release their own raw
            # connection without losing the main thread's migrated database.
            database = connections["default"]
            if database.connection is not None:
                database.connection.close()
                database.connection = None
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(pay, [1, 2]))
    assert results.count(201) == 1
    assert all(status in {201, 409, 503} for status in results)
    assert Settlement.objects.count() == 1
    assert client.get(BASE + f"/groups/{group['id']}/balances").json()["debts"] == []


def test_database_constraints_protect_duplicate_memberships_and_self_payment(dinner):
    client, people, group = dinner
    with pytest.raises(IntegrityError), transaction.atomic():
        Membership.objects.create(group_id=group["id"], person_id=people[0]["id"])
    with pytest.raises(IntegrityError), transaction.atomic():
        Settlement.objects.create(
            group_id=group["id"],
            from_user_id=people[0]["id"],
            to_user_id=people[0]["id"],
            amount_minor=1,
        )


def test_busy_error_is_retryable_and_readiness_detects_unmigrated_database(dinner):
    client, people, group = dinner
    with patch(
        "ledger.services.Expense.objects.create", side_effect=OperationalError("database is locked")
    ):
        response = expense(client, people, group)
    assert response.status_code == 503
    assert response["Retry-After"] == "1"
    with patch("config.http.connection.cursor", side_effect=OperationalError("no such table")):
        assert client.get("/health/ready").status_code == 503


def test_spa_safe_assets_and_methods(client, settings, tmp_path):
    settings.BASE_DIR = tmp_path
    assert client.get("/").status_code == 503
    root = tmp_path / "frontend" / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<html>app</html>")
    (root / "assets" / "app.js").write_text("console.log('safe')")
    (root / "brand.svg").write_text("<svg></svg>")
    assert client.get("/groups/42").status_code == 200
    assert client.get("/groups/42")["Referrer-Policy"] == "no-referrer"
    assert client.get("/assets/app.js")["Cache-Control"].endswith("immutable")
    assert client.get("/assets/missing.js").status_code == 404
    assert client.get("/assets/../../../../.local-secret").status_code == 404
    assert client.get("/brand.svg").status_code == 200
    assert client.post("/groups/42", {}).status_code == 405
    assert client.get("/api/v1/unknown").status_code == 404


def test_production_application_entrypoints():
    assert importlib.import_module("config.wsgi").application
    assert importlib.import_module("config.asgi").application


def test_standalone_api_explorer_renders_bundled_assets(client):
    response = client.get("/api/docs/")
    assert response.status_code == 200
    page = response.content.decode()
    assert "/api/openapi.json" in page
    assert "/static/drf_spectacular_sidecar/swagger-ui-dist/swagger-ui-bundle.js" in page


def test_seed_demo_is_explicit_and_uses_real_ledger():
    before = Workspace.objects.count()
    output = StringIO()
    call_command("seed_demo", stdout=output)
    assert Workspace.objects.count() == before + 1
    assert Expense.objects.count() == 2
    assert ExpenseShare.objects.count() == 6
    assert "Owner return link" in output.getvalue()
    assert "Dinner" in output.getvalue()
