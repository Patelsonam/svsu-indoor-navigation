from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from navigation.views import app_page, editor, manifest, service_worker

urlpatterns = [
    path("", app_page, name="app"),                                  # the navigation app (PWA)
    path("manifest.webmanifest", manifest),
    path("sw.js", service_worker),
    path("admin/", admin.site.urls),
    path("api/", include("navigation.urls")),
    path("editor/", editor, name="editor"),  # Step 2 map editor (staff only)
]

# Serve uploaded floor images in development.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
