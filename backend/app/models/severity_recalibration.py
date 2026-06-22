from sqlalchemy import Column, Integer, String, DateTime, func, Index
from sqlalchemy.dialects.postgresql import JSONB
from backend.app.database import Base

class SeverityRecalibrationLog(Base):
    __tablename__ = "severity_recalibration_log"

    recal_id = Column(Integer, primary_key=True, autoincrement=True)
    event_cause = Column(String, nullable=False)
    corridor = Column(String, nullable=False)
    class_weights = Column(JSONB, nullable=False) # e.g. {"Low": -0.1, "Medium": 0.2, "High": -0.1, "Critical": 0.0}
    n_outcomes_used = Column(Integer, nullable=False)
    recalibrated_at = Column(DateTime, nullable=True, server_default=func.now())

    __table_args__ = (
        Index("idx_sev_recal_cause_corridor", "event_cause", "corridor"),
    )
