import json
import re
import random
import secrets
import sqlite3
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "single-court.sqlite3"
CLUBS = (
    "Almere",
    "Amersfoort",
    "Amsterdam Kauwgomballenkwartier",
    "Amsterdam Sloterdijk",
    "Amsterdam Zuidoost",
    "Apeldoorn De Maten",
    "Apeldoorn Malkenschoten",
    "Arnhem",
    "Assen Fokkerstraat",
    "Breda",
    "Den Bosch",
    "Den Haag Benoordenhout",
    "Deventer",
    "Eindhoven Beursgebouw",
    "Eindhoven High Tech Campus",
    "Eindhoven Vijfkamplaan",
    "Emmen",
    "Enschede",
    "Goes",
    "Groningen Atoomweg",
    "Groningen Euroborg",
    "Groningen Suikerterrein",
    "Haarlem Haarlemmerstroom",
    "Heemskerk Kerkweg",
    "Heerlen Noord",
    "Helmond",
    "Leeuwarden",
    "Maastricht",
    "Nijmegen Westerpark",
    "Oisterwijk Sportlaan",
    "Papendrecht Oostpolder",
    "Roosendaal",
    "Rotterdam",
    "Sittard Riekswaeg Zuid",
    "Tilburg",
    "Utrecht Vechtsebanen",
    "Utrecht Zeehaenkade",
    "Zutphen Noorderhaven",
    "Zwolle Spoorzone",
)
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
CREATE TABLE IF NOT EXISTS demo_profiles (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, age INTEGER NOT NULL,
    gender TEXT NOT NULL, preference TEXT NOT NULL,
    club TEXT NOT NULL REFERENCES clubs(name), mutual INTEGER NOT NULL
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


def demo_profiles():
    rng = random.Random(20270214)
    names = {
        "vrouw": "Sophie Noor Lina Sara Emma Julia Mila Tess Eva Zoë Nina Isa Anna Lynn Lotte Yara Fleur Lieke Evi Roos".split(),
        "man": "Sam Milan Daan Sem Noah Finn Luuk Liam Levi Mees Lars Bram Max Jesse Noud Lucas Adam Ruben Kai Julian".split(),
    }
    for group, (gender, first_names) in enumerate(names.items()):
        opposite = "man" if gender == "vrouw" else "vrouw"
        locations = list(CLUBS) * 2 + rng.sample(CLUBS, 100 - 2 * len(CLUBS))
        rng.shuffle(locations)
        seen = set()
        for index, club in enumerate(locations):
            first_at_club = club not in seen
            seen.add(club)
            preference = "iedereen" if first_at_club else rng.choice(
                (opposite, opposite, gender, "iedereen"))
            yield (group * 100 + index + 1, first_names[index % len(first_names)],
                   rng.randint(21, 57), gender, preference, club,
                   int(first_at_club or rng.random() < .4))

    for group, (gender, first_names) in enumerate(names.items()):
        opposite = "man" if gender == "vrouw" else "vrouw"
        locations = list(CLUBS) * (400 // len(CLUBS))
        locations += rng.sample(CLUBS, 400 % len(CLUBS))
        rng.shuffle(locations)
        seen = set()
        for index, club in enumerate(locations):
            first_at_club = club not in seen
            seen.add(club)
            yield (201 + group * 400 + index, rng.choice(first_names),
                   rng.randint(21, 57), gender,
                   "iedereen" if first_at_club else rng.choice((opposite, opposite, gender, "iedereen")),
                   club, int(rng.random() < .4))


def matching_profiles(db, player):
    return db.execute("""
        SELECT id, name, age, gender, club, mutual FROM demo_profiles
        WHERE club = ?
          AND (? = 'iedereen' OR gender = ?)
          AND (preference = 'iedereen' OR preference = ?)
        ORDER BY mutual DESC, abs(age - ?), id
    """, (player["club"], player["preference"], player["preference"],
          player["gender"], player["age"]))


def setup():
    with closing(connect()) as db, db:
        db.executescript(SCHEMA)
        db.executemany("INSERT OR IGNORE INTO clubs VALUES (?)", [(club,) for club in CLUBS])
        db.executemany("INSERT OR IGNORE INTO slots VALUES (?, ?)",
                       [(club, time) for club in CLUBS for time in SLOTS])
        db.executemany("INSERT OR IGNORE INTO demo_profiles VALUES (?, ?, ?, ?, ?, ?, ?)", demo_profiles())


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
    match_id = data.get("match")
    match = next((row for row in matching_profiles(db, player)
                  if row["id"] == match_id and row["mutual"]), None)
    if time not in SLOTS or type(match_id) is not int or match is None:
        raise ValueError("Kies een geldig voorbeeldtijdslot en een demomatch.")
    match = f"{match['name']} (#{match_id})"
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
        if self.path in ("/api/slots", "/api/profiles"):
            with closing(connect()) as db:
                player = self.player(db)
                if not player:
                    return self.reply(401, {"error": "Meld je eerst aan."})
                if self.path == "/api/profiles":
                    return self.reply(200, {"profiles": [dict(row) for row in matching_profiles(db, player)]})
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
