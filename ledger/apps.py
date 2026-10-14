from django.apps import AppConfig


class LedgerConfig(AppConfig):
    """Expense sharing domain application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "ledger"
