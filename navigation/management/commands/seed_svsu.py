"""
Seed floors 0 and 3 and every room from the SVSU floor plans.

Rooms are created WITHOUT nodes — you place them on the map in Step 2 with the
editor. Safe to re-run (uses get_or_create / update_or_create).

Usage:
  python manage.py seed_svsu
  python manage.py seed_svsu --floor0-image ~/floor_0.jpg --floor3-image ~/floor_3.jpg
"""
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand

from navigation.models import Floor, Room, RoomCategory as C

# (name, category, capacity, description, aliases)
FLOOR_0 = [
    ("Entrance Lobby / Reception", C.ENTRANCE, None, "Main entrance lobby with reception desk", "reception, lobby, main entrance, front desk"),
    ("H.O.D. Cabin", C.OFFICE, None, "Head of Department cabin", "hod, head of department, head"),
    ("Faculty Lounge", C.FACULTY, None, "", "staff room, teachers room, lounge"),
    ("Department Office", C.OFFICE, None, "", "dept office, office, admin office"),
    ("Computer Lab (Top)", C.LAB, None, "", "computer lab, cs lab, lab"),
    ("Computer Lab (Bottom)", C.LAB, None, "", "computer lab, cs lab, lab"),
    ("CAD/CAM Lab", C.LAB, None, "", "cad lab, cam lab, cadcam"),
    ("Eng. Drawing Hall", C.CLASSROOM, None, "Engineering drawing hall", "drawing hall, engineering drawing, graphics hall"),
    ("Male Toilet", C.TOILET, None, "", "washroom, restroom, men, gents, boys toilet, bathroom"),
    ("Female Toilet", C.TOILET, None, "", "washroom, restroom, women, ladies, girls toilet, bathroom"),
    ("Pantry", C.UTILITY, None, "", "canteen, tea, water"),
    ("Server Room", C.UTILITY, None, "", "server, network room"),
    ("Staircase 1", C.STAIRS, None, "", "stairs 1, steps 1"),
    ("Staircase 2", C.STAIRS, None, "", "stairs 2, steps 2"),
    ("Staircase 3", C.STAIRS, None, "", "stairs 3, steps 3"),
    ("Goods Lift", C.LIFT, None, "Service lift for goods", "freight lift, service lift, elevator"),
    ("Passenger Lift", C.LIFT, 13, "Passenger lift (13 persons)", "lift, elevator"),
    ("Entry Steps", C.ENTRANCE, None, "Steps at the building entry", "entrance steps, front steps"),
    ("Open-to-Sky Courtyard", C.OPEN_AREA, None, "Open-to-sky courtyard", "courtyard, open area, garden"),
]

FLOOR_3 = [
    ("Classroom A (60 seats)", C.CLASSROOM, 60, "", "classroom, class"),
    ("Classroom B (60 seats)", C.CLASSROOM, 60, "", "classroom, class"),
    ("Computer Lab (Large)", C.LAB, None, "Computer lab, 9000 x 7215 mm", "computer lab, cs lab, lab"),
    ("Classroom C (30 seats)", C.CLASSROOM, 30, "", "classroom, class"),
    ("Classroom D (30 seats)", C.CLASSROOM, 30, "", "classroom, class"),
    ("Computer Lab (Bottom)", C.LAB, None, "", "computer lab, cs lab, lab"),
    ("Faculty Lounge", C.FACULTY, None, "", "staff room, teachers room, lounge"),
    ("Guest / Visiting Faculty Room", C.FACULTY, None, "", "guest room, visiting faculty"),
    ("Asst. Professor Room 1", C.FACULTY, None, "", "assistant professor, faculty cabin"),
    ("Asst. Professor Room 2", C.FACULTY, None, "", "assistant professor, faculty cabin"),
    ("Male Toilet", C.TOILET, None, "", "washroom, restroom, men, gents, boys toilet, bathroom"),
    ("Female Toilet", C.TOILET, None, "", "washroom, restroom, women, ladies, girls toilet, bathroom"),
    ("Pantry", C.UTILITY, None, "", "canteen, tea, water"),
    ("Server Room", C.UTILITY, None, "", "server, network room"),
    ("Staircase 1", C.STAIRS, None, "", "stairs 1, steps 1"),
    ("Staircase 2", C.STAIRS, None, "", "stairs 2, steps 2"),
    ("Staircase 3", C.STAIRS, None, "", "stairs 3, steps 3"),
    ("Goods Lift", C.LIFT, None, "Service lift for goods", "freight lift, service lift, elevator"),
    ("Passenger Lift", C.LIFT, None, "", "lift, elevator"),
]


class Command(BaseCommand):
    help = "Create floors 0 and 3 plus all SVSU rooms (unplaced)."

    def add_arguments(self, parser):
        parser.add_argument("--floor0-image")
        parser.add_argument("--floor3-image")

    def handle(self, *args, **opts):
        for number, name, rooms, img in (
            (0, "Ground Floor", FLOOR_0, opts["floor0_image"]),
            (3, "Third Floor", FLOOR_3, opts["floor3_image"]),
        ):
            floor, _ = Floor.objects.get_or_create(number=number, defaults={"name": name})
            if img:
                path = Path(img).expanduser()
                with path.open("rb") as fh:
                    floor.image.save(path.name, File(fh), save=True)  # also sets width/height
            for rname, cat, cap, desc, aliases in rooms:
                Room.objects.update_or_create(
                    floor=floor, name=rname,
                    defaults={"category": cat, "capacity": cap, "description": desc, "aliases": aliases},
                )
            self.stdout.write(self.style.SUCCESS(f"Floor {number}: {len(rooms)} rooms"))
