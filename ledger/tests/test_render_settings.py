"""Render proxy configuration preserves HTTPS, CSRF, and local header boundaries."""

import runpy
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import Client, override_settings

SETTINGS_PATH = Path(__file__).resolve().parents[2] / "config" / "settings.py"
HOST = "splitly-deployment-test.onrender.com"


def environment_settings(monkeypatch, **environment):
    """Evaluate the real config with isolated environment and a public test secret."""
    for name in [
        "RENDER",
        "RENDER_EXTERNAL_HOSTNAME",
        "DJANGO_ALLOWED_HOSTS",
        "DJANGO_DEBUG",
        "DJANGO_SECURE_COOKIES",
        "DJANGO_HTTPS",
        "DJANGO_CSRF_TRUSTED_ORIGINS",
    ]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DJANGO_SECRET_KEY", "deployment-test-only-not-a-real-secret-" * 3)
    monkeypatch.setenv("DJANGO_DEBUG", "false")
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    return runpy.run_path(str(SETTINGS_PATH))


def request_settings(config):
    """Apply only deployment settings while retaining the test database/session setup."""
    return override_settings(
        **{
            name: config.get(name)
            for name in [
                "ALLOWED_HOSTS",
                "SECURE_PROXY_SSL_HEADER",
                "SECURE_SSL_REDIRECT",
                "SESSION_COOKIE_SECURE",
                "CSRF_COOKIE_SECURE",
                "CSRF_TRUSTED_ORIGINS",
            ]
        }
    )


def test_render_hostname_and_https_trust_are_enabled_together(monkeypatch):
    config = environment_settings(monkeypatch, RENDER="true", RENDER_EXTERNAL_HOSTNAME=HOST)
    assert HOST in config["ALLOWED_HOSTS"]
    assert config["RENDER_TLS"] is True
    assert config["SECURE_PROXY_SSL_HEADER"] == ("HTTP_X_FORWARDED_PROTO", "https")
    assert config["SESSION_COOKIE_SECURE"] is True
    assert config["CSRF_COOKIE_SECURE"] is True


def test_render_host_is_added_without_wildcard_or_duplicate(monkeypatch):
    config = environment_settings(
        monkeypatch,
        RENDER="true",
        RENDER_EXTERNAL_HOSTNAME=HOST,
        DJANGO_ALLOWED_HOSTS=f"localhost, {HOST}, app.example.com, ",
    )
    assert config["ALLOWED_HOSTS"] == ["localhost", HOST, "app.example.com"]
    assert "*" not in config["ALLOWED_HOSTS"]


@pytest.mark.parametrize(
    "environment",
    [
        {},
        {"RENDER": "true"},
        {"RENDER_EXTERNAL_HOSTNAME": HOST},
        {"RENDER": "false", "RENDER_EXTERNAL_HOSTNAME": HOST},
    ],
)
def test_local_or_incomplete_render_environment_never_trusts_forwarded_proto(
    monkeypatch, environment
):
    config = environment_settings(monkeypatch, **environment)
    assert config["RENDER_TLS"] is False
    assert config["SECURE_PROXY_SSL_HEADER"] is None
    with request_settings(config):
        response = Client().get(
            "/health/live", HTTP_HOST="localhost", HTTP_X_FORWARDED_PROTO="https"
        )
    assert response.status_code == 301
    assert response["Location"] == "https://localhost/health/live"


@pytest.mark.parametrize(
    "hostname",
    [
        "*",
        "https://evil.example",
        "service.onrender.com/evil",
        "service.onrender.com.evil.test",
        ".onrender.com",
        "unrelated.example",
    ],
)
def test_invalid_render_host_is_rejected_before_enabling_proxy_trust(monkeypatch, hostname):
    with pytest.raises(ImproperlyConfigured, match="RENDER_EXTERNAL_HOSTNAME"):
        environment_settings(monkeypatch, RENDER="true", RENDER_EXTERNAL_HOSTNAME=hostname)


@pytest.mark.django_db
def test_proxy_https_cookie_journey_and_origin_check_do_not_redirect_or_fail_csrf(monkeypatch):
    config = environment_settings(monkeypatch, RENDER="true", RENDER_EXTERNAL_HOSTNAME=HOST)
    headers = {"HTTP_HOST": HOST, "HTTP_X_FORWARDED_PROTO": "https"}
    with request_settings(config):
        client = Client(enforce_csrf_checks=True)
        initial = client.get("/api/v1/workspace", **headers)
        assert initial.status_code == 401
        assert initial.cookies["csrftoken"]["secure"] is True
        token = client.cookies["csrftoken"].value
        created = client.post(
            "/api/v1/workspace",
            "{}",
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN=f"https://{HOST}",
            **headers,
        )
        assert created.status_code == 201
        assert created.cookies["sessionid"]["secure"] is True
        group = client.post(
            "/api/v1/groups",
            '{"name":"Hosted group"}',
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN=f"https://{HOST}",
            **headers,
        )
        assert group.status_code == 201
        hostile = client.post(
            "/api/v1/groups",
            '{"name":"Hostile origin"}',
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN="https://evil.example",
            **headers,
        )
        assert hostile.status_code == 403
        assert client.get("/health/live", **headers).status_code == 200
        assert client.get("/health/live", HTTP_HOST=HOST, secure=True).status_code == 200


def test_non_https_proxy_requests_still_redirect_and_bad_hosts_still_fail(monkeypatch):
    config = environment_settings(monkeypatch, RENDER="true", RENDER_EXTERNAL_HOSTNAME=HOST)
    with request_settings(config):
        client = Client()
        assert (
            client.get("/health/live", HTTP_HOST=HOST, HTTP_X_FORWARDED_PROTO="http").status_code
            == 301
        )
        assert (
            client.get(
                "/health/live", HTTP_HOST="evil.example", HTTP_X_FORWARDED_PROTO="https"
            ).status_code
            == 400
        )
