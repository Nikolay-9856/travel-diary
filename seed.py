"""Демо-данные: python seed.py (создаёт пользователей, записи и
иллюстрации-заглушки к ним). Пароль у демо-пользователей: secret1"""
import os
import random

from werkzeug.security import generate_password_hash

from app import app, get_db, init_db

TRIPS = [
    ("masha", "Неделя на Байкале", "Листвянка, Иркутская обл.", 51.8536, 104.8643, "2026-02-10", "2026-02-17",
     "Прозрачный лёд, нерпинарий и подъём на Камень Черского. Мороз до −25, но очень солнечно.", 85000, "RUB", (3, 5, 4, 5), (90, 140, 200)),
    ("masha", "Выходные в Казани", "Казань, Татарстан", 55.7963, 49.1088, "2026-05-01", "2026-05-03",
     "Кремль, улица Баумана, музей чак-чака. Много пешком, метро удобное.", 32000, "RUB", (5, 5, 2, 3), (200, 120, 80)),
    ("petya", "Горный Алтай на машине", "Чемал, Республика Алтай", 51.4117, 86.0047, "2025-08-03", "2025-08-14",
     "Чуйский тракт, Гейзерное озеро, Марсианские горы. Дороги местами грунтовые.", 140000, "RUB", (2, 4, 5, 5), (70, 150, 90)),
    ("petya", "Стамбул за 4 дня", "Стамбул, Турция", 41.0082, 28.9784, "2026-03-20", "2026-03-24",
     "Султанахмет, паром по Босфору, рынок в Кадыкёе. Очень людно, но атмосферно.", 1100, "USD", (4, 4, 1, 2), (180, 90, 150)),
]


def make_picture(path, color, seed):
    from PIL import Image, ImageDraw
    rnd = random.Random(seed)
    w, h = 800, 500
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):  # небо-градиент
        k = y / h
        d.line([(0, y), (w, y)], fill=(int(220 - 80 * k), int(230 - 60 * k), int(250 - 40 * k)))
    for layer in range(3):  # силуэты холмов
        base = 260 + layer * 70
        pts = [(0, h)]
        for x in range(0, w + 40, 40):
            pts.append((x, base - rnd.randint(0, 110 - layer * 30)))
        pts.append((w, h))
        shade = tuple(max(0, c - layer * 35) for c in color)
        d.polygon(pts, fill=shade)
    img.save(path, quality=85)


with app.app_context():
    init_db()
    db = get_db()
    for name, disp in [("masha", "Маша"), ("petya", "Петя")]:
        db.execute("INSERT INTO users(username, display_name, password_hash) VALUES (?,?,?)",
                   (name, disp, generate_password_hash("secret1")))
    ids = {r["username"]: r["id"] for r in db.execute("SELECT id, username FROM users")}
    for i, (u, title, place, lat, lon, d1, d2, text, cost, cur, r, color) in enumerate(TRIPS, 1):
        c = db.execute(
            """INSERT INTO trips(user_id,title,place,lat,lon,date_from,date_to,description,cost,currency,
               r_transport,r_safety,r_crowd,r_nature) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ids[u], title, place, lat, lon, d1, d2, text, cost, cur, *r))
        for k in range(2):
            fname = f"demo_{i}_{k}.jpg"
            make_picture(os.path.join(app.config["UPLOAD_DIR"], fname), color, i * 10 + k)
            db.execute("INSERT INTO photos(trip_id, filename, caption) VALUES (?,?,?)",
                       (c.lastrowid, fname, "иллюстрация"))
    db.commit()
    print("Демо-данные загружены")
