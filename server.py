import json
import re
import secrets
import sqlite3
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "single-court.sqlite3"
CLUBS = ("Amsterdam Zuidoost", "Amersfoort", "Nijmegen Westerpark")
SLOTS = tuple(f"{hour:02}:00" for hour in range(10, 20))

SCHEMA = """
CREATE TABLE IF NOT EXISTS clubs (name TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS slots (
    club TEXT REFERENCES clubs(name), time TEXT,
    PRIMARY KEY (club, time)
);
CREATE TABLE IF NOT EXISTS registrations (
    id INTEGER PRIMARY KEY, token TEXT UNIQUE NOT NULL, email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL, age INTEGER NOT NULL CHECK(age >= 18),
    gender TEXT NOT NULL, preference TEXT NOT NULL,
    club TEXT NOT NULL REFERENCES clubs(name)
);
CREATE TABLE IF NOT EXISTS claims (
    registration_id INTEGER PRIMARY KEY REFERENCES registrations(id),
    club TEXT NOT NULL, time TEXT NOT NULL, match_name TEXT NOT NULL,
    UNIQUE (club, time), FOREIGN KEY (club, time) REFERENCES slots(club, time)
);
"""


def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def setup():
    with closing(connect()) as db, db:
        db.executescript(SCHEMA)
        db.executemany("INSERT OR IGNORE INTO clubs VALUES (?)", [(club,) for club in CLUBS])
        db.executemany("INSERT OR IGNORE INTO slots VALUES (?, ?)",
                       [(club, time) for club in CLUBS for time in SLOTS])


def register(db, data):
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    age = data.get("age")
    gender = data.get("gender")
    preference = data.get("preference")
    club = data.get("club")
    if (not 1 <= len(name) <= 60 or len(email) > 254
            or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)
            or type(age) is not int or not 18 <= age <= 120
            or gender not in ("vrouw", "man", "anders")
            or preference not in ("vrouw", "man", "iedereen")
            or club not in CLUBS or data.get("visible") is not True):
        raise ValueError("Controleer je gegevens en bevestig je demoaanmelding.")
    token = secrets.token_urlsafe(32)
    db.execute("""INSERT INTO registrations (token,email,name,age,gender,preference,club)
                  VALUES (?,?,?,?,?,?,?)""", (token, email, name, age, gender, preference, club))
    return {"token": token}


def claim(db, player, data):
    time = data.get("time")
    match = data.get("match")
    allowed = {"vrouw": ("Sophie", "Lina"), "man": ("Sam", "Milan"),
               "iedereen": ("Sophie", "Lina", "Sam", "Milan")}
    if time not in SLOTS or match not in allowed[player["preference"]]:
        raise ValueError("Kies een geldig voorbeeldtijdslot en een demomatch.")
    db.execute("BEGIN IMMEDIATE")
    existing = db.execute("SELECT time,match_name FROM claims WHERE registration_id = ?",
                          (player["id"],)).fetchone()
    if existing:
        if (existing["time"], existing["match_name"]) == (time, match):
            return {"time": time}
        raise sqlite3.IntegrityError("Je hebt al een tijdslot geclaimd.")
    db.execute("INSERT INTO claims VALUES (?, ?, ?, ?)", (player["id"], player["club"], time, match))
    return {"time": time}


class Handler(BaseHTTPRequestHandler):
    def reply(self, code, body, mime="application/json; charset=utf-8"):
        raw = json.dumps(body).encode() if isinstance(body, dict) else body
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def player(self, db):
        token = self.headers.get("Authorization", "").removeprefix("Bearer ")
        return db.execute("SELECT * FROM registrations WHERE token = ?", (token,)).fetchone()

    def do_GET(self):
        if self.path == "/":
            return self.reply(200, (ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
        if self.path == "/api/clubs":
            return self.reply(200, {"clubs": CLUBS})
        if self.path == "/api/slots":
            with closing(connect()) as db:
                player = self.player(db)
                if not player:
                    return self.reply(401, {"error": "Meld je eerst aan."})
                rows = db.execute("""SELECT time FROM slots
                    WHERE club = ? AND NOT EXISTS (
                        SELECT 1 FROM claims WHERE claims.club = slots.club AND claims.time = slots.time
                    ) ORDER BY time""", (player["club"],))
                return self.reply(200, {"slots": [row["time"] for row in rows]})
        self.reply(404, {"error": "Pagina niet gevonden."})

    def do_POST(self):
        if self.path not in ("/api/register", "/api/claim"):
            return self.reply(404, {"error": "Pagina niet gevonden."})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 4096:
                raise ValueError("Ongeldige aanvraag.")
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError("Ongeldige aanvraag.")
            with closing(connect()) as db, db:
                if self.path == "/api/register":
                    result = register(db, data)
                else:
                    player = self.player(db)
                    if not player:
                        return self.reply(401, {"error": "Meld je eerst aan."})
                    result = claim(db, player, data)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self.reply(400, {"error": "Ongeldige aanvraag."})
        except ValueError as error:
            return self.reply(400, {"error": str(error)})
        except sqlite3.IntegrityError:
            message = ("Dit testadres is al aangemeld." if self.path == "/api/register"
                       else "Dit tijdslot is bezet of je hebt al een plek geclaimd.")
            return self.reply(409, {"error": message})
        self.reply(201, result)


if __name__ == "__main__":
    setup()
    print("Open http://127.0.0.1:8000 in je browser.", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
