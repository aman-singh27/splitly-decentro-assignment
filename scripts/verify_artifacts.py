"""Verify exported API contracts against the live server, using only stdlib.

Usage: python scripts/verify_artifacts.py [--base-url http://127.0.0.1:8000]
By default Django's in-process client reads actual exported endpoints without
starting a server. --base-url checks an already running deployment instead.
The command reads public exports only and does not mutate application data.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

REQUIRED_OPERATIONS = {
    ("get", "/api/v1/users"),
    ("post", "/api/v1/users"),
    ("get", "/api/v1/groups"),
    ("post", "/api/v1/groups"),
    ("get", "/api/v1/groups/{id}"),
    ("get", "/api/v1/groups/{id}/members"),
    ("post", "/api/v1/groups/{id}/members"),
    ("post", "/api/v1/expenses"),
    ("get", "/api/v1/groups/{id}/expenses"),
    ("get", "/api/v1/groups/{id}/balances"),
    ("get", "/api/v1/balances"),
    ("get", "/api/v1/groups/{id}/balances/explanation"),
    ("post", "/api/v1/settlements"),
    ("get", "/api/v1/groups/{id}/settlements"),
    ("get", "/api/v1/groups/{id}/invite"),
    ("get", "/api/v1/workspace"),
    ("post", "/api/v1/workspace"),
    ("post", "/api/v1/workspace/join"),
    ("post", "/api/v1/workspace/switch"),
    ("get", "/api/v1/workspace/invite"),
    ("post", "/api/v1/expenses/{id}/receipt"),
    ("get", "/api/v1/expenses/{id}/receipt"),
}
METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def normalized_path(path: str) -> str:
    """Treat serializer parameter names and Postman template names equivalently."""
    path = path.split("?", 1)[0].rstrip("/")
    path = re.sub(r"\{\{[^{}]+\}\}", "{id}", path)
    return re.sub(r"\{[^{}]+\}", "{id}", path)


def requests_in(items: list[dict]):
    """Yield leaf requests from a nested Postman collection."""
    for item in items:
        if "request" in item:
            yield item["request"]
        yield from requests_in(item.get("item", []))


def raw_url(request: dict) -> str:
    url = request.get("url", "")
    return url if isinstance(url, str) else url.get("raw", "")


def verify(schema: dict, collection: dict, environment: dict, root: Path) -> list[str]:
    """Return actionable export errors; an empty list means all checks passed."""
    errors: list[str] = []
    if not str(schema.get("openapi", "")).startswith("3."):
        errors.append("OpenAPI export is not an OpenAPI 3 document")
    operations = {
        (method.lower(), normalized_path(path))
        for path, spec in schema.get("paths", {}).items()
        for method in spec
        if method.lower() in METHODS
    }
    for method, path in sorted(REQUIRED_OPERATIONS - operations):
        errors.append(f"OpenAPI missing {method.upper()} {path}")

    schemas = schema.get("components", {}).get("schemas", {})
    expense_input = schemas.get("ExpenseInputRequest", {})
    if not {"split_type", "splits"}.issubset(expense_input.get("properties", {})):
        errors.append("OpenAPI expense input omits custom split fields")
    if "split_type" in expense_input.get("required", []):
        errors.append("OpenAPI incorrectly requires a split type for default equal allocation")
    if set(schemas.get("SplitTypeEnum", {}).get("enum", [])) != {"equal", "custom"}:
        errors.append("OpenAPI split types do not describe equal and custom allocation")
    receipt_spec = next(
        (
            spec
            for path, spec in schema.get("paths", {}).items()
            if normalized_path(path) == "/api/v1/expenses/{id}/receipt"
        ),
        {},
    )
    if "multipart/form-data" not in receipt_spec.get("post", {}).get("requestBody", {}).get(
        "content", {}
    ):
        errors.append("OpenAPI receipt upload omits multipart form data")
    receipt_formats = (
        receipt_spec.get("get", {}).get("responses", {}).get("200", {}).get("content", {})
    )
    if not {"image/jpeg", "image/png", "image/webp"}.issubset(receipt_formats):
        errors.append("OpenAPI receipt response omits supported image content types")
    photo_properties = schemas.get("PhotoInputRequest", {}).get("properties", {})
    if photo_properties.get("photo", {}).get("format") != "binary":
        errors.append("OpenAPI receipt photo is not described as a binary file")

    info = collection.get("info", {})
    if "v2.1.0" not in info.get("schema", ""):
        errors.append("Postman export is not collection schema v2.1.0")
    request_list = list(requests_in(collection.get("item", [])))
    collection_operations: set[tuple[str, str]] = set()
    example_fields = {
        "/api/v1/users": {"name"},
        "/api/v1/groups": {"name"},
        "/api/v1/groups/{id}/members": {"user_id"},
        "/api/v1/expenses": {"group_id", "paid_by", "amount", "description"},
        "/api/v1/settlements": {"group_id", "from_user_id", "to_user_id", "amount"},
        "/api/v1/workspace/join": {"access_key"},
        "/api/v1/workspace/switch": {"scope"},
    }
    for request in request_list:
        url = raw_url(request)
        match = re.search(r"(/api/v1/[^?#]*)", url)
        if not match:
            errors.append(f"Postman request has no API path: {url}")
            continue
        method = request.get("method", "").lower()
        path = normalized_path(match.group(1))
        collection_operations.add((method, path))
        if method == "post" and path in example_fields:
            body = request.get("body", {})
            if body.get("mode") != "raw":
                errors.append(f"Postman {path} has no JSON example")
            else:
                substituted = re.sub(r"\{\{[^{}]+\}\}", "1", body.get("raw", ""))
                try:
                    example = json.loads(substituted)
                    missing = example_fields[path] - example.keys()
                    if missing:
                        errors.append(
                            f"Postman {path} example missing {', '.join(sorted(missing))}"
                        )
                except (ValueError, AttributeError):
                    errors.append(
                        f"Postman {path} example is not runnable JSON after variable substitution"
                    )
        if method == "post" and path == "/api/v1/expenses/{id}/receipt":
            body = request.get("body", {})
            if body.get("mode") != "formdata" or not any(
                field.get("key") == "photo" and field.get("type") == "file"
                for field in body.get("formdata", [])
            ):
                errors.append("Postman receipt upload lacks its photo file field")
        if method == "post" and path in {
            "/api/v1/expenses",
            "/api/v1/settlements",
            "/api/v1/expenses/{id}/receipt",
        }:
            headers = {entry.get("key", "").lower(): entry for entry in request.get("header", [])}
            header = headers.get("idempotency-key")
            if not header or not header.get("value") or header.get("disabled"):
                errors.append(f"Postman {path} lacks an enabled Idempotency-Key")
    for method, path in sorted(REQUIRED_OPERATIONS - collection_operations):
        errors.append(f"Postman missing {method.upper()} {path}")
    for method, path in sorted(collection_operations - operations):
        errors.append(f"Postman contains operation absent from OpenAPI: {method.upper()} {path}")

    variables = {entry.get("key"): entry for entry in environment.get("values", [])}
    for name in [
        "base_url",
        "workspace_key",
        "group_key",
        "group_id",
        "user_a_id",
        "user_b_id",
        "expense_id",
    ]:
        if name not in variables:
            errors.append(f"Postman environment missing {name}")
    for name in ["workspace_key", "group_key"]:
        value = str(variables.get(name, {}).get("value", ""))
        if re.search(r"(?:ws|grp)_[A-Za-z0-9_-]{20,}", value):
            errors.append(f"Public environment appears to contain a real {name}")

    for name in ["api.md", "architecture.md", "enhancement.md"]:
        document = root / "docs" / "public" / name
        if not document.is_file() or not document.read_text(encoding="utf-8").strip():
            errors.append(f"Missing public documentation: {document}")
    return errors


def fetch_json(base_url: str, path: str) -> dict:
    request = Request(base_url.rstrip("/") + path, headers={"Accept": "application/json"})
    with urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise ValueError(f"{path}: HTTP {response.status}")
        value = json.load(response)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def in_process_artifacts(root: Path) -> list[dict]:
    """Exercise actual public Django views without requiring a network listener."""
    sys.path.insert(0, str(root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    from django.test import Client

    client = Client(HTTP_HOST="127.0.0.1")
    values = []
    for path in ["/api/openapi.json", "/api/postman.json", "/api/environment.json"]:
        response = client.get(path, HTTP_ACCEPT="application/json")
        if response.status_code != 200:
            raise ValueError(f"{path}: HTTP {response.status_code}")
        values.append(json.loads(response.content))
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url", help="Check a running server instead of in-process Django endpoints"
    )
    args = parser.parse_args()
    try:
        root = Path(__file__).resolve().parents[1]
        artifacts = (
            [
                fetch_json(args.base_url, path)
                for path in ["/api/openapi.json", "/api/postman.json", "/api/environment.json"]
            ]
            if args.base_url
            else in_process_artifacts(root)
        )
        errors = verify(*artifacts, root=root)
    except (OSError, ValueError) as exc:
        print(f"API artifact verification failed: {exc}", file=sys.stderr)
        return 1
    if errors:
        print("API artifact verification failed:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1
    print(
        f"API artifact verification passed: {len(REQUIRED_OPERATIONS)} required operations, public docs, and key placeholders."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
