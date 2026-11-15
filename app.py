"""«Дневник путешествий»: записи о поездках с геопозицией на карте,
фотографиями мест, стоимостью и оценками (передвижение, безопасность,
населённость, растительность).

Запуск:  python app.py      (http://127.0.0.1:5002)
"""
import os
import sqlite3
import uuid
from functools import wraps

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("TRAVEL_SECRET", "dev-only-change-me"),
    SESSION_COOKIE_NAME="travel_session",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    DATABASE=os.environ.get("TRAVEL_DB", os.path.join(BASE_DIR, "travel.sqlite3")),
    UPLOAD_DIR=os.path.join(BASE_DIR, "uploads"),
    MAX_CONTENT_LENGTH=15 * 1024 * 1024,      # не больше 15 МБ на запрос
)
ALLOWED_EXT = {"jpg", "jpeg", "png", "webp", "gif"}
MAX_PHOTOS = 8
RATINGS = {
    "r_transport": "Удобство передвижения",
    "r_safety": "Безопасность",
    "r_crowd": "Населённость (5 — малолюдно)",
    "r_nature": "Растительность",
}
CURRENCIES = ["RUB", "USD", "EUR", "CNY", "TRY", "KZT"]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with open(os.path.join(BASE_DIR, "schema.sql"), encoding="utf-8") as f:
        get_db().executescript(f.read())
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)


@app.before_request
def load_user():
    uid = session.get("uid")
    g.user = get_db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone() if uid else None


def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if g.user is None:
            return redirect(url_for("login", next=request.path))
        return view(*a, **kw)
    return wrapped


@app.context_processor
def ctx():
    return dict(RATINGS=RATINGS, CURRENCIES=CURRENCIES)


# ------------------------------------------------------------- пользователи
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("username", "").strip()
        display = request.form.get("display_name", "").strip() or name
        pwd = request.form.get("password", "")
        if len(name) < 3 or len(pwd) < 6:
            flash("Логин — от 3 символов, пароль — от 6")
        else:
            try:
                get_db().execute(
                    "INSERT INTO users(username, display_name, password_hash) VALUES (?,?,?)",
                    (name, display[:60], generate_password_hash(pwd)),
                )
                get_db().commit()
                flash("Готово! Теперь войдите")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Логин занят")
    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = get_db().execute("SELECT * FROM users WHERE username=?",
                             (request.form.get("username", "").strip(),)).fetchone()
        if u and check_password_hash(u["password_hash"], request.form.get("password", "")):
            session.clear()
            session["uid"] = u["id"]
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") else url_for("my_trips"))
        flash("Неверный логин или пароль")
    return render_template("auth.html", mode="login")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("explore"))


# ------------------------------------------------------------------ записи
def trip_rows(where="t.is_public = 1", params=(), order="t.created_at DESC"):
    rows = get_db().execute(
        f"""SELECT t.*, u.display_name, u.username,
                   (SELECT filename FROM photos p WHERE p.trip_id=t.id ORDER BY p.id LIMIT 1) AS cover,
                   ROUND((COALESCE(r_transport,0)+COALESCE(r_safety,0)+COALESCE(r_crowd,0)+COALESCE(r_nature,0))
                     / NULLIF((r_transport IS NOT NULL)+(r_safety IS NOT NULL)+(r_crowd IS NOT NULL)+(r_nature IS NOT NULL),0), 1) AS avg_rating
            FROM trips t JOIN users u ON u.id = t.user_id
            WHERE {where} ORDER BY {order}""",
        params,
    ).fetchall()
    return rows


ORDERS = {
    "new": "t.created_at DESC",
    "date": "t.date_from DESC",
    "cheap": "t.cost IS NULL, t.cost ASC",
    "rating": "avg_rating IS NULL, avg_rating DESC",
}


@app.route("/")
def explore():
    """Путешествия других пользователей (только публичные записи)."""
    sort = request.args.get("sort", "new")
    q = request.args.get("q", "").strip()
    where, params = "t.is_public = 1", []
    if q:
        where += " AND (t.place LIKE ? OR t.title LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if g.user and request.args.get("others") == "1":
        where += " AND t.user_id <> ?"
        params.append(g.user["id"])
    trips = trip_rows(where, params, ORDERS.get(sort, ORDERS["new"]))
    return render_template("list.html", trips=trips, sort=sort, q=q, title="Путешествия сообщества", mine=False)


@app.route("/my")
@login_required
def my_trips():
    trips = trip_rows("t.user_id = ?", (g.user["id"],), "t.date_from DESC")
    return render_template("list.html", trips=trips, sort="date", q="", title="Мои путешествия", mine=True)


@app.route("/api/trips")
def api_trips():
    """Точки для карты: публичные записи (и свои, если пользователь вошёл)."""
    where, params = "t.lat IS NOT NULL AND (t.is_public = 1", []
    if g.user:
        where += " OR t.user_id = ?"
        params.append(g.user["id"])
    where += ")"
    data = [
        {"id": r["id"], "title": r["title"], "place": r["place"], "lat": r["lat"], "lon": r["lon"],
         "author": r["display_name"], "url": url_for("trip", trip_id=r["id"])}
        for r in trip_rows(where, params)
    ]
    return jsonify(data)


def load_trip(trip_id, owner_only=False):
    t = get_db().execute(
        "SELECT t.*, u.display_name, u.username FROM trips t JOIN users u ON u.id=t.user_id WHERE t.id=?",
        (trip_id,),
    ).fetchone()
    if t is None:
        abort(404)
    is_owner = g.user is not None and g.user["id"] == t["user_id"]
    if owner_only and not is_owner:
        abort(403)
    if not t["is_public"] and not is_owner:
        abort(404)
    return t


@app.route("/trip/<int:trip_id>")
def trip(trip_id):
    t = load_trip(trip_id)
    photos = get_db().execute("SELECT * FROM photos WHERE trip_id=? ORDER BY id", (trip_id,)).fetchall()
    return render_template("trip.html", t=t, photos=photos)


def parse_form():
    f = request.form
    errors = []
    data = {
        "title": f.get("title", "").strip()[:150],
        "place": f.get("place", "").strip()[:150],
        "description": f.get("description", "").strip(),
        "date_from": f.get("date_from") or None,
        "date_to": f.get("date_to") or None,
        "is_public": 1 if f.get("is_public") else 0,
        "currency": f.get("currency", "RUB") if f.get("currency") in CURRENCIES else "RUB",
    }
    if not data["title"] or not data["place"]:
        errors.append("Укажите название и место")
    if data["date_from"] and data["date_to"] and data["date_to"] < data["date_from"]:
        errors.append("Дата окончания раньше даты начала")
    for key in ("lat", "lon", "cost"):
        raw = f.get(key, "").replace(",", ".").strip()
        try:
            data[key] = float(raw) if raw else None
        except ValueError:
            data[key] = None
            errors.append(f"Поле «{key}» должно быть числом")
    if data["lat"] is not None and not -90 <= data["lat"] <= 90:
        errors.append("Широта должна быть от −90 до 90")
    if data["lon"] is not None and not -180 <= data["lon"] <= 180:
        errors.append("Долгота должна быть от −180 до 180")
    if (data["lat"] is None) != (data["lon"] is None):
        errors.append("Координаты задаются парой: широта и долгота")
    if data["cost"] is not None and data["cost"] < 0:
        errors.append("Стоимость не может быть отрицательной")
    for key in RATINGS:
        v = f.get(key, type=int)
        data[key] = v if v in (1, 2, 3, 4, 5) else None
    return data, errors


def save_photos(trip_id):
    db = get_db()
    have = db.execute("SELECT COUNT(*) FROM photos WHERE trip_id=?", (trip_id,)).fetchone()[0]
    saved = 0
    for file in request.files.getlist("photos"):
        if not file or not file.filename:
            continue
        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in ALLOWED_EXT:
            flash(f"Файл {file.filename} пропущен: допустимы {', '.join(sorted(ALLOWED_EXT))}")
            continue
        if have + saved >= MAX_PHOTOS:
            flash(f"Можно прикрепить не более {MAX_PHOTOS} фото")
            break
        name = f"{uuid.uuid4().hex}.{ext}"      # своё имя файла — защита от подмены путей
        file.save(os.path.join(app.config["UPLOAD_DIR"], name))
        db.execute("INSERT INTO photos(trip_id, filename, caption) VALUES (?,?,?)",
                   (trip_id, name, request.form.get("caption", "")[:120]))
        saved += 1


@app.route("/trip/new", methods=["GET", "POST"])
@app.route("/trip/<int:trip_id>/edit", methods=["GET", "POST"])
@login_required
def edit_trip(trip_id=None):
    t = load_trip(trip_id, owner_only=True) if trip_id else None
    if request.method == "POST":
        data, errors = parse_form()
        if errors:
            for e in errors:
                flash(e)
            return render_template("edit.html", t=data | {"id": trip_id}, photos=[])
        db = get_db()
        cols = list(data)
        if t:
            db.execute(f"UPDATE trips SET {', '.join(c + '=?' for c in cols)} WHERE id=?",
                       [data[c] for c in cols] + [trip_id])
        else:
            cur = db.execute(
                f"INSERT INTO trips(user_id, {', '.join(cols)}) VALUES (?, {', '.join('?' * len(cols))})",
                [g.user["id"]] + [data[c] for c in cols],
            )
            trip_id = cur.lastrowid
        save_photos(trip_id)
        db.commit()
        return redirect(url_for("trip", trip_id=trip_id))
    photos = get_db().execute("SELECT * FROM photos WHERE trip_id=?", (trip_id,)).fetchall() if t else []
    return render_template("edit.html", t=t, photos=photos)


@app.route("/trip/<int:trip_id>/delete", methods=["POST"])
@login_required
def delete_trip(trip_id):
    load_trip(trip_id, owner_only=True)
    db = get_db()
    for p in db.execute("SELECT filename FROM photos WHERE trip_id=?", (trip_id,)).fetchall():
        try:
            os.remove(os.path.join(app.config["UPLOAD_DIR"], p["filename"]))
        except FileNotFoundError:
            pass
    db.execute("DELETE FROM trips WHERE id=?", (trip_id,))
    db.commit()
    flash("Запись удалена")
    return redirect(url_for("my_trips"))


@app.route("/photo/<int:photo_id>/delete", methods=["POST"])
@login_required
def delete_photo(photo_id):
    db = get_db()
    p = db.execute("SELECT p.*, t.user_id FROM photos p JOIN trips t ON t.id=p.trip_id WHERE p.id=?",
                   (photo_id,)).fetchone()
    if p is None or p["user_id"] != g.user["id"]:
        abort(403)
    try:
        os.remove(os.path.join(app.config["UPLOAD_DIR"], p["filename"]))
    except FileNotFoundError:
        pass
    db.execute("DELETE FROM photos WHERE id=?", (photo_id,))
    db.commit()
    return redirect(url_for("edit_trip", trip_id=p["trip_id"]))


@app.route("/uploads/<path:name>")
def uploaded(name):
    return send_from_directory(app.config["UPLOAD_DIR"], name)


@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(413)
def http_error(err):
    return render_template("error.html", err=err), err.code


if __name__ == "__main__":
    with app.app_context():
        if not os.path.exists(app.config["DATABASE"]):
            init_db()
    app.run(port=5002)
