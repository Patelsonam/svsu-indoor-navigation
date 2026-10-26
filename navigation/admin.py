from django.contrib import admin

from .models import Edge, Floor, Node, Room, SearchLog


@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "width", "height", "meters_per_pixel")


@admin.register(Node)
class NodeAdmin(admin.ModelAdmin):
    list_display = ("id", "floor", "type", "label", "x", "y", "connector_key")
    list_filter = ("floor", "type")
    readonly_fields = ("qr_code",)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("name", "floor", "category", "capacity", "faculty_name", "node")
    list_filter = ("floor", "category")
    search_fields = ("name", "aliases", "faculty_name")


@admin.register(Edge)
class EdgeAdmin(admin.ModelAdmin):
    list_display = ("id", "node_a", "node_b", "distance", "accessible", "name")
    list_filter = ("accessible",)


@admin.register(SearchLog)
class SearchLogAdmin(admin.ModelAdmin):
    list_display = ("query", "room", "results_count", "created_at")
