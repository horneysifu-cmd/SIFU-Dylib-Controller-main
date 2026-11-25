import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

APP_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DATABASE_PATH", str(APP_DIR / "sifu_licenses.db")))
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
ALLOWED_ORIGINS = [x.strip() for x in os.getenv("ALLOWED_ORIGINS", "").split(",") if x.strip()]
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))

app = FastAPI(title="SIFU License API", version="0.1.0", docs_url="/docs" if os.getenv("ENABLE_DOCS", "false").lower() == "true" else None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)

_rate_buckets: dict[str, list[float]] = {}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@contextmanager
def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS licenses (
            id TEXT PRIMARY KEY,
            key_hash TEXT NOT NULL UNIQUE,
            key_hint TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            expires_at TEXT,
            device_limit INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS devices (
            id TEXT PRIMARY KEY,
            license_id TEXT NOT NULL,
            device_ref_hash TEXT NOT NULL,
            device_hint TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            UNIQUE(license_id, device_ref_hash),
            FOREIGN KEY(license_id) REFERENCES licenses(id)
        );
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            subject_id TEXT,
            detail TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_devices_license ON devices(license_id);
        CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at);
        """)


@app.on_event("startup")
def startup():
    init_db()


def audit(conn: sqlite3.Connection, action: str, subject_id: Optional[str] = None, detail: str = ""):
    conn.execute(
        "INSERT INTO audit_logs(action, subject_id, detail, created_at) VALUES(?,?,?,?)",
        (action, subject_id, detail[:500], iso(utcnow())),
    )


def key_digest(value: str) -> str:
    return hashlib.sha256(value.strip().upper().encode("utf-8")).hexdigest()


def device_digest(value: str) -> str:
    return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()


def rate_limit(request: Request):
    now = time.time()
    ip = request.client.host if request.client else "unknown"
    bucket = [t for t in _rate_buckets.get(ip, []) if now - t < 60]
    if len(bucket) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
    bucket.append(now)
    _rate_buckets[ip] = bucket


def require_admin(authorization: Optional[str] = Header(default=None)):
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="Admin API is not configured. Set ADMIN_TOKEN.")
    expected = f"Bearer {ADMIN_TOKEN}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Invalid admin token.")
    return True


class CreateLicense(BaseModel):
    prefix: str = Field(default="SIFU", min_length=2, max_length=12, pattern=r"^[A-Za-z0-9]+$")
    duration_days: Optional[int] = Field(default=30, ge=1, le=36500)
    lifetime: bool = False
    device_limit: int = Field(default=1, ge=1, le=100)


class LicenseStatusUpdate(BaseModel):
    status: Literal["active", "banned", "revoked"]


class ActivateRequest(BaseModel):
    license_key: str = Field(min_length=8, max_length=128)
    device_ref: str = Field(min_length=8, max_length=256)


class ValidateRequest(BaseModel):
    license_key: str = Field(min_length=8, max_length=128)
    device_ref: str = Field(min_length=8, max_length=256)


class DeviceStatusUpdate(BaseModel):
    status: Literal["active", "blocked"]


@app.get("/health")
def health():
    return {"status": "ok", "service": "sifu-license-api", "version": app.version}


@app.post("/api/admin/licenses", dependencies=[Depends(require_admin)])
def create_license(payload: CreateLicense, request: Request):
    prefix = payload.prefix.upper()
    raw_key = f"{prefix}-" + "-".join(secrets.token_hex(2).upper() for _ in range(3))
    license_id = secrets.token_hex(12)
    created = utcnow()
    expires = None if payload.lifetime else created + timedelta(days=payload.duration_days or 30)
    with db() as conn:
        conn.execute(
            """INSERT INTO licenses(id,key_hash,key_hint,status,created_at,expires_at,device_limit)
               VALUES(?,?,?,?,?,?,?)""",
            (license_id, key_digest(raw_key), raw_key[-4:], "active", iso(created), iso(expires), payload.device_limit),
        )
        audit(conn, "license.created", license_id, f"prefix={prefix}; device_limit={payload.device_limit}")
    # Plaintext key is returned only in this creation response; it is never stored.
    return {
        "license_id": license_id,
        "license_key": raw_key,
        "status": "active",
        "created_at": iso(created),
        "expires_at": iso(expires),
        "device_limit": payload.device_limit,
    }


@app.get("/api/admin/licenses", dependencies=[Depends(require_admin)])
def list_licenses():
    with db() as conn:
        rows = conn.execute("""
            SELECT l.id AS license_id, l.key_hint, l.status, l.created_at, l.expires_at,
                   l.device_limit, COUNT(d.id) AS device_count
            FROM licenses l LEFT JOIN devices d ON d.license_id=l.id AND d.status='active'
            GROUP BY l.id ORDER BY l.created_at DESC
        """).fetchall()
    return {"licenses": [dict(row) for row in rows]}


@app.patch("/api/admin/licenses/{license_id}", dependencies=[Depends(require_admin)])
def update_license(license_id: str, payload: LicenseStatusUpdate):
    with db() as conn:
        cur = conn.execute("UPDATE licenses SET status=? WHERE id=?", (payload.status, license_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="License not found.")
        audit(conn, f"license.{payload.status}", license_id)
    return {"license_id": license_id, "status": payload.status}


@app.get("/api/admin/devices", dependencies=[Depends(require_admin)])
def list_devices():
    with db() as conn:
        rows = conn.execute("""
            SELECT d.id AS device_id, d.license_id, d.device_hint, d.status,
                   d.created_at, d.last_seen_at
            FROM devices d ORDER BY d.last_seen_at DESC
        """).fetchall()
    return {"devices": [dict(row) for row in rows]}


@app.patch("/api/admin/devices/{device_id}", dependencies=[Depends(require_admin)])
def update_device(device_id: str, payload: DeviceStatusUpdate):
    with db() as conn:
        cur = conn.execute("UPDATE devices SET status=? WHERE id=?", (payload.status, device_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Device not found.")
        audit(conn, f"device.{payload.status}", device_id)
    return {"device_id": device_id, "status": payload.status}


def check_license(conn: sqlite3.Connection, license_key: str):
    row = conn.execute("SELECT * FROM licenses WHERE key_hash=?", (key_digest(license_key),)).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid license key.")
    if row["status"] != "active":
        raise HTTPException(status_code=403, detail=f"License is {row['status']}.")
    expiry = parse_dt(row["expires_at"])
    if expiry and expiry <= utcnow():
        raise HTTPException(status_code=403, detail="License has expired.")
    return row


@app.post("/api/license/activate", dependencies=[Depends(rate_limit)])
def activate(payload: ActivateRequest, request: Request):
    device_hash = device_digest(payload.device_ref)
    with db() as conn:
        license_row = check_license(conn, payload.license_key)
        existing = conn.execute(
            "SELECT * FROM devices WHERE license_id=? AND device_ref_hash=?",
            (license_row["id"], device_hash),
        ).fetchone()
        if existing:
            if existing["status"] != "active":
                raise HTTPException(status_code=403, detail="This device is blocked.")
            conn.execute("UPDATE devices SET last_seen_at=? WHERE id=?", (iso(utcnow()), existing["id"]))
            audit(conn, "device.activated_existing", existing["id"])
            return {"valid": True, "license_id": license_row["id"], "device_id": existing["id"], "expires_at": license_row["expires_at"]}
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM devices WHERE license_id=? AND status='active'",
            (license_row["id"],),
        ).fetchone()["n"]
        if count >= license_row["device_limit"]:
            raise HTTPException(status_code=403, detail="Device limit reached.")
        device_id = secrets.token_hex(12)
        conn.execute(
            """INSERT INTO devices(id,license_id,device_ref_hash,device_hint,status,created_at,last_seen_at)
               VALUES(?,?,?,?,?,?,?)""",
            (device_id, license_row["id"], device_hash, payload.device_ref[-4:], "active", iso(utcnow()), iso(utcnow())),
        )
        audit(conn, "device.activated", device_id)
        return {"valid": True, "license_id": license_row["id"], "device_id": device_id, "expires_at": license_row["expires_at"]}


@app.post("/api/license/validate", dependencies=[Depends(rate_limit)])
def validate(payload: ValidateRequest):
    device_hash = device_digest(payload.device_ref)
    with db() as conn:
        license_row = check_license(conn, payload.license_key)
        device = conn.execute(
            "SELECT * FROM devices WHERE license_id=? AND device_ref_hash=?",
            (license_row["id"], device_hash),
        ).fetchone()
        if not device or device["status"] != "active":
            raise HTTPException(status_code=403, detail="Device is not activated or is blocked.")
        conn.execute("UPDATE devices SET last_seen_at=? WHERE id=?", (iso(utcnow()), device["id"]))
        audit(conn, "license.validated", license_row["id"])
        return {"valid": True, "license_id": license_row["id"], "device_id": device["id"], "expires_at": license_row["expires_at"]}


@app.get("/api/admin/audit-logs", dependencies=[Depends(require_admin)])
def list_audit_logs(limit: int = 100):
    limit = max(1, min(limit, 500))
    with db() as conn:
        rows = conn.execute(
            "SELECT action,subject_id,detail,created_at FROM audit_logs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return {"logs": [dict(row) for row in rows]}
