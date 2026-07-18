"""URL configuration for the restaurant project.

Each app declares its own public and staff routes; they are all mounted
at the root and use distinct prefixes (/, /menu/, /order/, /staff/...).
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("", include("core.urls")),
    path("", include("menu.urls")),
    path("", include("orders.urls")),
    path("", include("reservations.urls")),
    path("", include("accounts.urls")),
    path("", include("tables.urls")),
    path("", include("cash.urls")),
]

# Local / Cloudinary-off media serving
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif getattr(settings, "SERVE_MEDIA", False):
    urlpatterns += [
        re_path(
            r"^media/(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]
