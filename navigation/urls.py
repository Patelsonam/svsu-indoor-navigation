from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("floors", views.FloorViewSet, basename="floor")
router.register("nodes", views.NodeViewSet, basename="node")
router.register("edges", views.EdgeViewSet, basename="edge")
router.register("rooms", views.RoomViewSet, basename="room")

urlpatterns = [
    path("meta/", views.MetaView.as_view()),
    path("map/", views.MapView.as_view()),
    path("me/", views.me),
    path("locate/<uuid:qr_code>/", views.LocateView.as_view()),
    path("", include(router.urls)),
]
