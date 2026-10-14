"""Explicit, optional assignment sample; ordinary startup never creates demo data."""

from urllib.parse import urlencode

from django.core.management.base import BaseCommand
from django.db import transaction

from ledger.access import Access
from ledger.models import Group, Workspace
from ledger.services import add_member, create_expense, create_person


class Command(BaseCommand):
    help = "Create a new isolated sample workspace and print its private owner return link."

    @transaction.atomic
    def handle(self, *args, **options):
        workspace = Workspace.objects.create()
        access = Access(workspace)
        people = [create_person(access, {"name": name}) for name in ["Mohit", "Rahul", "Ankit"]]
        group = Group.objects.create(workspace=workspace, name="Dinner")
        for person in people:
            add_member(access, group, person["id"])
        create_expense(
            access,
            {
                "group_id": group.id,
                "paid_by": people[0]["id"],
                "amount": 120000,
                "description": "Dinner together",
                "split_type": "equal",
            },
        )
        create_expense(
            access,
            {
                "group_id": group.id,
                "paid_by": people[1]["id"],
                "amount": 30000,
                "description": "Coffee afterwards",
                "split_type": "equal",
            },
        )
        self.stdout.write(self.style.SUCCESS(f"Created isolated Dinner demo, group {group.id}."))
        self.stdout.write(
            "Owner return link (keep private): /join#" + urlencode({"key": workspace.key})
        )
