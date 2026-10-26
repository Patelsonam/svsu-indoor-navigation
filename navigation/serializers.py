"""DRF serializers. Validation lives here so the API returns clean 400 errors."""
from rest_framework import serializers

from .models import CONNECTOR_TYPES, Edge, Floor, Node, Room


class FloorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Floor
        fields = ["id", "number", "name", "image", "width", "height", "meters_per_pixel"]
        read_only_fields = ["width", "height"]


class NodeSerializer(serializers.ModelSerializer):
    floor_number = serializers.IntegerField(source="floor.number", read_only=True)

    class Meta:
        model = Node
        fields = ["id", "floor", "floor_number", "x", "y", "type", "label", "connector_key", "qr_code"]
        read_only_fields = ["qr_code"]

    def validate(self, attrs):
        # Merge incoming data with the existing instance (PATCH support).
        get = lambda k: attrs.get(k, getattr(self.instance, k, None))
        floor, x, y = get("floor"), get("x"), get("y")
        if get("connector_key") and get("type") not in CONNECTOR_TYPES:
            raise serializers.ValidationError({"connector_key": "Only stairs/lift nodes can have a connector key."})
        if floor and floor.width and floor.height and not (0 <= x <= floor.width and 0 <= y <= floor.height):
            raise serializers.ValidationError("Node lies outside the floor image.")
        return attrs


class EdgeSerializer(serializers.ModelSerializer):
    floor = serializers.IntegerField(source="node_a.floor_id", read_only=True)

    class Meta:
        model = Edge
        fields = ["id", "floor", "node_a", "node_b", "distance", "accessible", "name"]
        read_only_fields = ["distance"]

    def validate(self, attrs):
        a = attrs.get("node_a", getattr(self.instance, "node_a", None))
        b = attrs.get("node_b", getattr(self.instance, "node_b", None))
        if a.pk == b.pk:
            raise serializers.ValidationError("An edge cannot connect a node to itself.")
        if a.floor_id != b.floor_id:
            raise serializers.ValidationError(
                "Edges must connect nodes on the same floor (stairs/lifts are linked via connector_key)."
            )
        lo, hi = sorted((a.pk, b.pk))
        dup = Edge.objects.filter(node_a_id=lo, node_b_id=hi)
        if self.instance:
            dup = dup.exclude(pk=self.instance.pk)
        if dup.exists():
            raise serializers.ValidationError("These two nodes are already connected.")
        return attrs


class RoomSerializer(serializers.ModelSerializer):
    floor_number = serializers.IntegerField(source="floor.number", read_only=True)
    is_placed = serializers.BooleanField(read_only=True)
    category_display = serializers.CharField(source="get_category_display", read_only=True)

    class Meta:
        model = Room
        fields = [
            "id", "name", "floor", "floor_number", "node", "is_placed", "category", "category_display",
            "capacity", "description", "faculty_name", "aliases",
        ]

    def validate(self, attrs):
        floor = attrs.get("floor", getattr(self.instance, "floor", None))
        node = attrs.get("node", getattr(self.instance, "node", None))
        if node and floor and node.floor_id != floor.pk:
            raise serializers.ValidationError({"node": "Node must be on the same floor as the room."})
        return attrs


class RoomSearchSerializer(serializers.ModelSerializer):
    """Slim payload for autocomplete dropdowns."""

    floor_number = serializers.IntegerField(source="floor.number", read_only=True)
    is_placed = serializers.BooleanField(read_only=True)

    class Meta:
        model = Room
        fields = ["id", "name", "floor_number", "category", "node", "is_placed", "faculty_name"]
