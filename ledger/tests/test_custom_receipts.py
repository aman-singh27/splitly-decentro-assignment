"""Optional unequal allocation and bill-photo journeys, with scope and rollback checks."""

from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from ledger.models import Expense
from ledger.tests.helpers import BASE, expense, group_key, owner, post

pytestmark = pytest.mark.django_db


def photo(name="receipt.png", format="PNG"):
    buffer = BytesIO()
    Image.new("RGB", (20, 20), "white").save(buffer, format=format)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def upload(client, expense_id, file, key="receipt-upload"):
    return client.post(
        BASE + f"/expenses/{expense_id}/receipt",
        {"photo": file},
        format="multipart",
        HTTP_IDEMPOTENCY_KEY=key,
    )


def test_custom_snapshot_all_members_and_decimal_compatibility(dinner):
    client, people, group = dinner
    data = {
        "group_id": group["id"],
        "paid_by": people[0]["id"],
        "amount": 1000,
        "description": "Custom dinner",
        "splits": [
            {"user_id": people[0]["id"], "amount": 300},
            {"user_id": people[1]["id"], "amount": 400},
            {"user_id": people[2]["id"], "amount": 300},
        ],
    }
    response = post(client, "/expenses", data, "custom")
    assert response.status_code == 201, response.content
    assert response.json()["split_type"] == "custom"
    assert [s["amount_minor"] for s in response.json()["shares"]] == [30000, 40000, 30000]
    replay = post(
        client,
        "/expenses",
        {
            **data,
            "split_type": "custom",
            "amount": "1000.00",
            "splits": list(reversed(data["splits"])),
        },
        "custom",
    )
    assert replay.json() == response.json()
    assert (
        client.get(BASE + f"/groups/{group['id']}/balances").json()["debts"][0]["amount_minor"]
        == 40000
    )


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "duplicate",
        "unknown",
        "wrong_sum",
        "negative",
        "excess_precision",
        "bool",
        "equal_with_custom",
        "custom_without_custom",
    ],
)
def test_invalid_custom_shares_do_not_write(dinner, kind):
    client, people, group = dinner
    shares = [{"user_id": p["id"], "amount": "1.00"} for p in people]
    data = {
        "group_id": group["id"],
        "paid_by": people[0]["id"],
        "amount": "3.00",
        "description": "Bad split",
        "split_type": "custom",
        "splits": shares,
    }
    if kind == "missing":
        shares.pop()
    elif kind == "duplicate":
        shares[2]["user_id"] = people[0]["id"]
    elif kind == "unknown":
        shares[2]["user_id"] = 999999
    elif kind == "wrong_sum":
        shares[2]["amount"] = "2"
    elif kind == "negative":
        shares[2]["amount"] = "-1"
    elif kind == "excess_precision":
        shares[2]["amount"] = "1.001"
    elif kind == "bool":
        shares[2]["amount"] = False
    elif kind == "equal_with_custom":
        data["split_type"] = "equal"
    else:
        del data["splits"]
    assert post(client, "/expenses", data).status_code == 422
    assert Expense.objects.count() == 0


def test_zero_custom_share_is_allowed_and_photo_not_required(dinner):
    client, people, group = dinner
    data = {
        "group_id": group["id"],
        "paid_by": people[0]["id"],
        "amount": "0.01",
        "description": "Tiny",
        "splits": [
            {"user_id": p["id"], "amount": "0.01" if index == 1 else "0.00"}
            for index, p in enumerate(people)
        ],
    }
    response = post(client, "/expenses", data)
    assert response.status_code == 201
    assert response.json()["has_receipt"] is False
    assert response.json()["receipt_url"] is None
    assert response.json()["participant_count"] == 3


@pytest.mark.parametrize("format", ["JPEG", "PNG", "WEBP"])
def test_optional_photo_is_verified_private_and_idempotent(dinner, settings, tmp_path, format):
    settings.MEDIA_ROOT = tmp_path
    client, people, group = dinner
    record = expense(client, people, group).json()
    response = upload(client, record["id"], photo("../../sensitive" + format, format))
    assert response.status_code == 201, response.content
    assert response.json()["has_receipt"] is True
    path = response.json()["receipt_url"]
    saved = Expense.objects.get(id=record["id"]).receipt.name
    assert "sensitive" not in saved and ".." not in saved
    replay = upload(client, record["id"], photo("different-name", format))
    assert replay.json() == response.json()
    assert replay["Idempotency-Replayed"] == "true"
    assert len(list(tmp_path.rglob("*.*"))) == 1
    assert client.get(path).status_code == 200
    assert APIClient().get(path).status_code == 401
    assert owner().get(path).status_code == 404
    guest = APIClient()
    guest.credentials(HTTP_X_GROUP_KEY=group_key(client, group))
    assert guest.get(path).status_code == 200
    assert client.get("/media/" + saved).status_code != 200


@pytest.mark.parametrize("bad", ["fake", "svg", "oversize", "gif", "missing_key"])
def test_bad_photo_does_not_damage_existing_expense(dinner, settings, tmp_path, bad):
    settings.MEDIA_ROOT = tmp_path
    client, people, group = dinner
    record = expense(client, people, group).json()
    files = {
        "fake": SimpleUploadedFile("receipt.png", b"not an image", content_type="image/png"),
        "svg": SimpleUploadedFile(
            "receipt.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"></svg>',
            content_type="image/svg+xml",
        ),
        "oversize": SimpleUploadedFile(
            "big.jpg", b"0" * (5 * 1024 * 1024 + 1), content_type="image/jpeg"
        ),
        "gif": photo("receipt.gif", "GIF"),
        "missing_key": photo(),
    }
    response = (
        client.post(
            BASE + f"/expenses/{record['id']}/receipt", {"photo": files[bad]}, format="multipart"
        )
        if bad == "missing_key"
        else upload(client, record["id"], files[bad])
    )
    assert response.status_code == 422, response.content
    assert Expense.objects.count() == 1
    assert not Expense.objects.get(id=record["id"]).receipt
    assert not list(tmp_path.rglob("*.*"))


def test_attachment_failure_rolls_back_file_and_idempotency(dinner, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client, people, group = dinner
    record = expense(client, people, group).json()
    with patch("ledger.models.Expense.save", side_effect=RuntimeError("failure after file write")):
        with pytest.raises(RuntimeError):
            upload(client, record["id"], photo())
    assert not Expense.objects.get(id=record["id"]).receipt
    assert not list(tmp_path.rglob("*.*"))


def test_expense_and_shares_are_atomic_on_insert_failure(dinner):
    client, people, group = dinner
    with patch(
        "ledger.models.ExpenseShare.objects.bulk_create",
        side_effect=RuntimeError("share insert failure"),
    ):
        with pytest.raises(RuntimeError):
            expense(client, people, group)
    assert Expense.objects.count() == 0


def test_guest_count_does_not_reveal_other_group_memberships(dinner):
    client, people, group = dinner
    other = post(client, "/groups", {"name": "Hidden"}).json()
    post(client, f"/groups/{other['id']}/members", {"user_id": people[0]["id"]})
    guest = APIClient()
    guest.credentials(HTTP_X_GROUP_KEY=group_key(client, group))
    assert guest.get(BASE + "/users").json()["items"][0]["group_count"] == 1
    assert guest.get(BASE + f"/groups/{group['id']}/members").json()["items"][0]["group_count"] == 1
    assert guest.get(BASE + "/balances").json()["scope"] == {
        "type": "group",
        "group_id": group["id"],
    }
    assert (
        guest.get(BASE + f"/groups/{group['id']}").json()["member_preview"][0]["group_count"] == 1
    )


def test_photo_orientation_and_metadata_are_sanitized(dinner, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client, people, group = dinner
    record = expense(client, people, group).json()
    buffer = BytesIO()
    image = Image.new("RGB", (30, 20), "white")
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "Private metadata"
    image.save(buffer, format="JPEG", exif=exif)
    response = upload(
        client,
        record["id"],
        SimpleUploadedFile("camera.jpg", buffer.getvalue(), content_type="image/jpeg"),
    )
    assert response.status_code == 201
    saved = Expense.objects.get(id=record["id"])
    with Image.open(saved.receipt.path) as sanitized:
        assert sanitized.size == (20, 30)
        assert not sanitized.getexif()


@pytest.mark.django_db(transaction=True)
def test_old_photo_cleanup_failure_does_not_delete_committed_replacement(
    dinner, settings, tmp_path
):
    settings.MEDIA_ROOT = tmp_path
    client, people, group = dinner
    record = expense(client, people, group).json()
    assert upload(client, record["id"], photo(), key="first-photo").status_code == 201
    original_name = Expense.objects.get(id=record["id"]).receipt.name
    with patch(
        "django.core.files.storage.FileSystemStorage.delete",
        side_effect=PermissionError("Old photo still open"),
    ):
        response = upload(client, record["id"], photo(), key="replacement-photo")
    assert response.status_code == 201
    replacement = Expense.objects.get(id=record["id"]).receipt
    assert replacement.name != original_name
    assert replacement.storage.exists(replacement.name)
    replay = upload(client, record["id"], photo(), key="replacement-photo")
    assert replay.json() == response.json()
    assert replay["Idempotency-Replayed"] == "true"
