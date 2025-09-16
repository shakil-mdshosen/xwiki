# xwiki — Cross-wiki user activity tracker (Toolforge)

xwiki tracks configured Wikimedia usernames across all wikis using EventStreams (RecentChanges), stores matching events in ToolsDB, and presents them in a protected web UI. Admins manage which users are tracked via the web interface.

## Features

- Wikimedia OAuth 2.0 login; allowlist authorization with roles (viewer/admin).
- Admins can add/remove tracked users from the UI.
- Consumes global RecentChanges EventStreams and stores only events where `user ∈ tracked_users`.
- Dashboard with filters: tracked user, wiki, type, date range; pagination; links out to diffs/logs.

## Architecture

- Web: Flask (Python), Authlib (OAuth2), Tailwind (CDN), HTMX (CDN).
- Ingestion: SSE client to `https://stream.wikimedia.org/v2/stream/recentchange` in a background continuous job.
- Storage: ToolsDB (MariaDB) tables `events`, `state`, `allowed_users`, `tracked_users`.

## Toolforge setup

Prereqs:
- Toolforge tool created at https://toolsadmin.wikimedia.org/ (tool name: `xwiki`).
- Kubernetes backend enabled.

### 1) Upload code and install dependencies

```bash
become xwiki
cd /data/project/xwiki
# put this repo here (git clone or upload files)
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
```

### 2) Create database and schema

```bash
# Open ToolsDB
sql tools

# In the SQL shell:
CREATE DATABASE xwiki__events;
USE xwiki__events;
SOURCE /data/project/xwiki/schema.sql;

# Seed allowed users (must be exact Wikimedia usernames); make at least one admin:
INSERT INTO allowed_users (username, role) VALUES ('YourWikiUsername', 'admin');
# Optionally pre-seed a tracked user:
INSERT INTO tracked_users (username, normalized_username) VALUES ('ExampleUser', 'exampleuser');
```

Your tool account’s `~/.my.cnf` should contain DB credentials. If missing, see Toolforge docs for setting it up.

### 3) Configure environment

Copy `.env.example` to `.env` and fill values:
- `TOOLSDB_DATABASE=xwiki__events`
- `MYSQL_CNF_PATH=/data/project/xwiki/.my.cnf`
- Set a strong `FLASK_SECRET_KEY`.
- Keep `USER_AGENT` descriptive and include a contact.

### 4) Register a Wikimedia OAuth 2.0 client (Meta-Wiki)

- Register an OAuth2 client (see Wikitech for current UI).
- Callback/redirect URI:
  `https://toolforge.org/tool/xwiki/oauth/callback`
- Scope: `basic` is typically sufficient to identify the username.
- Put `OAUTH_CLIENT_ID` and `OAUTH_CLIENT_SECRET` in `.env`.

Endpoints to verify:
- Authorization: `https://meta.wikimedia.org/w/rest.php/oauth2/authorize`
- Token: `https://meta.wikimedia.org/w/rest.php/oauth2/access_token`
- Profile: `https://meta.wikimedia.org/w/rest.php/oauth2/resource/profile`

### 5) Start the webservice

```bash
become xwiki
cd /data/project/xwiki
webservice --backend=kubernetes python3.11 start
```

The Flask app binds to `$PORT` automatically.

To restart after changes:
```bash
webservice --backend=kubernetes python3.11 restart
```

### 6) Run the consumer continuously

Test interactively first:
```bash
webservice --backend=kubernetes python3.11 shell
. venv/bin/activate
python consumer.py
# Ctrl+C to stop
```

Run as a continuous job:
```bash
toolforge-jobs run xwiki-rc-consumer \
  --image python3.11 \
  --command '/data/project/xwiki/venv/bin/python /data/project/xwiki/consumer.py' \
  --continuous
```

Check status/logs:
```bash
toolforge-jobs list
toolforge-jobs logs xwiki-rc-consumer
```

### Using the app

- Visit: `https://toolforge.org/tool/xwiki/`
- Sign in with Wikimedia OAuth2.
- Only usernames in `allowed_users` may access. Admins can:
  - Add or remove tracked users in “Manage tracked users”.
- Events begin accumulating after the consumer is running; historical backfill is not automatic.

## Notes and extensions

- Backfill: If you need past edits, do a temporary backfill using the MediaWiki API per wiki (iterate sitematrix) with throttling; store into `events`.
- Link building: Events store `server_url`; use it to construct links to diffs/logs on the dashboard.
- Rate/throughput: The RC stream is high-volume; filtering client-side by a small set of usernames remains efficient.
- Security: Keep `.env` and secrets under `/data/project/xwiki` with `chmod 600` if desired; do not commit secrets.

## Local development

- You can use a local MariaDB and update `TOOLSDB_HOST`/`TOOLSDB_DATABASE`.
- For OAuth locally, make a separate client with callback `http://localhost:8000/oauth/callback`.