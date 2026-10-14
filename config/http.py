"""Health probes and safe SPA/static delivery for a single-origin runtime."""

import mimetypes

from django.conf import settings
from django.db import connection
from django.http import FileResponse, HttpResponse, JsonResponse


def live(request):
    return JsonResponse({"status": "ok"})


def ready(request):
    """Probe migrations, not merely process liveness. Never exposes filesystem paths."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM ledger_workspace LIMIT 1")
        return JsonResponse({"status": "ready", "database": "ok"})
    except Exception:
        return JsonResponse({"status": "not ready", "database": "unavailable"}, status=503)


def missing_api(request, path=None):
    return JsonResponse({"detail": "API endpoint not found."}, status=404)


def spa(request, path=""):
    """Serve assets only within dist; application routes receive the SPA index."""
    if request.method not in {"GET", "HEAD"}:
        return JsonResponse({"detail": "Method not allowed."}, status=405)
    root = (settings.BASE_DIR / "frontend" / "dist").resolve()
    candidate = (root / path).resolve()
    if path and not candidate.is_relative_to(root):
        return JsonResponse({"detail": "File not found."}, status=404)
    if path.startswith("assets/"):
        if not candidate.is_file():
            return JsonResponse({"detail": "Asset not found."}, status=404)
        response = FileResponse(
            candidate.open("rb"),
            content_type=mimetypes.guess_type(candidate.name)[0] or "application/octet-stream",
        )
        response["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
    if path and candidate.is_file() and path.endswith((".svg", ".png", ".ico", ".webmanifest")):
        return FileResponse(
            candidate.open("rb"),
            content_type=mimetypes.guess_type(candidate.name)[0] or "application/octet-stream",
        )
    index = root / "index.html"
    if not index.exists():
        return HttpResponse(
            "Frontend is not built. Run npm ci && npm run build inside frontend/.",
            status=503,
            content_type="text/plain",
        )
    response = FileResponse(index.open("rb"), content_type="text/html")
    response["Cache-Control"] = "no-cache"
    response["Referrer-Policy"] = "no-referrer"
    return response
