# SIFU Dylib Controller

A license-management dashboard and API for software you own or are authorized to modify. The intended integration is a Dylib/SDK inside an authorized host app that unlocks only its own protected features after license validation.

## Current status

- [x] Initial responsive admin dashboard UI
- [x] FastAPI backend with SQLite persistence
- [x] Admin license creation, listing, ban, unban and revoke
- [x] Device activation, validation, listing and blocking
- [x] Basic per-IP throttling for public activation/validation
- [x] Audit log records for key admin and license actions
- [ ] Automated backend tests and dashboard end-to-end tests
- [ ] Dylib login/activation client
- [ ] Signed update manifest and release flow
- [ ] Production deployment and security review

The dashboard and API source are committed, but the service is not deployed. Configure the backend environment and run it locally before connecting the dashboard.

## Project layout

- `dashboard/index.html` — responsive admin dashboard
- `backend/main.py` — FastAPI service and SQLite data model
- `backend/requirements.txt` — Python dependencies
- `backend/.env.example` — environment variable template

## Run the backend locally

1. Create a virtual environment and install dependencies:

   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Set environment variables. At minimum, set a long random `ADMIN_TOKEN`. For example:

   ```bash
   export ADMIN_TOKEN="replace-with-a-long-random-secret"
   export DATABASE_PATH="./data/sifu_licenses.db"
   export ALLOWED_ORIGINS="http://localhost:8000"
   ```

3. Start the API:

   ```bash
   uvicorn main:app --host 127.0.0.1 --port 8000
   ```

4. Open `http://127.0.0.1:8000/health` to check service health. To use the dashboard, serve the dashboard file from an origin included in `ALLOWED_ORIGINS`, then enter the API URL and admin token in Settings.

Interactive API docs are disabled by default. Set `ENABLE_DOCS=true` only during development if you need `/docs`.

## API routes

Admin routes require `Authorization: Bearer <ADMIN_TOKEN>`.

- `GET /health` — service health
- `GET /api/admin/licenses` — list license metadata; plaintext keys are never returned
- `POST /api/admin/licenses` — create a license; plaintext key is returned once
- `PATCH /api/admin/licenses/{license_id}` — set status to `active`, `banned`, or `revoked`
- `GET /api/admin/devices` — list registered devices
- `PATCH /api/admin/devices/{device_id}` — set status to `active` or `blocked`
- `GET /api/admin/audit-logs` — recent audit events

Public client routes accept JSON bodies and are rate-limited per IP:

- `POST /api/license/activate` — `{"license_key":"…","device_ref":"…"}`
- `POST /api/license/validate` — `{"license_key":"…","device_ref":"…"}`

## Security notes

- License keys are stored as SHA-256 digests; plaintext is returned only in the creation response.
- Admin credentials must be configured outside source control. Never commit a real `.env` file or token.
- Use HTTPS, exact CORS origin allowlists, rate limiting, request validation, and audit logs in production.
- The current device reference is an app-provided identifier, not cryptographic device attestation; it can be spoofed by a determined attacker. Do not treat it as high-assurance identity.
- For stronger production abuse resistance, move rate limiting to a shared gateway/store and add monitoring and alerting.
- Use signed update metadata and verify signatures before accepting client updates.
- Scope enforcement to the integrating app's own protected features. Do not attempt system-wide iOS locking or universal injection.

## Next milestone

Build and test the authorized Dylib/SDK login client against the activation and validation API. The client should fail closed for its own protected feature when a license is invalid, expired, revoked, or the device is blocked, while preserving a safe recovery path.
