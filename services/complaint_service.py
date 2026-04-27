import uuid
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from werkzeug.utils import secure_filename

from ai_service.model import verify_waste
from config import (
    ISSUE_BASE_SCORE,
    ISSUE_STREAMS,
    ISSUE_TYPES,
    PRIORITY_BONUS,
    UPLOAD_DIR,
    WARD_CENTROIDS,
)
from models.complaint import Complaint
from routing.astar import default_router

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def _new_complaint_id():
    return f"CMP-{datetime.now().year}-{uuid.uuid4().hex[:4].upper()}"


def _safe_float(value):
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _public_image_url(image_path):
    if not image_path:
        return None
    return "/" + str(image_path).replace("\\", "/").lstrip("/")


def _save_evidence(file_storage):
    if not file_storage or not file_storage.filename:
        return None, None

    filename = secure_filename(file_storage.filename)
    if not filename or not _allowed_file(filename):
        return None, None

    unique_name = f"{uuid.uuid4().hex[:10]}-{filename}"
    target_path = UPLOAD_DIR / unique_name
    file_storage.save(target_path)
    relative_path = Path("static") / "uploads" / unique_name
    return str(relative_path).replace("\\", "/"), str(target_path)


def _severity_label(score):
    if score >= 82:
        return "Critical"
    if score >= 64:
        return "High"
    if score >= 46:
        return "Moderate"
    return "Low"


def _estimate_severity(issue_type, priority, description, verification_score, verified):
    score = ISSUE_BASE_SCORE.get(issue_type, ISSUE_BASE_SCORE["other"])
    score += PRIORITY_BONUS.get(priority, 0)
    score += min(len(description or "") // 10, 12)
    score += int((verification_score or 0) * 12)
    if verified:
        score += 6
    score = round(_clamp(score, 20, 99), 1)
    return score, _severity_label(score)


def _nearest_ward(latitude, longitude):
    return default_router.nearest_ward(latitude, longitude)


def _build_verification_payload(complaint):
    flags = []
    if complaint.image_path:
        flags.append("Photo evidence attached")
    if complaint.latitude is not None and complaint.longitude is not None:
        flags.append("GPS coordinates captured")
    if complaint.verified:
        flags.append("YOLOv8 verification succeeded")
    else:
        flags.append("Manual review recommended due to low model confidence or no detection")

    return {
        "model": "GEOSMART YOLOv8",
        "status": "Verified" if complaint.verified else "Needs review",
        "confidence": round(complaint.verification_score or 0.0, 2),
        "predictedWaste": complaint.predicted_type or ISSUE_STREAMS.get(complaint.issue_type, ISSUE_STREAMS["other"]),
        "flags": flags,
    }


def serialize_complaint(complaint):
    severity_score, severity_label = _estimate_severity(
        complaint.issue_type,
        complaint.priority,
        complaint.description,
        complaint.verification_score,
        complaint.verified,
    )
    route_hint = default_router.route_hint_for_point(complaint.latitude, complaint.longitude, complaint.ward)
    return {
        "id": complaint.id,
        "issueType": complaint.issue_type,
        "issueLabel": ISSUE_TYPES.get(complaint.issue_type, ISSUE_TYPES["other"]),
        "priority": complaint.priority,
        "ward": complaint.ward,
        "location": complaint.location,
        "description": complaint.description,
        "contact": complaint.contact or "",
        "status": complaint.status,
        "createdAt": complaint.created_at.isoformat(),
        "updatedAt": complaint.updated_at.isoformat(),
        "latitude": round(complaint.latitude, 6),
        "longitude": round(complaint.longitude, 6),
        "imageUrl": _public_image_url(complaint.image_path),
        "severityScore": severity_score,
        "severityLabel": severity_label,
        "verification": _build_verification_payload(complaint),
        "routeHint": route_hint,
        "resolvedAt": complaint.updated_at.isoformat() if complaint.status == "Resolved" else None,
        "resolvedBy": "Admin Team" if complaint.status == "Resolved" else None,
    }


def _build_complaint_entity(payload, image_path=None, prediction=None, created_at=None, status=None):
    issue_type = payload.get("issueType", "other")
    priority = payload.get("priority", "normal")
    latitude = _safe_float(payload.get("latitude"))
    longitude = _safe_float(payload.get("longitude"))
    ward = (payload.get("ward") or "").strip()

    if not ward and latitude is not None and longitude is not None:
        ward = _nearest_ward(latitude, longitude)
    if not ward:
        ward = "Ward 11"
    if latitude is None or longitude is None:
        latitude, longitude = WARD_CENTROIDS.get(ward, WARD_CENTROIDS["Ward 11"])

    prediction = prediction or {
        "verified": False,
        "verification_score": 0.0,
        "predicted_type": ISSUE_STREAMS.get(issue_type, ISSUE_STREAMS["other"]),
    }
    timestamp = created_at or datetime.utcnow()
    complaint = Complaint(
        id=payload.get("id") or _new_complaint_id(),
        issue_type=issue_type,
        priority=priority,
        ward=ward,
        location=(payload.get("location") or ward).strip(),
        description=(payload.get("description") or "").strip(),
        contact=(payload.get("contact") or "").strip(),
        status=status or ("Assigned" if priority == "critical" else "Pending"),
        image_path=image_path,
        latitude=latitude,
        longitude=longitude,
        predicted_type=prediction["predicted_type"],
        verification_score=float(prediction["verification_score"]),
        verified=bool(prediction["verified"]),
        created_at=timestamp,
        updated_at=timestamp,
    )
    complaint.set_geometry()
    return complaint


def list_complaints(session, contact=None):
    statement = select(Complaint)
    if contact:
        statement = statement.where(Complaint.contact == contact)
    complaints = session.scalars(statement.order_by(Complaint.created_at.desc())).all()
    return [serialize_complaint(complaint) for complaint in complaints]


def create_complaint(session, payload, image_file=None):
    image_path, disk_path = _save_evidence(image_file)
    prediction = verify_waste(disk_path) if disk_path else {
        "verified": False,
        "verification_score": 0.0,
        "predicted_type": ISSUE_STREAMS.get(payload.get("issueType", "other"), ISSUE_STREAMS["other"]),
    }
    complaint = _build_complaint_entity(payload, image_path=image_path, prediction=prediction)
    session.add(complaint)
    session.flush()

    from services.hotspot_service import refresh_hotspots

    refresh_hotspots(session)
    return serialize_complaint(complaint)


def update_complaint_status(session, complaint_id, status):
    complaint = session.get(Complaint, complaint_id)
    if not complaint:
        return None

    complaint.status = status
    complaint.updated_at = datetime.utcnow()
    session.flush()

    from services.hotspot_service import refresh_hotspots

    refresh_hotspots(session)
    return serialize_complaint(complaint)


def bootstrap_sample_data(session):
    if session.scalar(select(Complaint.id).limit(1)):
        return

    seed_rows = [
        _build_complaint_entity(
            {
                "id": "CMP-2026-0187",
                "issueType": "overflow",
                "priority": "high",
                "ward": "Ward 11",
                "location": "7th Cross, Eco Park",
                "description": "Community bin overflowing for over 24 hours. Residents reporting foul odour and mosquito breeding.",
                "contact": "Sahana (Resident Welfare Association)",
                "latitude": 12.9349,
                "longitude": 77.6107,
            },
            prediction={"verified": True, "verification_score": 0.84, "predicted_type": "organic waste"},
            created_at=datetime.utcnow() - timedelta(hours=20),
            status="In Progress",
        ),
        _build_complaint_entity(
            {
                "id": "CMP-2026-0192",
                "issueType": "hazardous_waste",
                "priority": "critical",
                "ward": "Ward 14",
                "location": "Koramangala Industrial Layout",
                "description": "Chemical drums dumped near storm-water drain. Immediate removal needed before rainfall.",
                "contact": "Mohan (Health Inspector)",
                "latitude": 12.9364,
                "longitude": 77.6226,
            },
            prediction={"verified": True, "verification_score": 0.91, "predicted_type": "hazardous waste"},
            created_at=datetime.utcnow() - timedelta(hours=6),
            status="Pending",
        ),
        _build_complaint_entity(
            {
                "id": "CMP-2026-0201",
                "issueType": "illegal_dumping",
                "priority": "high",
                "ward": "Ward 21",
                "location": "Milk Colony service road",
                "description": "Construction debris and plastic bags dumped beside the footpath, blocking pedestrian movement.",
                "contact": "Field volunteer desk",
                "latitude": 12.9271,
                "longitude": 77.6286,
            },
            prediction={"verified": False, "verification_score": 0.43, "predicted_type": "mixed waste"},
            created_at=datetime.utcnow() - timedelta(hours=11),
            status="Pending",
        ),
    ]

    session.add_all(seed_rows)
    session.flush()

    from services.hotspot_service import refresh_hotspots

    refresh_hotspots(session)