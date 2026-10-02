from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Helply Administration"
admin.site.site_title = "Helply"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("tickets/", include("apps.tickets.urls")),
    path("kb/", include("apps.kb.urls")),
    path("assets/", include("apps.assets.urls")),
    path("", include("apps.core.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
