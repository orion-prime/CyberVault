# Module 10 — Simple Investigator Authentication

## Implemented
- Login endpoint: `POST /api/auth/login`
- Current user endpoint: `GET /api/auth/me`
- Password storage uses salted scrypt hashes (never plaintext).
- Short-lived HMAC-SHA256 bearer access tokens.
- All `/api/*` routes are protected except `/api/auth/login`.
- Inactive users and expired/invalid tokens are rejected.
- Newly created custody events use the authenticated username as the actor.
- Frontend login screen, token attachment, and sign-out.
- Configurable API URL using `VITE_API_URL`.

## Initial account provisioning
There is intentionally no public registration endpoint. Set the initial account through deployment environment variables:

- `CYBERVAULT_BOOTSTRAP_USERNAME`
- `CYBERVAULT_BOOTSTRAP_PASSWORD` (minimum 14 characters)

The account is created if that username does not already exist. Changing the environment password does not reset an existing account. Password reset/account administration is a later module.

## Local development
1. Copy `.env.example` to `.env`.
2. Set unique database password, token secret (at least 32 characters), bootstrap username and strong password.
3. Start with Docker Compose: `docker compose up --build`.
4. Open `http://localhost:8080`.

For direct local development, set `DATABASE_URL=sqlite:///./cybervault.db`, configure the token and bootstrap variables, run the backend on port 8000 and frontend on port 5173.

## Cloud deployment
- Use managed PostgreSQL with TLS and a restricted application database user.
- Set `DATABASE_URL` to `postgresql+psycopg://...`.
- Store secrets in the cloud provider's secret manager, not in source control.
- Terminate HTTPS at a managed load balancer or reverse proxy.
- Set `CYBERVAULT_CORS_ORIGINS` to the exact trusted frontend origins.
- Mount persistent, encrypted evidence storage or replace the local volume with private object storage.
- Configure backups, restore drills, monitoring and alerting.
- Never expose PostgreSQL directly to the public internet.

## Security boundaries and remaining work
This is the first authentication layer, not a complete production identity platform. It uses bearer tokens in browser localStorage, which increases impact of a frontend XSS vulnerability. Before public production use, prefer Secure/HttpOnly/SameSite cookies or a managed identity provider, add rate limiting and account lockout, password reset/rotation, audit login attempts, TLS, CSRF protections if cookie auth is adopted, and formal database migrations. The initial account bootstrap is deliberately not a user-registration workflow.
