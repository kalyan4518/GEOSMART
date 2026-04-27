from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String

from config import Base, geometry_column_type, is_postgres

try:
    from geoalchemy2.elements import WKTElement
except Exception:
    WKTElement = None


class Hotspot(Base):
    __tablename__ = "hotspots"

    id = Column(String(32), primary_key=True)
    center_lat = Column(Float, nullable=False)
    center_lon = Column(Float, nullable=False)
    severity = Column(String(32), nullable=False)
    complaint_count = Column(Integer, nullable=False, default=0)
    open_count = Column(Integer, nullable=False, default=0)
    critical_count = Column(Integer, nullable=False, default=0)
    priority_score = Column(Float, nullable=False, default=0.0)
    average_confidence = Column(Float, nullable=False, default=0.0)
    lead_issue = Column(String(128))
    recommended_depot = Column(String(128))
    eta_minutes = Column(Integer)
    latest_complaint_id = Column(String(32))
    cluster_label = Column(String(64))
    refreshed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    geom = Column(geometry_column_type())

    def set_geometry(self):
        point_wkt = f"POINT({self.center_lon} {self.center_lat})"
        if is_postgres() and WKTElement is not None:
            self.geom = WKTElement(point_wkt, srid=4326)
        else:
            self.geom = point_wkt