from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, String, Text

from config import Base, geometry_column_type, is_postgres

try:
    from geoalchemy2.elements import WKTElement
except Exception:
    WKTElement = None


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(String(32), primary_key=True)
    issue_type = Column(String(64), nullable=False, default="other")
    priority = Column(String(32), nullable=False, default="normal")
    ward = Column(String(64), nullable=False)
    location = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    contact = Column(String(255))
    status = Column(String(32), nullable=False, default="Pending")
    image_path = Column(String(255))
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    predicted_type = Column(String(128))
    verification_score = Column(Float, nullable=False, default=0.0)
    verified = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    geom = Column(geometry_column_type())

    def set_geometry(self):
        point_wkt = f"POINT({self.longitude} {self.latitude})"
        if is_postgres() and WKTElement is not None:
            self.geom = WKTElement(point_wkt, srid=4326)
        else:
            self.geom = point_wkt