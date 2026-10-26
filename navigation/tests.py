from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .models import Floor, Node, Room, SearchLog


class ApiTests(APITestCase):
    def setUp(self):
        self.f0 = Floor.objects.create(number=0, name="Ground")
        self.f3 = Floor.objects.create(number=3, name="Third")
        self.a = Node.objects.create(floor=self.f0, x=0, y=0, type="corridor")
        self.b = Node.objects.create(floor=self.f0, x=30, y=40, type="corridor")
        self.c = Node.objects.create(floor=self.f3, x=5, y=5, type="corridor")
        self.staff = get_user_model().objects.create_user("staff", password="x", is_staff=True)

    def test_public_read_but_no_public_write(self):
        self.assertEqual(self.client.get("/api/floors/").status_code, 200)
        r = self.client.post("/api/nodes/", {"floor": self.f0.id, "x": 1, "y": 1}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_staff_edge_distance_auto_and_canonical_order(self):
        self.client.force_login(self.staff)
        r = self.client.post("/api/edges/", {"node_a": self.b.id, "node_b": self.a.id}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["distance"], 50.0)  # 3-4-5 triangle
        dup = self.client.post("/api/edges/", {"node_a": self.a.id, "node_b": self.b.id}, format="json")
        self.assertEqual(dup.status_code, 400)

    def test_edge_rejects_cross_floor_and_self_loop(self):
        self.client.force_login(self.staff)
        r = self.client.post("/api/edges/", {"node_a": self.a.id, "node_b": self.c.id}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/api/edges/", {"node_a": self.a.id, "node_b": self.a.id}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_moving_node_updates_edge_distance(self):
        self.client.force_login(self.staff)
        e = self.client.post("/api/edges/", {"node_a": self.a.id, "node_b": self.b.id}, format="json").data
        self.client.patch(f"/api/nodes/{self.b.id}/", {"x": 6, "y": 8}, format="json")
        self.assertEqual(self.client.get(f"/api/edges/{e['id']}/").data["distance"], 10.0)

    def test_connector_key_only_on_stairs_or_lift(self):
        self.client.force_login(self.staff)
        r = self.client.post("/api/nodes/", {"floor": self.f0.id, "x": 1, "y": 1, "type": "corridor",
                                             "connector_key": "staircase-1"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/api/nodes/", {"floor": self.f0.id, "x": 1, "y": 1, "type": "stairs",
                                             "connector_key": "staircase-1"}, format="json")
        self.assertEqual(r.status_code, 201)

    def test_search_ranking_aliases_and_logging(self):
        Room.objects.create(floor=self.f0, name="H.O.D. Cabin", category="office", aliases="hod, head of department")
        Room.objects.create(floor=self.f0, name="Male Toilet", category="toilet", aliases="washroom")
        Room.objects.create(floor=self.f3, name="Female Toilet", category="toilet", aliases="washroom")
        r = self.client.get("/api/rooms/search/?q=hod")
        self.assertEqual(r.data[0]["name"], "H.O.D. Cabin")
        r = self.client.get("/api/rooms/search/?q=washroom&log=1")
        self.assertEqual(len(r.data), 2)
        self.assertEqual(SearchLog.objects.count(), 1)
        self.assertEqual(self.client.get("/api/rooms/search/?q=").data, [])

    def test_room_node_must_be_on_same_floor(self):
        self.client.force_login(self.staff)
        r = self.client.post("/api/rooms/", {"name": "X", "floor": self.f0.id, "node": self.c.id}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_locate_by_qr_and_floor_graph(self):
        r = self.client.get(f"/api/locate/{self.a.qr_code}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["floor"]["number"], 0)
        g = self.client.get("/api/floors/0/graph/")
        self.assertEqual(len(g.data["nodes"]), 2)


class EditorTests(APITestCase):
    def test_editor_requires_staff_and_sets_csrf_cookie(self):
        r = self.client.get("/editor/")
        self.assertEqual(r.status_code, 302)  # -> admin login
        get_user_model().objects.create_user("s", password="x", is_staff=True)
        self.client.login(username="s", password="x")
        r = self.client.get("/editor/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("csrftoken", r.cookies)
        self.assertContains(r, "L.CRS.Simple")

    def test_editor_workflow_via_api(self):
        """Mirror what the editor does: place nodes, draw a path, attach a room."""
        u = get_user_model().objects.create_user("s", password="x", is_staff=True)
        self.client.force_login(u)
        f = Floor.objects.create(number=0, name="G")
        room = Room.objects.create(floor=f, name="Staircase 1", category="stairs")
        a = self.client.post("/api/nodes/", {"floor": f.id, "x": 10, "y": 10, "type": "corridor"}, format="json").data
        b = self.client.post("/api/nodes/", {"floor": f.id, "x": 10, "y": 60, "type": "corridor"}, format="json").data
        e = self.client.post("/api/edges/", {"node_a": b["id"], "node_b": a["id"], "accessible": True}, format="json")
        self.assertEqual(e.status_code, 201)
        self.assertEqual(e.data["distance"], 50.0)
        r = self.client.patch(f"/api/rooms/{room.id}/", {"node": b["id"]}, format="json")
        self.assertEqual(r.status_code, 200)
        r = self.client.patch(f"/api/nodes/{b['id']}/", {"type": "stairs", "connector_key": "staircase-1"}, format="json")
        self.assertEqual(r.status_code, 200)
        r = self.client.patch(f"/api/rooms/{room.id}/", {"node": None}, format="json")
        self.assertEqual(r.status_code, 200)
        g = self.client.get("/api/floors/0/graph/").data
        self.assertEqual((len(g["nodes"]), len(g["edges"])), (2, 1))
        # deleting a node removes its edges and leaves rooms unplaced
        self.client.patch(f"/api/rooms/{room.id}/", {"node": b["id"]}, format="json")
        self.assertEqual(self.client.delete(f"/api/nodes/{b['id']}/").status_code, 204)
        g = self.client.get("/api/floors/0/graph/").data
        self.assertEqual(len(g["edges"]), 0)
        self.assertFalse([x for x in g["rooms"] if x["node"]])


class AppAndMapTests(APITestCase):
    PAYLOAD = {"floors": [{"n": 0, "name": "G"}], "nodes": [], "edges": [], "rooms": []}

    def staff(self):
        u = get_user_model().objects.create_user("s", password="x", is_staff=True)
        self.client.force_login(u)

    def test_pages_and_pwa_files(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "manifest.webmanifest")
        self.assertIn("csrftoken", r.cookies)
        self.assertEqual(self.client.get("/manifest.webmanifest").json()["display"], "standalone")
        sw = self.client.get("/sw.js")
        self.assertEqual(sw["Content-Type"], "application/javascript")
        self.assertEqual(self.client.get("/static/pwa/icon-192.png").status_code, 200)
        self.assertEqual(self.client.get("/static/vendor/qrcode.js").status_code, 200)

    def test_me_endpoint(self):
        self.assertFalse(self.client.get("/api/me/").json()["staff"])
        self.staff()
        self.assertTrue(self.client.get("/api/me/").json()["staff"])

    def test_map_empty_then_staff_save_then_public_read(self):
        self.assertEqual(self.client.get("/api/map/").json(), {"version": 0, "data": None})
        self.assertEqual(self.client.put("/api/map/", {"data": self.PAYLOAD, "base_version": 0}, format="json").status_code, 403)
        self.staff()
        r = self.client.put("/api/map/", {"data": self.PAYLOAD, "base_version": 0}, format="json")
        self.assertEqual((r.status_code, r.json()["version"]), (200, 1))
        self.client.logout()
        g = self.client.get("/api/map/").json()
        self.assertEqual((g["version"], g["data"]["floors"][0]["name"]), (1, "G"))
        self.assertEqual(self.client.get("/api/map/?since=1").json(), {"version": 1, "unchanged": True})

    def test_map_conflict_and_validation(self):
        self.staff()
        self.client.put("/api/map/", {"data": self.PAYLOAD, "base_version": 0}, format="json")
        stale = self.client.put("/api/map/", {"data": self.PAYLOAD, "base_version": 0}, format="json")
        self.assertEqual(stale.status_code, 409)
        ok = self.client.put("/api/map/", {"data": self.PAYLOAD, "base_version": 1}, format="json")
        self.assertEqual(ok.json()["version"], 2)
        bad = self.client.put("/api/map/", {"data": {"floors": []}, "base_version": 2}, format="json")
        self.assertEqual(bad.status_code, 400)
