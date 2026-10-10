from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LoginView, PasswordResetView
from django.urls import include, path

from apps.accounts.forms import ThrottledAdminAuthenticationForm, ThrottledAuthenticationForm, ThrottledPasswordResetForm

admin.site.site_header = "Helply Administration"
admin.site.site_title = "Helply"
admin.site.login_form = ThrottledAdminAuthenticationForm  # the admin login is a second door for password guessing

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", LoginView.as_view(authentication_form=ThrottledAuthenticationForm), name="login"),
    path("accounts/password_reset/", PasswordResetView.as_view(form_class=ThrottledPasswordResetForm), name="password_reset"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("tickets/", include("apps.tickets.urls")),
    path("kb/", include("apps.kb.urls")),
    path("assets/", include("apps.assets.urls")),
    path("monitoring/", include("apps.monitoring.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("people/", include("apps.accounts.urls")),
    path("sla/", include("apps.sla.urls")),
    path("", include("apps.core.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
