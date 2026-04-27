from collections import Counter, defaultdict
from datetime import datetime

from sqlalchemy import func, select

from config import Config, ISSUE_TYPES, is_postgres
from models.complaint import Complaint
from models.hotspot import Hotspot
from routing.astar import default_router
from services.complaint_service import serialize_complaint


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def _severity_label(score):
    if score >= 82:
        return "Critical"
    if score >= 64:
        return "High"
    if score >= 46:
        return "Moderate"
    return "Low"


def _complaint_weight(row):
    base = 34.0
    if row.priority == "high":
        base += 12
    elif row.priority == "critical":
        base += 22
    if row.status != "Resolved":
        base += 8
    if row.verified:
        base += 6
    base += float(row.verification_score or 0) * 18
    return base


def _serialize_hotspot(hotspot):
    route_hint = default_router.route_hint_for_point(hotspot.center_lat, hotspot.center_lon)
    ward_name = hotspot.cluster_label if hotspot.cluster_label and hotspot.cluster_label.startswith("Ward") else f"Cluster {hotspot.id}"
    return {
        "id": hotspot.id,
        "ward": ward_name,
        "title": f"{ward_name} hotspot cluster",
        "latitude": round(hotspot.center_lat, 6),
        "longitude": round(hotspot.center_lon, 6),
        "complaintCount": hotspot.complaint_count,
        "openCount": hotspot.open_count,
        "criticalCount": hotspot.critical_count,
        "priorityScore": round(hotspot.priority_score, 1),
        "severity": hotspot.severity,
        "leadIssue": hotspot.lead_issue or ISSUE_TYPES["other"],
        "averageConfidence": round(hotspot.average_confidence, 2),
        "recommendedDepot": hotspot.recommended_depot or route_hint["depot"],
        "etaMinutes": hotspot.eta_minutes or route_hint["etaMinutes"],
        "latestComplaintId": hotspot.latest_complaint_id,
    }


def _refresh_hotspots_postgres(session):
    session.query(Hotspot).delete()

    cluster_id = func.ST_ClusterDBSCAN(
        func.ST_Transform(Complaint.geom, 3857),
        Config.HOTSPOT_CLUSTER_EPS_METERS,
        Config.HOTSPOT_MIN_POINTS,
    ).over().label("cluster_id")

    rows = session.execute(
        select(
            Complaint.id,
            Complaint.issue_type,
            Complaint.priority,
            Complaint.status,
            Complaint.ward,
            Complaint.predicted_type,
            Complaint.verification_score,
            Complaint.verified,
            Complaint.latitude,
            Complaint.longitude,
            Complaint.updated_at,
            cluster_id,
        ).where(Complaint.geom.is_not(None))
    ).all()

    grouped = defaultdict(list)
    for row in rows:
        grouped[row.cluster_id].append(row)

    hotspots = []
    for index, (group_key, group_rows) in enumerate(grouped.items(), start=1):
        center_lat = sum(row.latitude for row in group_rows) / len(group_rows)
        center_lon = sum(row.longitude for row in group_rows) / len(group_rows)
        center_geom = func.ST_Transform(
            func.ST_SetSRID(func.ST_MakePoint(center_lon, center_lat), 4326),
            3857,
        )
        spread_meters = session.scalar(
            select(
                func.avg(
                    func.ST_Distance(
                        func.ST_Transform(Complaint.geom, 3857),
                        center_geom,
                    )
                )
            ).where(Complaint.id.in_([row.id for row in group_rows]))
        ) or 0.0

        open_count = sum(1 for row in group_rows if row.status != "Resolved")
        critical_count = sum(1 for row in group_rows if row.priority == "critical")
        avg_confidence = sum(float(row.verification_score or 0) for row in group_rows) / len(group_rows)
        lead_issue = Counter(row.issue_type for row in group_rows).most_common(1)[0][0]
        priority_score = _clamp(
            sum(_complaint_weight(row) for row in group_rows) / len(group_rows)
            + len(group_rows) * 6
            + open_count * 4
            + critical_count * 6
            + spread_meters / 75.0,
            10,
            99,
        )
        route_hint = default_router.route_hint_for_point(center_lat, center_lon)

        hotspot = Hotspot(
            id=f"HS-{index}",
            center_lat=round(center_lat, 6),
            center_lon=round(center_lon, 6),
            severity=_severity_label(priority_score),
            complaint_count=len(group_rows),
            open_count=open_count,
            critical_count=critical_count,
            priority_score=round(priority_score, 1),
            average_confidence=round(avg_confidence, 2),
            lead_issue=ISSUE_TYPES.get(lead_issue, ISSUE_TYPES["other"]),
            recommended_depot=route_hint["depot"],
            eta_minutes=route_hint["etaMinutes"],
            latest_complaint_id=max(group_rows, key=lambda row: row.updated_at).id,
            cluster_label=str(group_key),
            refreshed_at=datetime.utcnow(),
        )
        hotspot.set_geometry()
        session.add(hotspot)
        hotspots.append(hotspot)

    session.flush()
    return hotspots


def _refresh_hotspots_fallback(session):
    session.query(Hotspot).delete()
    complaints = session.scalars(select(Complaint).order_by(Complaint.created_at.desc())).all()
    grouped = defaultdict(list)
    for complaint in complaints:
        grouped[complaint.ward].append(complaint)

    hotspots = []
    for index, (ward, entries) in enumerate(grouped.items(), start=1):
        center_lat = sum(entry.latitude for entry in entries) / len(entries)
        center_lon = sum(entry.longitude for entry in entries) / len(entries)
        open_count = sum(1 for entry in entries if entry.status != "Resolved")
        critical_count = sum(1 for entry in entries if entry.priority == "critical")
        avg_confidence = sum(float(entry.verification_score or 0) for entry in entries) / len(entries)
        lead_issue = Counter(entry.issue_type for entry in entries).most_common(1)[0][0]
        priority_score = _clamp(
            sum(_complaint_weight(entry) for entry in entries) / len(entries) + len(entries) * 7,
            10,
            99,
        )
        route_hint = default_router.route_hint_for_point(center_lat, center_lon, ward)

        hotspot = Hotspot(
            id=f"HS-{index}",
            center_lat=round(center_lat, 6),
            center_lon=round(center_lon, 6),
            severity=_severity_label(priority_score),
            complaint_count=len(entries),
            open_count=open_count,
            critical_count=critical_count,
            priority_score=round(priority_score, 1),
            average_confidence=round(avg_confidence, 2),
            lead_issue=ISSUE_TYPES.get(lead_issue, ISSUE_TYPES["other"]),
            recommended_depot=route_hint["depot"],
            eta_minutes=route_hint["etaMinutes"],
            latest_complaint_id=max(entries, key=lambda entry: entry.updated_at).id,
            cluster_label=ward,
            refreshed_at=datetime.utcnow(),
        )
        hotspot.set_geometry()
        session.add(hotspot)
        hotspots.append(hotspot)

    session.flush()
    return hotspots


def refresh_hotspots(session):
    hotspots = _refresh_hotspots_postgres(session) if is_postgres() else _refresh_hotspots_fallback(session)
    hotspots.sort(key=lambda item: (item.open_count, item.priority_score), reverse=True)
    return hotspots


def list_hotspots(session, refresh=False):
    if refresh:
        hotspots = refresh_hotspots(session)
    else:
        hotspots = session.scalars(
            select(Hotspot).order_by(Hotspot.open_count.desc(), Hotspot.priority_score.desc())
        ).all()
        if not hotspots:
            hotspots = refresh_hotspots(session)

    return [_serialize_hotspot(hotspot) for hotspot in hotspots]


def build_heatmap(session):
    complaints = session.scalars(select(Complaint).order_by(Complaint.created_at.desc())).all()
    return [
        {
            "id": complaint.id,
            "latitude": complaint.latitude,
            "longitude": complaint.longitude,
            "weight": round(_complaint_weight(complaint), 1),
            "status": complaint.status,
        }
        for complaint in complaints
    ]


def get_route_payload(session, hotspot_id=None):
    hotspots = list_hotspots(session, refresh=True)
    if not hotspots:
        return None
    hotspot = next((item for item in hotspots if str(item["id"]) == str(hotspot_id)), hotspots[0])
    return {
        "hotspot": hotspot,
        "route": default_router.build_route_plan(hotspot),
    }


def build_dashboard_summary(session):
    complaints = session.scalars(select(Complaint).order_by(Complaint.created_at.desc())).all()
    hotspots = list_hotspots(session, refresh=True)
    total = len(complaints)
    verified_count = sum(1 for complaint in complaints if complaint.verified)
    resolved = sum(1 for complaint in complaints if complaint.status == "Resolved")
    critical = sum(1 for complaint in complaints if complaint.priority == "critical")
    eta_values = [hotspot["etaMinutes"] for hotspot in hotspots if hotspot.get("etaMinutes") is not None]
    average_eta = round(sum(eta_values) / len(eta_values), 1) if eta_values else None
    top_hotspot = hotspots[0] if hotspots else None
    recommended_route = default_router.build_route_plan(top_hotspot) if top_hotspot else None
    avg_priority = sum(hotspot["priorityScore"] for hotspot in hotspots) / max(len(hotspots), 1) if hotspots else 0

    return {
        "generatedAt": datetime.utcnow().isoformat(),
        "totalComplaints": total,
        "verifiedComplaints": verified_count,
        "activeHotspots": sum(1 for hotspot in hotspots if hotspot["openCount"] > 0),
        "averageResponseEta": average_eta,
        "openComplaints": sum(1 for complaint in complaints if complaint.status != "Resolved"),
        "resolvedComplaints": resolved,
        "criticalComplaints": critical,
        "verifiedRate": round((verified_count / max(total, 1)) * 100, 1),
        "averageDispatchEta": average_eta,
        "healthSafetyScore": round(_clamp(100 - avg_priority * 0.45, 42, 98), 0),
        "topHotspot": top_hotspot,
        "recommendedRoute": recommended_route,
        "recentComplaints": [serialize_complaint(complaint) for complaint in complaints[:5]],
    }