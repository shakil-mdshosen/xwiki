import os
import json
import time
import traceback
from typing import Set, Tuple

from sseclient import SSEClient
from dotenv import load_dotenv

from db import get_connection

load_dotenv()

STREAM_URL = os.getenv("EVENTSTREAM_URL", "https://stream.wikimedia.org/v2/stream/recentchange")
USER_AGENT = os.getenv("USER_AGENT", "Toolforge-xwiki/1.0 (contact: https://toolforge.org/tool/xwiki)")
RECONNECT_DELAY = float(os.getenv("RECONNECT_DELAY", "3.0"))
TRACKED_REFRESH_SEC = int(os.getenv("TRACKED_REFRESH_SEC", "60"))

def normalize_username(u: str) -> str:
    return (u or "").strip().casefold()

def get_last_event_id(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT val FROM state WHERE name='last_event_id'")
        row = cur.fetchone()
        return row["val"] if row else None

def set_last_event_id(conn, event_id):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO state (name, val) VALUES ('last_event_id', %s) ON DUPLICATE KEY UPDATE val=VALUES(val)",
            (event_id,),
        )

def load_tracked_users(conn) -> Set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT normalized_username FROM tracked_users")
        return {r["normalized_username"] for r in cur.fetchall()}

def store_event(conn, ev):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO events
              (id, wiki, namespace, title, user, normalized_user, type, minor, patrolled, bot, comment, timestamp,
               rev_id, page_id, log_type, log_action, server_url, raw)
            VALUES
              (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FROM_UNIXTIME(%s),
               %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
              comment=VALUES(comment), timestamp=VALUES(timestamp), rev_id=VALUES(rev_id),
              page_id=VALUES(page_id), log_type=VALUES(log_type), log_action=VALUES(log_action),
              server_url=VALUES(server_url), raw=VALUES(raw)
            """,
            (
                ev.get("id"),
                ev.get("wiki"),
                ev.get("namespace"),
                ev.get("title"),
                ev.get("user"),
                normalize_username(ev.get("user")),
                ev.get("type"),
                1 if ev.get("minor") else 0,
                1 if ev.get("patrolled") else 0,
                1 if ev.get("bot") else 0,
                ev.get("comment"),
                ev.get("timestamp"),
                ev.get("rev_id"),
                ev.get("page_id"),
                (ev.get("log", {}) or {}).get("type"),
                (ev.get("log", {}) or {}).get("action"),
                ev.get("server_url"),
                json.dumps(ev, ensure_ascii=False),
            ),
        )

def run():
    headers = {"User-Agent": USER_AGENT}
    tracked: Set[str] = set()
    last_tracked_load = 0

    while True:
        try:
            with get_connection() as conn:
                # initial load of tracked set
                now = time.time()
                if now - last_tracked_load > 1:
                    tracked = load_tracked_users(conn)
                    last_tracked_load = now

                last_id = get_last_event_id(conn)
                h = dict(headers)
                if last_id:
                    h["Last-Event-ID"] = last_id

                messages = SSEClient(STREAM_URL, headers=h, retry=3000)
                last_refresh = time.time()

                for msg in messages:
                    if msg.event in (None, "message"):
                        if not msg.data:
                            continue
                        ev = json.loads(msg.data)
                        u = ev.get("user")
                        if u and normalize_username(u) in tracked:
                            store_event(conn, ev)
                        if msg.id:
                            set_last_event_id(conn, msg.id)

                        # periodic refresh of tracked usernames
                        if time.time() - last_refresh >= TRACKED_REFRESH_SEC:
                            tracked = load_tracked_users(conn)
                            last_refresh = time.time()

        except Exception as e:
            traceback.print_exc()
            time.sleep(RECONNECT_DELAY)

if __name__ == "__main__":
    run()