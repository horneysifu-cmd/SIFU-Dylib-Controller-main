# SIFU Dylib Controller

A license-management dashboard and API for software you own or are authorized to modify. The intended integration is a Dylib/SDK inside an authorized host app that unlocks only its own protected features after license validation.

## Current status

- [x] Initial responsive admin dashboard UI
- [ ] Backend API and database
- [ ] API integration tests
- [ ] Dylib login/activation client
- [ ] Signed update manifest and release flow
- [ ] Production deployment and security review

The dashboard is an initial frontend shell. It is not a deployed service and will not show real license data until the backend is implemented and connected.

## Project layout

- `dashboard/index.html` — initial admin dashboard
- `backend/` — planned FastAPI service
- `dylib/` — planned authorized client integration

## Planned API contract

All admin routes require an `Authorization: Bearer <ADMIN_TOKEN>` header and HTTPS in production.

- `GET /health` — service health
- `GET /api/admin/licenses` — list license metadata (never return stored plaintext keys)
- `POST /api/admin/licenses` — create a license; return the plaintext key once
- `PATCH /api/admin/licenses/{license_id}` — update license status
- `GET /api/admin/devices` — list device registrations
- `PATCH /api/admin/devices/{device_id}` — update device status

The exact request/response schemas will be documented alongside the backend implementation and kept in sync with the dashboard.

## Security requirements before production

- Store only a cryptographic hash of license keys; reveal a generated key only once.
- Keep admin credentials out of source control; use environment variables or a secret manager.
- Use HTTPS, strict CORS allowlists, request validation, rate limiting, and audit logs.
- Do not trust a caller-supplied device identifier as strong device attestation.
- Prefer POST JSON for license validation rather than putting secrets in URL query strings.
- Use signed update metadata and verify signatures before accepting client updates.
- Provide a recovery path and scope enforcement to the integrating app's own protected features; do not attempt system-wide iOS locking or universal injection.

## Local preview

Open `dashboard/index.html` in a browser to preview the interface. API-backed actions require the backend to exist and be reachable.
