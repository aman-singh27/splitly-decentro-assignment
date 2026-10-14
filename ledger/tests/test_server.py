"""Render terminates TLS before Waitress; local deployments must remain HTTP."""

from unittest.mock import patch

import pytest


@pytest.mark.parametrize("render_tls,scheme", [(True, "https"), (False, "http")])
def test_server_matches_platform_tls_and_binds_assigned_port(
    settings, monkeypatch, render_tls, scheme
):
    from config import serve

    settings.RENDER_TLS = render_tls
    monkeypatch.setenv("PORT", "10000")
    with patch("config.serve.waitress_serve") as start:
        serve.main()
    assert start.call_args.kwargs == {
        "host": "0.0.0.0",
        "port": 10000,
        "url_scheme": scheme,
        "trusted_proxy": None,
        "clear_untrusted_proxy_headers": True,
    }
