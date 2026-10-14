"""Waitress startup for local Docker and Render's TLS-terminating public edge."""

import os

from django.conf import settings
from waitress import serve as waitress_serve

from config.wsgi import application


def main():
    """Use Render's externally HTTPS scheme while clearing untrusted proxy headers.

    Waitress clears forwarded headers by default. Merely configuring Django's
    proxy header cannot establish the HTTPS scheme after those headers vanish.
    Render redirects HTTP at its edge; its private backend connection is HTTP.
    Local Docker has no such TLS edge, so its default scheme remains HTTP.
    """
    waitress_serve(
        application,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        url_scheme="https" if getattr(settings, "RENDER_TLS", False) else "http",
        trusted_proxy=None,
        clear_untrusted_proxy_headers=True,
    )


if __name__ == "__main__":
    main()
