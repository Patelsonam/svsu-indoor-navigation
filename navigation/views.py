"""REST API views. Everything is read-only for the public; staff can write."""
from django.db.models import Case, IntegerField, Q, Value, When
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Edge, Floor, Node, NodeType, Room, RoomCategory, SearchLog
from .serializers import (
    EdgeSerializer, FloorSerializer, NodeSerializer, RoomSearchSerializer, RoomSerializer,
)


class FloorViewSet(viewsets.ModelViewSet):
    """/api/floors/ — looked up by floor NUMBER (e.g. /api/floors/3/)."""

    queryset = Floor.objects.all()
    serializer_class = FloorSerializer
    lookup_field = "number"

    @action(detail=True, methods=["get"])
    def graph(self, request, number=None):
        """Everything the map/editor needs for one floor in a single request."""
        floor = self.get_object()
        ctx = {"request": request}
        return Response({
            "floor": FloorSerializer(floor, context=ctx).data,
            "nodes": NodeSerializer(floor.nodes.select_related("floor"), many=True).data,
            "edges": EdgeSerializer(
                Edge.objects.filter(node_a__floor=floor).select_related("node_a"), many=True
            ).data,
            "rooms": RoomSerializer(floor.rooms.select_related("floor"), many=True).data,
        })


class NodeViewSet(viewsets.ModelViewSet):
    """/api/nodes/?floor=<number>&type=<type>"""

    serializer_class = NodeSerializer

    def get_queryset(self):
        qs = Node.objects.select_related("floor")
        p = self.request.query_params
        if p.get("floor") not in (None, ""):
            qs = qs.filter(floor__number=p["floor"])
        if p.get("type"):
            qs = qs.filter(type=p["type"])
        return qs


class EdgeViewSet(viewsets.ModelViewSet):
    """/api/edges/?floor=<number>"""

    serializer_class = EdgeSerializer

    def get_queryset(self):
        qs = Edge.objects.select_related("node_a")
        floor = self.request.query_params.get("floor")
        if floor not in (None, ""):
            qs = qs.filter(node_a__floor__number=floor)
        return qs


class RoomViewSet(viewsets.ModelViewSet):
    """/api/rooms/?floor=<number>&category=<cat>  and  /api/rooms/search/?q=..."""

    serializer_class = RoomSerializer

    def get_queryset(self):
        qs = Room.objects.select_related("floor")
        p = self.request.query_params
        if p.get("floor") not in (None, ""):
            qs = qs.filter(floor__number=p["floor"])
        if p.get("category"):
            qs = qs.filter(category=p["category"])
        return qs

    @action(detail=False, methods=["get"])
    def search(self, request):
        """
        Autocomplete: matches name, aliases, faculty name, description and category.
        Names that START with the query rank first. Pass ?log=1 when the user
        actually picks a result so analytics isn't flooded by keystrokes.
        """
        q = request.query_params.get("q", "").strip()
        if not q:
            return Response([])
        limit = min(int(request.query_params.get("limit", 10)), 25)
        rooms = (
            Room.objects.select_related("floor")
            .filter(
                Q(name__icontains=q) | Q(aliases__icontains=q) | Q(faculty_name__icontains=q)
                | Q(description__icontains=q) | Q(category__icontains=q.replace(" ", "_"))
            )
            .annotate(
                rank=Case(
                    When(name__istartswith=q, then=Value(0)),
                    When(name__icontains=q, then=Value(1)),
                    default=Value(2),
                    output_field=IntegerField(),
                )
            )
            .order_by("rank", "floor__number", "name")[:limit]
        )
        results = list(rooms)
        if request.query_params.get("log") == "1":
            SearchLog.objects.create(
                query=q[:200], room=results[0] if results else None, results_count=len(results)
            )
        return Response(RoomSearchSerializer(results, many=True).data)


class LocateView(APIView):
    """
    GET /api/locate/<qr_uuid>/ — resolve a scanned QR code to "you are here".
    The QR code simply encodes the node's UUID (or a URL ending in it).
    """

    def get(self, request, qr_code):
        node = get_object_or_404(Node.objects.select_related("floor"), qr_code=qr_code)
        return Response({
            "node": NodeSerializer(node).data,
            "floor": FloorSerializer(node.floor, context={"request": request}).data,
            "rooms": RoomSerializer(node.rooms.select_related("floor"), many=True).data,
        })


class MetaView(APIView):
    """GET /api/meta/ — enum values for dropdowns in the editor/admin UI."""

    def get(self, request):
        return Response({
            "node_types": [{"value": v, "label": l} for v, l in NodeType.choices],
            "room_categories": [{"value": v, "label": l} for v, l in RoomCategory.choices],
        })


# ---------------------------------------------------------------------------
# Step 2: browser-based map editor (staff only).
# Served by Django itself so the session login + CSRF cookie just work.
# ---------------------------------------------------------------------------
from django.contrib.admin.views.decorators import staff_member_required  # noqa: E402
from django.views.decorators.csrf import ensure_csrf_cookie  # noqa: E402
from django.shortcuts import render  # noqa: E402


@staff_member_required(login_url="/admin/login/")
@ensure_csrf_cookie
def editor(request):
    return render(request, "navigation/editor.html")


# ---------------------------------------------------------------------------
# Web app (PWA) + shared map API
# ---------------------------------------------------------------------------
from pathlib import Path  # noqa: E402

from django.http import HttpResponse, JsonResponse  # noqa: E402
from django.db import transaction  # noqa: E402

from .models import MapSnapshot  # noqa: E402

_HERE = Path(__file__).resolve().parent


def _read(rel):
    return (_HERE / rel).read_text(encoding="utf-8")


@ensure_csrf_cookie
def app_page(request):
    """The navigation app itself (kept as one HTML file; sets the CSRF cookie for admin saves)."""
    resp = HttpResponse(_read("templates/navigation/app.html"), content_type="text/html; charset=utf-8")
    resp["Cache-Control"] = "no-cache"
    return resp


def manifest(request):
    data = {
        "name": "SVSU Indoor Navigation", "short_name": "SVSU Nav", "start_url": "/", "scope": "/",
        "display": "standalone", "orientation": "portrait", "background_color": "#ffffff", "theme_color": "#2563eb",
        "icons": [
            {"src": "/static/pwa/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "/static/pwa/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
    }
    return JsonResponse(data, content_type="application/manifest+json")


def service_worker(request):
    """Served from the site root so it can control the whole app (offline support)."""
    resp = HttpResponse(_read("static/pwa/sw.js"), content_type="application/javascript")
    resp["Cache-Control"] = "no-cache"
    return resp


def me(request):
    return JsonResponse({"staff": bool(request.user.is_authenticated and request.user.is_staff)})


class MapView(APIView):
    """
    GET  /api/map/?since=<version>  -> {"version", "data"} or {"version","unchanged":true}
    PUT  /api/map/  (staff only)    -> body {"data": {...}, "base_version": n}
                                       409 if someone else saved in between.
    """

    def get(self, request):
        snap = MapSnapshot.objects.filter(pk=1).first()
        if not snap:
            return Response({"version": 0, "data": None})
        if request.query_params.get("since") == str(snap.version):
            return Response({"version": snap.version, "unchanged": True})
        return Response({"version": snap.version, "data": snap.data})

    def put(self, request):
        if not (request.user.is_authenticated and request.user.is_staff):
            return Response({"detail": "Staff login required."}, status=403)
        data, base = request.data.get("data"), request.data.get("base_version", 0)
        ok = isinstance(data, dict) and all(isinstance(data.get(k), list) for k in ("floors", "nodes", "edges", "rooms"))
        if not ok or not data["floors"]:
            return Response({"detail": "Invalid map data."}, status=400)
        with transaction.atomic():
            snap = MapSnapshot.objects.select_for_update().filter(pk=1).first()
            if snap and base != snap.version:
                return Response({"detail": "Map changed elsewhere.", "version": snap.version}, status=409)
            if snap:
                snap.data, snap.version = data, snap.version + 1
                snap.save()
            else:
                snap = MapSnapshot.objects.create(pk=1, data=data, version=1)
        return Response({"version": snap.version})
