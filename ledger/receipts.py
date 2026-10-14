"""Private bill-photo handling: decode, sanitize, store, and clean up failed writes."""

import hashlib
import warnings
from io import BytesIO
from uuid import uuid4

from django.core.files.base import ContentFile
from django.db import transaction
from django.http import FileResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import NotFound
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from ledger.access import resolve_request
from ledger.errors import FieldError
from ledger.models import Expense
from ledger.schema import ExpenseOutput
from ledger.serializers import PhotoInput
from ledger.services import expense_data, mutate
from ledger.views import AUTH_PARAMETERS, ERRORS, IDEMPOTENCY, SafeAPI, validated

MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 20_000_000
FORMAT_CONFIG = {
    "JPEG": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
    "WEBP": ("webp", "image/webp"),
}


def sanitize_photo(upload):
    """Verify actual bytes; re-encode to strip metadata and ignore user filenames."""
    if upload.size > MAX_BYTES:
        raise FieldError({"photo": "Photo must be 5 MB or smaller."})
    raw = upload.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise FieldError({"photo": "Photo must be 5 MB or smaller."})
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(BytesIO(raw))
            format_name = image.format
            if format_name not in FORMAT_CONFIG:
                raise FieldError({"photo": "Choose a real JPEG, PNG, or WebP image."})
            if image.width * image.height > MAX_PIXELS:
                raise FieldError(
                    {"photo": "Photo dimensions are too large (maximum20 megapixels)."}
                )
            image.verify()
            image = Image.open(BytesIO(raw))
            image.load()
            if getattr(image, "is_animated", False):
                raise FieldError({"photo": "Use a still image rather than an animation."})
            converted = ImageOps.exif_transpose(image).convert(
                "RGB" if format_name == "JPEG" else "RGBA"
            )
            output = BytesIO()
            converted.save(output, format=format_name)
            sanitized = output.getvalue()
            if len(sanitized) > MAX_BYTES:
                raise FieldError({"photo": "Decoded photo is too large. Export a smaller image."})
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise FieldError({"photo": "File could not be decoded as a safe image."}) from exc
    return sanitized, FORMAT_CONFIG[format_name][0], hashlib.sha256(raw).hexdigest()


@extend_schema(parameters=AUTH_PARAMETERS)
class ReceiptView(SafeAPI):
    """Optional attachment is a separate write; an upload error never undoes the expense."""

    parser_classes = [MultiPartParser]

    def get_expense(self, access, expense_id):
        try:
            return Expense.objects.select_related("paid_by").get(
                id=expense_id, group__in=access.groups()
            )
        except Expense.DoesNotExist as exc:
            raise NotFound("Expense not found.") from exc

    @extend_schema(
        responses={
            (200, "image/jpeg"): OpenApiTypes.BINARY,
            (200, "image/png"): OpenApiTypes.BINARY,
            (200, "image/webp"): OpenApiTypes.BINARY,
            **ERRORS,
        },
        description="Read a private receipt using the same owner/group access as its expense. No public media paths.",
    )
    def get(self, request, expense_id):
        expense = self.get_expense(resolve_request(request), expense_id)
        if not expense.receipt:
            raise NotFound("This expense has no bill photo.")
        try:
            file = expense.receipt.open("rb")
        except FileNotFoundError as exc:
            raise NotFound("Bill photo is unavailable.") from exc
        suffix = expense.receipt.name.rsplit(".", 1)[-1]
        content_type = {extension: mime for extension, mime in FORMAT_CONFIG.values()}[suffix]
        response = FileResponse(file, content_type=content_type)
        response["Content-Disposition"] = f'inline; filename="receipt.{suffix}"'
        response["Cache-Control"] = "private, no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response

    @extend_schema(
        parameters=[IDEMPOTENCY],
        request=PhotoInput,
        responses={201: ExpenseOutput, **ERRORS},
        description="Optional multipart photo (field photo), JPEG/PNG/WebP up to5 MB and20 megapixels. Decoded/re-encoded, metadata removed, random storage name. Replaces old image only after successful commit. Retain Idempotency-Key for retries.",
    )
    def post(self, request, expense_id):
        access = resolve_request(request)
        self.get_expense(access, expense_id)
        if set(request.data) != {"photo"}:
            raise FieldError({"photo": "Supply exactly one photo field."})
        data = validated(PhotoInput, request.data)
        sanitized, suffix, digest = sanitize_photo(data["photo"])
        written = []

        def save_photo():
            expense = self.get_expense(access, expense_id)
            old_name = expense.receipt.name
            storage = expense.receipt.storage
            expense.receipt.save(f"{uuid4().hex}.{suffix}", ContentFile(sanitized), save=False)
            written.append((storage, expense.receipt.name))
            expense.save(update_fields=["receipt"])
            if old_name:
                # Cleanup cannot undo a committed replacement: Windows may still
                # have the old photo open for a download. Django logs cleanup
                # failures; the inaccessible old file can be removed later.
                transaction.on_commit(lambda: storage.delete(old_name), robust=True)
            return expense_data(expense)

        try:
            result, status, replay = mutate(
                access,
                f"expense:{expense_id}:receipt",
                request.headers.get("Idempotency-Key"),
                {"sha256": digest},
                save_photo,
                required=True,
            )
        except Exception:
            for storage, name in written:
                storage.delete(name)
            raise
        return Response(
            result, status=status, headers={"Idempotency-Replayed": "true"} if replay else {}
        )
