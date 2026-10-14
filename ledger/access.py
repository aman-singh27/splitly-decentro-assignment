"""Capability resolution and cookie CSRF enforcement without user authentication."""

from dataclasses import dataclass

from django.conf import settings
from django.core import signing
from django.db.models import Q
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import NotFound, PermissionDenied

from ledger.errors import AccessError
from ledger.models import Group, Person, Workspace

SALT = "splitly.group.v1"


@dataclass(frozen=True)
class Access:
    """Resolved owner or exactly-one-group scope; every query starts here."""

    workspace: Workspace
    group: Group | None = None

    @property
    def scope_key(self):
        return f"group:{self.group.id}" if self.group else "workspace"

    def groups(self):
        return Group.objects.filter(
            workspace=self.workspace, **({"id": self.group.id} if self.group else {})
        )

    def people(self):
        query = Person.objects.filter(workspace=self.workspace)
        if self.group:
            query = query.filter(
                Q(memberships__group=self.group) | Q(creation_group=self.group)
            ).distinct()
        return query

    def get_group(self, group_id):
        try:
            return self.groups().get(id=group_id)
        except Group.DoesNotExist as exc:
            raise NotFound("Group not found.") from exc

    def get_person(self, person_id):
        try:
            return self.people().get(id=person_id)
        except Person.DoesNotExist as exc:
            raise NotFound("Person not found.") from exc

    def require_owner(self):
        if self.group:
            raise PermissionDenied("Only the workspace owner can do this.")


def group_capability(group):
    """Sign a group's persistent nonce so IDs cannot become share credentials."""
    return "grp_" + signing.dumps(
        {"id": group.id, "nonce": group.share_nonce}, salt=SALT, compress=True
    )


def resolve_key(key):
    """Resolve a supplied credential; invalid credentials never fall back to cookies."""
    if not isinstance(key, str):
        raise AccessError("Invalid access key.")
    if key.startswith("ws_"):
        workspace = Workspace.objects.filter(key=key).first()
        if workspace:
            return Access(workspace)
    elif key.startswith("grp_"):
        try:
            payload = signing.loads(key[4:], salt=SALT)
            group = Group.objects.select_related("workspace").get(
                id=payload["id"], share_nonce=payload["nonce"]
            )
            return Access(group.workspace, group)
        except (signing.BadSignature, KeyError, TypeError, ValueError, Group.DoesNotExist):
            pass
    raise AccessError("Invalid or unavailable access key.")


def resolve_request(request):
    """Explicit capability headers override active cookie scope, including failures."""
    if "X-Group-Key" in request.headers:
        access = resolve_key(request.headers["X-Group-Key"])
        if not access.group:
            raise AccessError("X-Group-Key requires a group capability.")
        return access
    if "X-Workspace-Key" in request.headers:
        access = resolve_key(request.headers["X-Workspace-Key"])
        if access.group:
            raise AccessError("X-Workspace-Key requires an owner capability.")
        return access
    active = request.session.get("active_key")
    if not active:
        raise AccessError()
    return resolve_key(active)


def enforce_request_safety(request):
    """Cookie writes require CSRF; explicit headers bypass token, never hostile Origin."""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    origin = request.headers.get("Origin")
    own_origin = f"{'https' if request.is_secure() else 'http'}://{request.get_host()}"
    if origin and origin != own_origin and origin not in settings.CSRF_TRUSTED_ORIGINS:
        raise PermissionDenied("Untrusted request origin.")
    if "X-Workspace-Key" not in request.headers and "X-Group-Key" not in request.headers:
        SessionAuthentication().enforce_csrf(request)


def metadata(request, access):
    """No secret keys in public metadata; retained owner access stays in the session."""
    return {
        "id": access.workspace.id,
        "scope": "group" if access.group else "workspace",
        "group_id": access.group.id if access.group else None,
        "can_switch_to_owner": bool(request.session.get("owner_key")),
    }
