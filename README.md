# CyberVault

**CyberVault** is a digital forensic investigation application for
collecting evidence, checking file integrity, comparing candidate files,
and producing investigation reports.

This repository contains the Docker-based deployment configured for
**FastAPI, React/Vite, and PostgreSQL**.

> **Project status:** Module 10 deployment has been tested locally with
> Docker Compose. The frontend, backend, and PostgreSQL containers
> started successfully; login worked; image and PDF analysis and report
> generation were exercised; and evidence records remained available
> after a backend-container restart. A full database backup/restore test
> and production security review are still required.

## Features

-   Evidence collection and evidence records
-   SHA-256 integrity verification
-   PDF semantic comparison, including detected text/numeric differences
    and metadata/structure indicators
-   Image comparison with pixel-level metrics and visual exhibits
    (original/candidate, heatmap, and overlay)
-   Trust score, risk band, severity, forensic explanations, and
    recommended investigator actions
-   Forensic PDF report generation
-   Hash-linked chain-of-custody event history and integrity
    verification
-   Username/password authentication for protected API routes
-   PostgreSQL database deployment through Docker Compose

Automated findings are investigative indicators, not proof of fraud,
manipulation, intent, or authenticity. Investigators should preserve
originals and independently validate provenance and context.

## Architecture

``` text
Browser
   |
   v
React + Vite production build
   |
   v
Nginx (http://localhost:8080)
   |  /api/* proxy
   v
FastAPI backend (container port 8000)
   |
   v
PostgreSQL 16 (container port 5432)

Docker named volumes:
- PostgreSQL data
- Evidence storage
```

The browser should use the same-origin `/api` path through Nginx. Do not
configure the browser-side API URL as `http://127.0.0.1:8000` for the
Docker deployment.

## Requirements

-   Docker Desktop with Docker Compose
-   Git (optional, for source control)
-   A modern web browser

You do not need to install PostgreSQL separately when using the supplied
Docker Compose setup.

## Quick start

1.  Clone or download this repository.
2.  In the project root, create a local `.env` file using `.env.example`
    as a starting point.
3.  Replace every placeholder with unique local values. Do not commit
    `.env`.
4.  Build and start the services:

``` powershell
docker compose up --build -d
```

5.  Check service status:

``` powershell
docker compose ps
```

6.  Open the application:

-   Frontend: http://localhost:8080
-   Health check: http://localhost:8080/health
-   API documentation (if exposed through the Nginx proxy
    configuration): http://localhost:8080/docs

The initial account is bootstrapped from `CYBERVAULT_BOOTSTRAP_USERNAME`
and `CYBERVAULT_BOOTSTRAP_PASSWORD` when the application initializes and
the account does not already exist. Use those credentials on the login
page.

### Environment variables

See `.env.example` for the exact variables expected by the current
Compose configuration. Common settings include:

  -----------------------------------------------------------------------
  Variable                            Purpose
  ----------------------------------- -----------------------------------
  `POSTGRES_DB`                       PostgreSQL database name

  `POSTGRES_USER`                     PostgreSQL application user

  `POSTGRES_PASSWORD`                 PostgreSQL password

  `DATABASE_URL`                      SQLAlchemy connection URL; inside
                                      Compose, the host is `db`

  `CYBERVAULT_TOKEN_SECRET`           Secret used to sign authentication
                                      tokens; use a unique random value
                                      of at least 32 characters

  `CYBERVAULT_TOKEN_TTL_SECONDS`      Authentication token lifetime in
                                      seconds

  `CYBERVAULT_BOOTSTRAP_USERNAME`     Initial investigator username

  `CYBERVAULT_BOOTSTRAP_PASSWORD`     Initial investigator password (at
                                      least 14 characters)

  `CYBERVAULT_CORS_ORIGINS`           Allowed browser origins
  -----------------------------------------------------------------------

`POSTGRES_PASSWORD` and the password embedded in `DATABASE_URL` must
match. If a database password contains URL-reserved characters,
URL-encode it in `DATABASE_URL`.

Changing the bootstrap password in `.env` does not automatically reset
an account that already exists. Use an approved account-management
procedure to rotate existing credentials.

## Useful Docker commands

``` powershell
# Start or rebuild
docker compose up --build -d

# View service status
docker compose ps -a

# Follow all logs
docker compose logs -f

# View backend logs
docker compose logs --tail=100 backend

# Restart the backend
docker compose restart backend

# Stop containers without deleting persistent volumes
docker compose down
```

**Data safety:** Do not use `docker compose down -v` unless you
intentionally want to delete the named database and evidence volumes.
Back up important evidence and database data before maintenance.

## API and authentication

The backend is a FastAPI application. The login endpoint is:

``` text
POST /api/auth/login
```

The application returns an access token after successful authentication.
The frontend attaches that token to protected API requests.

For Docker deployment, access the backend through the frontend's Nginx
proxy using the same origin (`http://localhost:8080`). The backend
container's port `8000` is internal to the Compose network unless
separately published.

## Repository hygiene

The root `.gitignore` excludes local secrets, Python/Node build
artifacts, local database files, evidence directories, generated
reports, logs, and editor/OS files.

Before committing, inspect the staged files:

``` powershell
git status --short
git add .
git status
```

Confirm that `.env`, real credentials, private evidence, uploaded
originals, and generated forensic reports are not staged.

If a secret has ever been committed or shared, adding it to `.gitignore`
is not enough. Rotate the secret. If it was committed, remove it from
repository history before making the repository public.

## Security and operational notes

-   Keep `.env` private and use unique secrets for each deployment.
-   Use HTTPS and a managed secret store for any internet-facing
    deployment.
-   Restrict network access to the application and database.
-   The current simple authentication implementation should receive a
    production security review, including rate limiting, account
    lockout, secure session/token storage, and account recovery.
-   The chain-of-custody ledger is hash-linked at the application level.
    It is not tamper-proof against an attacker with sufficient database
    privileges who can rewrite records and recompute hashes.
-   Protect the Docker volumes and maintain separate, tested backups.
-   Do not use automated scores or classifications as standalone legal
    conclusions.

## Current limitations / planned hardening

The Module 10 deployment does not by itself establish that the system is
production-ready. The next reliability/security work should include:

-   Managed database schema migrations (for example, Alembic)
-   Tested PostgreSQL backup and restore procedures
-   Explicit data migration support for existing SQLite installations,
    if required
-   Stronger authentication controls and security review
-   Deployment behind HTTPS with production secrets management
-   Operational monitoring and documented recovery procedures

## Development

Frontend source is under `frontend/`; backend source is under
`backend/`. The Dockerfiles and `docker-compose.yml` define the
containerized deployment. For local development, inspect the respective
package and Python dependency files and keep the API base URL aligned
with the environment in which the browser runs.

## License

No license is specified in this repository yet. Add a `LICENSE` file
before distributing the project as open source.
