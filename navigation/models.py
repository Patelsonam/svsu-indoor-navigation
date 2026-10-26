"""
Data model for indoor navigation.

Coordinate system
-----------------
Node.x / Node.y are IMAGE PIXELS of the floor plan, origin at the TOP-LEFT
(x grows right, y grows down). The frontend converts to Leaflet's CRS.Simple
([lat, lng] = [height - y, x]) so the backend never deals with Leaflet quirks.

Multi-floor linking
-------------------
Stairs/lift nodes that are the same physical structure on different floors
share a `connector_key` (e.g. "staircase-1"). Step 4 will join nodes with the
same key on adjacent floors. Same-floor connections are `Edge` rows.
"""
import math

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
import uuid


class Floor(models.Model):
    number = models.IntegerField(unique=True, help_text="0 = ground floor. Any number of floors is supported.")
    name = models.CharField(max_length=100, help_text='e.g. "Ground Floor"')
    image = models.ImageField(
        upload_to="floors/", width_field="width", height_field="height", blank=True, null=True
    )
    # Filled automatically from the uploaded image.
    width = models.PositiveIntegerField(default=0, editable=False)
    height = models.PositiveIntegerField(default=0, editable=False)
    # Optional real-world scale (set it once you measure a known corridor).
    meters_per_pixel = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["number"]

    def __str__(self):
        return f"Floor {self.number} – {self.name}"


class NodeType(models.TextChoices):
    ROOM = "room", "Room"
    CORRIDOR = "corridor", "Corridor"
    JUNCTION = "junction", "Junction"
    STAIRS = "stairs", "Stairs"
    LIFT = "lift", "Lift"
    ENTRANCE = "entrance", "Entrance"
    EXIT = "exit", "Exit"


CONNECTOR_TYPES = (NodeType.STAIRS, NodeType.LIFT)


class Node(models.Model):
    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name="nodes")
    x = models.FloatField(help_text="Image pixels from left")
    y = models.FloatField(help_text="Image pixels from top")
    type = models.CharField(max_length=10, choices=NodeType.choices, default=NodeType.CORRIDOR)
    label = models.CharField(max_length=120, blank=True, help_text="Optional, e.g. 'Corridor near Lab 1'")
    connector_key = models.SlugField(
        max_length=60, blank=True,
        help_text="Stairs/lifts only. Same key on different floors = same physical staircase/lift.",
    )
    # Printed in the QR code so a scan can resolve "you are here".
    qr_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        ordering = ["floor__number", "id"]
        constraints = [
            # One staircase/lift key may appear only once per floor.
            models.UniqueConstraint(
                fields=["floor", "connector_key"],
                condition=~Q(connector_key=""),
                name="unique_connector_key_per_floor",
            )
        ]

    def __str__(self):
        return f"#{self.pk} {self.type} F{self.floor.number} ({self.x:.0f},{self.y:.0f})"

    def clean(self):
        if self.connector_key and self.type not in CONNECTOR_TYPES:
            raise ValidationError({"connector_key": "Only stairs/lift nodes can have a connector key."})
        f = self.floor
        if f.width and f.height and not (0 <= self.x <= f.width and 0 <= self.y <= f.height):
            raise ValidationError("Node lies outside the floor image.")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Node moved => keep the stored edge lengths in sync.
        for edge in Edge.objects.filter(Q(node_a=self) | Q(node_b=self)):
            edge.save()


class RoomCategory(models.TextChoices):
    CLASSROOM = "classroom", "Classroom / Hall"
    LAB = "lab", "Lab"
    OFFICE = "office", "Office"
    FACULTY = "faculty", "Faculty room"
    TOILET = "toilet", "Toilet"
    UTILITY = "utility", "Utility (pantry, server…)"
    STAIRS = "stairs", "Staircase"
    LIFT = "lift", "Lift"
    ENTRANCE = "entrance", "Entrance / Reception"
    OPEN_AREA = "open_area", "Open area"
    OTHER = "other", "Other"


class Room(models.Model):
    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name="rooms")
    name = models.CharField(max_length=150)
    # Nullable: a room can exist (and be searchable) before its node is marked
    # on the map with the editor tool (Step 2).
    node = models.ForeignKey(Node, on_delete=models.SET_NULL, null=True, blank=True, related_name="rooms")
    category = models.CharField(max_length=12, choices=RoomCategory.choices, default=RoomCategory.OTHER)
    capacity = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    faculty_name = models.CharField(max_length=150, blank=True)
    aliases = models.CharField(
        max_length=300, blank=True,
        help_text="Comma-separated search synonyms, e.g. 'hod, head of department'",
    )

    class Meta:
        ordering = ["floor__number", "name"]
        constraints = [models.UniqueConstraint(fields=["floor", "name"], name="unique_room_name_per_floor")]

    def __str__(self):
        return f"{self.name} (Floor {self.floor.number})"

    @property
    def is_placed(self):
        return self.node_id is not None

    def clean(self):
        if self.node_id and self.node.floor_id != self.floor_id:
            raise ValidationError({"node": "Node must be on the same floor as the room."})


class Edge(models.Model):
    """Undirected walkable link between two nodes on the SAME floor."""

    node_a = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="edges_a")
    node_b = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="edges_b")
    # Auto-computed (pixel units) from node coordinates on every save.
    distance = models.FloatField(editable=False, default=0)
    accessible = models.BooleanField(
        default=True, help_text="False for steps/stairs; wheelchair mode skips these edges."
    )
    name = models.CharField(
        max_length=120, blank=True,
        help_text="Used in directions, e.g. '2100mm passage'",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["node_a", "node_b"], name="unique_edge_pair"),
            models.CheckConstraint(condition=~Q(node_a=F("node_b")), name="edge_no_self_loop"),
        ]

    def __str__(self):
        return f"Edge {self.node_a_id}↔{self.node_b_id} ({self.distance:.0f}px)"

    def clean(self):
        if self.node_a_id and self.node_b_id and self.node_a.floor_id != self.node_b.floor_id:
            raise ValidationError("Edges must connect nodes on the same floor "
                                  "(use connector_key for stairs/lifts).")

    def save(self, *args, **kwargs):
        # Canonical order so (a,b) and (b,a) can't both exist.
        if self.node_a_id > self.node_b_id:
            self.node_a, self.node_b = self.node_b, self.node_a
        self.distance = math.hypot(self.node_a.x - self.node_b.x, self.node_a.y - self.node_b.y)
        super().save(*args, **kwargs)


class SearchLog(models.Model):
    """One row per completed search/selection — feeds the analytics dashboard (Step 8)."""

    query = models.CharField(max_length=200)
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name="searches")
    results_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"'{self.query}' → {self.results_count}"


class MapSnapshot(models.Model):
    """
    The complete map used by the web app (floors + plans, nodes, edges, rooms,
    room polygons, faculty names) as ONE JSON document, so every phone shows
    exactly the map the admin saved. Only one row (pk=1) is used.
    """

    data = models.JSONField()
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Map v{self.version} ({self.updated_at:%Y-%m-%d %H:%M})"
