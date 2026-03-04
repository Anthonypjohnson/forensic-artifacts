# ForensicArtifacts

A self-hosted knowledge base for forensic artifacts and indicators of compromise (IOCs), built for internal security team use.

## Features

- **Artifact library** — document forensic artifacts with location, tools, instructions, and significance
- **IOC tracking** — record network, file, system, and other indicators with severity and case grouping
- **Tagging** — tag artifacts and IOCs independently; filter by tag on index pages
- **Edit history** — every create and edit is snapshotted; diff view shows exactly what changed
- **Activity log** — admin-only unified log of all artifact and IOC changes across the site
- **IP whitelist** — non-whitelisted IPs are silently dropped before reaching the app
- **Account lockout** — 5 failed logins triggers a 15-minute lockout
- **HTTPS** — nginx terminates TLS; auto-generates a self-signed cert or uses a CA-provided cert (e.g. Windows PKI)

## Stack

| Layer | Technology |
|-------|------------|
| Web framework | Flask 3.0 |
| Database | SQLite (WAL mode) |
| Auth | Flask-Login + Argon2id |
| CSRF | Flask-WTF |
| Input sanitisation | bleach |
| Frontend | Bootstrap 5.3 dark theme |
| Reverse proxy | nginx (Docker sidecar) |

## Quick Start

### Prerequisites

- Docker + Docker Compose

### 1. Clone and configure

```bash
git clone <repo-url>
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
| `SESSION_COOKIE_SECURE` | `True` | Set to `False` only if not using HTTPS |
| `PROXY_COUNT` | `1` | Number of trusted reverse proxies (1 = nginx sidecar) |

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
├── middleware/
│   └── ip_whitelist.py     # WSGI silent-drop middleware
├── models/
│   ├── artifact.py
│   ├── history.py
│   ├── ioc.py
│   ├── log.py              # Unified activity log query
│   ├── tag.py
│   └── user.py
├── routes/
│   ├── admin.py            # /admin — user management, activity log
│   ├── api.py              # /api — JSON endpoints for live search
│   ├── artifacts.py        # /artifact
│   ├── auth.py             # /auth — login, logout, change password
│   └── iocs.py             # /iocs
├── static/
└── templates/
```

## Security Notes

- The IP whitelist performs a silent drop (no HTTP response) for non-whitelisted addresses
- `PROXY_COUNT` must match the exact number of proxies in front of the app — over-trusting allows IP spoofing
- Passwords are hashed with Argon2id (time_cost=3, memory_cost=64 MB, parallelism=4)
- All POST forms are CSRF-protected via Flask-WTF
- The `editor_name` field on all forms is locked to the logged-in user server-side and cannot be spoofed
- TLS private keys are excluded from both git history and Docker image builds
