"""API regressions using disposable databases and uploads."""
import io
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from server import create_app


class ChoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent, prefix=".tmp-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = create_app({
            "TESTING": True,
            "DATABASE": str(self.root / "test.db"),
            "UPLOAD_FOLDER": str(self.root / "uploads"),
        })
        self.client = self.app.test_client()

    def create(self, **files):
        return self.client.post("/api/chores", data={
            "chore": " Wash dishes ", "target": " roommate@example.com ", **files,
        })

    def test_create_and_read_with_uploads(self):
        response = self.create(
            evidence=(io.BytesIO(b"photo"), "evidence.PNG"),
            payload=(io.BytesIO(b"audio"), "sound.mp3", "application/octet-stream"),
            walker=(io.BytesIO(b"mascot"), "walker.png"),
        )
        self.assertEqual(response.status_code, 201)
        chore = self.client.get("/api/chores/" + response.json["id"]).json
        self.assertEqual(chore["chore"], "Wash dishes")
        self.assertEqual(chore["target"], "roommate@example.com")
        self.assertEqual(chore["status"], "pending")
        self.assertEqual(chore["ptype"], "audio/mpeg")
        with self.client.get(chore["evidence"]) as media:
            self.assertEqual(media.data, b"photo")
        with self.client.get(chore["walker"]) as media:
            self.assertEqual(media.data, b"mascot")
        self.assertEqual(self.client.get("/api/chores").json, [chore])

    def test_required_fields(self):
        for data in ({}, {"chore": "  ", "target": "someone"}, {"chore": "dishes"}):
            with self.subTest(data=data):
                response = self.client.post("/api/chores", data=data)
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.json)

    def test_roulette_deadline_is_saved_for_each_difficulty(self):
        for difficulty, minutes in (("easy", 5), ("medium", 10), ("boss", 15)):
            with self.subTest(difficulty=difficulty), patch("server.time.time", return_value=1000):
                response = self.create(challenge=difficulty)
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json["deadline"], 1000 + minutes * 60)
                saved = self.client.get("/api/chores/" + response.json["id"]).json
                self.assertEqual(saved["deadline"], response.json["deadline"])
                self.assertEqual(saved["challenge"], difficulty)
                self.assertEqual(saved["created"], 1000)

    def test_invalid_roulette_difficulty_is_rejected_before_saving_files(self):
        response = self.create(challenge="impossible", evidence=(io.BytesIO(b"photo"), "photo.png"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/api/chores").json, [])
        self.assertEqual(list((self.root / "uploads").iterdir()), [])

    def test_regular_chores_have_no_deadline(self):
        response = self.create()
        self.assertIsNone(response.json["deadline"])
        self.assertIsNone(response.json["challenge"])

    def test_invalid_uploads_leave_no_chores_or_files(self):
        for field, filename, content in (
            ("payload", "script.html", b"html"),
            ("evidence", "sound.mp3", b"audio"),
            ("walker", "walker.gif", b"gif"),
            ("payload", "empty.png", b""),
        ):
            with self.subTest(field=field, filename=filename):
                response = self.create(**{
                    "evidence": (io.BytesIO(b"photo"), "valid.png"),
                    field: (io.BytesIO(content), filename),
                })
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.json)
                self.assertEqual(list((self.root / "uploads").iterdir()), [])
                self.assertEqual(self.client.get("/api/chores").json, [])

    def test_resolution_requires_photo_and_preserves_first_submission(self):
        path = "/api/chores/" + self.create().json["id"]
        for data in ({}, {"age": (io.BytesIO(b"audio"), "age.mp3")}):
            response = self.client.post(path + "/resolve", data=data)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(self.client.get(path).json["status"], "pending")
        response = self.client.post(path + "/resolve", data={
            "age": (io.BytesIO(b"face"), "face.jpg"),
        })
        self.assertEqual(response.status_code, 200)
        saved = self.client.get(path).json
        self.assertEqual(saved["status"], "resolved")
        self.assertIsNotNone(saved["resolved"])
        with self.client.get(saved["age_photo"]) as media:
            self.assertEqual(media.data, b"face")
        response = self.client.post(path + "/resolve", data={
            "age": (io.BytesIO(b"replacement"), "face.jpg"),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(path).json, saved)
        self.assertEqual(len(list((self.root / "uploads").iterdir())), 1)

    def test_failed_database_write_cleans_upload(self):
        with patch("server.db", side_effect=sqlite3.OperationalError("unavailable")):
            with self.assertRaises(sqlite3.OperationalError):
                self.create(evidence=(io.BytesIO(b"photo"), "photo.png"))
        self.assertEqual(list((self.root / "uploads").iterdir()), [])

    def test_api_errors_are_json(self):
        for method, path in (
            ("get", "/api/chores/missing"),
            ("post", "/api/chores/missing/resolve"),
            ("get", "/api/missing"),
        ):
            response = getattr(self.client, method)(path)
            self.assertEqual(response.status_code, 404)
            self.assertIn("error", response.json)
        self.app.config["MAX_CONTENT_LENGTH"] = 100
        response = self.create(payload=(io.BytesIO(b"x" * 200), "large.mp3"))
        self.assertEqual(response.status_code, 413)
        self.assertIn("error", response.json)

    def test_upload_path_cannot_escape_upload_directory(self):
        self.assertEqual(self.client.get("/uploads/../test.db").status_code, 404)

    def test_existing_database_migrates_without_losing_chores(self):
        legacy = self.root / "legacy.db"
        with closing(sqlite3.connect(legacy)) as connection, connection:
            connection.execute("""CREATE TABLE chores (
                id TEXT PRIMARY KEY, chore TEXT, target TEXT, evidence TEXT,
                payload TEXT, ptype TEXT, status TEXT DEFAULT 'pending',
                age_photo TEXT, created REAL, resolved REAL)""")
            connection.execute("INSERT INTO chores(id,chore,target) VALUES('old','Dishes','Roommate')")
        app = create_app({"TESTING": True, "DATABASE": str(legacy),
                          "UPLOAD_FOLDER": str(self.root / "uploads")})
        response = app.test_client().get("/api/chores/old")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["chore"], "Dishes")
        self.assertIsNone(response.json["walker"])
        self.assertIsNone(response.json["deadline"])
        self.assertIsNone(response.json["challenge"])

    def test_pages_load(self):
        for path in ("/", "/dashboard", "/static/tung.js", "/leaderboard", "/static/leaderboard.js"):
            with self.client.get(path) as response:
                self.assertEqual(response.status_code, 200)

    def test_leaderboard_empty(self):
        response = self.client.get("/api/leaderboard")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["roommates"], [])
        self.assertEqual(response.json["totals"], {"roommates": 0, "completed": 0, "pending": 0})

    def test_leaderboard_scores_grouping_times_and_tiebreaks(self):
        rows = [
            ("1", " Alice@example.com ", "resolved", 100, 160, 170),
            ("2", "alice@EXAMPLE.com", "resolved", 200, 320, 300),
            ("3", "ALICE@example.com", "pending", 300, None, 350),
            ("4", "Bob", "resolved", 100, 200, None),
            ("5", "Bob", "resolved", 100, 300, None),
            ("6", "Zoe", "resolved", 100, 100, None),
            ("7", "Charlie", "resolved", 100, 150, None),
            ("8", "Dana", "pending", 100, None, None),
            ("9", " ", "pending", 100, None, None),
        ]
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as connection, connection:
            connection.executemany("INSERT INTO chores(id,target,status,created,resolved,deadline) VALUES(?,?,?,?,?,?)", rows)
        with patch("server.time.time", return_value=400):
            result = self.client.get("/api/leaderboard").json
        self.assertEqual(result["totals"], {"roommates": 5, "completed": 6, "pending": 2})
        self.assertEqual([member["target"] for member in result["roommates"]],
                         ["Alice@example.com", "Bob", "Zoe", "Charlie", "Dana"])
        alice = result["roommates"][0]
        self.assertEqual(alice["rank"], 1)
        self.assertEqual(alice["points"], 25)
        self.assertEqual(alice["completed"], 2)
        self.assertEqual(alice["on_time"], 1)
        self.assertEqual(alice["pending"], 1)
        self.assertEqual(alice["overdue"], 1)
        self.assertEqual(alice["fastest_seconds"], 60)
        self.assertEqual(alice["average_seconds"], 90)
        self.assertEqual(result["roommates"][2]["fastest_seconds"], 0)
        self.assertIsNone(result["roommates"][-1]["average_seconds"])

    def test_leaderboard_updates_on_resolution_without_duplicate_credit(self):
        with patch("server.time.time", return_value=1000):
            cid = self.create(challenge="easy").json["id"]
        before = self.client.get("/api/leaderboard").json["roommates"][0]
        self.assertEqual(before["points"], 0)
        self.assertEqual(before["pending"], 1)
        with patch("server.time.time", return_value=1100):
            self.client.post(f"/api/chores/{cid}/resolve", data={"age": (io.BytesIO(b"face"), "face.png")})
        self.client.post(f"/api/chores/{cid}/resolve")
        after = self.client.get("/api/leaderboard").json["roommates"][0]
        self.assertEqual(after["points"], 15)
        self.assertEqual(after["completed"], 1)
        self.assertEqual(after["pending"], 0)
        self.assertEqual(after["average_seconds"], 100)

    def test_leaderboard_legacy_missing_times_do_not_invent_speed_records(self):
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as connection, connection:
            connection.execute("INSERT INTO chores(id,target,status) VALUES('old','Legacy','resolved')")
        member = self.client.get("/api/leaderboard").json["roommates"][0]
        self.assertEqual(member["points"], 10)
        self.assertIsNone(member["fastest_seconds"])
        self.assertIsNone(member["average_seconds"])


if __name__ == "__main__":
    unittest.main()
