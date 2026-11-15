DROP TABLE IF EXISTS photos;
DROP TABLE IF EXISTS trips;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE trips (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    place       TEXT NOT NULL,
    lat         REAL CHECK (lat BETWEEN -90 AND 90),
    lon         REAL CHECK (lon BETWEEN -180 AND 180),
    date_from   TEXT,
    date_to     TEXT,
    description TEXT DEFAULT '',
    cost        REAL CHECK (cost >= 0),
    currency    TEXT DEFAULT 'RUB',
    r_transport INTEGER CHECK (r_transport BETWEEN 1 AND 5),
    r_safety    INTEGER CHECK (r_safety    BETWEEN 1 AND 5),
    r_crowd     INTEGER CHECK (r_crowd     BETWEEN 1 AND 5),
    r_nature    INTEGER CHECK (r_nature    BETWEEN 1 AND 5),
    is_public   INTEGER NOT NULL DEFAULT 1,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE photos (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id  INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    caption  TEXT DEFAULT ''
);

CREATE INDEX idx_trips_user ON trips(user_id);
CREATE INDEX idx_trips_public ON trips(is_public, created_at);
