"""Consistent API errors without exposing database or capability details."""

from django.db import OperationalError
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class FieldError(APIException):
    status_code = 422
    default_detail = "Check the supplied fields."


class AccessError(APIException):
    status_code = 401
    default_detail = "Open or create a workspace to continue."


class Conflict(APIException):
    status_code = 409
    default_detail = "This operation conflicts with the saved state."


def exception_handler(exc, context):
    """Translate validation and bounded SQLite contention into stable error bodies."""
    if isinstance(exc, OperationalError) and any(
        word in str(exc).lower() for word in ["locked", "busy"]
    ):
        return Response(
            {"detail": "The ledger is busy. Retry with the same Idempotency-Key."},
            status=503,
            headers={"Retry-After": "1"},
        )
    if isinstance(exc, (FieldError, ValidationError)):
        details = exc.detail
        return Response({"detail": "Check the supplied fields.", "errors": details}, status=422)
    response = drf_exception_handler(exc, context)
    if response is not None and not isinstance(response.data, dict):
        response.data = {"detail": response.data}
    return response
