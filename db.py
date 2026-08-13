"""Neon (Postgres) を使った永続化レイヤー。

Vercel のサーバーレス環境ではリクエストごとにプロセスが異なるため、
ルーム・予約をプロセス内の dict で持つことができない。
接続は Neon のプール済みエンドポイントを前提に、リクエストごとに張る。
"""

import os
import random
import string

import psycopg
from psycopg.rows import dict_row

# 期限切れデータの保持時間
RESERVATION_TTL = "30 minutes"
ROOM_TTL = "6 hours"

_schema_ready = False


def _dsn():
    """Neon/Vercel が注入する接続文字列を拾う"""
    for key in ('DATABASE_URL', 'POSTGRES_URL', 'NEON_DATABASE_URL', 'POSTGRES_PRISMA_URL'):
        value = os.environ.get(key)
        if value:
            return value
    raise RuntimeError('DATABASE_URL is not set (Neon integration required)')


def connect():
    conn = psycopg.connect(_dsn(), autocommit=True, row_factory=dict_row)
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn):
    global _schema_ready
    if _schema_ready:
        return
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rooms (
                id                 TEXT PRIMARY KEY,
                url                TEXT,
                reservation_number TEXT,
                created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                number     TEXT PRIMARY KEY,
                url        TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
    _schema_ready = True


def _purge_expired(cur):
    cur.execute(f"DELETE FROM reservations WHERE created_at < now() - INTERVAL '{RESERVATION_TTL}'")
    cur.execute(f"DELETE FROM rooms WHERE created_at < now() - INTERVAL '{ROOM_TTL}'")


def generate_reservation_number():
    """4桁のランダムな数字を生成"""
    return ''.join(random.choices(string.digits, k=4))


def create_room(room_id):
    with connect() as conn, conn.cursor() as cur:
        _purge_expired(cur)
        cur.execute(
            "INSERT INTO rooms (id) VALUES (%s) ON CONFLICT (id) DO NOTHING",
            (room_id,),
        )


def get_room(room_id):
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, url, reservation_number FROM rooms WHERE id = %s", (room_id,))
        return cur.fetchone()


def set_room_url(room_id, url):
    """ルームが存在すれば URL を設定する。存在しなければ False"""
    with connect() as conn, conn.cursor() as cur:
        cur.execute("UPDATE rooms SET url = %s WHERE id = %s", (url, room_id))
        return cur.rowcount > 0


def create_reservation(url):
    """一意な4桁コードを採番して予約を作る"""
    with connect() as conn, conn.cursor() as cur:
        _purge_expired(cur)
        for _ in range(50):
            number = generate_reservation_number()
            cur.execute(
                "INSERT INTO reservations (number, url) VALUES (%s, %s) "
                "ON CONFLICT (number) DO NOTHING RETURNING number",
                (number, url),
            )
            row = cur.fetchone()
            if row:
                return row['number']
    return None


def take_reservation(number):
    """コードを消費して URL を返す（一度限り）。無ければ None"""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"DELETE FROM reservations WHERE number = %s "
            f"AND created_at > now() - INTERVAL '{RESERVATION_TTL}' RETURNING url",
            (number,),
        )
        row = cur.fetchone()
        return row['url'] if row else None


def apply_reservation(room_id, number):
    """コードを消費してルームに URL を適用する。成否を返す"""
    with connect() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("SELECT 1 FROM rooms WHERE id = %s FOR UPDATE", (room_id,))
            if cur.fetchone() is None:
                return False
            cur.execute(
                f"DELETE FROM reservations WHERE number = %s "
                f"AND created_at > now() - INTERVAL '{RESERVATION_TTL}' RETURNING url",
                (number,),
            )
            row = cur.fetchone()
            if row is None:
                return False
            cur.execute(
                "UPDATE rooms SET url = %s, reservation_number = %s WHERE id = %s",
                (row['url'], number, room_id),
            )
            return True


def has_pending_reservation():
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT EXISTS (SELECT 1 FROM reservations "
            f"WHERE created_at > now() - INTERVAL '{RESERVATION_TTL}') AS found"
        )
        return cur.fetchone()['found']
