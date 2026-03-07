# ForensicArtifacts

A self-hosted knowledge base for forensic artifacts and indicators of compromise (IOCs), built for internal security team use.

## Features

- **Artifact library** — document forensic artifacts with location, tools, instructions, and significance
- **IOC tracking** — record network, file, system, and other indicators with severity and case grouping; import from STIX 1.x XML or STIX 2.x JSON
- **Events** — log forensic events (authentication, execution, network activity, etc.) with system, account, source, datetime, notes, and optional screenshot attachment; link events to IOCs and tasks
- **Tasks** — track investigation tasks with status (Open / In Progress / Blocked / Done) and priority (Low / Medium / High / Critical); claim/release assignment
- **Timeline** — chronological view of events grouped by date, with filtering by date range, system, IOC, category, and tag
- **Tagging** — tag artifacts, IOCs, and events independently; filter by tag on index pages
- **Edit history** — every create and edit is snapshotted; diff view shows exactly what changed
- **Activity log** — admin-only unified log of all artifact and IOC changes across the site
- **CSV import/export** — import and export IOCs, events, and tasks as CSV; downloadable template included
- **Settings** — configure the UTC clock bar with up to 20 IANA timezones
- **IP whitelist** — non-whitelisted IPs are silently dropped before reaching the app
- **Account lockout** — 5 failed logins triggers a 15-minute lockout
- **Security headers** — CSP, X-Frame-Options, X-Content-Type-Options, and Referrer-Policy on every response
- **HTTPS** — nginx terminates TLS; auto-generates a self-signed cert or uses a CA-provided cert (e.g. Windows PKI)

## Stack

| Layer | Technology |
|-------|------------|
| Web framework | Flask 3.1 |
| Database | SQLite (WAL mode) |
| Auth | Flask-Login + Argon2id |
| CSRF | Flask-WTF |
| Input sanitisation | bleach |
| XML safety | defusedxml |
| Frontend | Bootstrap 5.3 dark theme |
| Reverse proxy | nginx (Docker sidecar) |

## Images
<img width="916" height="496" alt="Screenshot 2026-03-07 at 8 36 19 AM" src="https://github.com/user-attachments/assets/d927ef5a-d78d-456c-985f-21b34b99bfdd" />
<img width="910" height="565" alt="Screenshot 2026-03-07 at 8 36 09 AM" src="https://github.com/user-attachments/assets/f735ba7a-9b1f-49b5-b1f0-57df9b12d201" />
<img width="916" height="350" alt="Screenshot 2026-03-07 at 8 35 58 AM" src="https://github.com/user-attachments/assets/dfa7a8f4-e242-4b0d-8cb3-e31c76d4e9b1" />
<img width="918" height="284" alt="Screenshot 2026-03-07 at 8 35 47 AM" src="https://github.com/user-attachments/assets/1c0904de-b211-4a9c-9f62-4d857b16e807" />
<img width="919" height="353" alt="Screenshot 2026-03-07 at 8 35 23 AM" src="https://github.com/user-attachments/assets/47e3049b-2d70-41e4-8fc4-12e1251cc290" />


## Quick Start

### Prerequisites

- Docker + Docker Compose

### 1. Clone and configure

```bash
git clone https://github.com/Anthonypjohnson/forensic-artifacts
cd forensic-artifacts

cp .env.example .env
```

Edit `.env` and set a real `SECRET_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Configure IP whitelist

Edit `allowed_ips.conf` — one entry per line, supports single IPs and CIDR ranges:

```
127.0.0.1
::1
192.168.1.0/24
203.0.113.50
```

Changes take effect immediately without restarting.

#### Finding your IP address

**macOS**
```bash
ipconfig getifaddr en0
```
> If that returns nothing, try `en1` (Wi-Fi vs Ethernet). To see all interfaces: `ifconfig | grep "inet "`

**Windows** (Command Prompt or PowerShell)
```cmd
ipconfig
```
> Look for the **IPv4 Address** under your active adapter (Ethernet or Wi-Fi).

#### Important — Docker NAT and hairpin NAT

Due to the way Docker Desktop and home/office routers handle NAT, the IP the application sees may **not** be your machine's local IP (`192.168.x.x`). Instead it may appear as your **public IP** (the one assigned by your ISP to your router).

To find the exact IP being seen by the app, check the nginx logs after a blocked or allowed request:

```bash
docker compose logs nginx | tail -20
```

The first field on each line is the client IP the app received. Use that value in `allowed_ips.conf`.

If multiple people on the same network need access, whitelist the whole subnet instead of individual IPs:

```
192.168.1.0/24
```

### 3. Start

```bash
docker compose up -d --build
```

On first start, nginx will generate a self-signed TLS certificate automatically.

### 4. Create the admin account

```bash
docker compose exec app flask create-admin
```

### 5. Browse

```
https://<your-ip>
```

HTTP on port 80 redirects to HTTPS automatically. Accept the browser warning for the self-signed cert (or install a CA cert — see below).

---

## TLS Certificates

### Self-signed (default)

A self-signed certificate is generated automatically on first start and stored in `./certs/`. It persists across container restarts.

### CA-signed certificate (Windows PKI or other)

Export your certificate as PFX/P12, then convert to PEM:

```bash
openssl pkcs12 -in your-cert.pfx -clcerts -nokeys -out certs/cert.pem
openssl pkcs12 -in your-cert.pfx -nocerts -nodes  -out certs/key.pem

docker compose restart nginx
```

Drop `cert.pem` and `key.pem` into `./certs/` — nginx picks them up on next start.

> **Note:** `certs/` is excluded from git and never baked into the Docker image.

---

## Configuration (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | *(required)* | Flask session signing key — generate with `secrets.token_hex(32)` |
| `FLASK_ENV` | `production` | Set to `development` to enable debug mode |
| `SESSION_COOKIE_SECURE` | `False` | Set to `True` when running behind HTTPS (required for production) |
| `PROXY_COUNT` | `0` | Number of trusted reverse proxies in front of the app — set to `1` when using the nginx sidecar |

---

## Project Structure

```
├── app.py                  # App factory, Flask-Login setup, CLI commands
├── config.py               # Config from .env
├── docker-compose.yml
├── Dockerfile
├── nginx.conf              # HTTPS + HTTP→HTTPS redirect
├── nginx-entrypoint.sh     # Auto-generates cert if none present
├── allowed_ips.conf        # IP whitelist (re-read on every request)
├── certs/                  # TLS certs (gitignored, dockerignored)
├── database/
│   ├── db.py               # SQLite connection, WAL mode, foreign keys
│   └── schema.sql          # DDL
├── forms/
│   ├── artifact_form.py
│   ├── auth_form.py
│   ├── event_form.py
│   ├── ioc_form.py
│   └── task_form.py
├── middleware/
│   └── ip_whitelist.py     # WSGI silent-drop middleware
├── models/
│   ├── artifact.py
│   ├── event.py
│   ├── history.py
│   ├── ioc.py
│   ├── log.py              # Unified activity log query
│   ├── settings.py         # App settings (timezones)
│   ├── tag.py
│   ├── task.py
│   └── user.py
├── routes/
│   ├── admin.py            # /admin — user management, activity log
│   ├── api.py              # /api — JSON endpoints for live search
│   ├── artifacts.py        # /artifacts
│   ├── auth.py             # /auth — login, logout, change password
│   ├── events.py           # /events — event log with screenshot upload
│   ├── iocs.py             # /iocs — IOC tracking + STIX/CSV import
│   ├── settings.py         # /settings — timezone configuration
│   ├── tasks.py            # /tasks — task tracking
│   └── timeline.py         # /timeline — chronological event view
├── static/
│   └── uploads/
│       └── events/         # Uploaded event screenshots
└── utils/
    ├── csv_io.py           # CSV export/import helpers
    └── stix_parser.py      # STIX 1.x XML and STIX 2.x JSON parser
```

## Security Notes

- The IP whitelist performs a silent drop (no HTTP response) for non-whitelisted addresses
- `PROXY_COUNT` must match the exact number of proxies in front of the app — over-trusting allows IP spoofing
- Passwords are hashed with Argon2id (time_cost=3, memory_cost=64 MB, parallelism=4)
- All POST forms are CSRF-protected via Flask-WTF
- The `editor_name` field on all forms is locked to the logged-in user server-side and cannot be spoofed
- STIX XML parsing uses `defusedxml` to prevent XML bomb and XXE attacks
- Uploaded screenshots are validated by extension and MIME type; stored with UUID filenames under `static/uploads/events/`
- TLS private keys are excluded from both git history and Docker image builds
