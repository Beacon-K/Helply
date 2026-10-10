from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Accounts"

    def ready(self):
        from . import login_records  # noqa: F401  (connects the sign-in / sign-out signals)
