"""Each journey starts from independent anonymous owner scope and real API writes."""

import pytest

from ledger.tests.helpers import owner, post


@pytest.fixture
def dinner():
    client = owner()
    people = [post(client, "/users", {"name": name}).json() for name in ["Mohit", "Rahul", "Ankit"]]
    group = post(client, "/groups", {"name": "Dinner"}).json()
    for person in people:
        response = post(client, f"/groups/{group['id']}/members", {"user_id": person["id"]})
        assert response.status_code == 201, response.content
    return client, people, group
