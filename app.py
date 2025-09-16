import os
import functools
from datetime import datetime
from urllib.parse import urlencode

from flask import (
    Flask, redirect, request, session, url_for, render_template,
    abort, jsonify, flash
)
from authlib.integrations.flask_client import OAuth
import pymysql
from dotenv import load_dotenv

from db import get_connection

load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder=None)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(32))

# OAuth2 client config
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID", "")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET", "")
OAUTH_AUTHORIZE_URL = os.getenv("OAUTH_AUTHORIZE_URL", "https://meta.wikimedia.org/w/rest.php/oauth2/authorize")
OAUTH_TOKEN_URL = os.getenv("OAUTH_TOKEN_URL", "https://meta.wikimedia.org/w/rest.php/oauth2/access_token")
OAUTH_USERINFO_URL = os.getenv("OAUTH_USERINFO_URL", "https://meta.wikimedia.org/w/rest.php/oauth2/resource/profile")
OAUTH_SCOPE = os.getenv("OAUTH_SCOPE", "basic")

oauth = OAuth(app)
oauth.register(
    name="wikimedia",
    client_id=OAUTH_CLIENT_ID,
    client_secret=OAUTH_CLIENT_SECRET,
    access_token_url=OAUTH_TOKEN_URL,
    authorize_url=OAUTH_AUTHORIZE_URL,
    client_kwargs={"scope": OAUTH_SCOPE},
)

def normalize_username(u: str) -> str:
    return (u or "").strip().casefold()

def login_required(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login", next=request.full_path))
        return view(*args, **kwargs)
    return wrapper

def role_required(roles=("viewer","admin")):
    def decorator(view):
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            if "user" not in session:
                return redirect(url_for("login", next=request.full_path))
            username = session["user"]["username"]
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute("SELECT role FROM allowed_users WHERE username=%s", (username,))
                row = cur.fetchone()
                if not row or row["role"] not in roles:
                    abort(403)
            return view(*args, **kwargs)
        return wrapper
    return decorator

@app.route("/")
@login_required
@role_required(("viewer","admin"))
def index():
    # Filters
    selected_user = request.args.get("user", "").strip()
    wiki = request.args.get("wiki", "").strip()
    ev_type = request.args.get("type", "").strip()  # edit/new/log
    date_from = request.args.get("from", "").strip()
    date_to = request.args.get("to", "").strip()
    page = max(1, int(request.args.get("page", "1")))
    page_size = min(200, max(10, int(request.args.get("page_size", "50"))))
    offset = (page - 1) * page_size

    where = []
    params = []

    if selected_user:
        where.append("e.normalized_user = %s")
        params.append(normalize_username(selected_user))
    if wiki:
        where.append("e.wiki = %s")
        params.append(wiki)
    if ev_type:
        where.append("e.type = %s")
        params.append(ev_type)
    if date_from:
        where.append("e.timestamp >= %s")
        params.append(date_from)
    if date_to:
        where.append("e.timestamp <= %s")
        params.append(date_to)

    where_sql = "WHERE " + " AND ".join(where) if where else ""

    with get_connection() as conn, conn.cursor() as cur:
        # For filters: load tracked users and distinct wikis/types present
        cur.execute("SELECT username FROM tracked_users ORDER BY username")
        tracked_users = [r["username"] for r in cur.fetchall()]

        cur.execute(f"SELECT COUNT(*) AS cnt FROM events e {where_sql}", params)
        total = cur.fetchone()["cnt"]

        cur.execute(
            f"""
            SELECT e.id, e.wiki, e.namespace, e.title, e.user, e.type, e.minor, e.patrolled, e.bot,
                   e.comment, e.timestamp, e.rev_id, e.page_id, e.log_type, e.log_action, e.server_url
            FROM events e
            {where_sql}
            ORDER BY e.timestamp DESC
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        rows = cur.fetchall()

        cur.execute("SELECT DISTINCT wiki FROM events ORDER BY wiki")
        wikis = [r["wiki"] for r in cur.fetchall()]
        cur.execute("SELECT DISTINCT type FROM events ORDER BY