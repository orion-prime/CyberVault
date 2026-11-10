import os
from contextvars import ContextVar
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, Body, Request
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .database import Base, engine, get_db, SessionLocal
from .models import Evidence, EvidenceEvent, CustodyEvent, User
from .schemas import EvidenceOut, VerificationOut
from .services import STORAGE_DIR, save_upload, sha256_file
from .semantic import compare_pdfs
from .scoring import calculate_trust_score
from .explanations import generate_forensic_explanation
from .image_analysis import compare_images
from .reporting import build_forensic_pdf
from .security import hash_password, verify_password, create_access_token, decode_access_token

Base.metadata.create_all(bind=engine)
app = FastAPI(title="CyberVault API", version="0.2.0")
CORS_ORIGINS = [origin.strip() for origin in os.getenv("CYBERVAULT_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["GET","POST","OPTIONS"], allow_headers=["Authorization","Content-Type"])

@app.middleware("http")
async def require_authentication(request: Request, call_next):
    # Health and login remain public; every evidence API requires a valid bearer token.
    if request.url.path == "/health" or request.url.path == "/api/auth/login" or request.method == "OPTIONS":
        return await call_next(request)
    if request.url.path.startswith("/api/"):
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return Response(content=json.dumps({"detail":"Authentication required."}), status_code=401, media_type="application/json")
        try:
            claims = decode_access_token(authorization[7:])
            db = SessionLocal()
            try:
                user = db.get(User, int(claims["sub"]))
                if not user or not user.is_active or user.username != claims.get("username"):
                    raise ValueError("Inactive or unknown account.")
                actor_context = CURRENT_ACTOR.set(user.username)
            finally:
                db.close()
        except Exception:
            return Response(content=json.dumps({"detail":"Invalid or expired access token."}), status_code=401, media_type="application/json")
        try:
            return await call_next(request)
        finally:
            CURRENT_ACTOR.reset(actor_context)
    return await call_next(request)


GENESIS_HASH = "0" * 64
CURRENT_ACTOR = ContextVar("cybervault_current_actor", default="system")

def _custody_payload(evidence_id: int, event_type: str, actor: str, details: str, occurred_at: str, previous_hash: str) -> dict:
    return {
        "evidence_id": evidence_id,
        "event_type": event_type,
        "actor": actor,
        "details": details,
        "occurred_at": occurred_at,
        "previous_hash": previous_hash,
    }

def _hash_custody_payload(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

def append_custody_event(db: Session, evidence_id: int, event_type: str, details: str, actor: str | None = None) -> CustodyEvent:
    actor = actor or CURRENT_ACTOR.get()
    previous = (
        db.query(CustodyEvent)
        .filter(CustodyEvent.evidence_id == evidence_id)
        .order_by(CustodyEvent.id.desc())
        .first()
    )
    previous_hash = previous.event_hash if previous else GENESIS_HASH
    occurred_at = datetime.now(timezone.utc).isoformat()
    payload = _custody_payload(evidence_id, event_type, actor, details, occurred_at, previous_hash)
    row = CustodyEvent(
        evidence_id=evidence_id,
        event_type=event_type,
        actor=actor,
        details=details,
        occurred_at=occurred_at,
        previous_hash=previous_hash,
        event_hash=_hash_custody_payload(payload),
    )
    db.add(row)
    return row

def verify_custody_chain(db: Session, evidence_id: int) -> dict:
    rows = (
        db.query(CustodyEvent)
        .filter(CustodyEvent.evidence_id == evidence_id)
        .order_by(CustodyEvent.id.asc())
        .all()
    )
    expected_previous = GENESIS_HASH
    for row in rows:
        payload = _custody_payload(
            row.evidence_id, row.event_type, row.actor, row.details,
            row.occurred_at, expected_previous
        )
        expected_hash = _hash_custody_payload(payload)
        if row.previous_hash != expected_previous or row.event_hash != expected_hash:
            return {
                "evidence_id": evidence_id, "valid": False,
                "checked_events": len(rows), "failed_event_id": row.id,
                "message": "The custody event chain has an integrity mismatch."
            }
        expected_previous = row.event_hash
    return {
        "evidence_id": evidence_id, "valid": True,
        "checked_events": len(rows), "failed_event_id": None,
        "message": "All recorded custody events pass the hash-chain integrity check."
    }


def backfill_legacy_custody_events():
    """Hash-link existing application event records once; mark them as legacy imports."""
    db = SessionLocal()
    try:
        evidence_ids = [row[0] for row in db.query(Evidence.id).all()]
        for evidence_id in evidence_ids:
            existing = db.query(CustodyEvent.id).filter(CustodyEvent.evidence_id == evidence_id).first()
            if existing:
                continue
            legacy_rows = (
                db.query(EvidenceEvent)
                .filter(EvidenceEvent.evidence_id == evidence_id)
                .order_by(EvidenceEvent.id.asc())
                .all()
            )
            previous = (
                db.query(CustodyEvent)
                .filter(CustodyEvent.evidence_id == evidence_id)
                .order_by(CustodyEvent.id.desc())
                .first()
            )
            previous_hash = previous.event_hash if previous else GENESIS_HASH
            for legacy in legacy_rows:
                occurred_at = legacy.created_at.isoformat() if legacy.created_at else datetime.now(timezone.utc).isoformat()
                details = f"Backfilled from legacy event #{legacy.id}: {legacy.details}"
                payload = _custody_payload(
                    evidence_id, legacy.event_type, "legacy-event-log",
                    details, occurred_at, previous_hash
                )
                event_hash = _hash_custody_payload(payload)
                db.add(CustodyEvent(
                    evidence_id=evidence_id,
                    event_type=legacy.event_type,
                    actor="legacy-event-log",
                    details=details,
                    occurred_at=occurred_at,
                    previous_hash=previous_hash,
                    event_hash=event_hash,
                ))
                previous_hash = event_hash
        db.commit()
    finally:
        db.close()

backfill_legacy_custody_events()


def bootstrap_initial_user():
    """Create the first login from deployment secrets; never ship a default password."""
    username = os.getenv("CYBERVAULT_BOOTSTRAP_USERNAME", "").strip()
    password = os.getenv("CYBERVAULT_BOOTSTRAP_PASSWORD", "")
    if not username and not password:
        return
    if not username or len(password) < 14:
        raise RuntimeError("Set both CYBERVAULT_BOOTSTRAP_USERNAME and a password of at least 14 characters.")
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if not existing:
            db.add(User(username=username, password_hash=hash_password(password), is_active=True))
            db.commit()
    finally:
        db.close()

bootstrap_initial_user()

@app.post("/api/auth/login")
def login(credentials: dict = Body(...), db: Session = Depends(get_db)):
    username = str(credentials.get("username", "")).strip()
    password = str(credentials.get("password", ""))
    if not username or not password:
        raise HTTPException(400, "Username and password are required.")
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        raise HTTPException(401, "Invalid username or password.")
    try:
        token = create_access_token(user.id, user.username)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    return {"access_token": token, "token_type": "bearer", "expires_in": int(os.getenv("CYBERVAULT_TOKEN_TTL_SECONDS", "3600")), "user": {"id": user.id, "username": user.username}}

@app.get("/api/auth/me")
def current_user(request: Request):
    claims = decode_access_token(request.headers["Authorization"][7:])
    return {"id": int(claims["sub"]), "username": claims["username"]}

@app.get("/health")
def health():
    return {"status": "ok", "service": "CyberVault API"}

@app.post("/api/evidence", response_model=EvidenceOut)
async def collect(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename:
        raise HTTPException(400, "A filename is required.")
    data = await file.read()
    if not data:
        raise HTTPException(400, "The uploaded file is empty.")
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(413, "Maximum upload size is 25 MB.")
    stored, path = save_upload(data, file.filename)
    record = Evidence(original_filename=Path(file.filename).name[:255], stored_filename=stored, sha256=sha256_file(path), size_bytes=len(data))
    db.add(record); db.flush()
    details = f"SHA-256 recorded: {record.sha256}"
    db.add(EvidenceEvent(evidence_id=record.id, event_type="COLLECTED_AND_HASHED", details=details))
    append_custody_event(db, record.id, "COLLECTED_AND_HASHED", details)
    db.commit(); db.refresh(record)
    return record

@app.get("/api/evidence", response_model=list[EvidenceOut])
def list_evidence(db: Session = Depends(get_db)):
    return db.query(Evidence).order_by(Evidence.id.desc()).all()

@app.post("/api/evidence/{evidence_id}/verify", response_model=VerificationOut)
async def verify(evidence_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    record = db.get(Evidence, evidence_id)
    if not record:
        raise HTTPException(404, "Evidence record not found.")
    data = await file.read()
    if not data:
        raise HTTPException(400, "The uploaded file is empty.")
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(413, "Maximum upload size is 25 MB.")
    _, temp = save_upload(data, file.filename or "candidate")
    digest = sha256_file(temp); temp.unlink(missing_ok=True)
    matched = digest == record.sha256
    event_type = "VERIFIED" if matched else "HASH_MISMATCH"
    details = f"Candidate SHA-256: {digest}"
    db.add(EvidenceEvent(evidence_id=record.id, event_type=event_type, details=details))
    append_custody_event(db, record.id, event_type, details)
    db.commit()
    return VerificationOut(evidence_id=record.id, filename=file.filename or "candidate", original_sha256=record.sha256, uploaded_sha256=digest, status="MATCH" if matched else "MISMATCH", message="Uploaded bytes match the collected baseline." if matched else "Uploaded bytes differ from the baseline; this alone does not prove malicious tampering.")

@app.post("/api/evidence/{evidence_id}/analyze-pdf")
async def analyze_pdf(evidence_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    record = db.get(Evidence, evidence_id)
    if not record:
        raise HTTPException(404, "Evidence record not found.")
    original = STORAGE_DIR / record.stored_filename
    if not original.exists():
        raise HTTPException(404, "Stored original evidence is missing.")
    filename = file.filename or "candidate.pdf"
    if Path(record.original_filename).suffix.lower() != ".pdf" or Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(415, "Both the collected original and candidate must be PDFs.")
    data = await file.read()
    if not data:
        raise HTTPException(400, "The uploaded file is empty.")
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(413, "Maximum upload size is 25 MB.")
    _, candidate = save_upload(data, filename)
    try:
        result = compare_pdfs(original, candidate)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    finally:
        candidate.unlink(missing_ok=True)
    score = calculate_trust_score(result)
    result.update(score)
    result["forensic_explanation"] = generate_forensic_explanation(result)
    details = f"{result['classification']} / {result['severity']} / trust score {result['trust_score']}"
    db.add(EvidenceEvent(evidence_id=record.id, event_type="SEMANTIC_ANALYSIS", details=details))
    append_custody_event(db, record.id, "SEMANTIC_ANALYSIS", details)
    db.commit()
    return {"evidence_id": record.id, "filename": filename, **result}

@app.get("/api/evidence/{evidence_id}/events")
def events(evidence_id: int, db: Session = Depends(get_db)):
    if not db.get(Evidence, evidence_id):
        raise HTTPException(404, "Evidence record not found.")
    rows = db.query(EvidenceEvent).filter(EvidenceEvent.evidence_id == evidence_id).order_by(EvidenceEvent.id).all()
    return [{"id": e.id, "event_type": e.event_type, "details": e.details, "created_at": e.created_at} for e in rows]


@app.post("/api/evidence/{evidence_id}/analyze-image")
async def analyze_image(evidence_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    record = db.get(Evidence, evidence_id)
    if not record:
        raise HTTPException(404, "Evidence record not found.")
    original = STORAGE_DIR / record.stored_filename
    if not original.exists():
        raise HTTPException(404, "Stored original evidence is missing.")

    allowed = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
    original_ext = Path(record.original_filename).suffix.lower()
    candidate_name = file.filename or "candidate-image"
    candidate_ext = Path(candidate_name).suffix.lower()
    if original_ext not in allowed or candidate_ext not in allowed:
        raise HTTPException(415, "Both collected and uploaded files must be supported images (JPG, PNG, TIFF, BMP or WEBP).")

    data = await file.read()
    if not data:
        raise HTTPException(400, "The uploaded image is empty.")
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(413, "Maximum upload size is 25 MB.")

    _, candidate = save_upload(data, candidate_name)
    try:
        result = compare_images(original, candidate)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    finally:
        candidate.unlink(missing_ok=True)

    score = calculate_trust_score(result)
    result.update(score)
    result["forensic_explanation"] = generate_forensic_explanation(result)
    details = f"{result['classification']} / {result['severity']} / trust score {result['trust_score']}"
    db.add(EvidenceEvent(evidence_id=record.id, event_type="IMAGE_ANALYSIS", details=details))
    append_custody_event(db, record.id, "IMAGE_ANALYSIS", details)
    db.commit()
    return {"evidence_id": record.id, "filename": candidate_name, **result}



@app.get("/api/evidence/{evidence_id}/custody")
def custody_history(evidence_id: int, db: Session = Depends(get_db)):
    if not db.get(Evidence, evidence_id):
        raise HTTPException(404, "Evidence record not found.")
    rows = (
        db.query(CustodyEvent)
        .filter(CustodyEvent.evidence_id == evidence_id)
        .order_by(CustodyEvent.id.asc())
        .all()
    )
    return [{
        "id": row.id,
        "event_type": row.event_type,
        "actor": row.actor,
        "details": row.details,
        "occurred_at": row.occurred_at,
        "previous_hash": row.previous_hash,
        "event_hash": row.event_hash,
    } for row in rows]

@app.get("/api/evidence/{evidence_id}/custody/verify")
def custody_integrity(evidence_id: int, db: Session = Depends(get_db)):
    if not db.get(Evidence, evidence_id):
        raise HTTPException(404, "Evidence record not found.")
    return verify_custody_chain(db, evidence_id)

@app.post("/api/evidence/{evidence_id}/report")
def download_forensic_report(evidence_id: int, analysis: dict = Body(...), db: Session = Depends(get_db)):
    record = db.get(Evidence, evidence_id)
    if not record:
        raise HTTPException(404, "Evidence record not found.")
    evidence = {
        "id": record.id,
        "original_filename": record.original_filename,
        "sha256": record.sha256,
        "size_bytes": record.size_bytes,
    }
    try:
        pdf_bytes = build_forensic_pdf(evidence, analysis)
    except Exception as exc:
        raise HTTPException(422, f"Could not generate report: {exc}")
    append_custody_event(db, record.id, "REPORT_GENERATED", "Forensic PDF report generated.")
    db.commit()
    safe_name = Path(record.original_filename).stem.replace(" ", "_")[:60]
    filename = f"CyberVault_EV-{record.id:04d}_{safe_name}_forensic_report.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
